#!/usr/bin/env -S uv run python
"""Explicit catch-up of stale existing records, in bounded deterministic cohorts.

No discovery or model calls. Each worker has an isolated crawler state file.
Failed records retain their prior files; every cohort is validated before the next.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
import tomllib

from public_product_content import record_status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-root", type=Path, default=Path("index"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 5))
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error("--limit must be 1..1000")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    targets = []
    for path in sorted((args.index_root / "repos").glob("*/*/*/record.toml")):
        doc = tomllib.loads(path.read_text())
        record = doc["record"]
        if record.get("mode") != "overlay" or record.get("status") in {"canonical", "reviewed"}:
            continue
        status, _ = record_status({"generatedAt": record.get("generated_at")}, now)
        if status != "fresh":
            targets.append(
                (
                    record.get("generated_at", ""),
                    path.parent.relative_to(args.index_root / "repos").as_posix(),
                )
            )
    identities = [identity for _, identity in sorted(targets)[: args.limit]]
    (args.output_dir / "targets.json").write_text(json.dumps(identities, indent=2) + "\n")
    subprocess.run(
        ["cargo", "build", "-q", "-p", "dotrepo-crawler", "-p", "dotrepo-cli"], check=True
    )
    env = os.environ.copy()
    env["INDEX_MAX_ADJUDICATION_CALLS"] = "0"
    for key in list(env):
        if key.startswith("DOTREPO_ADJUDICATION_"):
            env.pop(key)
    results = []

    def crawl(identity):
        host, owner, repo = identity.split("/")
        started = time.perf_counter()
        output = args.output_dir / host / owner / repo
        output.mkdir(parents=True, exist_ok=True)
        command = [
            "target/debug/dotrepo-crawler",
            "crawl",
            "--index-root",
            str(args.index_root),
            "--state-path",
            str(output / "state.toml"),
            "--host",
            host,
            "--owner",
            owner,
            "--repo",
            repo,
            "--write",
            "--json",
        ]
        try:
            run = subprocess.run(command, env=env, capture_output=True, text=True, timeout=180)
            (output / "crawl.json").write_text(run.stdout)
            (output / "stderr.txt").write_text(run.stderr)
            return {
                "repository": identity,
                "success": run.returncode == 0,
                "elapsedSeconds": round(time.perf_counter() - started, 3),
                "error": run.stderr[-2000:] if run.returncode else None,
            }
        except subprocess.TimeoutExpired:
            return {"repository": identity, "success": False, "error": "crawl timeout"}

    for offset in range(0, len(identities), 50):
        with ThreadPoolExecutor(max_workers=args.workers) as workers:
            results.extend(workers.map(crawl, identities[offset : offset + 50]))
        summary = {
            "generatedAt": now,
            "mode": "deterministic-catch-up",
            "modelCalls": 0,
            "attempted": len(results),
            "succeeded": sum(r["success"] for r in results),
            "failed": sum(not r["success"] for r in results),
            "results": results,
        }
        (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(
            f"Cohort complete: {summary['succeeded']}/{summary['attempted']} refreshed", flush=True
        )
        subprocess.run(
            ["target/debug/dotrepo", "validate-index", "--index-root", str(args.index_root)],
            check=True,
        )
    return int(any(not r["success"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
