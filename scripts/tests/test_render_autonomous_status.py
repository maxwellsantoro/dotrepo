import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

SPEC = importlib.util.spec_from_file_location(
    "render_autonomous_status", SCRIPTS / "render_autonomous_status.py"
)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


def _summary():
    return {
        "runCount": 36,
        "firstRunAt": "2026-06-29T00:55:19Z",
        "lastRunAt": "2026-10-27T19:59:52Z",
        "generatedAt": "2026-10-27T19:59:52Z",
        "totals": {
            "crawled": 1779,
            "written": 1770,
            "failed": 9,
            "promoted": 1213,
            "qualityReprocessQueued": 1538,
            "adjudicationCalls": 0,
            "adjudicationCallBudget": 68,
            "tokensUsed": 0,
        },
        "rates": {"failureRate": 0.005, "promotionRate": 0.68, "zeroModelRate": 1.0},
    }


def test_render_includes_operation_and_adjudication_state():
    now = datetime(2026, 10, 28, tzinfo=timezone.utc)
    report = mod.render_status(_summary(), [{"failed": 0}, {"failed": 2}], None, now)
    assert "Retained runs: 36" in report
    assert "Adjudication calls: 0" in report
    assert "Zero-model rate: 100%" in report
    assert "Recent 2 runs with failures: 1" in report
    assert "Not evaluated in this report" in report


def test_render_includes_freshness_when_supplied():
    now = datetime(2026, 10, 28, tzinfo=timezone.utc)
    freshness = {
        "fresh": 615,
        "stale": 0,
        "unknown": 0,
        "staleOrUnknownRate": 0.0,
        "oldestRefreshOverdueDays": 0.0,
        "passed": True,
    }
    report = mod.render_status(_summary(), [], freshness, now)
    assert "Fresh 615, stale 0" in report
    assert "gate passed: True" in report
