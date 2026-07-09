#!/usr/bin/env -S uv run python
"""Export lookup-miss demand for Milestone 4 cohort selection.

Wraps ``aggregate_lookup_misses.py`` with a standard output layout so operators
can run a fixed cadence without re-deriving paths:

1. Collect Worker ``DOTREPO_LOOKUP_MISS`` lines (Logpush, ``wrangler tail``,
   or dashboard export) into one or more log files.
2. Run this script to produce JSON + markdown demand reports under
   ``index/telemetry/`` (gitignored optional copies can stay local).

Offline proof (no network):

```bash
uv run python scripts/export_lookup_miss_demand.py \\
  --input scripts/fixtures/lookup_miss_sample.log
```
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        help="Worker log or NDJSON file; may be repeated. Defaults to the offline fixture.",
    )
    parser.add_argument(
        "--output-dir",
        default="index/telemetry",
        help="Directory for demand reports (default: index/telemetry)",
    )
    parser.add_argument(
        "--stamp",
        default="",
        help="Optional YYYYMMDD stamp; default is UTC today",
    )
    parser.add_argument("--top", type=int, default=50)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    inputs = args.input or [
        str(repo_root / "scripts" / "fixtures" / "lookup_miss_sample.log")
    ]
    stamp = args.stamp.strip() or datetime.now(timezone.utc).strftime("%Y%m%d")
    out_dir = Path(args.output_dir)
    if not out_dir.is_absolute():
        out_dir = repo_root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    output_json = out_dir / f"lookup-miss-demand-{stamp}.json"
    output_md = out_dir / f"lookup-miss-demand-{stamp}.md"
    latest_json = out_dir / "lookup-miss-demand-latest.json"
    latest_md = out_dir / "lookup-miss-demand-latest.md"

    cmd = [
        "uv",
        "run",
        "python",
        str(repo_root / "scripts" / "aggregate_lookup_misses.py"),
        "--output-json",
        str(output_json),
        "--output-md",
        str(output_md),
        "--top",
        str(args.top),
    ]
    for path in inputs:
        cmd.extend(["--input", path])

    completed = subprocess.run(cmd, cwd=repo_root, check=False)
    if completed.returncode != 0:
        return completed.returncode

    latest_json.write_bytes(output_json.read_bytes())
    latest_md.write_bytes(output_md.read_bytes())
    print(f"wrote {output_json}")
    print(f"wrote {output_md}")
    print(f"updated {latest_json}")
    print(f"updated {latest_md}")
    print(
        "Next: feed repeated misses into scripts/plan_index_growth_tranche.py "
        "after ecosystem balancing (see docs/distribution.md)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
