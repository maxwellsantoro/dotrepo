#!/usr/bin/env python3
"""Fetch and validate the deployed PageDigest manifest used as an export baseline."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

MAX_MANIFEST_BYTES = 16 * 1024 * 1024
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class BaselineError(ValueError):
    """The deployed PageDigest baseline could not be trusted."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch the currently deployed PageDigest manifest, validate the "
            "revision-bearing fields, and write an atomic local baseline."
        )
    )
    parser.add_argument("--url", required=True, help="HTTPS PageDigest manifest URL")
    parser.add_argument("--output", required=True, type=Path, help="Output JSON path")
    parser.add_argument("--timeout", type=float, default=20.0, help="Per-attempt timeout")
    parser.add_argument("--attempts", type=int, default=3, help="Fetch attempts")
    return parser.parse_args()


def positive_integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise BaselineError(f"{field} must be a positive integer")
    return value


def sha256_digest(value: object, field: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise BaselineError(f"{field} must be a lowercase sha256 digest")
    return value


def validate_manifest(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise BaselineError("manifest root must be an object")
    if payload.get("version") != 1:
        raise BaselineError("manifest version must be 1")

    positive_integer(payload.get("site_rev"), "site_rev")
    entries = payload.get("entries")
    if not isinstance(entries, dict) or not entries:
        raise BaselineError("entries must be a non-empty object")

    for url, entry in entries.items():
        if not isinstance(url, str) or not url.startswith("/"):
            raise BaselineError("entry keys must be absolute URL paths")
        if not isinstance(entry, dict):
            raise BaselineError(f"entry {url} must be an object")
        positive_integer(entry.get("rev"), f"entries[{url!r}].rev")
        sha256_digest(entry.get("digest"), f"entries[{url!r}].digest")
        sha256_digest(entry.get("content_digest"), f"entries[{url!r}].content_digest")

    return payload


def fetch_manifest(url: str, timeout: float) -> dict:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "User-Agent": "dotrepo-public-deploy/1.0",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read(MAX_MANIFEST_BYTES + 1)
    if len(body) > MAX_MANIFEST_BYTES:
        raise BaselineError(f"manifest exceeds the {MAX_MANIFEST_BYTES}-byte safety limit")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BaselineError(f"manifest is not valid UTF-8 JSON: {exc}") from exc
    return validate_manifest(payload)


def fetch_with_retries(url: str, timeout: float, attempts: int) -> dict:
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise BaselineError("baseline URL must be an absolute HTTPS URL")
    if attempts < 1:
        raise BaselineError("attempts must be at least 1")

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fetch_manifest(url, timeout)
        except (BaselineError, OSError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(min(2 ** (attempt - 1), 4))

    raise BaselineError(
        f"failed to fetch a valid PageDigest baseline after {attempts} attempts: {last_error}"
    )


def write_manifest(output: Path, manifest: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)


def main() -> int:
    args = parse_args()
    manifest = fetch_with_retries(args.url, args.timeout, args.attempts)
    write_manifest(args.output, manifest)
    print(
        f"fetched PageDigest baseline: site_rev={manifest['site_rev']} "
        f"entries={len(manifest['entries'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
