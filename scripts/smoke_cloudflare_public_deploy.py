#!/usr/bin/env -S uv run python
"""Smoke-test the live Cloudflare Worker deployment from a reviewed export."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


REQUEST_HEADERS = {
    # workers.dev may reject the default Python urllib signature with Cloudflare 1010.
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 "
        "dotrepo-release-gate/1.0"
    ),
    "Accept": "application/json, text/plain;q=0.9, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test a deployed Cloudflare Worker public surface."
    )
    parser.add_argument(
        "--deploy-url",
        required=True,
        help="Base deployed Worker URL, for example https://name.subdomain.workers.dev",
    )
    parser.add_argument(
        "--base-path",
        default="/",
        help="Hosted base path emitted into the reviewed export, default: /",
    )
    parser.add_argument(
        "--public-root",
        required=True,
        help="Path to the reviewed exported public tree used for deployment",
    )
    parser.add_argument(
        "--settle-timeout-seconds",
        type=float,
        default=45.0,
        help="How long to wait for edge caches to converge before failing (default: 45)",
    )
    parser.add_argument(
        "--settle-interval-seconds",
        type=float,
        default=3.0,
        help="How often to retry while waiting for live assets to converge (default: 3)",
    )
    parser.add_argument(
        "--manifest-sample-limit",
        type=int,
        default=24,
        help=(
            "Maximum public file-manifest entries to fetch and hash from the live "
            "deployment after core coherence passes. Use 0 to disable the sampled "
            "manifest content check."
        ),
    )
    return parser.parse_args()


def normalize_base_path(value: str) -> str:
    trimmed = value.strip()
    if trimmed in ("", "/"):
        return ""
    return trimmed if trimmed.startswith("/") else f"/{trimmed}"


def with_query_param(url: str, name: str, value: str) -> str:
    split = urlsplit(url)
    pairs = parse_qsl(split.query, keep_blank_values=True)
    pairs.append((name, value))
    return urlunsplit(
        (split.scheme, split.netloc, split.path, urlencode(pairs), split.fragment)
    )


# Transient HTTP statuses worth retrying. The deploy smoke runs against the
# production custom origin moments after a new Worker version is promoted, so a
# brand-new content-addressed snapshot path can briefly 404 (or hit a 5xx) at
# the edge before propagation settles. Retry these so the gate does not flap on
# every snapshot-changing deploy; a genuinely missing file still fails, just
# after the retries are exhausted. Status 0 represents a connection failure.
TRANSIENT_STATUSES = {404, 408, 425, 429, 500, 502, 503, 504}
RETRY_BACKOFF_SECONDS = (5, 10, 15)


def _request_once(url: str) -> tuple[int, bytes]:
    request = Request(url, headers=REQUEST_HEADERS)
    try:
        with urlopen(request, timeout=15) as response:
            status = getattr(response, "status", response.getcode())
            return status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read()


def _request_with_retry(url: str) -> tuple[int, bytes]:
    """Fetch `url`, retrying transient post-deploy edge states.

    Returns the final (status, body). Raises SystemExit only if a connection
    error persists across all retries; HTTP statuses (including persistent 404)
    are returned for the caller to format.
    """
    reason: str | None = None
    status = 0
    body = b""
    for attempt in range(len(RETRY_BACKOFF_SECONDS) + 1):
        try:
            status, body = _request_once(url)
            reason = None
        except URLError as exc:
            reason = str(exc.reason)
            status, body = 0, b""
        if status != 0 and status not in TRANSIENT_STATUSES:
            return status, body
        if attempt < len(RETRY_BACKOFF_SECONDS):
            time.sleep(RETRY_BACKOFF_SECONDS[attempt])
    if status == 0 and reason is not None:
        raise SystemExit(f"smoke failed for {url}: {reason}")
    return status, body


def http_get_json(url: str) -> Any:
    status, body = _request_with_retry(url)
    decoded = body.decode("utf-8", errors="replace")
    if status == 403 and "error code: 1010" in decoded:
        raise SystemExit(
            f"smoke failed (403) for {url}: {decoded}"
            " (Cloudflare blocked the client signature on workers.dev; "
            "verify with a browser-like User-Agent or promote the smoke check "
            "to the final custom domain instead)"
        )
    if status != 200:
        raise SystemExit(f"smoke failed ({status}) for {url}: {decoded}")
    try:
        return json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"smoke returned invalid JSON for {url}: {exc}") from exc


def http_get_bytes(url: str) -> bytes:
    status, body = _request_with_retry(url)
    decoded = body.decode("utf-8", errors="replace")
    if status == 403 and "error code: 1010" in decoded:
        raise SystemExit(
            f"smoke failed (403) for {url}: {decoded}"
            " (Cloudflare blocked the client signature on workers.dev; "
            "verify with a browser-like User-Agent or promote the smoke check "
            "to the final custom domain instead)"
        )
    if status != 200:
        raise SystemExit(f"smoke failed ({status}) for {url}: {decoded}")
    return body


def http_get_text(url: str) -> str:
    return http_get_bytes(url).decode("utf-8")


def extract_homepage_snapshot_state(document: str, source: str) -> dict[str, Any]:
    match = re.search(
        r'<script id="dotrepo-homepage-snapshot" type="application/json">(.+?)</script>',
        document,
        re.DOTALL,
    )
    if match is None:
        raise SystemExit(f"smoke could not find homepage snapshot state in {source}")
    try:
        payload = json.loads(html.unescape(match.group(1)))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"smoke found invalid homepage snapshot state in {source}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"smoke found malformed homepage snapshot state in {source}: {payload!r}")
    return payload


def expected_homepage_snapshot_state(meta: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    return {
        "apiVersion": meta.get("apiVersion"),
        "generatedAt": meta.get("generatedAt"),
        "snapshotDigest": meta.get("snapshotDigest"),
        "staleAfter": meta.get("staleAfter"),
        "repositoryCount": inventory.get("repositoryCount"),
    }


def load_json_file(path: Path, description: str) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"missing reviewed export {description}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"reviewed export {description} is invalid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"reviewed export {description} is malformed: {path}")
    return payload


def load_reviewed_public_state(public_root: Path) -> dict[str, dict[str, Any]]:
    return {
        "meta": load_json_file(public_root / "v0" / "meta.json", "metadata"),
        "files": load_json_file(public_root / "v0" / "files.json", "file manifest"),
        "inventory": load_json_file(
            public_root / "v0" / "repos" / "index.json", "repository inventory"
        ),
        "log": load_json_file(public_root / "v0" / "snapshots" / "log.json", "snapshot log"),
        "stats": load_json_file(public_root / "v0" / "stats.json", "stats"),
    }


def deploy_coherence_mismatches(
    reviewed: dict[str, dict[str, Any]], live: dict[str, dict[str, Any]]
) -> list[str]:
    mismatches = []
    for key, label in (
        ("meta", "v0/meta.json"),
        ("files", "v0/files.json"),
        ("inventory", "v0/repos/index.json"),
        ("log", "v0/snapshots/log.json"),
        ("stats", "v0/stats.json"),
    ):
        if live.get(key) != reviewed.get(key):
            mismatches.append(label)
    return mismatches


def manifest_entries_by_path(files_manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = files_manifest.get("files")
    if not isinstance(entries, list):
        raise SystemExit("reviewed export file manifest is missing files[]")
    by_path = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise SystemExit(f"reviewed export file manifest has malformed entry: {entry!r}")
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            raise SystemExit(f"reviewed export file manifest entry is missing path: {entry!r}")
        if path.startswith("/") or ".." in path.split("/"):
            raise SystemExit(f"reviewed export file manifest path is unsafe: {path}")
        if not isinstance(entry.get("bytes"), int) or entry["bytes"] < 0:
            raise SystemExit(f"reviewed export file manifest entry is missing bytes: {path}")
        sha256 = entry.get("sha256")
        if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise SystemExit(f"reviewed export file manifest entry is missing sha256: {path}")
        by_path[path] = entry
    return by_path


def public_manifest_entry(entry: dict[str, Any]) -> bool:
    path = str(entry.get("path") or "")
    return not path.startswith("query-input/") and "/query-input/" not in path


def select_manifest_coherence_entries(
    files_manifest: dict[str, Any],
    first_identity: dict[str, Any],
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    entries_by_path = manifest_entries_by_path(files_manifest)
    inventory_paths = [
        path for path in entries_by_path if path.endswith("/repos/index.json")
    ]
    snapshot_root = (
        inventory_paths[0][: -len("/repos/index.json")]
        if len(inventory_paths) == 1
        else "v0"
    )
    first_repo_prefix = (
        f"{snapshot_root}/repos/{first_identity.get('host')}/"
        f"{first_identity.get('owner')}/{first_identity.get('repo')}/"
    )
    priority_paths = [
        "v0/meta.json",
        "v0/files.json",
        f"{snapshot_root}/repos/index.json",
        f"{first_repo_prefix}index.json",
        f"{first_repo_prefix}profile.json",
        f"{first_repo_prefix}trust.json",
        f"{first_repo_prefix}relations.json",
    ]
    selected_paths = []
    for path in priority_paths:
        entry = entries_by_path.get(path)
        if entry and public_manifest_entry(entry) and path not in selected_paths:
            selected_paths.append(path)
        if len(selected_paths) >= limit:
            return [entries_by_path[path] for path in selected_paths]

    remaining = [
        entry
        for path, entry in sorted(entries_by_path.items())
        if path not in selected_paths and public_manifest_entry(entry)
    ]
    open_slots = limit - len(selected_paths)
    if open_slots <= 0 or not remaining:
        return [entries_by_path[path] for path in selected_paths]
    if len(remaining) <= open_slots:
        selected_paths.extend(entry["path"] for entry in remaining)
    else:
        # Deterministic spread across the manifest catches partition or routing
        # drift without turning every deploy smoke into hundreds of requests.
        last_index = len(remaining) - 1
        for index in range(open_slots):
            selected = remaining[round(index * last_index / max(open_slots - 1, 1))]
            if selected["path"] not in selected_paths:
                selected_paths.append(selected["path"])
    return [entries_by_path[path] for path in selected_paths]


def manifest_entry_url(deploy_url: str, base_path: str, entry_path: str) -> str:
    return f"{deploy_url}{base_path}/{entry_path.lstrip('/')}"


def live_manifest_entry_mismatches(
    deploy_url: str,
    base_path: str,
    entries: list[dict[str, Any]],
    cache_bust: str,
) -> list[str]:
    mismatches = []
    for entry in entries:
        path = entry["path"]
        url = with_query_param(
            manifest_entry_url(deploy_url, base_path, path), "_smoke", cache_bust
        )
        body = http_get_bytes(url)
        digest = hashlib.sha256(body).hexdigest()
        if len(body) != entry["bytes"] or digest != entry["sha256"]:
            mismatches.append(path)
    return mismatches


def fetch_live_public_state(
    deploy_url: str, base_path: str, cache_bust: str
) -> tuple[Any, ...]:
    homepage_url = f"{deploy_url}{base_path or '/'}"
    meta_url = f"{deploy_url}{base_path}/v0/meta.json"
    files_url = f"{deploy_url}{base_path}/v0/files.json"
    inventory_url = f"{deploy_url}{base_path}/v0/repos/index.json"
    log_url = f"{deploy_url}{base_path}/v0/snapshots/log.json"
    stats_url = f"{deploy_url}{base_path}/v0/stats.json"

    homepage = http_get_text(with_query_param(homepage_url, "_smoke", cache_bust))
    homepage_state = extract_homepage_snapshot_state(homepage, homepage_url)
    meta = http_get_json(with_query_param(meta_url, "_smoke", cache_bust))
    files = http_get_json(with_query_param(files_url, "_smoke", cache_bust))
    inventory = http_get_json(with_query_param(inventory_url, "_smoke", cache_bust))
    log = http_get_json(with_query_param(log_url, "_smoke", cache_bust))
    stats = http_get_json(with_query_param(stats_url, "_smoke", cache_bust))
    return homepage, homepage_state, meta, files, inventory, log, stats, homepage_url, files_url, inventory_url, log_url, stats_url


def main() -> int:
    args = parse_args()
    public_root = Path(args.public_root).resolve()
    reviewed = load_reviewed_public_state(public_root)

    repositories = reviewed["inventory"].get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise SystemExit("reviewed export inventory contains no repositories")
    links = repositories[0].get("links", {})
    query_template = links.get("queryTemplate")
    if not isinstance(query_template, str):
        raise SystemExit("reviewed export inventory contains no queryTemplate")
    first_identity = repositories[0].get("identity", {})
    try:
        first_repo = "/".join(
            [
                first_identity["host"],
                first_identity["owner"],
                first_identity["repo"],
            ]
        )
    except KeyError as exc:
        raise SystemExit(f"reviewed export inventory missing identity key: {exc}") from exc

    deploy_url = args.deploy_url.rstrip("/")
    base_path = normalize_base_path(args.base_path)
    manifest_entries = select_manifest_coherence_entries(
        reviewed["files"], first_identity, args.manifest_sample_limit
    )
    deadline = time.monotonic() + max(args.settle_timeout_seconds, 0.0)
    meta_url = f"{deploy_url}{base_path}/v0/meta.json"
    inventory_url = f"{deploy_url}{base_path}/v0/repos/index.json"

    while True:
        cache_bust = uuid.uuid4().hex
        (
            homepage,
            homepage_state,
            meta,
            files,
            inventory,
            log,
            stats,
            homepage_url,
            files_url,
            inventory_url,
            log_url,
            stats_url,
        ) = fetch_live_public_state(deploy_url, base_path, cache_bust)
        if meta.get("apiVersion") != "v0":
            raise SystemExit(f"unexpected apiVersion from {meta_url}: {meta.get('apiVersion')}")

        expected_homepage_state = expected_homepage_snapshot_state(meta, inventory)
        live = {"meta": meta, "files": files, "inventory": inventory, "log": log, "stats": stats}
        mismatches = deploy_coherence_mismatches(reviewed, live)
        manifest_mismatches = []
        if homepage_state == expected_homepage_state and not mismatches:
            manifest_mismatches = live_manifest_entry_mismatches(
                deploy_url, base_path, manifest_entries, cache_bust
            )
        if (
            homepage_state == expected_homepage_state
            and not mismatches
            and not manifest_mismatches
        ):
            break
        if time.monotonic() >= deadline:
            raise SystemExit(
                "deployed public surface did not converge to the reviewed export after waiting "
                f"{args.settle_timeout_seconds:g}s: homepage expected {expected_homepage_state}, "
                f"homepage got {homepage_state}, mismatched reviewed files: "
                f"{', '.join(mismatches) or 'none'}, mismatched manifest entries: "
                f"{', '.join(manifest_mismatches) or 'none'}"
            )
        time.sleep(max(args.settle_interval_seconds, 0.0))

    query_url = (
        f"{deploy_url}{query_template.replace('{dot_path}', 'repo.description')}"
    )
    query_response = http_get_json(with_query_param(query_url, "_smoke", uuid.uuid4().hex))
    if query_response.get("path") != "repo.description":
        raise SystemExit("deployed queryTemplate smoke returned unexpected path")
    self_link = query_response.get("links", {}).get("self")
    expected_prefix = base_path or "/"
    if not isinstance(self_link, str) or not self_link.startswith(expected_prefix):
        raise SystemExit(
            f"deployed queryTemplate smoke returned unexpected self link: {self_link}"
        )

    batch_profiles_url = f"{deploy_url}{base_path}/v0/batch/profiles?{urlencode([('repo', first_repo)])}"
    batch_profiles = http_get_json(
        with_query_param(batch_profiles_url, "_smoke", uuid.uuid4().hex)
    )
    if batch_profiles.get("resultCount") != 1:
        raise SystemExit("deployed batch profile smoke returned unexpected resultCount")
    if batch_profiles.get("results", [{}])[0].get("profile", {}).get("identity") != first_identity:
        raise SystemExit("deployed batch profile smoke returned unexpected identity")

    batch_query_url = f"{deploy_url}{base_path}/v0/batch/query?{urlencode([('repo', first_repo), ('path', 'repo.description')])}"
    batch_query = http_get_json(
        with_query_param(batch_query_url, "_smoke", uuid.uuid4().hex)
    )
    if batch_query.get("repositoryCount") != 1 or batch_query.get("pathCount") != 1:
        raise SystemExit("deployed batch query smoke returned unexpected counts")
    batch_query_result = batch_query.get("results", [{}])[0]
    if batch_query_result.get("path") != "repo.description" or "query" not in batch_query_result:
        raise SystemExit("deployed batch query smoke returned unexpected result")

    search_url = f"{deploy_url}{base_path}/v0/search?{urlencode([('q', first_identity['repo'])])}"
    search_response = http_get_json(
        with_query_param(search_url, "_smoke", uuid.uuid4().hex)
    )
    if search_response.get("returnedCount", 0) < 1:
        raise SystemExit("deployed search smoke returned no results")

    compare_url = f"{deploy_url}{base_path}/v0/compare?{urlencode([('repo', first_repo)])}"
    compare_response = http_get_json(
        with_query_param(compare_url, "_smoke", uuid.uuid4().hex)
    )
    if compare_response.get("repositoryCount") != 1:
        raise SystemExit("deployed compare smoke returned unexpected repositoryCount")
    if compare_response.get("results", [{}])[0].get("identity") != first_identity:
        raise SystemExit("deployed compare smoke returned unexpected identity")

    relations_url = (
        f"{deploy_url}{base_path}/v0/repos/"
        f"{first_identity['host']}/{first_identity['owner']}/{first_identity['repo']}/relations"
    )
    relations_response = http_get_json(
        with_query_param(relations_url, "_smoke", uuid.uuid4().hex)
    )
    if relations_response.get("identity") != first_identity:
        raise SystemExit("deployed relations smoke returned unexpected identity")
    if not isinstance(relations_response.get("references"), list):
        raise SystemExit("deployed relations smoke returned malformed references")

    print(f"smoke ok: {homepage_url}")
    print(f"smoke ok: {meta_url}")
    print(f"smoke ok: {files_url}")
    print(f"smoke ok: {inventory_url}")
    print(f"smoke ok: {log_url}")
    print(f"smoke ok: {stats_url}")
    print(f"smoke ok: {query_url}")
    print(f"smoke ok: {batch_profiles_url}")
    print(f"smoke ok: {batch_query_url}")
    print(f"smoke ok: {search_url}")
    print(f"smoke ok: {compare_url}")
    print(f"smoke ok: {relations_url}")
    if manifest_entries:
        print(f"smoke ok: {len(manifest_entries)} manifest entries matched reviewed hashes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
