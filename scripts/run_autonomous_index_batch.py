#!/usr/bin/env python3
"""Run one autonomous index refresh batch: crawl, gate, writeback, validate."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-root", default="index")
    parser.add_argument("--state-path", default="index/.crawler-state.toml")
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--batch-id", default="refresh-batch-01")
    parser.add_argument("--output-dir", default="index-autonomous-batch")
    parser.add_argument(
        "--skip-automation-enabled-check",
        action="store_true",
        help="Allow local runs without INDEX_AUTOMATION_ENABLED=true",
    )
    return parser.parse_args()


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(command), flush=True)
    return subprocess.run(command, check=check, text=True, capture_output=True)


def main() -> int:
    args = parse_args()
    if not args.skip_automation_enabled_check and os.environ.get(
        "INDEX_AUTOMATION_ENABLED", "true"
    ).lower() not in {"1", "true", "yes"}:
        print("INDEX_AUTOMATION_ENABLED is not true; skipping autonomous batch", file=sys.stderr)
        return 0

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    refresh_plan = output_dir / "refresh-plan.json"
    refresh_batches = output_dir / "refresh-batches.json"
    selected_targets = output_dir / "selected-targets.txt"
    telemetry_path = output_dir / "telemetry.json"

    proc = run(
        [
            "cargo",
            "run",
            "-q",
            "-p",
            "dotrepo-crawler",
            "--",
            "refresh-plan",
            "--state-path",
            args.state_path,
            "--limit",
            str(args.limit),
            "--json",
        ]
    )
    refresh_plan.write_text(proc.stdout)

    run(
        [
            "python3",
            "scripts/plan_refresh_review_batches.py",
            "--input",
            str(refresh_plan),
            "--batch-size",
            str(args.batch_size),
            "--output-json",
            str(refresh_batches),
            "--output-md",
            str(output_dir / "refresh-batches.md"),
        ]
    )

    run(
        [
            "python3",
            "scripts/select_review_batch.py",
            "--input",
            str(refresh_batches),
            "--batch-id",
            args.batch_id,
            "--output-targets",
            str(selected_targets),
            "--output-metadata",
            str(output_dir / "selected-batch.json"),
        ]
    )

    crawls: list[dict] = []
    if not selected_targets.is_file() or selected_targets.stat().st_size == 0:
        telemetry = {
            "batchId": args.batch_id,
            "crawled": 0,
            "written": 0,
            "failed": 0,
            "skipped": 0,
            "adjudicationCalls": 0,
            "tokensUsed": 0,
            "adjudicationRate": 0.0,
            "crawls": crawls,
        }
        telemetry_path.write_text(json.dumps(telemetry, indent=2) + "\n")
        print("No refresh targets in selected batch")
        return 0

    for line in selected_targets.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        host, owner, repo = line.split("/", 2)
        entry = {"repository": f"{host}/{owner}/{repo}", "status": "failed"}
        crawls.append(entry)
        try:
            proc = run(
                [
                    "cargo",
                    "run",
                    "-q",
                    "-p",
                    "dotrepo-crawler",
                    "--",
                    "crawl",
                    "--index-root",
                    args.index_root,
                    "--state-path",
                    args.state_path,
                    "--host",
                    host,
                    "--owner",
                    owner,
                    "--repo",
                    repo,
                    "--write",
                    "--json",
                ],
                check=False,
            )
            if proc.returncode == 0:
                payload = json.loads(proc.stdout)
                entry["status"] = "written" if payload.get("wrote") else "skipped"
                entry["manifestPath"] = payload.get("manifestPath")
                escalation = payload.get("escalation") or {}
                entry["escalation"] = escalation
                entry["adjudicationCalls"] = int(escalation.get("modelCalls") or 0)
                entry["tokensUsed"] = int(escalation.get("tokensUsed") or 0)
            else:
                entry["status"] = "failed"
                entry["error"] = (proc.stderr or proc.stdout).strip()[-500:]
        except Exception as exc:  # noqa: BLE001 - batch telemetry should continue
            entry["status"] = "failed"
            entry["error"] = str(exc)

    written = sum(1 for item in crawls if item["status"] == "written")
    failed = sum(1 for item in crawls if item["status"] == "failed")
    skipped = sum(1 for item in crawls if item["status"] == "skipped")
    adjudication_calls = sum(int(item.get("adjudicationCalls") or 0) for item in crawls)
    tokens_used = sum(int(item.get("tokensUsed") or 0) for item in crawls)
    repos_with_adjudication = sum(
        1 for item in crawls if int(item.get("adjudicationCalls") or 0) > 0
    )
    adjudication_rate = (
        repos_with_adjudication / len(crawls) if crawls else 0.0
    )

    if written > 0:
        run(["cargo", "run", "-q", "-p", "dotrepo-cli", "--", "validate-index"])

    telemetry = {
        "batchId": args.batch_id,
        "crawled": len(crawls),
        "written": written,
        "failed": failed,
        "skipped": skipped,
        "adjudicationCalls": adjudication_calls,
        "tokensUsed": tokens_used,
        "adjudicationRate": adjudication_rate,
        "crawls": crawls,
    }
    telemetry_path.write_text(json.dumps(telemetry, indent=2) + "\n")
    print(json.dumps(telemetry, indent=2))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())