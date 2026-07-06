#!/usr/bin/env -S uv run python
"""Upload immutable public snapshot payloads to a Cloudflare R2 archive bucket."""

from __future__ import annotations

import argparse
import shlex
import subprocess
from pathlib import Path


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


def main() -> int:
    args = parse_args()
    public_root = Path(args.public_root).resolve()
    wrangler_cwd = Path(args.wrangler_cwd).resolve()

    if not public_root.is_dir():
        raise SystemExit(f"public root does not exist: {public_root}")
    if not wrangler_cwd.is_dir():
        raise SystemExit(f"wrangler cwd does not exist: {wrangler_cwd}")

    files = snapshot_files(public_root)
    for path in files:
        command = upload_command(args.bucket, public_root, path)
        print(shlex.join(command))
        if not args.dry_run:
            subprocess.run(command, cwd=wrangler_cwd, check=True)
    print(f"archived {len(files)} snapshot object(s) to R2 bucket {args.bucket}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
