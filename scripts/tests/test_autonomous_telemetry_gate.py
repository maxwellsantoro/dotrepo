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
        "max_recent_failure_rate_delta": 0.02,
        "max_recent_adjudication_rate_delta": 0.10,
        "max_recent_second_opinion_rate_delta": 0.05,
        "max_recent_api_escalation_rate_delta": 0.02,
        "max_recent_zero_model_rate_drop": 0.10,
        "max_fixture_eligible_recurring_failures": 0,
        "min_zero_model_rate": 0.75,
        "max_adjudication_budget_use_rate": 1.0,
        "max_tokens_per_crawled": 5000.0,
        "max_recent_adjudication_budget_use_rate_delta": 0.25,
        "max_recent_tokens_per_crawled_delta": 1000.0,
    }
    defaults.update(overrides)
    return Namespace(**defaults)


def test_evaluate_passes_when_retained_telemetry_meets_thresholds() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 4,
        "budgetExhaustedRuns": 0,
        "totals": {
            "adjudicationCallBudget": 10,
            "adjudicationCalls": 4,
            "crawled": 20,
            "written": 18,
            "failed": 0,
            "promoted": 8,
            "tokensUsed": 1000,
        },
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
            "zeroModelRate": 0.8,
        },
        "recentWindowRunCount": 3,
        "recentWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
            "zeroModelRate": 0.8,
        },
        "previousWindowRunCount": 1,
        "previousWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
            "zeroModelRate": 0.8,
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
        "total": 34,
        "passed": 34,
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
        "maxRecentFailureRateDelta": 0.02,
        "maxRecentAdjudicationRateDelta": 0.10,
        "maxRecentSecondOpinionRateDelta": 0.05,
        "maxRecentApiEscalationRateDelta": 0.02,
        "maxRecentZeroModelRateDrop": 0.10,
        "maxFixtureEligibleRecurringFailures": 0,
        "minZeroModelRate": 0.75,
        "maxAdjudicationBudgetUseRate": 1.0,
        "maxTokensPerCrawled": 5000.0,
        "maxRecentAdjudicationBudgetUseRateDelta": 0.25,
        "maxRecentTokensPerCrawledDelta": 1000.0,
    }
    assert report["inputs"]["secondOpinionRate"] == 0.0
    assert report["inputs"]["apiEscalationRate"] == 0.05
    assert report["inputs"]["driftReference"] == "previous-window"
    assert report["inputs"]["promotionRate"] == 0.4
    assert report["inputs"]["adjudicationBudgetUseRate"] == 0.4
    assert report["inputs"]["tokensPerCrawled"] == 50.0
    assert report["inputs"]["fixtureEligibleRecurringFailures"] == []


def test_evaluate_reports_not_yet_for_insufficient_or_expensive_runs() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 1,
        "budgetExhaustedRuns": 2,
        "totals": {
            "adjudicationCallBudget": 2,
            "adjudicationCalls": 3,
            "crawled": 4,
            "written": 0,
            "failed": 1,
            "promoted": 0,
            "tokensUsed": 40000,
        },
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
            "zeroModelRate": 0.5,
        },
        "recentWindowRunCount": 1,
        "recentWindowRates": {
            "failureRate": 0.25,
            "adjudicationRate": 0.5,
            "secondOpinionRate": 0.25,
            "apiEscalationRate": 0.25,
            "zeroModelRate": 0.5,
        },
        "previousWindowRunCount": 0,
        "previousWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.0,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.0,
            "zeroModelRate": 0.0,
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
    failed_labels = {item["label"] for item in report["checks"] if not item["passed"]}

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
    assert "recent-window failure rate" in failed_labels
    assert "model adjudication rate" in failed_labels
    assert "worst-run model adjudication rate" in failed_labels
    assert "recent-window model adjudication rate" in failed_labels
    assert "second-opinion adjudication rate" in failed_labels
    assert "worst-run second-opinion adjudication rate" in failed_labels
    assert "recent-window second-opinion adjudication rate" in failed_labels
    assert "strong remote escalation rate" in failed_labels
    assert "worst-run strong remote escalation rate" in failed_labels
    assert "recent-window strong remote escalation rate" in failed_labels
    assert "adjudication budget exhaustion" in failed_labels
    assert "adjudication call budget usage" in failed_labels
    assert "tokens per crawled repository" in failed_labels
    assert "fixture-eligible recurring failures" in failed_labels
    assert "zero-model deterministic rate" in failed_labels
    assert "worst-run zero-model deterministic rate" in failed_labels
    assert "recent-window zero-model deterministic rate" in failed_labels


