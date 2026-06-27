from __future__ import annotations

import importlib.util
from argparse import Namespace
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "check_autonomous_telemetry_gate.py"
SPEC = importlib.util.spec_from_file_location("check_autonomous_telemetry_gate", SCRIPT)
telemetry_gate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(telemetry_gate)


def args(**overrides: object) -> Namespace:
    defaults = {
        "min_runs": 3,
        "min_crawled": 10,
        "min_written": 1,
        "min_promoted": 1,
        "max_failure_rate": 0.05,
        "max_adjudication_rate": 0.25,
        "max_second_opinion_rate": 0.10,
        "max_api_escalation_rate": 0.05,
        "max_fixture_eligible_recurring_failures": 0,
        "min_zero_model_rate": 0.75,
    }
    defaults.update(overrides)
    return Namespace(**defaults)


def test_evaluate_passes_when_retained_telemetry_meets_thresholds() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 4,
        "budgetExhaustedRuns": 0,
        "totals": {"crawled": 20, "written": 18, "failed": 0, "promoted": 8},
        "rates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "promotionRate": 0.4,
            "zeroModelRate": 0.8,
        },
        "worstRunRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
        },
        "repositoriesByAdjudicationTier": {"local_primary": 4, "api_escalation": 1},
        "regressionFixtureCandidates": [
            {
                "failureClass": "provider",
                "ecosystem": "unknown",
                "fixtureEligible": False,
                "fingerprint": "model provider timeout",
                "count": 2,
                "suggestedFixture": "model-provider-timeout",
            }
        ],
    }

    report = telemetry_gate.evaluate(summary, args())

    assert report["passed"]
    assert all(item["passed"] for item in report["checks"])
    assert report["checkSummary"] == {
        "total": 17,
        "passed": 17,
        "failed": 0,
        "failedLabels": [],
    }
    assert report["thresholds"] == {
        "minRuns": 3,
        "minCrawled": 10,
        "minWritten": 1,
        "minPromoted": 1,
        "maxFailureRate": 0.05,
        "maxAdjudicationRate": 0.25,
        "maxSecondOpinionRate": 0.10,
        "maxApiEscalationRate": 0.05,
        "maxFixtureEligibleRecurringFailures": 0,
        "minZeroModelRate": 0.75,
    }
    assert report["inputs"]["secondOpinionRate"] == 0.0
    assert report["inputs"]["apiEscalationRate"] == 0.05
    assert report["inputs"]["promotionRate"] == 0.4
    assert report["inputs"]["fixtureEligibleRecurringFailures"] == []


def test_evaluate_reports_not_yet_for_insufficient_or_expensive_runs() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 1,
        "budgetExhaustedRuns": 2,
        "totals": {"crawled": 4, "written": 0, "failed": 1, "promoted": 0},
        "rates": {
            "failureRate": 0.25,
            "adjudicationRate": 0.5,
            "promotionRate": 0.0,
            "zeroModelRate": 0.5,
        },
        "worstRunRates": {
            "failureRate": 0.25,
            "adjudicationRate": 0.5,
            "secondOpinionRate": 0.25,
            "apiEscalationRate": 0.25,
        },
        "repositoriesByAdjudicationTier": {
            "local_second_opinion": 1,
            "api_escalation": 1,
        },
        "regressionFixtureCandidates": [
            {
                "failureClass": "parser",
                "ecosystem": "rust",
                "fixtureEligible": True,
                "fingerprint": "Cargo.toml parse error",
                "count": 2,
                "suggestedFixture": "cargo-toml-parse-error",
            }
        ],
    }

    report = telemetry_gate.evaluate(summary, args())
    failed_labels = {
        item["label"] for item in report["checks"] if not item["passed"]
    }

    assert not report["passed"]
    assert report["checkSummary"]["failedLabels"] == [
        item["label"] for item in report["checks"] if not item["passed"]
    ]
    assert "retained repeated runs" in failed_labels
    assert "processed repository volume" in failed_labels
    assert "direct writeback activity" in failed_labels
    assert "verified promotion activity" in failed_labels
    assert "failure rate" in failed_labels
    assert "worst-run failure rate" in failed_labels
    assert "model adjudication rate" in failed_labels
    assert "worst-run model adjudication rate" in failed_labels
    assert "second-opinion adjudication rate" in failed_labels
    assert "worst-run second-opinion adjudication rate" in failed_labels
    assert "strong remote escalation rate" in failed_labels
    assert "worst-run strong remote escalation rate" in failed_labels
    assert "adjudication budget exhaustion" in failed_labels
    assert "fixture-eligible recurring failures" in failed_labels
    assert "zero-model deterministic rate" in failed_labels


