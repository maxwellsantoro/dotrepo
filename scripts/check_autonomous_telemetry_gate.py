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
    parser.add_argument("--min-promoted", type=int, default=1)
    parser.add_argument("--max-failure-rate", type=float, default=0.05)
    parser.add_argument("--max-adjudication-rate", type=float, default=0.25)
    parser.add_argument("--max-second-opinion-rate", type=float, default=0.10)
    parser.add_argument("--max-api-escalation-rate", type=float, default=0.05)
    parser.add_argument("--max-recent-failure-rate-delta", type=float, default=0.02)
    parser.add_argument("--max-recent-adjudication-rate-delta", type=float, default=0.10)
    parser.add_argument("--max-recent-api-escalation-rate-delta", type=float, default=0.02)
    parser.add_argument("--max-recent-zero-model-rate-drop", type=float, default=0.10)
    parser.add_argument("--max-fixture-eligible-recurring-failures", type=int, default=0)
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


def summarize_checks(checks: list[dict]) -> dict:
    failed_labels = [item["label"] for item in checks if not item.get("passed")]
    return {
        "total": len(checks),
        "passed": len(checks) - len(failed_labels),
        "failed": len(failed_labels),
        "failedLabels": failed_labels,
    }


def thresholds(args: argparse.Namespace) -> dict:
    return {
        "minRuns": args.min_runs,
        "minCrawled": args.min_crawled,
        "minWritten": args.min_written,
        "minPromoted": args.min_promoted,
        "maxFailureRate": args.max_failure_rate,
        "maxAdjudicationRate": args.max_adjudication_rate,
        "maxSecondOpinionRate": args.max_second_opinion_rate,
        "maxApiEscalationRate": args.max_api_escalation_rate,
        "maxRecentFailureRateDelta": args.max_recent_failure_rate_delta,
        "maxRecentAdjudicationRateDelta": args.max_recent_adjudication_rate_delta,
        "maxRecentApiEscalationRateDelta": args.max_recent_api_escalation_rate_delta,
        "maxRecentZeroModelRateDrop": args.max_recent_zero_model_rate_drop,
        "maxFixtureEligibleRecurringFailures": args.max_fixture_eligible_recurring_failures,
        "minZeroModelRate": args.min_zero_model_rate,
    }


def fixture_eligible_recurring_failures(summary: dict) -> list[dict]:
    candidates = summary.get("regressionFixtureCandidates") or []
    if not isinstance(candidates, list):
        return []
    return [
        candidate
        for candidate in candidates
        if isinstance(candidate, dict) and bool(candidate.get("fixtureEligible", False))
    ]


def retained_proof_fields_present(summary: dict) -> bool:
    worst_rates = summary.get("worstRunRates")
    recent_window_rates = summary.get("recentWindowRates")
    previous_window_rates = summary.get("previousWindowRates")
    if (
        "budgetExhaustedRuns" not in summary
        or "recentWindowRunCount" not in summary
        or "previousWindowRunCount" not in summary
        or not isinstance(worst_rates, dict)
        or not isinstance(recent_window_rates, dict)
        or not isinstance(previous_window_rates, dict)
    ):
        return False
    required_rate_keys = {
        "failureRate",
        "adjudicationRate",
        "secondOpinionRate",
        "apiEscalationRate",
    }
    required_worst_rate_keys = required_rate_keys | {"zeroModelRate"}
    return (
        required_worst_rate_keys.issubset(worst_rates)
        and required_rate_keys.issubset(recent_window_rates)
        and required_rate_keys.issubset(previous_window_rates)
    )


