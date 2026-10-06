#!/usr/bin/env -S uv run python
"""Render a Worker deployment config with a matching snapshot archive binding."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path


def render_config(config_path: Path, bucket: str | None, *, require_archive: bool = False) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    bindings = config.get("r2_buckets", [])
    if not isinstance(bindings, list):
        raise ValueError("r2_buckets must be an array")
    archives = [binding for binding in bindings if binding.get("binding") == "SNAPSHOT_ARCHIVE"]
    if len(archives) > 1:
        raise ValueError("Worker config has duplicate SNAPSHOT_ARCHIVE bindings")
    if bucket:
        if re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket) is None:
            raise ValueError("archive bucket must be a valid R2 bucket name")
        if archives and archives[0].get("bucket_name") != bucket:
            raise ValueError("Worker SNAPSHOT_ARCHIVE binding does not match the upload bucket")
        if not archives:
            config["r2_buckets"] = [
                *bindings,
                {"binding": "SNAPSHOT_ARCHIVE", "bucket_name": bucket},
            ]
    elif require_archive:
        raise ValueError("DOTREPO_PUBLIC_R2_ARCHIVE_BUCKET is required for public deployment")
    elif archives:
        raise ValueError("Worker archive binding requires a matching upload bucket")

    # Wrangler resolves these paths against the config location. The rendered
    # config may live in RUNNER_TEMP, so retain the checked-in source locations.
    source_root = config_path.resolve().parent
    config["main"] = str((source_root / config["main"]).resolve())
    config["assets"]["directory"] = str((source_root / config["assets"]["directory"]).resolve())
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("cloudflare/hosted-query/wrangler.jsonc")
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--archive-bucket", default=os.environ.get("DOTREPO_PUBLIC_R2_ARCHIVE_BUCKET")
    )
    parser.add_argument("--require-archive", action="store_true")
    args = parser.parse_args()
    config = render_config(args.config, args.archive_bucket, require_archive=args.require_archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"rendered hosted config: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
