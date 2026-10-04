#!/usr/bin/env -S uv run python
"""Upload immutable public snapshot payloads to a Cloudflare R2 archive bucket."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import tempfile
from pathlib import Path

from sync_cloudflare_public_snapshot import load_json, merge_log_documents


IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
MUTABLE_CACHE_CONTROL = "no-cache"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--public-root",
        required=True,
        help="Reviewed exported public tree containing v0/snapshots/",
    )
    parser.add_argument(
        "--bucket",
        required=True,
        help="R2 bucket name that stores archived public snapshots",
    )
    parser.add_argument(
        "--wrangler-cwd",
        default="cloudflare/hosted-query",
        help="Directory from which to run npx wrangler (default: cloudflare/hosted-query)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the upload plan without invoking Wrangler",
    )
    parser.add_argument(
        "--require-complete-history",
        action="store_true",
        help="Fail if the reviewed local log omits an existing archive entry",
    )
    return parser.parse_args()


def snapshot_files(public_root: Path) -> list[Path]:
    snapshot_root = public_root / "v0" / "snapshots"
    if not snapshot_root.is_dir():
        raise SystemExit(f"snapshot root does not exist: {snapshot_root}")
    files = sorted(path for path in snapshot_root.rglob("*") if path.is_file())
    if not files:
        raise SystemExit(f"snapshot root contains no files: {snapshot_root}")
    return files


def content_type(path: Path) -> str:
    if path.suffix == ".json":
        return "application/json; charset=utf-8"
    if path.suffix in {".html", ".htm"}:
        return "text/html; charset=utf-8"
    if path.suffix == ".txt":
        return "text/plain; charset=utf-8"
    return "application/octet-stream"


def cache_control(relative_path: str) -> str:
    return (
        MUTABLE_CACHE_CONTROL
        if relative_path == "v0/snapshots/log.json"
        else IMMUTABLE_CACHE_CONTROL
    )


def upload_command(bucket: str, public_root: Path, path: Path) -> list[str]:
    relative_path = path.relative_to(public_root).as_posix()
    return [
        "npx",
        "wrangler",
        "r2",
        "object",
        "put",
        f"{bucket}/{relative_path}",
        "--remote",
        "--file",
        str(path),
        "--content-type",
        content_type(path),
        "--cache-control",
        cache_control(relative_path),
    ]


def read_archive_log(bucket: str, wrangler_cwd: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="dotrepo-archive-log-") as temporary:
        path = Path(temporary) / "log.json"
        command = [
            "npx",
            "wrangler",
            "r2",
            "object",
            "get",
            f"{bucket}/v0/snapshots/log.json",
            "--remote",
            "--file",
            str(path),
        ]
        result = subprocess.run(command, cwd=wrangler_cwd, capture_output=True, text=True)
        if result.returncode != 0:
            # Wrangler distinguishes a missing object from authentication,
            # bucket and transport failures. Only an empty archive is optional.
            if "The specified key does not exist." in result.stderr:
                return {}
            raise RuntimeError(f"failed to read archived snapshot log: {result.stderr.strip()}")
        log = load_json(path)
        merge_log_documents(log)
        return log


def archive_snapshots(
    public_root: Path, bucket: str, wrangler_cwd: Path, *, require_complete_history: bool = False
) -> int:
    files = snapshot_files(public_root)
    local_log = load_json(public_root / "v0/snapshots/log.json")
    if not local_log.get("entries"):
        raise ValueError("public snapshot log is missing or empty")
    archived_log = read_archive_log(bucket, wrangler_cwd)
    merged_log = merge_log_documents(archived_log, local_log)
    if require_complete_history and merged_log != merge_log_documents(local_log):
        raise ValueError("reviewed snapshot log omits archive history; restore it before export")

    # Upload the mutable log last so every newly advertised payload is available.
    payloads = [
        path
        for path in files
        if path.relative_to(public_root).as_posix() != "v0/snapshots/log.json"
    ]
    for path in payloads:
        subprocess.run(upload_command(bucket, public_root, path), cwd=wrangler_cwd, check=True)
    with tempfile.TemporaryDirectory(prefix="dotrepo-archive-merged-") as temporary:
        merged_root = Path(temporary)
        path = merged_root / "v0/snapshots/log.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(merged_log, indent=2) + "\n", encoding="utf-8")
        subprocess.run(upload_command(bucket, merged_root, path), cwd=wrangler_cwd, check=True)
    return len(payloads) + 1


def main() -> int:
    args = parse_args()
    public_root = Path(args.public_root).resolve()
    wrangler_cwd = Path(args.wrangler_cwd).resolve()

    if not public_root.is_dir():
        raise SystemExit(f"public root does not exist: {public_root}")
    if not wrangler_cwd.is_dir():
        raise SystemExit(f"wrangler cwd does not exist: {wrangler_cwd}")

    if args.dry_run:
        files = snapshot_files(public_root)
        for path in files:
            print(shlex.join(upload_command(args.bucket, public_root, path)))
        print(
            "Before upload, the existing archive log is read and merged; the log is uploaded last."
        )
        return 0
    count = archive_snapshots(
        public_root,
        args.bucket,
        wrangler_cwd,
        require_complete_history=args.require_complete_history,
    )
    print(f"archived {count} snapshot object(s) to R2 bucket {args.bucket}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