def evaluate(summary: dict, args: argparse.Namespace) -> dict:
    totals = summary.get("totals") or {}
    rates = summary.get("rates") or {}
    worst_rates = summary.get("worstRunRates") or {}
    recent_window_rates = summary.get("recentWindowRates") or {}
    previous_window_rates = summary.get("previousWindowRates") or {}
    tiers = summary.get("repositoriesByAdjudicationTier") or {}

    schema = str(summary.get("schema") or "")
    run_count = int(summary.get("runCount") or 0)
    crawled = int(totals.get("crawled") or 0)
    written = int(totals.get("written") or 0)
    promoted = int(totals.get("promoted") or 0)
    budget_exhausted_runs = int(summary.get("budgetExhaustedRuns") or 0)
    recent_window_run_count = int(summary.get("recentWindowRunCount") or 0)
    previous_window_run_count = int(summary.get("previousWindowRunCount") or 0)
    second_opinions = int(tiers.get("local_second_opinion") or 0)
    second_opinion_rate = second_opinions / crawled if crawled else 0.0
    api_escalations = int(tiers.get("api_escalation") or 0)
    api_escalation_rate = api_escalations / crawled if crawled else 0.0
    failure_rate = number(rates.get("failureRate"))
    adjudication_rate = number(rates.get("adjudicationRate"))
    promotion_rate = number(rates.get("promotionRate"))
    zero_model_rate = number(rates.get("zeroModelRate"))
    worst_failure_rate = number(worst_rates.get("failureRate"))
    worst_adjudication_rate = number(worst_rates.get("adjudicationRate"))
    worst_second_opinion_rate = number(worst_rates.get("secondOpinionRate"))
    worst_api_escalation_rate = number(worst_rates.get("apiEscalationRate"))
    worst_zero_model_rate = number(worst_rates.get("zeroModelRate"))
    recent_failure_rate = number(recent_window_rates.get("failureRate"))
    recent_adjudication_rate = number(recent_window_rates.get("adjudicationRate"))
    recent_second_opinion_rate = number(
        recent_window_rates.get("secondOpinionRate")
    )
    recent_api_escalation_rate = number(
        recent_window_rates.get("apiEscalationRate")
    )
    recent_zero_model_rate = number(recent_window_rates.get("zeroModelRate"))
    drift_reference_rates = previous_window_rates if previous_window_run_count else rates
    drift_reference_label = "previous-window" if previous_window_run_count else "aggregate"
    recent_failure_rate_delta = recent_failure_rate - number(
        drift_reference_rates.get("failureRate")
    )
    recent_adjudication_rate_delta = recent_adjudication_rate - number(
        drift_reference_rates.get("adjudicationRate")
    )
    recent_api_escalation_rate_delta = recent_api_escalation_rate - number(
        drift_reference_rates.get("apiEscalationRate")
    )
    recent_zero_model_rate_drop = number(
        drift_reference_rates.get("zeroModelRate")
    ) - recent_zero_model_rate
    fixture_eligible_failures = fixture_eligible_recurring_failures(summary)
    fixture_eligible_failure_count = len(fixture_eligible_failures)
    proof_fields_present = retained_proof_fields_present(summary)

    checks = [
        check(
            "retained summary schema",
            schema or "missing",
            "dotrepo/autonomous-telemetry-summary/v0.1",
            schema == "dotrepo/autonomous-telemetry-summary/v0.1",
        ),
        check(
            "retained proof fields",
            "present" if proof_fields_present else "missing",
            "present",
            proof_fields_present,
        ),
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
            "verified promotion activity",
            promoted,
            f">= {args.min_promoted}",
            promoted >= args.min_promoted,
        ),
        check(
            "failure rate",
            round(failure_rate, 6),
            f"<= {args.max_failure_rate}",
            failure_rate <= args.max_failure_rate,
        ),
        check(
            "worst-run failure rate",
            round(worst_failure_rate, 6),
            f"<= {args.max_failure_rate}",
            worst_failure_rate <= args.max_failure_rate,
        ),
        check(
            "recent-window failure rate",
            round(recent_failure_rate, 6),
            f"<= {args.max_failure_rate}",
            recent_failure_rate <= args.max_failure_rate,
        ),
        check(
            "recent-window failure drift",
            round(recent_failure_rate_delta, 6),
            f"<= {args.max_recent_failure_rate_delta}",
            recent_failure_rate_delta <= args.max_recent_failure_rate_delta,
        ),
        check(
            "model adjudication rate",
            round(adjudication_rate, 6),
            f"<= {args.max_adjudication_rate}",
            adjudication_rate <= args.max_adjudication_rate,
        ),
        check(
            "worst-run model adjudication rate",
            round(worst_adjudication_rate, 6),
            f"<= {args.max_adjudication_rate}",
            worst_adjudication_rate <= args.max_adjudication_rate,
        ),
        check(
            "recent-window model adjudication rate",
            round(recent_adjudication_rate, 6),
            f"<= {args.max_adjudication_rate}",
            recent_adjudication_rate <= args.max_adjudication_rate,
        ),
        check(
            "recent-window model adjudication drift",
            round(recent_adjudication_rate_delta, 6),
            f"<= {args.max_recent_adjudication_rate_delta}",
            recent_adjudication_rate_delta <= args.max_recent_adjudication_rate_delta,
        ),
        check(
            "second-opinion adjudication rate",
            round(second_opinion_rate, 6),
            f"<= {args.max_second_opinion_rate}",
            second_opinion_rate <= args.max_second_opinion_rate,
        ),
        check(
            "worst-run second-opinion adjudication rate",
            round(worst_second_opinion_rate, 6),
            f"<= {args.max_second_opinion_rate}",
            worst_second_opinion_rate <= args.max_second_opinion_rate,
        ),
        check(
            "recent-window second-opinion adjudication rate",
            round(recent_second_opinion_rate, 6),
            f"<= {args.max_second_opinion_rate}",
            recent_second_opinion_rate <= args.max_second_opinion_rate,
        ),
        check(
            "strong remote escalation rate",
            round(api_escalation_rate, 6),
            f"<= {args.max_api_escalation_rate}",
            api_escalation_rate <= args.max_api_escalation_rate,
        ),
        check(
            "worst-run strong remote escalation rate",
            round(worst_api_escalation_rate, 6),
            f"<= {args.max_api_escalation_rate}",
            worst_api_escalation_rate <= args.max_api_escalation_rate,
        ),
        check(
            "recent-window strong remote escalation rate",
            round(recent_api_escalation_rate, 6),
            f"<= {args.max_api_escalation_rate}",
            recent_api_escalation_rate <= args.max_api_escalation_rate,
        ),
        check(
            "recent-window strong remote escalation drift",
            round(recent_api_escalation_rate_delta, 6),
            f"<= {args.max_recent_api_escalation_rate_delta}",
            recent_api_escalation_rate_delta <= args.max_recent_api_escalation_rate_delta,
        ),
        check(
            "recent-window zero-model deterministic rate drop",
            round(recent_zero_model_rate_drop, 6),
            f"<= {args.max_recent_zero_model_rate_drop}",
            recent_zero_model_rate_drop <= args.max_recent_zero_model_rate_drop,
        ),
        check(
            "adjudication budget exhaustion",
            budget_exhausted_runs,
            "0 exhausted runs",
            budget_exhausted_runs == 0,
        ),
        check(
            "fixture-eligible recurring failures",
            fixture_eligible_failure_count,
            f"<= {args.max_fixture_eligible_recurring_failures}",
            fixture_eligible_failure_count <= args.max_fixture_eligible_recurring_failures,
        ),
        check(
            "zero-model deterministic rate",
            round(zero_model_rate, 6),
            f">= {args.min_zero_model_rate}",
            zero_model_rate >= args.min_zero_model_rate,
        ),
        check(
            "worst-run zero-model deterministic rate",
            round(worst_zero_model_rate, 6),
            f">= {args.min_zero_model_rate}",
            not proof_fields_present or worst_zero_model_rate >= args.min_zero_model_rate,
        ),
        check(
            "recent-window zero-model deterministic rate",
            round(recent_zero_model_rate, 6),
            f">= {args.min_zero_model_rate}",
            recent_zero_model_rate >= args.min_zero_model_rate,
        ),
    ]

    passed = all(item["passed"] for item in checks)
    check_summary = summarize_checks(checks)
    return {
        "schema": "dotrepo/autonomous-telemetry-gate/v0.1",
        "summaryGeneratedAt": summary.get("generatedAt"),
        "passed": passed,
        "thresholds": thresholds(args),
        "checkSummary": check_summary,
        "checks": checks,
        "inputs": {
            "schema": schema,
            "runCount": run_count,
            "budgetExhaustedRuns": budget_exhausted_runs,
            "recentWindowRunCount": recent_window_run_count,
            "previousWindowRunCount": previous_window_run_count,
            "secondOpinionRate": second_opinion_rate,
            "apiEscalationRate": api_escalation_rate,
            "driftReference": drift_reference_label,
            "recentFailureRateDelta": recent_failure_rate_delta,
            "recentAdjudicationRateDelta": recent_adjudication_rate_delta,
            "recentApiEscalationRateDelta": recent_api_escalation_rate_delta,
            "recentZeroModelRateDrop": recent_zero_model_rate_drop,
            "promotionRate": promotion_rate,
            "fixtureEligibleRecurringFailures": fixture_eligible_failures,
            "totals": totals,
            "rates": rates,
            "worstRunRates": worst_rates,
            "recentWindowRates": recent_window_rates,
            "previousWindowRates": previous_window_rates,
            "repositoriesByAdjudicationTier": tiers,
        },
    }


