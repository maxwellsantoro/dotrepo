#!/usr/bin/env -S uv run python
"""Gate factual record age independently of snapshot publication time."""

import argparse
import json
from pathlib import Path

from public_product_content import freshness_summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--max-stale-or-unknown-rate", type=float, default=0.1)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    if not 0 <= args.max_stale_or_unknown_rate <= 1:
        parser.error("rate must be between 0 and 1")
    meta = json.loads((args.public_root / "v0/meta.json").read_text())
    inventory = json.loads((args.public_root / "v0/repos/index.json").read_text())
    result = freshness_summary(args.public_root, inventory, meta["generatedAt"])
    total = result["fresh"] + result["stale"] + result["unknown"]
    result["staleOrUnknownRate"] = (result["stale"] + result["unknown"]) / total if total else 1.0
    result["maxStaleOrUnknownRate"] = args.max_stale_or_unknown_rate
    result["passed"] = total > 0 and result["staleOrUnknownRate"] <= args.max_stale_or_unknown_rate
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return int(not result["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
