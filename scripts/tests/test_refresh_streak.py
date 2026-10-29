import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_refresh_streak import SCHEMA, assess

NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


def entries():
    values = []
    for index in range(7):
        timestamp = (NOW - timedelta(days=index, hours=6)).isoformat().replace("+00:00", "Z")
        run = {
            "id": 100 - index,
            "event": "schedule",
            "created_at": timestamp,
            "run_attempt": 1,
            "conclusion": "success",
        }
        receipt = {
            "schema": SCHEMA,
            "runId": run["id"],
            "event": "schedule",
            "runAttempt": 1,
            "startedAt": timestamp,
            "checks": dict.fromkeys(["batch", "telemetry", "index", "base", "landing"], "success"),
            "budget": {
                "adjudicationCallBudget": 0,
                "adjudicationCalls": 0,
                "tokensUsed": 0,
                "failed": 0,
                "crawled": 50,
            },
            "landing": {
                "status": "published",
                "publicationVerified": True,
                "deployRunId": 200 - index,
                "headSha": "a" * 40,
            },
        }
        values.append({"run": run, "receipt": receipt})
    return values


def test_seven_days_require_seven_actual_qualified_receipts():
    values = entries()
    assert assess(values, now=NOW)["passed"]
    assert not assess(values[:6], now=NOW)["passed"]
    duplicate = copy.deepcopy(values[0])
    duplicate["run"]["id"] = duplicate["receipt"]["runId"] = 101
    assert assess([duplicate, *values[:6]], now=NOW)["qualifiedDays"] == 6


@pytest.mark.parametrize(
    "failure",
    [
        "green-skipped-publication",
        "no-receipt",
        "budget-missing",
        "over-budget",
        "retry",
        "failed",
        "missing-day",
        "wrong-run",
        "wrong-deployment",
        "skipped-gate",
    ],
)
def test_each_missing_evidence_boundary_breaks_streak(failure):
    values = entries()
    item = values[2]
    if failure == "green-skipped-publication":
        item["receipt"]["landing"]["status"] = "landed-deployment-disabled"
    elif failure == "no-receipt":
        item["receipt"] = None
    elif failure == "budget-missing":
        del item["receipt"]["budget"]["tokensUsed"]
    elif failure == "over-budget":
        item["receipt"]["budget"]["adjudicationCalls"] = 1
    elif failure == "retry":
        item["run"]["run_attempt"] = item["receipt"]["runAttempt"] = 2
    elif failure == "failed":
        item["run"]["conclusion"] = "failure"
    elif failure == "missing-day":
        del values[2]
    elif failure == "wrong-run":
        item["receipt"]["runId"] = 999
    elif failure == "wrong-deployment":
        item["verificationErrors"] = ["deployment-receipt-not-corroborated"]
    else:
        item["receipt"]["checks"]["index"] = "skipped"
    report = assess(values, now=NOW)
    assert not report["passed"]
    assert report["qualifiedDays"] == 2
    assert report["runs"][-1]["reasons"]


def test_old_streak_and_manual_runs_do_not_meet_current_gate():
    assert not assess(entries(), now=NOW + timedelta(days=2))["passed"]
    values = entries()
    for value in values:
        value["run"]["event"] = "workflow_dispatch"
    assert assess(values, now=NOW)["qualifiedDays"] == 0


@pytest.mark.parametrize("published", [True, False])
def test_collector_corroborates_retained_receipt_with_actual_deploy_steps(monkeypatch, published):
    import io
    import json
    import zipfile
    import check_refresh_streak as streak

    item = entries()[0]
    item["run"].update(path=streak.WORKFLOW, status="completed")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as payload:
        payload.writestr("refresh-receipt.json", json.dumps(item["receipt"]))

    def api(path, *, binary=False):
        if "workflows/index-autonomous-refresh.yml/runs?" in path:
            return {"workflow_runs": [item["run"]]}
        if "/artifacts?" in path:
            return {"artifacts": [{"id": 1, "name": "refresh-receipt", "expired": False}]}
        if path.endswith("/zip"):
            assert binary
            return archive.getvalue()
        if "/jobs?" in path:
            return {
                "jobs": [
                    {
                        "name": "deploy",
                        "conclusion": "success",
                        "steps": [
                            {
                                "name": "Deploy Worker",
                                "conclusion": "success" if published else "skipped",
                            },
                            {"name": "Smoke deployed Worker", "conclusion": "success"},
                        ],
                    }
                ]
            }
        return {
            "conclusion": "success",
            "head_sha": "a" * 40,
            "path": ".github/workflows/public-cloudflare.yml",
        }

    monkeypatch.setattr(streak, "api", api)
    report = assess(streak.collect("example/repo"), now=NOW, required=1)
    assert report["passed"] is published
    if not published:
        assert "deployment-receipt-not-corroborated" in report["runs"][0]["reasons"]


@pytest.mark.parametrize(
    "usage, reason",
    [
        (
            {
                "tokensUsed": None,
                "tokensUsedKnownSubtotal": 120,
                "unknownTokenUsageCalls": 1,
                "tokenUsageComplete": False,
            },
            "budget-token-usage-incomplete",
        ),
        ({"tokensUsed": 0}, "budget-token-usage-incomplete"),
        ({"tokensUsed": 120}, "budget-token-usage-incomplete"),
        ({"tokensUsed": None, "tokenUsageComplete": True}, "budget-evidence-missing-or-malformed"),
    ],
)
def test_unknown_and_legacy_called_usage_do_not_qualify(usage, reason):
    values = entries()
    budget = values[0]["receipt"]["budget"]
    budget.update(adjudicationCallBudget=1, adjudicationCalls=1, **usage)
    report = assess(values, now=NOW)
    assert not report["passed"]
    assert report["qualifiedDays"] == 0
    assert reason in report["runs"][0]["reasons"]


def test_explicit_native_zero_with_calls_and_no_call_zero_are_known():
    values = entries()
    values[0]["receipt"]["budget"].update(
        adjudicationCallBudget=1,
        adjudicationCalls=1,
        tokensUsed=0,
        tokensUsedKnownSubtotal=0,
        unknownTokenUsageCalls=0,
        tokenUsageComplete=True,
    )
    assert assess(values, now=NOW)["passed"]
