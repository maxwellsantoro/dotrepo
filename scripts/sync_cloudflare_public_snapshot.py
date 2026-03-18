#!/usr/bin/env python3

import argparse
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage a reviewed dotrepo public export for the Cloudflare Worker."
    )
    parser.add_argument("--input", required=True, help="Source public export directory")
    parser.add_argument("--output", required=True, help="Destination Worker snapshot directory")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()

    if not input_dir.is_dir():
      raise SystemExit(f"input public export directory does not exist: {input_dir}")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(input_dir, output_dir)
    print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