def test_evaluate_allows_environmental_recurring_failures_for_fixture_gate() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 4,
        "budgetExhaustedRuns": 0,
        "totals": {
            "adjudicationCallBudget": 10,
            "adjudicationCalls": 4,
            "crawled": 20,
            "written": 18,
            "failed": 0,
            "promoted": 8,
            "tokensUsed": 1000,
        },
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
            "zeroModelRate": 0.8,
        },
        "recentWindowRunCount": 3,
        "recentWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
            "zeroModelRate": 0.8,
        },
        "previousWindowRunCount": 1,
        "previousWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
            "zeroModelRate": 0.8,
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
        item for item in report["checks"] if item["label"] == "fixture-eligible recurring failures"
    )

    assert report["passed"]
    assert fixture_check["passed"]
    assert report["inputs"]["fixtureEligibleRecurringFailures"] == []


def test_evaluate_rejects_recent_cost_spike_hidden_by_aggregate_rates() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 4,
        "budgetExhaustedRuns": 0,
        "totals": {
            "adjudicationCallBudget": 10,
            "adjudicationCalls": 4,
            "crawled": 20,
            "written": 18,
            "failed": 0,
            "promoted": 8,
            "tokensUsed": 1000,
        },
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
            "zeroModelRate": 0.8,
        },
        "recentWindowRunCount": 3,
        "recentWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
            "zeroModelRate": 0.8,
        },
        "previousWindowRunCount": 1,
        "previousWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
            "zeroModelRate": 0.8,
        },
        "recentWindowCosts": {
            "adjudicationCallBudget": 6,
            "adjudicationCalls": 6,
            "adjudicationBudgetUseRate": 1.0,
            "crawled": 12,
            "tokensUsed": 72000,
            "tokensPerCrawled": 6000.0,
        },
        "previousWindowCosts": {
            "adjudicationCallBudget": 4,
            "adjudicationCalls": 2,
            "adjudicationBudgetUseRate": 0.5,
            "crawled": 8,
            "tokensUsed": 200,
            "tokensPerCrawled": 25.0,
        },
        "repositoriesByAdjudicationTier": {"local_primary": 4, "api_escalation": 1},
        "regressionFixtureCandidates": [],
    }

    report = telemetry_gate.evaluate(summary, args())
    failed_labels = {item["label"] for item in report["checks"] if not item["passed"]}

    assert not report["passed"]
    assert failed_labels == {
        "recent-window adjudication budget usage drift",
        "recent-window token intensity drift",
        "recent-window tokens per crawled repository",
    }


def test_evaluate_rejects_worst_run_regression_when_aggregate_rates_pass() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 4,
        "budgetExhaustedRuns": 0,
        "totals": {
            "adjudicationCallBudget": 20,
            "adjudicationCalls": 8,
            "crawled": 40,
            "written": 38,
            "failed": 1,
            "promoted": 8,
            "tokensUsed": 2000,
        },
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
            "zeroModelRate": 0.8,
        },
        "recentWindowRunCount": 3,
        "recentWindowRates": {
            "failureRate": 0.025,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.025,
            "zeroModelRate": 0.8,
        },
        "previousWindowRunCount": 1,
        "previousWindowRates": {
            "failureRate": 0.025,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.025,
            "zeroModelRate": 0.8,
        },
        "repositoriesByAdjudicationTier": {"local_primary": 7, "api_escalation": 1},
        "regressionFixtureCandidates": [],
    }

    report = telemetry_gate.evaluate(summary, args())
    failed_labels = {item["label"] for item in report["checks"] if not item["passed"]}

    assert not report["passed"]
    assert failed_labels == {
        "worst-run failure rate",
        "worst-run model adjudication rate",
        "worst-run second-opinion adjudication rate",
        "worst-run strong remote escalation rate",
    }


