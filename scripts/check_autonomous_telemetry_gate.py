#!/usr/bin/env -S uv run python
"""Evaluate retained autonomous-run telemetry against Milestone 1 proof gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--summary",
        default="index/telemetry/autonomous-summary.json",
        help="Retained autonomous telemetry summary JSON",
    )
    parser.add_argument("--output-json", help="Optional machine-readable report path")
    parser.add_argument("--output-md", help="Optional markdown report path")
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Emit the report but exit 0 even when proof gates are not yet satisfied",
    )
    parser.add_argument("--min-runs", type=int, default=3)
    parser.add_argument("--min-crawled", type=int, default=10)
    parser.add_argument("--min-written", type=int, default=1)
    parser.add_argument("--max-failure-rate", type=float, default=0.05)
    parser.add_argument("--max-adjudication-rate", type=float, default=0.25)
    parser.add_argument("--max-api-escalation-rate", type=float, default=0.05)
    parser.add_argument("--min-zero-model-rate", type=float, default=0.75)
    return parser.parse_args()


def load_summary(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"missing autonomous telemetry summary: {path}")
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise SystemExit(f"autonomous telemetry summary is malformed: {path}")
    return data


def number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def check(label: str, actual: object, expected: str, passed: bool) -> dict:
    return {
        "label": label,
        "actual": actual,
        "expected": expected,
        "passed": bool(passed),
    }


def evaluate(summary: dict, args: argparse.Namespace) -> dict:
    totals = summary.get("totals") or {}
    rates = summary.get("rates") or {}
    tiers = summary.get("repositoriesByAdjudicationTier") or {}

    run_count = int(summary.get("runCount") or 0)
    crawled = int(totals.get("crawled") or 0)
    written = int(totals.get("written") or 0)
    api_escalations = int(tiers.get("api_escalation") or 0)
    api_escalation_rate = api_escalations / crawled if crawled else 0.0
    failure_rate = number(rates.get("failureRate"))
    adjudication_rate = number(rates.get("adjudicationRate"))
    zero_model_rate = number(rates.get("zeroModelRate"))

    checks = [
        check(
            "retained repeated runs",
            run_count,
            f">= {args.min_runs}",
            run_count >= args.min_runs,
        ),
        check(
            "processed repository volume",
            crawled,
            f">= {args.min_crawled}",
            crawled >= args.min_crawled,
        ),
        check(
            "direct writeback activity",
            written,
            f">= {args.min_written}",
            written >= args.min_written,
        ),
        check(
            "failure rate",
            round(failure_rate, 6),
            f"<= {args.max_failure_rate}",
            failure_rate <= args.max_failure_rate,
        ),
        check(
            "model adjudication rate",
            round(adjudication_rate, 6),
            f"<= {args.max_adjudication_rate}",
            adjudication_rate <= args.max_adjudication_rate,
        ),
        check(
            "strong remote escalation rate",
            round(api_escalation_rate, 6),
            f"<= {args.max_api_escalation_rate}",
            api_escalation_rate <= args.max_api_escalation_rate,
        ),
        check(
            "zero-model deterministic rate",
            round(zero_model_rate, 6),
            f">= {args.min_zero_model_rate}",
            zero_model_rate >= args.min_zero_model_rate,
        ),
    ]

    passed = all(item["passed"] for item in checks)
    return {
        "schema": "dotrepo/autonomous-telemetry-gate/v0.1",
        "summaryGeneratedAt": summary.get("generatedAt"),
        "passed": passed,
        "checks": checks,
        "inputs": {
            "runCount": run_count,
            "totals": totals,
            "rates": rates,
            "repositoriesByAdjudicationTier": tiers,
        },
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Autonomous Telemetry Gate",
        "",
        f"- result: {'pass' if report.get('passed') else 'not yet'}",
        f"- summary generated at: {report.get('summaryGeneratedAt') or 'unknown'}",
        "",
        "| Check | Actual | Expected | Result |",
        "| --- | ---: | ---: | --- |",
    ]
    for item in report.get("checks") or []:
        lines.append(
            f"| {item['label']} | {item['actual']} | {item['expected']} | {'pass' if item['passed'] else 'fail'} |"
        )
    return "\n".join(lines) + "\n"


def write_report(report: dict, output_json: str | None, output_md: str | None) -> None:
    if output_json:
        path = Path(output_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if output_md:
        path = Path(output_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(report))


def main() -> int:
    args = parse_args()
    summary = load_summary(Path(args.summary))
    report = evaluate(summary, args)
    write_report(report, args.output_json, args.output_md)
    if not args.output_json and not args.output_md:
        print(render_markdown(report), end="")
    return 0 if report["passed"] or args.warn_only else 1


if __name__ == "__main__":
    raise SystemExit(main())
