#!/usr/bin/env python3

import argparse
import json
import tarfile
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package a versioned bundle from a dotrepo public export tree."
    )
    parser.add_argument(
        "--input",
        dest="input_dir",
        default="public",
        help="Path to the exported public tree (default: public)",
    )
    parser.add_argument(
        "--output-dir",
        default="dist",
        help="Directory where the bundle will be written (default: dist)",
    )
    parser.add_argument(
        "--prefix",
        default="dotrepo-public-export",
        help="Bundle filename prefix (default: dotrepo-public-export)",
    )
    return parser.parse_args()


def normalize_tarinfo(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    return info


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    meta_path = input_dir / "v0" / "meta.json"
    if not meta_path.is_file():
        raise SystemExit(f"missing export metadata file: {meta_path}")

    meta = json.loads(meta_path.read_text())
    api_version = meta.get("apiVersion")
    snapshot_digest = meta.get("snapshotDigest")
    if not isinstance(api_version, str) or not api_version:
        raise SystemExit(f"meta.json is missing apiVersion: {meta_path}")
    if not isinstance(snapshot_digest, str) or not snapshot_digest:
        raise SystemExit(f"meta.json is missing snapshotDigest: {meta_path}")

    digest_prefix = snapshot_digest[:12]
    bundle_stem = f"{args.prefix}-{api_version}-{digest_prefix}"
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = output_dir / f"{bundle_stem}.tar.gz"

    with tarfile.open(bundle_path, "w:gz") as archive:
        for path in sorted(input_dir.rglob("*")):
            if path.is_dir():
                continue
            arcname = Path(bundle_stem) / path.relative_to(input_dir)
            archive.add(path, arcname=str(arcname), recursive=False, filter=normalize_tarinfo)

    print(bundle_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
