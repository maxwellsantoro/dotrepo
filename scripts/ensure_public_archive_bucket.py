#!/usr/bin/env -S uv run python
"""Create the declared R2 archive bucket only after a successful account listing."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


def list_buckets(cwd: Path) -> set[str]:
    result = subprocess.run(
        ["npx", "wrangler", "r2", "bucket", "list"],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    output = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    if "Listing buckets..." not in output:
        raise ValueError("Wrangler bucket listing has an unsupported output format")
    names = set(re.findall(r"(?m)^name:\s*([a-z0-9][a-z0-9-]{1,61}[a-z0-9])\s*$", output))
    if "creation_date:" in output and not names:
        raise ValueError("Wrangler bucket listing names could not be validated")
    return names


def ensure_bucket(bucket: str, cwd: Path) -> dict:
    if re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket) is None:
        raise ValueError("archive bucket must be a valid R2 bucket name")
    if bucket in list_buckets(cwd):
        return {"bucket": bucket, "created": False}
    subprocess.run(
        ["npx", "wrangler", "r2", "bucket", "create", bucket, "--update-config=false"],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    if bucket not in list_buckets(cwd):
        raise ValueError("created archive bucket is absent from the verified account listing")
    return {"bucket": bucket, "created": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--wrangler-cwd", type=Path, default=Path("cloudflare/hosted-query"))
    args = parser.parse_args()
    print(json.dumps(ensure_bucket(args.bucket, args.wrangler_cwd.resolve())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
