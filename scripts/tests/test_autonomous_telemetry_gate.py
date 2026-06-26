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
        "max_failure_rate": 0.05,
        "max_adjudication_rate": 0.25,
        "max_api_escalation_rate": 0.05,
        "min_zero_model_rate": 0.75,
    }
    defaults.update(overrides)
    return Namespace(**defaults)


def test_evaluate_passes_when_retained_telemetry_meets_thresholds() -> None:
    summary = {
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 4,
        "totals": {"crawled": 20, "written": 18, "failed": 0},
        "rates": {
            "failureRate": 0.0,
            "adjudicationRate": 0.2,
            "zeroModelRate": 0.8,
        },
        "repositoriesByAdjudicationTier": {"local_primary": 4, "api_escalation": 1},
    }

    report = telemetry_gate.evaluate(summary, args())

    assert report["passed"]
    assert all(item["passed"] for item in report["checks"])


def test_evaluate_reports_not_yet_for_insufficient_or_expensive_runs() -> None:
    summary = {
        "generatedAt": "2026-03-18T12:00:00Z",
        "runCount": 1,
        "totals": {"crawled": 4, "written": 0, "failed": 1},
        "rates": {
            "failureRate": 0.25,
            "adjudicationRate": 0.5,
            "zeroModelRate": 0.5,
        },
        "repositoriesByAdjudicationTier": {"api_escalation": 1},
    }

    report = telemetry_gate.evaluate(summary, args())
    failed_labels = {
        item["label"] for item in report["checks"] if not item["passed"]
    }

    assert not report["passed"]
    assert "retained repeated runs" in failed_labels
    assert "processed repository volume" in failed_labels
    assert "direct writeback activity" in failed_labels
    assert "failure rate" in failed_labels
    assert "model adjudication rate" in failed_labels
    assert "strong remote escalation rate" in failed_labels
    assert "zero-model deterministic rate" in failed_labels


def test_render_markdown_includes_check_table() -> None:
    report = {
        "passed": False,
        "summaryGeneratedAt": "2026-03-18T12:00:00Z",
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
    assert "| retained repeated runs | 1 | >= 3 | fail |" in rendered
