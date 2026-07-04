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
    parser.add_argument(
        "--sample-archived-snapshot",
        action="store_true",
        help="Fetch one older immutable snapshot path to verify archive fallback.",
    )
    return parser.parse_args()


def fetch(origin: str, path: str) -> bytes:
    separator = "&" if "?" in path else "?"
    url = urljoin(f"{origin.rstrip('/')}/", path.lstrip("/"))
    request = Request(
        f"{url}{separator}_canary={uuid.uuid4().hex}",
        headers={
            "User-Agent": "dotrepo-public-edge-canary/1.0",
            "Cache-Control": "no-cache",
        },
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


def required_int(value: Any, message: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise CanaryFailure(message) from exc


def freshness(value: dict[str, Any], context: str) -> dict[str, Any]:
    result = value.get("freshness")
    require(isinstance(result, dict), f"{context} is missing freshness")
    return result


def archived_snapshot_sample(
    origin: str, log_entries: list[Any], latest_digest: str
) -> dict[str, Any] | None:
    candidates = [
        entry
        for entry in log_entries
        if isinstance(entry, dict) and entry.get("snapshotDigest") != latest_digest
    ]
    if not candidates:
        return None
    selected = candidates[0]
    snapshot_id = selected.get("snapshotId")
    require(
        isinstance(snapshot_id, str) and snapshot_id,
        "archived snapshot candidate has no snapshotId",
    )
    files_path = f"/v0/snapshots/{snapshot_id}/files.json"
    files = fetch_json(origin, files_path)
    public_paths = [
        entry.get("path")
        for entry in files.get("files", [])
        if isinstance(entry, dict)
        and isinstance(entry.get("path"), str)
        and "/query-input/" not in entry["path"]
    ]
    require(
        public_paths,
        f"archived snapshot {snapshot_id} file manifest has no public paths",
    )
    sample_path = "/" + public_paths[0].lstrip("/")
    fetch(origin, sample_path)
    return {
        "snapshotId": snapshot_id,
        "filesPath": files_path,
        "samplePath": sample_path,
    }


def validate_pagedigest_stats(
    stats: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any] | None:
    pagedigest = stats.get("pagedigest")
    if pagedigest is None:
        return None
    require(isinstance(pagedigest, dict), "stats pagedigest block is not an object")
    entries = manifest.get("entries")
    require(
        isinstance(entries, dict),
        "dotrepo pagedigest manifest entries are not an object",
    )
    require(
        pagedigest.get("version") == manifest.get("version"),
        "stats pagedigest version disagrees with manifest",
    )
    require(
        pagedigest.get("siteRev") == manifest.get("site_rev"),
        "stats pagedigest siteRev disagrees with manifest",
    )
    require(
        pagedigest.get("generated") == manifest.get("generated"),
        "stats pagedigest generated timestamp disagrees with manifest",
    )
    require(
        pagedigest.get("recordsCovered") == len(entries),
        "stats pagedigest recordsCovered disagrees with manifest entries",
    )

    new_records = required_int(
        pagedigest.get("newRecords"), "stats pagedigest newRecords is not an integer"
    )
    changed_records = required_int(
        pagedigest.get("changedRecords"),
        "stats pagedigest changedRecords is not an integer",
    )
    unchanged_records = required_int(
        pagedigest.get("unchangedRecords"),
        "stats pagedigest unchangedRecords is not an integer",
    )
    records_needing_fetch = required_int(
        pagedigest.get("recordsNeedingFetch"),
        "stats pagedigest recordsNeedingFetch is not an integer",
    )
    fetches_avoided = required_int(
        pagedigest.get("fetchesAvoided"),
        "stats pagedigest fetchesAvoided is not an integer",
    )
    bytes_covered = required_int(
        pagedigest.get("bytesCovered"),
        "stats pagedigest bytesCovered is not an integer",
    )
    bytes_avoided = required_int(
        pagedigest.get("bytesAvoided"),
        "stats pagedigest bytesAvoided is not an integer",
    )
    estimated_tokens_avoided = required_int(
        pagedigest.get("estimatedTokensAvoided"),
        "stats pagedigest estimatedTokensAvoided is not an integer",
    )
    require(
        pagedigest.get("recordsCovered")
        == new_records + changed_records + unchanged_records,
        "stats pagedigest record buckets do not add up",
    )
    require(
        records_needing_fetch == new_records + changed_records,
        "stats pagedigest recordsNeedingFetch disagrees with new+changed records",
    )
    require(
        fetches_avoided == unchanged_records,
        "stats pagedigest fetchesAvoided disagrees with unchanged records",
    )
    require(bytes_covered >= 0, "stats pagedigest bytesCovered is negative")
    require(bytes_avoided >= 0, "stats pagedigest bytesAvoided is negative")
    require(
        bytes_avoided <= bytes_covered,
        "stats pagedigest bytesAvoided exceeds bytesCovered",
    )
    require(
        estimated_tokens_avoided == bytes_avoided // 4,
        "stats pagedigest estimatedTokensAvoided disagrees with bytesAvoided",
    )
    require(
        required_int(
            pagedigest.get("manifestBytes"),
            "stats pagedigest manifestBytes is not an integer",
        )
        > 0,
        "stats pagedigest manifestBytes is missing",
    )
    return {
        "recordsCovered": pagedigest.get("recordsCovered"),
        "recordsNeedingFetch": records_needing_fetch,
        "fetchesAvoided": fetches_avoided,
        "bytesAvoided": bytes_avoided,
        "estimatedTokensAvoided": estimated_tokens_avoided,
    }


def validate_health(
    health: dict[str, Any], meta: dict[str, Any], inventory: dict[str, Any], stats: dict[str, Any]
) -> dict[str, Any]:
    repositories = inventory.get("repositories")
    require(isinstance(repositories, list), "health validation needs inventory repositories")
    latest = stats.get("latest")
    require(isinstance(latest, dict), "health validation needs stats latest")
    pagedigest_stats = stats.get("pagedigest")
    require(isinstance(pagedigest_stats, dict), "health validation needs stats pagedigest")
    expected = {
        "ok": True,
        "canonicalOrigin": "https://dotrepo.org",
        "apiVersion": meta.get("apiVersion"),
        "snapshotId": meta.get("snapshotId"),
        "snapshotDigest": meta.get("snapshotDigest"),
        "reposIndexCount": len(repositories),
        "statsRepositoryCount": latest.get("repositoryCount"),
        "pagedigestSiteRev": pagedigest_stats.get("siteRev"),
        "pagedigestRecordsCovered": pagedigest_stats.get("recordsCovered"),
        "checkedAt": meta.get("generatedAt"),
    }
    for key, expected_value in expected.items():
        require(
            health.get(key) == expected_value,
            f"health {key} disagrees with public surface",
        )
    require(
        health.get("reposIndexCount") == health.get("statsRepositoryCount"),
        "health repository counts disagree",
    )
    for key in (
        "homepageDigest",
        "metaDigest",
        "statsDigest",
        "reposIndexDigest",
        "filesDigest",
        "pagedigestDigest",
    ):
        digest = health.get(key)
        require(
            isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
            f"health {key} is not a sha256 hex digest",
        )
    return {
        "ok": health.get("ok"),
        "snapshotId": health.get("snapshotId"),
        "reposIndexCount": health.get("reposIndexCount"),
        "pagedigestSiteRev": health.get("pagedigestSiteRev"),
    }


def check_dotrepo(origin: str, sample_archived_snapshot: bool) -> dict[str, Any]:
    meta = fetch_json(origin, "/v0/meta.json")
    paths = meta.get("paths")
    require(isinstance(paths, dict), "dotrepo meta is missing content-addressed paths")
    snapshot_id = meta.get("snapshotId")
    digest = meta.get("snapshotDigest")
    require(
        isinstance(snapshot_id, str) and snapshot_id, "dotrepo meta has no snapshotId"
    )
    require(
        isinstance(digest, str) and digest.startswith(snapshot_id),
        "snapshotId does not match snapshotDigest",
    )
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
    health = fetch_json(origin, "/v0/health.json")
    expected_freshness = {
        key: meta.get(key)
        for key in ("generatedAt", "snapshotDigest", "staleAfter")
        if meta.get(key) is not None
    }
    require(
        freshness(inventory, "inventory") == expected_freshness,
        "inventory freshness disagrees with pointer",
    )
    require(
        freshness(files, "files manifest") == expected_freshness,
        "files freshness disagrees with pointer",
    )
    require(
        inventory.get("repositoryCount") == len(inventory.get("repositories", [])),
        "repository count is inconsistent",
    )
    log_entries = log.get("entries")
    require(isinstance(log_entries, list) and log_entries, "snapshot log is empty")
    latest_log = log_entries[-1]
    require(
        latest_log.get("snapshotDigest") == digest,
        "snapshot log latest digest disagrees with pointer",
    )
    require(
        latest_log.get("repositoryCount") == inventory.get("repositoryCount"),
        "snapshot log repository count disagrees",
    )
    require(
        latest_log.get("fileCount") == files.get("fileCount"),
        "snapshot log file count disagrees",
    )
    require(
        stats.get("latest", {}).get("snapshotDigest") == digest,
        "stats latest digest disagrees with pointer",
    )
    require(
        stats.get("snapshotCount") == log.get("snapshotCount"),
        "stats snapshot count disagrees with log",
    )
    for entry in files.get("files", []):
        require(
            isinstance(entry, dict)
            and str(entry.get("path", "")).startswith(root.lstrip("/") + "/"),
            "files manifest contains a path outside the immutable snapshot",
        )

    repositories = inventory.get("repositories", [])
    require(
        len(repositories) >= 2,
        "dotrepo inventory has fewer than two sample repositories",
    )
    for repository in (repositories[0], repositories[-1]):
        identity = repository.get("identity", {})
        record_path = f"{root}/repos/{identity.get('host')}/{identity.get('owner')}/{identity.get('repo')}/index.json"
        record = fetch_json(origin, record_path)
        require(
            freshness(record, record_path) == expected_freshness,
            f"{record_path} disagrees with pointer",
        )
    archive_sample = (
        archived_snapshot_sample(origin, log_entries, digest)
        if sample_archived_snapshot
        else None
    )

    homepage = fetch(origin, "/").decode("utf-8")
    match = re.search(
        r'<script id="dotrepo-homepage-snapshot" type="application/json">(.+?)</script>',
        homepage,
        re.DOTALL,
    )
    require(match is not None, "dotrepo homepage has no embedded snapshot state")
    homepage_state = json.loads(html.unescape(match.group(1)))
    require(
        homepage_state.get("snapshotDigest") == digest,
        "dotrepo homepage snapshot disagrees with pointer",
    )
    require(
        homepage_state.get("repositoryCount") == inventory.get("repositoryCount"),
        "dotrepo homepage repository count disagrees with inventory",
    )

    manifest = fetch_json(origin, "/.well-known/pagedigest.json")
    require(
        manifest.get("version") == 1, "dotrepo pagedigest manifest is not version 1"
    )
    require(
        isinstance(manifest.get("site_rev"), int) and manifest["site_rev"] > 0,
        "dotrepo site_rev is invalid",
    )
    pagedigest_stats = validate_pagedigest_stats(stats, manifest)
    health_summary = validate_health(health, meta, inventory, stats)
    return {
        "snapshotDigest": digest,
        "generatedAt": meta.get("generatedAt"),
        "staleAfter": meta.get("staleAfter"),
        "repositoryCount": inventory.get("repositoryCount"),
        "fileCount": files.get("fileCount"),
        "snapshotCount": log.get("snapshotCount"),
        "archiveSample": archive_sample,
        "siteRev": manifest.get("site_rev"),
        "pagedigestStats": pagedigest_stats,
        "health": health_summary,
    }


def check_pagedigest(origin: str, repo_root: Path | None) -> dict[str, Any]:
    homepage = fetch(origin, "/").decode("utf-8")
    manifest = fetch_json(origin, "/.well-known/pagedigest.json")
    require(manifest.get("version") == 1, "pagedigest.org manifest is not version 1")
    require(
        isinstance(manifest.get("site_rev"), int) and manifest["site_rev"] > 0,
        "pagedigest.org site_rev is invalid",
    )
    for claim in ("Version 1, release candidate", "Rust generator", "Python consumer"):
        require(
            claim in homepage, f"pagedigest homepage is missing current claim: {claim}"
        )

    if repo_root is not None:
        local_manifest = json.loads(
            (repo_root / "site/.well-known/pagedigest.json").read_text()
        )
        require(
            local_manifest.get("version") == manifest.get("version"),
            "pagedigest live and repository versions disagree",
        )
        require(
            (repo_root / "implementations/rust-generator").is_dir(),
            "Rust generator is missing from repository",
        )
        require(
            (repo_root / "implementations/python-consumer").is_dir(),
            "Python consumer is missing from repository",
        )
    return {"version": manifest.get("version"), "siteRev": manifest.get("site_rev")}


def main() -> int:
    args = parse_args()
    try:
        report = {
            "checkedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "dotrepo": check_dotrepo(
                args.dotrepo_origin, args.sample_archived_snapshot
            ),
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