def test_evaluate_rejects_worst_run_zero_model_regression() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 4,
        "budgetExhaustedRuns": 0,
        "totals": {
            "adjudicationCallBudget": 20,
            "adjudicationCalls": 8,
            "crawled": 40,
            "written": 38,
            "failed": 0,
            "promoted": 8,
            "tokensUsed": 2000,
        },
        "rates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "promotionRate": 0.2,
            "zeroModelRate": 0.8,
        },
        "worstRunRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.25,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.0,
            "zeroModelRate": 0.7,
        },
        "recentWindowRunCount": 3,
        "recentWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.0,
            "zeroModelRate": 0.8,
        },
        "previousWindowRunCount": 1,
        "previousWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.0,
            "zeroModelRate": 0.8,
        },
        "repositoriesByAdjudicationTier": {"local_primary": 8},
        "regressionFixtureCandidates": [],
    }

    report = telemetry_gate.evaluate(summary, args())
    failed_labels = {item["label"] for item in report["checks"] if not item["passed"]}

    assert not report["passed"]
    assert failed_labels == {"worst-run zero-model deterministic rate"}


def test_evaluate_rejects_recent_window_drift_when_ceiling_rates_pass() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 6,
        "budgetExhaustedRuns": 0,
        "totals": {
            "adjudicationCallBudget": 30,
            "adjudicationCalls": 6,
            "crawled": 60,
            "written": 58,
            "failed": 0,
            "promoted": 10,
            "tokensUsed": 3000,
        },
        "rates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.1,
            "promotionRate": 0.166667,
            "zeroModelRate": 0.9,
        },
        "worstRunRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.25,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.04,
            "zeroModelRate": 0.8,
        },
        "recentWindowRunCount": 3,
        "recentWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.25,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.04,
            "zeroModelRate": 0.8,
        },
        "previousWindowRunCount": 0,
        "previousWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.0,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.0,
            "zeroModelRate": 0.0,
        },
        "repositoriesByAdjudicationTier": {"local_primary": 5, "api_escalation": 1},
        "regressionFixtureCandidates": [],
    }

    report = telemetry_gate.evaluate(summary, args())
    failed_labels = {item["label"] for item in report["checks"] if not item["passed"]}

    assert not report["passed"]
    assert failed_labels == {
        "recent-window model adjudication drift",
        "recent-window strong remote escalation drift",
    }


def test_evaluate_rejects_previous_window_drift_when_aggregate_rates_pass() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 6,
        "budgetExhaustedRuns": 0,
        "totals": {
            "adjudicationCallBudget": 30,
            "adjudicationCalls": 6,
            "crawled": 60,
            "written": 58,
            "failed": 0,
            "promoted": 10,
            "tokensUsed": 3000,
        },
        "rates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "promotionRate": 0.166667,
            "zeroModelRate": 0.8,
        },
        "worstRunRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.25,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.04,
            "zeroModelRate": 0.75,
        },
        "recentWindowRunCount": 3,
        "recentWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.25,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.04,
            "zeroModelRate": 0.8,
        },
        "previousWindowRunCount": 3,
        "previousWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.1,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.0,
            "zeroModelRate": 0.85,
        },
        "repositoriesByAdjudicationTier": {"local_primary": 12, "api_escalation": 2},
        "regressionFixtureCandidates": [],
    }

    report = telemetry_gate.evaluate(summary, args())
    failed_labels = {item["label"] for item in report["checks"] if not item["passed"]}

    assert report["inputs"]["driftReference"] == "previous-window"
    assert not report["passed"]
    assert failed_labels == {
        "recent-window model adjudication drift",
        "recent-window strong remote escalation drift",
    }