def test_evaluate_allows_environmental_recurring_failures_for_fixture_gate() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 4,
        "budgetExhaustedRuns": 0,
        "totals": {"crawled": 20, "written": 18, "failed": 0, "promoted": 8},
        "rates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "promotionRate": 0.4,
            "zeroModelRate": 0.8,
        },
        "worstRunRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
        },
        "repositoriesByAdjudicationTier": {"local_primary": 4, "api_escalation": 1},
        "regressionFixtureCandidates": [
            {
                "failureClass": "infrastructure",
                "ecosystem": "unknown",
                "fixtureEligible": False,
                "fingerprint": "network timeout",
                "count": 2,
                "suggestedFixture": "network-timeout",
            }
        ],
    }

    report = telemetry_gate.evaluate(summary, args())
    fixture_check = next(
        item
        for item in report["checks"]
        if item["label"] == "fixture-eligible recurring failures"
    )

    assert report["passed"]
    assert fixture_check["passed"]
    assert report["inputs"]["fixtureEligibleRecurringFailures"] == []


def test_evaluate_rejects_worst_run_regression_when_aggregate_rates_pass() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 4,
        "budgetExhaustedRuns": 0,
        "totals": {"crawled": 40, "written": 38, "failed": 1, "promoted": 8},
        "rates": {
            "failureRate": 0.025,
            "adjudicationRate": 0.2,
            "promotionRate": 0.2,
            "zeroModelRate": 0.8,
        },
        "worstRunRates": {
            "failureRate": 0.25,
            "adjudicationRate": 0.5,
            "secondOpinionRate": 0.25,
            "apiEscalationRate": 0.25,
        },
        "repositoriesByAdjudicationTier": {"local_primary": 7, "api_escalation": 1},
        "regressionFixtureCandidates": [],
    }

    report = telemetry_gate.evaluate(summary, args())
    failed_labels = {
        item["label"] for item in report["checks"] if not item["passed"]
    }

    assert not report["passed"]
    assert failed_labels == {
        "worst-run failure rate",
        "worst-run model adjudication rate",
        "worst-run second-opinion adjudication rate",
        "worst-run strong remote escalation rate",
    }


def test_evaluate_rejects_missing_summary_schema() -> None:
    summary = {
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 4,
        "budgetExhaustedRuns": 0,
        "totals": {"crawled": 20, "written": 18, "failed": 0, "promoted": 8},
        "rates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "promotionRate": 0.4,
            "zeroModelRate": 0.8,
        },
        "worstRunRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
        },
        "repositoriesByAdjudicationTier": {"local_primary": 4, "api_escalation": 1},
    }

    report = telemetry_gate.evaluate(summary, args())
    failed_labels = {
        item["label"] for item in report["checks"] if not item["passed"]
    }

    assert not report["passed"]
    assert failed_labels == {"retained summary schema"}


def test_evaluate_rejects_missing_retained_proof_fields() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 4,
        "totals": {"crawled": 20, "written": 18, "failed": 0, "promoted": 8},
        "rates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "promotionRate": 0.4,
            "zeroModelRate": 0.8,
        },
        "repositoriesByAdjudicationTier": {"local_primary": 4, "api_escalation": 1},
        "regressionFixtureCandidates": [],
    }

    report = telemetry_gate.evaluate(summary, args())
    failed_labels = {
        item["label"] for item in report["checks"] if not item["passed"]
    }

    assert not report["passed"]
    assert failed_labels == {"retained proof fields"}


def test_render_markdown_includes_check_table() -> None:
    report = {
        "passed": False,
        "summaryGeneratedAt": "2026-03-18T12:00:00Z",
        "thresholds": {
            "minRuns": 3,
            "minCrawled": 10,
            "maxAdjudicationRate": 0.25,
            "maxApiEscalationRate": 0.05,
        },
        "inputs": {
            "runCount": 4,
            "rates": {
                "promotionRate": 0.4,
                "adjudicationRate": 0.2,
            },
            "worstRunRates": {
                "failureRate": 0.05,
                "adjudicationRate": 0.25,
                "secondOpinionRate": 0.1,
            },
            "fixtureEligibleRecurringFailures": [{"fingerprint": "Cargo.toml parse error"}],
        },
        "checks": [
            {
                "label": "retained repeated runs",
                "actual": 1,
                "expected": ">= 3",
                "passed": False,
            }
        ],
    }

    rendered = telemetry_gate.render_markdown(report)

    assert "# Autonomous Telemetry Gate" in rendered
    assert "- retained runs: 4" in rendered
    assert "- aggregate promotion rate: 40.00%" in rendered
    assert "- worst-run adjudication rate: 25.00%" in rendered
    assert "- worst-run second-opinion rate: 10.00%" in rendered
    assert "- fixture-eligible recurring failures: 1" in rendered
    assert "- thresholds: min runs 3, min crawled 10, max adjudication 25.00%, max API escalation 5.00%" in rendered
    assert "| retained repeated runs | 1 | >= 3 | fail |" in rendered
