#!/usr/bin/env -S uv run python
"""Restore deployed snapshot history and public payloads before a clean CI export."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from archive_public_snapshot_r2 import read_archive_log
from sync_cloudflare_public_snapshot import merge_log_documents

MAX_ASSET_BYTES = 32 * 1024 * 1024


def fetch_bytes(url: str, timeout: float) -> bytes:
    request = Request(
        url,
        headers={"Accept": "application/json", "Cache-Control": "no-cache"},
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read(MAX_ASSET_BYTES + 1)
    if len(body) > MAX_ASSET_BYTES:
        raise ValueError(f"deployed asset exceeds {MAX_ASSET_BYTES} bytes: {url}")
    return body


def json_object(body: bytes, description: str) -> dict:
    value = json.loads(body)
    if not isinstance(value, dict):
        raise ValueError(f"{description} must be an object")
    return value


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def restore_public_state(
    base_url: str,
    base_path: str,
    export_root: Path,
    staging_root: Path,
    *,
    timeout: float = 30,
    workers: int = 8,
    archive_bucket: str | None = None,
    wrangler_cwd: Path = Path("cloudflare/hosted-query"),
) -> dict:
    origin = urlsplit(base_url)
    if (
        origin.scheme != "https"
        or not origin.netloc
        or origin.username is not None
        or origin.path not in {"", "/"}
        or origin.query
        or origin.fragment
    ):
        raise ValueError("state base URL must be an HTTPS origin")
    prefix = "/" + base_path.strip("/") if base_path.strip("/") else ""
    if any(segment in {".", ".."} for segment in prefix.split("/")):
        raise ValueError("base path contains traversal segments")
    if workers < 1:
        raise ValueError("workers must be at least 1")

    def fetch(path: str) -> bytes:
        return fetch_bytes(f"{base_url.rstrip('/')}{quote(path, safe='/')}", timeout)

    meta_path = f"{prefix}/v0/meta.json"
    meta = json_object(fetch(meta_path), "deployed metadata")
    snapshot = meta.get("snapshotId")
    if not isinstance(snapshot, str) or re.fullmatch(r"[A-Za-z0-9_-]+", snapshot) is None:
        raise ValueError("deployed metadata has an invalid snapshotId")
    root = f"v0/snapshots/{snapshot}"
    if meta.get("paths", {}).get("root") != f"{prefix}/{root}":
        raise ValueError("deployed metadata has an unexpected snapshot root")

    log = json_object(fetch(f"{prefix}/v0/snapshots/log.json"), "deployed snapshot log")
    log = merge_log_documents(log)
    published = next(
        (entry for entry in log["entries"] if entry.get("snapshotId") == snapshot), None
    )
    if published is None or any(
        published.get(field) != meta.get(field) for field in ["snapshotDigest", "generatedAt"]
    ):
        raise ValueError("deployed snapshot log does not contain the current metadata entry")
    if archive_bucket:
        log = merge_log_documents(read_archive_log(archive_bucket, wrangler_cwd), log)

    manifest_body = fetch(f"{prefix}/{root}/files.json")
    manifest = json_object(manifest_body, "deployed file manifest")
    if any(
        manifest.get("freshness", {}).get(field) != meta.get(field)
        for field in ["snapshotDigest", "generatedAt"]
    ):
        raise ValueError("deployed file manifest does not match current metadata")
    entries = manifest.get("files")
    if not isinstance(entries, list) or manifest.get("fileCount") != len(entries):
        raise ValueError("deployed file manifest has an invalid file count")
    public_entries = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("deployed file manifest entries must be objects")
        path = entry.get("path")
        if (
            not isinstance(path, str)
            or not path.startswith(f"{root}/")
            or any(segment in {"", ".", ".."} for segment in path.split("/"))
            or "\\" in path
            or path in seen
        ):
            raise ValueError(f"deployed file manifest has an unsafe or duplicate path: {path}")
        seen.add(path)
        if (
            not isinstance(entry.get("bytes"), int)
            or isinstance(entry["bytes"], bool)
            or entry["bytes"] < 0
            or not isinstance(entry.get("sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) is None
        ):
            raise ValueError(f"deployed file manifest has invalid validators: {path}")
        # These implementation payloads are deliberately private on the Worker.
        # All externally retrievable immutable snapshot leaves are restored.
        if not PurePosixPath(path).relative_to(root).parts[0] == "query-input":
            public_entries.append(entry)

    staging_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="dotrepo-public-restored-", dir=staging_root.parent
    ) as temporary:
        restored = Path(temporary) / "snapshot"
        restored.mkdir()

        def restore_entry(entry: dict) -> None:
            body = fetch(f"{prefix}/{entry['path']}")
            if len(body) != entry["bytes"] or hashlib.sha256(body).hexdigest() != entry["sha256"]:
                raise ValueError(
                    f"deployed payload fails file manifest validation: {entry['path']}"
                )
            path = restored / entry["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)

        with ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(restore_entry, public_entries))
        # A concurrent manual deployment must not turn the history and pointer
        # into a mixture of two snapshots. Keep the old local state on failure.
        if json_object(fetch(meta_path), "deployed metadata") != meta:
            raise ValueError("deployed metadata changed during restoration; retry before exporting")
        write_json(restored / "v0/meta.json", meta)
        write_json(restored / "v0/snapshots/log.json", log)
        manifest_path = restored / root / "files.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_bytes(manifest_body)

        # Seed the exporter before it computes stats; staging then retains this
        # snapshot as the previous public payload after the new export is built.
        write_json(export_root / "v0/snapshots/log.json", log)
        if staging_root.exists():
            shutil.rmtree(staging_root)
        restored.replace(staging_root)
    return {
        "snapshotId": snapshot,
        "snapshotCount": log["snapshotCount"],
        "restoredFiles": len(public_entries),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Currently deployed HTTPS origin")
    parser.add_argument("--base-path", default="/", help="Deployed public base path")
    parser.add_argument("--export-root", required=True, type=Path, help="Export directory to seed")
    parser.add_argument("--staging-root", required=True, type=Path, help="Worker staging directory")
    parser.add_argument(
        "--archive-bucket", help="Optional R2 bucket whose history is also restored"
    )
    parser.add_argument("--wrangler-cwd", type=Path, default=Path("cloudflare/hosted-query"))
    parser.add_argument("--timeout", type=float, default=30, help="Per-asset timeout in seconds")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent public asset fetches")
    args = parser.parse_args()
    result = restore_public_state(
        args.base_url,
        args.base_path,
        args.export_root.resolve(),
        args.staging_root.resolve(),
        timeout=args.timeout,
        workers=args.workers,
        archive_bucket=args.archive_bucket,
        wrangler_cwd=args.wrangler_cwd.resolve(),
    )
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