def test_evaluate_rejects_recent_second_opinion_drift_when_ceiling_rate_passes() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 6,
        "budgetExhaustedRuns": 0,
        "totals": {
            "adjudicationCallBudget": 30,
            "adjudicationCalls": 6,
            "crawled": 60,
            "written": 58,
            "failed": 0,
            "promoted": 10,
            "tokensUsed": 3000,
        },
        "rates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "promotionRate": 0.166667,
            "zeroModelRate": 0.8,
        },
        "worstRunRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.25,
            "secondOpinionRate": 0.08,
            "apiEscalationRate": 0.0,
            "zeroModelRate": 0.75,
        },
        "recentWindowRunCount": 3,
        "recentWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.25,
            "secondOpinionRate": 0.08,
            "apiEscalationRate": 0.0,
            "zeroModelRate": 0.8,
        },
        "previousWindowRunCount": 3,
        "previousWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.0,
            "zeroModelRate": 0.8,
        },
        "repositoriesByAdjudicationTier": {"local_primary": 10, "local_second_opinion": 2},
        "recentWindowRepositoriesByAdjudicationTier": {
            "local_primary": 4,
            "local_second_opinion": 2,
        },
        "previousWindowRepositoriesByAdjudicationTier": {"local_primary": 6},
        "regressionFixtureCandidates": [],
    }

    report = telemetry_gate.evaluate(summary, args())
    failed_labels = {item["label"] for item in report["checks"] if not item["passed"]}

    assert not report["passed"]
    assert failed_labels == {"recent-window second-opinion adjudication drift"}
    assert report["inputs"]["recentSecondOpinionRateDelta"] == 0.08
    assert report["inputs"]["recentWindowRepositoriesByAdjudicationTier"] == {
        "local_primary": 4,
        "local_second_opinion": 2,
    }


def test_evaluate_rejects_recent_zero_model_drop_when_absolute_rates_pass() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 6,
        "budgetExhaustedRuns": 0,
        "totals": {
            "adjudicationCallBudget": 30,
            "adjudicationCalls": 6,
            "crawled": 60,
            "written": 58,
            "failed": 0,
            "promoted": 10,
            "tokensUsed": 3000,
        },
        "rates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.1,
            "promotionRate": 0.166667,
            "zeroModelRate": 0.9,
        },
        "worstRunRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.25,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.0,
            "zeroModelRate": 0.75,
        },
        "recentWindowRunCount": 3,
        "recentWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.25,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.0,
            "zeroModelRate": 0.75,
        },
        "previousWindowRunCount": 3,
        "previousWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.0,
            "zeroModelRate": 0.95,
        },
        "repositoriesByAdjudicationTier": {"local_primary": 6},
        "regressionFixtureCandidates": [],
    }

    report = telemetry_gate.evaluate(summary, args())
    failed_labels = {item["label"] for item in report["checks"] if not item["passed"]}

    assert not report["passed"]
    assert failed_labels == {"recent-window zero-model deterministic rate drop"}
    assert report["inputs"]["recentZeroModelRateDrop"] == 0.19999999999999996


def test_evaluate_rejects_missing_summary_schema() -> None:
    summary = {
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 4,
        "budgetExhaustedRuns": 0,
        "totals": {
            "adjudicationCallBudget": 10,
            "adjudicationCalls": 4,
            "crawled": 20,
            "written": 18,
            "failed": 0,
            "promoted": 8,
            "tokensUsed": 1000,
        },
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
            "zeroModelRate": 0.8,
        },
        "recentWindowRunCount": 3,
        "recentWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
            "zeroModelRate": 0.8,
        },
        "previousWindowRunCount": 1,
        "previousWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
            "zeroModelRate": 0.8,
        },
        "repositoriesByAdjudicationTier": {"local_primary": 4, "api_escalation": 1},
        "regressionFixtureCandidates": [],
    }

    report = telemetry_gate.evaluate(summary, args())
    failed_labels = {item["label"] for item in report["checks"] if not item["passed"]}

    assert not report["passed"]
    assert failed_labels == {"retained summary schema"}


