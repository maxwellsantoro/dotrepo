#!/usr/bin/env -S uv run python
"""Render a one-page autonomous-operation status report from retained telemetry.

Reads only checked-in artifacts (autonomous telemetry summary, retained run
history, and an optional freshness-check JSON), so it can run in a weekly
workflow artifact job with no credentials. It reports operating state; it
does not grade factual accuracy, which has separate sampled gates.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def render_status(summary: dict, runs: list[dict], freshness: dict | None, now: datetime) -> str:
    totals = summary.get("totals", {})
    rates = summary.get("rates", {})
    last_run_at = _parse_ts(summary.get("lastRunAt"))
    last_age = (
        f"{(now - last_run_at).total_seconds() / 86400:.1f}d ago" if last_run_at else "unknown"
    )
    recent = runs[-7:]
    recent_failures = sum(1 for run in recent if run.get("failed", 0) > 0)
    lines = [
        "# Autonomous operation status",
        "",
        f"Generated {now.strftime('%Y-%m-%dT%H:%M:%SZ')} from retained telemetry "
        f"(summary generated {summary.get('generatedAt', 'unknown')}).",
        "",
        "## Refresh operation",
        "",
        f"- Retained runs: {summary.get('runCount', 0)} "
        f"(first {summary.get('firstRunAt', 'unknown')}, last {summary.get('lastRunAt', 'unknown')}, {last_age})",
        f"- Crawled {totals.get('crawled', 0)}, written {totals.get('written', 0)}, "
        f"failed {totals.get('failed', 0)} (aggregate failure rate {rates.get('failureRate', 0):.2%})",
        f"- Promoted {totals.get('promoted', 0)} (promotion rate {rates.get('promotionRate', 0):.2%})",
        f"- Recent {len(recent)} runs with failures: {recent_failures}",
        f"- Quality reprocess queued (cumulative): {totals.get('qualityReprocessQueued', 0)}",
        "",
        "## Model adjudication",
        "",
        f"- Adjudication calls: {totals.get('adjudicationCalls', 0)} "
        f"of budget {totals.get('adjudicationCallBudget', 0)}; tokens used {totals.get('tokensUsed', 0)}",
        f"- Zero-model rate: {rates.get('zeroModelRate', 0):.0%} "
        "(operating mode: deterministic-only until a dated canary shows a quality delta; "
        "see docs/factual-crawl-automation.md)",
        "",
        "## Public freshness",
        "",
    ]
    if freshness is None:
        lines.append("- Not evaluated in this report (no freshness JSON supplied).")
    else:
        lines.append(
            f"- Fresh {freshness.get('fresh', 0)}, stale {freshness.get('stale', 0)}, "
            f"unknown {freshness.get('unknown', 0)}; stale-or-unknown rate "
            f"{freshness.get('staleOrUnknownRate', 0):.2%}; oldest refresh overdue "
            f"{freshness.get('oldestRefreshOverdueDays', 0):.1f}d; gate passed: {freshness.get('passed')}"
        )
    lines += [
        "",
        "Landing and deployment state are not derivable from telemetry alone; "
        "check the latest `index-autonomous-refresh` run and "
        "`CLOUDFLARE_PUBLIC_DEPLOY_ENABLED` before treating this page as operating proof.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", default="index/telemetry/autonomous-summary.json")
    parser.add_argument("--runs", default="index/telemetry/autonomous-runs.ndjson")
    parser.add_argument("--freshness-json", default=None)
    parser.add_argument("--output", default=None, help="Write here instead of stdout")
    args = parser.parse_args()

    summary = json.loads(Path(args.summary).read_text())
    runs = []
    runs_path = Path(args.runs)
    if runs_path.is_file():
        runs = [json.loads(line) for line in runs_path.read_text().splitlines() if line.strip()]
    freshness = json.loads(Path(args.freshness_json).read_text()) if args.freshness_json else None
    report = render_status(summary, runs, freshness, datetime.now(timezone.utc))
    if args.output:
        Path(args.output).write_text(report)
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