def render_markdown(report: dict) -> str:
    inputs = report.get("inputs") or {}
    limits = report.get("thresholds") or {}
    rates = inputs.get("rates") or {}
    worst_rates = inputs.get("worstRunRates") or {}
    recent_window_rates = inputs.get("recentWindowRates") or {}
    previous_window_rates = inputs.get("previousWindowRates") or {}
    fixture_backlog = inputs.get("fixtureEligibleRecurringFailures") or []
    lines = [
        "# Autonomous Telemetry Gate",
        "",
        f"- result: {'pass' if report.get('passed') else 'not yet'}",
        f"- summary generated at: {report.get('summaryGeneratedAt') or 'unknown'}",
        f"- retained runs: {inputs.get('runCount', 0)}",
        f"- recent window runs: {inputs.get('recentWindowRunCount', 0)}",
        f"- previous window runs: {inputs.get('previousWindowRunCount', 0)}",
        f"- aggregate promotion rate: {number(rates.get('promotionRate')):.2%}",
        f"- aggregate adjudication rate: {number(rates.get('adjudicationRate')):.2%}",
        f"- previous-window adjudication rate: {number(previous_window_rates.get('adjudicationRate')):.2%}",
        f"- recent-window adjudication rate: {number(recent_window_rates.get('adjudicationRate')):.2%}",
        f"- recent-window zero-model rate: {number(recent_window_rates.get('zeroModelRate')):.2%}",
        f"- recent-window zero-model drop: {number(inputs.get('recentZeroModelRateDrop')):.2%}",
        f"- drift reference: {inputs.get('driftReference') or 'unknown'}",
        f"- worst-run failure rate: {number(worst_rates.get('failureRate')):.2%}",
        f"- worst-run adjudication rate: {number(worst_rates.get('adjudicationRate')):.2%}",
        f"- worst-run second-opinion rate: {number(worst_rates.get('secondOpinionRate')):.2%}",
        f"- worst-run zero-model rate: {number(worst_rates.get('zeroModelRate')):.2%}",
        f"- fixture-eligible recurring failures: {len(fixture_backlog)}",
        f"- thresholds: min runs {limits.get('minRuns', 0)}, min crawled {limits.get('minCrawled', 0)}, max adjudication {number(limits.get('maxAdjudicationRate')):.2%}, max API escalation {number(limits.get('maxApiEscalationRate')):.2%}",
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