def test_evaluate_rejects_missing_retained_proof_fields() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 4,
        "totals": {
            "adjudicationCallBudget": 10,
            "adjudicationCalls": 4,
            "crawled": 20,
            "written": 18,
            "failed": 0,
            "promoted": 8,
            "tokensUsed": 1000,
        },
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
        "recentWindowRunCount": 3,
        "recentWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
            "zeroModelRate": 0.8,
        },
        "previousWindowRunCount": 3,
        "previousWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
            "zeroModelRate": 0.8,
        },
        "repositoriesByAdjudicationTier": {"local_primary": 4, "api_escalation": 1},
        "regressionFixtureCandidates": [],
    }

    report = telemetry_gate.evaluate(summary, args())
    failed_labels = {item["label"] for item in report["checks"] if not item["passed"]}

    assert not report["passed"]
    assert failed_labels == {"retained proof fields"}


def test_evaluate_rejects_missing_window_zero_model_proof_fields() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 4,
        "budgetExhaustedRuns": 0,
        "totals": {
            "adjudicationCallBudget": 10,
            "adjudicationCalls": 4,
            "crawled": 20,
            "written": 18,
            "failed": 0,
            "promoted": 8,
            "tokensUsed": 1000,
        },
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
            "zeroModelRate": 0.8,
        },
        "recentWindowRunCount": 3,
        "recentWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
        },
        "previousWindowRunCount": 3,
        "previousWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
        },
        "repositoriesByAdjudicationTier": {"local_primary": 4, "api_escalation": 1},
        "regressionFixtureCandidates": [],
    }

    report = telemetry_gate.evaluate(
        summary,
        args(min_zero_model_rate=0.0, max_recent_zero_model_rate_drop=1.0),
    )
    failed_labels = {item["label"] for item in report["checks"] if not item["passed"]}

    assert not report["passed"]
    assert failed_labels == {"retained proof fields"}


def test_evaluate_rejects_missing_or_invalid_rate_proof_fields() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 4,
        "budgetExhaustedRuns": 0,
        "totals": {
            "adjudicationCallBudget": 10,
            "adjudicationCalls": 4,
            "crawled": 20,
            "written": 18,
            "failed": 0,
            "promoted": 8,
            "tokensUsed": 1000,
        },
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
            "zeroModelRate": 0.8,
        },
        "recentWindowRunCount": 3,
        "recentWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
            "zeroModelRate": 0.8,
        },
        "previousWindowRunCount": 3,
        "previousWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
            "zeroModelRate": 0.8,
        },
        "repositoriesByAdjudicationTier": {"local_primary": 4, "api_escalation": 1},
        "regressionFixtureCandidates": [],
    }

    cases = []
    missing_aggregate = {
        **summary,
        "rates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "zeroModelRate": 0.8,
        },
    }
    cases.append(missing_aggregate)
    invalid_aggregate = {
        **summary,
        "rates": {
            **summary["rates"],
            "failureRate": -0.1,
        },
    }
    cases.append(invalid_aggregate)
    invalid_recent = {
        **summary,
        "recentWindowRates": {
            **summary["recentWindowRates"],
            "zeroModelRate": 1.2,
        },
    }
    cases.append(invalid_recent)
    invalid_worst = {
        **summary,
        "worstRunRates": {
            **summary["worstRunRates"],
            "zeroModelRate": True,
        },
    }
    cases.append(invalid_worst)

    for candidate_summary in cases:
        report = telemetry_gate.evaluate(
            candidate_summary,
            args(min_zero_model_rate=0.0, max_recent_zero_model_rate_drop=1.0),
        )
        failed_labels = {item["label"] for item in report["checks"] if not item["passed"]}

        assert not report["passed"]
        assert failed_labels == {"retained proof fields"}


