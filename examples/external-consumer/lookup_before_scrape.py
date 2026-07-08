#!/usr/bin/env -S uv run python
"""Reference external consumer: hosted dotrepo lookup before scrape.

This is a template-complete, non-operator-style client that implements the
acceptance bullets in ``docs/external-consumer-integration.md``:

1. Prefer hosted lookup before any clone/scrape fallback. Default surface is
   ``GET /v0/repos/{host}/{owner}/{repo}/profile.json`` (agent-oriented fields);
   ``index.json`` remains available via ``--surface index``.
2. Surface trust / status / freshness from the response (never drop them).
3. Missing fields stay missing — the client does not invent build/test commands.
4. HTTP 404 is counted as a lookup miss (client-side metrics suitable for
   feeding ``scripts/aggregate_lookup_misses.py``).
5. This client is an integration example, not operator CI smoke.

Live traffic against ``https://dotrepo.org`` is optional (``--base-url``).
Unit tests exercise the real parse/decision path with fixture HTTP responses.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlparse


DEFAULT_BASE_URL = "https://dotrepo.org"


@dataclass
class LookupMiss:
    host: str
    owner: str
    repo: str
    route: str = "profile"
    source: str = "external-consumer"


@dataclass
class LookupResult:
    identity: str
    status_code: int
    hit: bool
    miss: bool
    profile: dict[str, Any] | None = None
    trust: dict[str, Any] | None = None
    freshness: dict[str, Any] | None = None
    record_status: str | None = None
    missing_fields: list[str] = field(default_factory=list)
    error: str | None = None


def parse_repository_identity(url_or_identity: str) -> tuple[str, str, str]:
    """Parse ``host/owner/repo`` or a GitHub-style repository URL."""
    text = url_or_identity.strip().rstrip("/")
    if "://" in text:
        parsed = urlparse(text)
        host = parsed.netloc.lower()
        parts = [p for p in parsed.path.split("/") if p]
        if host.startswith("www."):
            host = host[4:]
        if len(parts) < 2:
            raise ValueError(f"cannot parse repository identity from URL: {url_or_identity}")
        owner, repo = parts[0], parts[1]
        if repo.endswith(".git"):
            repo = repo[: -len(".git")]
        return host, owner, repo

    parts = [p for p in text.split("/") if p]
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return "github.com", parts[0], parts[1]
    raise ValueError(f"cannot parse repository identity: {url_or_identity}")


def profile_url(base_url: str, host: str, owner: str, repo: str, *, surface: str = "profile") -> str:
    base = base_url.rstrip("/")
    name = "profile.json" if surface == "profile" else "index.json"
    return f"{base}/v0/repos/{host}/{owner}/{repo}/{name}"


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() != "unknown"
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def extract_trust_and_freshness(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    """Pull trust/status/freshness without inventing values.

    Supports both the public ``profile.json`` envelope and the ``index.json``
    selection wrapper.
    """
    freshness = payload.get("freshness") if isinstance(payload.get("freshness"), dict) else {}
    trust: dict[str, Any] = {}
    record_status: str | None = None

    # profile.json: top-level trust block
    top_trust = payload.get("trust")
    if isinstance(top_trust, dict):
        trust = {
            k: top_trust[k]
            for k in ("confidence", "provenance", "notes", "selectedStatus", "selectionReason")
            if k in top_trust
        }
        if isinstance(top_trust.get("selectedStatus"), str):
            record_status = top_trust["selectedStatus"]

    # index.json: selection.record.record.{status,trust}
    selection = payload.get("selection")
    if isinstance(selection, dict):
        selected = selection.get("record")
        if isinstance(selected, dict):
            inner = selected.get("record")
            if isinstance(inner, dict):
                if record_status is None and isinstance(inner.get("status"), str):
                    record_status = inner["status"]
                inner_trust = inner.get("trust")
                if isinstance(inner_trust, dict) and not trust:
                    trust = {
                        k: inner_trust[k]
                        for k in ("confidence", "provenance", "notes")
                        if k in inner_trust
                    }

    # Nested record.trust fallback
    record = payload.get("record")
    if isinstance(record, dict) and not trust:
        raw_trust = record.get("trust")
        if isinstance(raw_trust, dict):
            trust = {
                k: raw_trust[k]
                for k in ("confidence", "provenance", "notes")
                if k in raw_trust
            }
        if record_status is None and isinstance(record.get("status"), str):
            record_status = record["status"]

    return trust, freshness, record_status


def missing_high_value_fields(payload: dict[str, Any]) -> list[str]:
    """Report high-value fields that are absent — do not invent replacements.

    Understands profile.json (execution/ownership) and index.json (repository).
    """
    missing: list[str] = []

    # profile.json shape
    execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
    ownership = payload.get("ownership") if isinstance(payload.get("ownership"), dict) else {}
    repository = payload.get("repository") if isinstance(payload.get("repository"), dict) else {}
    # legacy/flat repo block (tests and some wrappers)
    repo = payload.get("repo") if isinstance(payload.get("repo"), dict) else {}
    owners = payload.get("owners") if isinstance(payload.get("owners"), dict) else {}

    build = execution.get("build") or repo.get("build")
    test = execution.get("test") or repo.get("test")
    homepage = payload.get("homepage") or repository.get("homepage") or repo.get("homepage")
    description = (
        payload.get("purpose")
        or payload.get("description")
        or repository.get("description")
        or repo.get("description")
    )
    security = (
        ownership.get("securityContact")
        or repository.get("securityContact")
        or owners.get("security_contact")
    )

    if not _nonempty(build):
        missing.append("repo.build")
    if not _nonempty(test):
        missing.append("repo.test")
    if not _nonempty(homepage):
        missing.append("repo.homepage")
    if not _nonempty(description):
        missing.append("repo.description")
    if not _nonempty(security):
        missing.append("owners.security_contact")
    return missing


def interpret_http_response(
    *,
    identity: str,
    status_code: int,
    body: bytes | str | None,
) -> LookupResult:
    """Core decision path: 200 → profile; 404 → countable miss; else error."""
    if status_code == 404:
        return LookupResult(
            identity=identity,
            status_code=status_code,
            hit=False,
            miss=True,
            error="repository-not-found",
        )

    if status_code != 200:
        return LookupResult(
            identity=identity,
            status_code=status_code,
            hit=False,
            miss=False,
            error=f"unexpected-status:{status_code}",
        )

    if body is None:
        return LookupResult(
            identity=identity,
            status_code=status_code,
            hit=False,
            miss=False,
            error="empty-body",
        )

    text = body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return LookupResult(
            identity=identity,
            status_code=status_code,
            hit=False,
            miss=False,
            error=f"invalid-json:{exc}",
        )

    if not isinstance(payload, dict):
        return LookupResult(
            identity=identity,
            status_code=status_code,
            hit=False,
            miss=False,
            error="non-object-json",
        )

    trust, freshness, record_status = extract_trust_and_freshness(payload)
    return LookupResult(
        identity=identity,
        status_code=status_code,
        hit=True,
        miss=False,
        profile=payload,
        trust=trust or None,
        freshness=freshness or None,
        record_status=record_status,
        missing_fields=missing_high_value_fields(payload),
    )


def fetch_profile(
    url_or_identity: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    surface: str = "profile",
    opener: Any | None = None,
    timeout: float = 20.0,
) -> LookupResult:
    """Lookup-first path. ``opener`` is injectable for tests (must have ``open``)."""
    host, owner, repo = parse_repository_identity(url_or_identity)
    identity = f"{host}/{owner}/{repo}"
    url = profile_url(base_url, host, owner, repo, surface=surface)

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "dotrepo-external-consumer/0.1 (+https://github.com/maxwellsantoro/dotrepo)",
        },
        method="GET",
    )

    open_fn = opener.open if opener is not None else urllib.request.urlopen
    try:
        with open_fn(request, timeout=timeout) as response:
            status = getattr(response, "status", None) or response.getcode()
            body = response.read()
            return interpret_http_response(identity=identity, status_code=int(status), body=body)
    except urllib.error.HTTPError as exc:
        body = exc.read() if hasattr(exc, "read") else None
        return interpret_http_response(identity=identity, status_code=int(exc.code), body=body)
    except Exception as exc:  # network / DNS / timeout
        return LookupResult(
            identity=identity,
            status_code=0,
            hit=False,
            miss=False,
            error=f"transport:{type(exc).__name__}:{exc}",
        )


def miss_log_line(miss: LookupMiss) -> str:
    """Emit a Worker-compatible DOTREPO_LOOKUP_MISS line for operator aggregation."""
    payload = {
        "host": miss.host,
        "owner": miss.owner,
        "repo": miss.repo,
        "route": miss.route,
        "source": miss.source,
    }
    return f"DOTREPO_LOOKUP_MISS {json.dumps(payload, separators=(',', ':'))}"


def result_to_miss(result: LookupResult) -> LookupMiss | None:
    if not result.miss:
        return None
    host, owner, repo = result.identity.split("/", 2)
    return LookupMiss(host=host, owner=owner, repo=repo)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "repositories",
        nargs="+",
        help="Repository URL or host/owner/repo identity (repeatable)",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--surface",
        choices=("profile", "index"),
        default="profile",
        help="Hosted document to fetch (default: profile.json)",
    )
    parser.add_argument("--output-json")
    parser.add_argument(
        "--miss-log",
        help="Append DOTREPO_LOOKUP_MISS lines for 404s (aggregate with scripts/aggregate_lookup_misses.py)",
    )
    parser.add_argument(
        "--allow-scrape-fallback",
        action="store_true",
        help="Print a scrape-fallback hint on miss (still does not scrape itself)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    results: list[dict[str, Any]] = []
    miss_lines: list[str] = []

    for repo in args.repositories:
        result = fetch_profile(repo, base_url=args.base_url, surface=args.surface)
        payload = asdict(result)
        if result.hit and result.profile is not None:
            payload["profile_keys"] = sorted(result.profile.keys())
            payload.pop("profile", None)
        results.append(payload)

        print(f"## {result.identity}")
        print(f"- status_code: {result.status_code}")
        print(f"- hit: {result.hit}  miss: {result.miss}")
        if result.record_status:
            print(f"- record.status: {result.record_status}")
        if result.trust:
            print(f"- trust: {json.dumps(result.trust, sort_keys=True)}")
        if result.freshness:
            print(f"- freshness: {json.dumps(result.freshness, sort_keys=True)}")
        if result.missing_fields:
            print(f"- missing_fields (honest): {', '.join(result.missing_fields)}")
        if result.error:
            print(f"- error: {result.error}")
        if result.miss and args.allow_scrape_fallback:
            print("- fallback: clone/scrape permitted only after countable miss")

        miss = result_to_miss(result)
        if miss is not None:
            miss.route = args.surface
            miss_lines.append(miss_log_line(miss))

    if args.miss_log and miss_lines:
        path = args.miss_log
        with open(path, "a", encoding="utf-8") as handle:
            for line in miss_lines:
                handle.write(line + "\n")
        print(f"\nWrote {len(miss_lines)} miss log line(s) to {path}")

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as handle:
            json.dump({"results": results, "missCount": len(miss_lines)}, handle, indent=2)
            handle.write("\n")

    # Exit 0 even on misses: misses are a successful observation, not a client crash.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
