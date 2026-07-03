#!/usr/bin/env -S uv run python
"""Verify that the public dotrepo and pagedigest edges tell one coherent story."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen


class CanaryFailure(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dotrepo-origin", default="https://dotrepo.org")
    parser.add_argument("--pagedigest-origin", default="https://pagedigest.org")
    parser.add_argument("--pagedigest-repo-root")
    parser.add_argument("--output")
    return parser.parse_args()


def fetch(origin: str, path: str) -> bytes:
    separator = "&" if "?" in path else "?"
    url = urljoin(f"{origin.rstrip('/')}/", path.lstrip('/'))
    request = Request(
        f"{url}{separator}_canary={uuid.uuid4().hex}",
        headers={"User-Agent": "dotrepo-public-edge-canary/1.0", "Cache-Control": "no-cache"},
    )
    with urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise CanaryFailure(f"{url} returned HTTP {response.status}")
        return response.read()


def fetch_json(origin: str, path: str) -> dict[str, Any]:
    try:
        value = json.loads(fetch(origin, path))
    except json.JSONDecodeError as exc:
        raise CanaryFailure(f"{path} returned invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise CanaryFailure(f"{path} did not return a JSON object")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CanaryFailure(message)


def freshness(value: dict[str, Any], context: str) -> dict[str, Any]:
    result = value.get("freshness")
    require(isinstance(result, dict), f"{context} is missing freshness")
    return result


def check_dotrepo(origin: str) -> dict[str, Any]:
    meta = fetch_json(origin, "/v0/meta.json")
    paths = meta.get("paths")
    require(isinstance(paths, dict), "dotrepo meta is missing content-addressed paths")
    snapshot_id = meta.get("snapshotId")
    digest = meta.get("snapshotDigest")
    require(isinstance(snapshot_id, str) and snapshot_id, "dotrepo meta has no snapshotId")
    require(isinstance(digest, str) and digest.startswith(snapshot_id), "snapshotId does not match snapshotDigest")
    root = paths.get("root")
    inventory_path = paths.get("inventory")
    files_path = paths.get("files")
    require(
        isinstance(root, str) and root.endswith(f"/v0/snapshots/{snapshot_id}"),
        "dotrepo snapshot root does not match snapshotId",
    )
    require(isinstance(inventory_path, str), "dotrepo meta has no inventory path")
    require(isinstance(files_path, str), "dotrepo meta has no files path")

    inventory = fetch_json(origin, inventory_path)
    files = fetch_json(origin, files_path)
    log = fetch_json(origin, "/v0/snapshots/log.json")
    stats = fetch_json(origin, "/v0/stats.json")
    expected_freshness = {
        key: meta.get(key) for key in ("generatedAt", "snapshotDigest", "staleAfter") if meta.get(key) is not None
    }
    require(freshness(inventory, "inventory") == expected_freshness, "inventory freshness disagrees with pointer")
    require(freshness(files, "files manifest") == expected_freshness, "files freshness disagrees with pointer")
    require(inventory.get("repositoryCount") == len(inventory.get("repositories", [])), "repository count is inconsistent")
    log_entries = log.get("entries")
    require(isinstance(log_entries, list) and log_entries, "snapshot log is empty")
    latest_log = log_entries[-1]
    require(latest_log.get("snapshotDigest") == digest, "snapshot log latest digest disagrees with pointer")
    require(latest_log.get("repositoryCount") == inventory.get("repositoryCount"), "snapshot log repository count disagrees")
    require(latest_log.get("fileCount") == files.get("fileCount"), "snapshot log file count disagrees")
    require(stats.get("latest", {}).get("snapshotDigest") == digest, "stats latest digest disagrees with pointer")
    require(stats.get("snapshotCount") == log.get("snapshotCount"), "stats snapshot count disagrees with log")
    for entry in files.get("files", []):
        require(
            isinstance(entry, dict) and str(entry.get("path", "")).startswith(root.lstrip("/") + "/"),
            "files manifest contains a path outside the immutable snapshot",
        )

    repositories = inventory.get("repositories", [])
    require(len(repositories) >= 2, "dotrepo inventory has fewer than two sample repositories")
    for repository in (repositories[0], repositories[-1]):
        identity = repository.get("identity", {})
        record_path = f"{root}/repos/{identity.get('host')}/{identity.get('owner')}/{identity.get('repo')}/index.json"
        record = fetch_json(origin, record_path)
        require(freshness(record, record_path) == expected_freshness, f"{record_path} disagrees with pointer")

    homepage = fetch(origin, "/").decode("utf-8")
    match = re.search(
        r'<script id="dotrepo-homepage-snapshot" type="application/json">(.+?)</script>',
        homepage,
        re.DOTALL,
    )
    require(match is not None, "dotrepo homepage has no embedded snapshot state")
    homepage_state = json.loads(html.unescape(match.group(1)))
    require(homepage_state.get("snapshotDigest") == digest, "dotrepo homepage snapshot disagrees with pointer")
    require(
        homepage_state.get("repositoryCount") == inventory.get("repositoryCount"),
        "dotrepo homepage repository count disagrees with inventory",
    )

    manifest = fetch_json(origin, "/.well-known/pagedigest.json")
    require(manifest.get("version") == 1, "dotrepo pagedigest manifest is not version 1")
    require(isinstance(manifest.get("site_rev"), int) and manifest["site_rev"] > 0, "dotrepo site_rev is invalid")
    return {
        "snapshotDigest": digest,
        "generatedAt": meta.get("generatedAt"),
        "staleAfter": meta.get("staleAfter"),
        "repositoryCount": inventory.get("repositoryCount"),
        "fileCount": files.get("fileCount"),
        "snapshotCount": log.get("snapshotCount"),
        "siteRev": manifest.get("site_rev"),
    }


def check_pagedigest(origin: str, repo_root: Path | None) -> dict[str, Any]:
    homepage = fetch(origin, "/").decode("utf-8")
    manifest = fetch_json(origin, "/.well-known/pagedigest.json")
    require(manifest.get("version") == 1, "pagedigest.org manifest is not version 1")
    require(isinstance(manifest.get("site_rev"), int) and manifest["site_rev"] > 0, "pagedigest.org site_rev is invalid")
    for claim in ("Version 1, release candidate", "Rust generator", "Python consumer"):
        require(claim in homepage, f"pagedigest homepage is missing current claim: {claim}")

    if repo_root is not None:
        local_manifest = json.loads((repo_root / "site/.well-known/pagedigest.json").read_text())
        require(local_manifest.get("version") == manifest.get("version"), "pagedigest live and repository versions disagree")
        require((repo_root / "implementations/rust-generator").is_dir(), "Rust generator is missing from repository")
        require((repo_root / "implementations/python-consumer").is_dir(), "Python consumer is missing from repository")
    return {"version": manifest.get("version"), "siteRev": manifest.get("site_rev")}


def main() -> int:
    args = parse_args()
    try:
        report = {
            "checkedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "dotrepo": check_dotrepo(args.dotrepo_origin),
            "pagedigest": check_pagedigest(
                args.pagedigest_origin,
                Path(args.pagedigest_repo_root) if args.pagedigest_repo_root else None,
            ),
        }
    except Exception as exc:
        print(f"public edge canary failed: {exc}", file=sys.stderr)
        return 1
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