def test_evaluate_rejects_missing_or_invalid_count_proof_fields() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 4,
        "budgetExhaustedRuns": 0,
        "totals": {
            "adjudicationCallBudget": 10,
            "adjudicationCalls": 4,
            "crawled": 20,
            "written": 18,
            "failed": 0,
            "promoted": 8,
            "tokensUsed": 1000,
        },
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
            "zeroModelRate": 0.8,
        },
        "recentWindowRunCount": 3,
        "recentWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
            "zeroModelRate": 0.8,
        },
        "previousWindowRunCount": 3,
        "previousWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
            "zeroModelRate": 0.8,
        },
        "repositoriesByAdjudicationTier": {"local_primary": 4, "api_escalation": 1},
        "regressionFixtureCandidates": [],
    }

    cases = [
        {**summary, "runCount": "4"},
        {**summary, "budgetExhaustedRuns": True},
        {**summary, "recentWindowRunCount": -1},
        {
            **summary,
            "totals": {"crawled": 20, "written": 18, "failed": 0},
        },
        {
            **summary,
            "totals": {"crawled": 20, "written": 18, "failed": 0, "promoted": "8"},
        },
        {
            **summary,
            "totals": {
                "adjudicationCallBudget": 10,
                "crawled": 20,
                "written": 18,
                "failed": 0,
                "promoted": 8,
                "tokensUsed": 1000,
            },
        },
        {
            **summary,
            "totals": {
                "adjudicationCallBudget": 10,
                "adjudicationCalls": 4,
                "crawled": 20,
                "written": 18,
                "failed": 0,
                "promoted": 8,
                "tokensUsed": True,
            },
        },
        {
            **summary,
            "repositoriesByAdjudicationTier": {"local_primary": True},
        },
        {
            **summary,
            "recentWindowCosts": {
                "adjudicationCallBudget": 10,
                "adjudicationCalls": 4,
                "adjudicationBudgetUseRate": 0.3,
                "crawled": 20,
                "tokensUsed": 1000,
                "tokensPerCrawled": 50.0,
            },
        },
        {
            **summary,
            "previousWindowCosts": {
                "adjudicationCallBudget": 10,
                "adjudicationCalls": 4,
                "adjudicationBudgetUseRate": 0.4,
                "crawled": 20,
                "tokensUsed": 1000,
                "tokensPerCrawled": True,
            },
        },
    ]

    for candidate_summary in cases:
        report = telemetry_gate.evaluate(
            candidate_summary,
            args(
                min_runs=0,
                min_crawled=0,
                min_written=0,
                min_promoted=0,
                min_zero_model_rate=0.0,
                max_recent_zero_model_rate_drop=1.0,
            ),
        )
        failed_labels = {item["label"] for item in report["checks"] if not item["passed"]}

        assert not report["passed"]
        assert failed_labels == {"retained proof fields"}


def test_evaluate_rejects_missing_or_malformed_fixture_candidate_proof_field() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 4,
        "budgetExhaustedRuns": 0,
        "totals": {
            "adjudicationCallBudget": 10,
            "adjudicationCalls": 4,
            "crawled": 20,
            "written": 18,
            "failed": 0,
            "promoted": 8,
            "tokensUsed": 1000,
        },
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
            "zeroModelRate": 0.8,
        },
        "recentWindowRunCount": 3,
        "recentWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
            "zeroModelRate": 0.8,
        },
        "previousWindowRunCount": 3,
        "previousWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
            "zeroModelRate": 0.8,
        },
        "repositoriesByAdjudicationTier": {"local_primary": 4, "api_escalation": 1},
    }

    for candidate_value in (None, {"missing": "list"}):
        candidate_summary = summary.copy()
        if candidate_value is not None:
            candidate_summary["regressionFixtureCandidates"] = candidate_value
        report = telemetry_gate.evaluate(candidate_summary, args())
        failed_labels = {item["label"] for item in report["checks"] if not item["passed"]}

        assert not report["passed"]
        assert failed_labels == {"retained proof fields"}


def test_evaluate_rejects_malformed_fixture_candidate_entries() -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 4,
        "budgetExhaustedRuns": 0,
        "totals": {
            "adjudicationCallBudget": 10,
            "adjudicationCalls": 4,
            "crawled": 20,
            "written": 18,
            "failed": 0,
            "promoted": 8,
            "tokensUsed": 1000,
        },
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
            "zeroModelRate": 0.8,
        },
        "recentWindowRunCount": 3,
        "recentWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
            "zeroModelRate": 0.8,
        },
        "previousWindowRunCount": 3,
        "previousWindowRates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.05,
            "zeroModelRate": 0.8,
        },
        "repositoriesByAdjudicationTier": {"local_primary": 4, "api_escalation": 1},
    }
    malformed_candidates = [
        "not an object",
        {
            "failureClass": "parser",
            "ecosystem": "rust",
            "fixtureEligible": "true",
            "fingerprint": "Cargo.toml parse error",
            "count": 2,
            "suggestedFixture": "cargo-toml-parse-error",
        },
        {
            "failureClass": "parser",
            "ecosystem": "rust",
            "fixtureEligible": True,
            "fingerprint": "",
            "count": 2,
            "suggestedFixture": "cargo-toml-parse-error",
        },
        {
            "failureClass": "parser",
            "ecosystem": "rust",
            "fixtureEligible": True,
            "fingerprint": "Cargo.toml parse error",
            "count": "2",
            "suggestedFixture": "cargo-toml-parse-error",
        },
        {
            "failureClass": "parser",
            "ecosystem": "rust",
            "fixtureEligible": True,
            "fingerprint": "Cargo.toml parse error",
            "count": True,
            "suggestedFixture": "cargo-toml-parse-error",
        },
    ]

    for candidate in malformed_candidates:
        candidate_summary = summary.copy()
        candidate_summary["regressionFixtureCandidates"] = [candidate]
        report = telemetry_gate.evaluate(candidate_summary, args())
        failed_labels = {item["label"] for item in report["checks"] if not item["passed"]}

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
            "recentWindowRunCount": 3,
            "previousWindowRunCount": 1,
            "driftReference": "previous-window",
            "rates": {
                "promotionRate": 0.4,
                "adjudicationRate": 0.2,
            },
            "recentWindowRates": {
                "adjudicationRate": 0.2,
                "zeroModelRate": 0.8,
            },
            "recentZeroModelRateDrop": 0.1,
            "previousWindowRates": {
                "adjudicationRate": 0.1,
            },
            "worstRunRates": {
                "failureRate": 0.05,
                "adjudicationRate": 0.25,
                "secondOpinionRate": 0.1,
                "zeroModelRate": 0.75,
            },
            "fixtureEligibleRecurringFailures": [
                {
                    "failureClass": "parser",
                    "ecosystem": "rust",
                    "fixtureEligible": True,
                    "fingerprint": "Cargo.toml parse error",
                    "count": 2,
                    "suggestedFixture": "cargo-toml-parse-error",
                }
            ],
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
    assert "- recent window runs: 3" in rendered
    assert "- previous window runs: 1" in rendered
    assert "- aggregate promotion rate: 40.00%" in rendered
    assert "- previous-window adjudication rate: 10.00%" in rendered
    assert "- recent-window adjudication rate: 20.00%" in rendered
    assert "- recent-window zero-model rate: 80.00%" in rendered
    assert "- recent-window zero-model drop: 10.00%" in rendered
    assert "- drift reference: previous-window" in rendered
    assert "- worst-run adjudication rate: 25.00%" in rendered
    assert "- worst-run second-opinion rate: 10.00%" in rendered
    assert "- worst-run zero-model rate: 75.00%" in rendered
    assert "- fixture-eligible recurring failures: 1" in rendered
    assert (
        "- thresholds: min runs 3, min crawled 10, max adjudication 25.00%, max API escalation 5.00%"
        in rendered
    )
    assert "| retained repeated runs | 1 | >= 3 | fail |" in rendered
    assert "## Fixture-Eligible Recurring Failures" in rendered
    assert (
        "| `cargo-toml-parse-error` | `parser` | `rust` | 2 | `Cargo.toml parse error` |"
        in rendered
    )
