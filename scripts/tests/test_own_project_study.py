"""Completion must require observed work, including the named host proof."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parents[2] / "benchmarks/head-to-head"
sys.path.insert(0, str(BENCH))
from bench.own_projects import freeze, oracle, run, validate_fixed_tasks  # noqa: E402
from bench.tasks import score  # noqa: E402


def result(stdout="", stderr="", *, code=0, error=None):
    return {"exitCode": code, "stdout": stdout, "stderr": stderr, "executionError": error}


@pytest.mark.parametrize("name", ["core-test", "generator-test", "consumer-test"])
def test_zero_exit_without_executed_tests_is_not_completion(tmp_path, name):
    assert not oracle(name, tmp_path, result("Finished compiling tests"))
    assert not oracle(name, tmp_path, result("test result: ok. 0 passed; 0 failed"))


def test_success_text_cannot_erase_failed_process_or_timeout(tmp_path):
    text = "test result: ok. 34 passed; 0 failed"
    assert oracle("core-test", tmp_path, result(text))
    assert not oracle("core-test", tmp_path, result(text, code=1))
    assert not oracle("core-test", tmp_path, result(text, error="timeout"))


@pytest.mark.parametrize("field", ["validation", "denied_operation", "receipt_replay_checked"])
def test_host_proof_requires_validation_denial_and_replay(tmp_path, field):
    directory = tmp_path / "out/agent-task-proof-rt"
    directory.mkdir(parents=True)
    report = {
        "validation": {"outcome": "valid"},
        "candidate": {"content_id": "same"},
        "accepted": {"content_id": "same"},
        "denied_operation": {"status": 1, "mapping_cap": 0},
        "receipt_replay_checked": True,
    }
    path = directory / "report.json"
    path.write_text(json.dumps(report))
    assert oracle("host-proof", tmp_path, result())
    report[field] = {
        "validation": {"outcome": "invalid"},
        "denied_operation": {"status": 1, "mapping_cap": 99},
        "receipt_replay_checked": False,
    }[field]
    path.write_text(json.dumps(report))
    assert not oracle("host-proof", tmp_path, result())


def test_existing_partial_packet_cannot_be_rewritten(tmp_path):
    sentinel = tmp_path / "workload.json"
    sentinel.write_text("frozen")
    with pytest.raises(ValueError, match="empty output"):
        freeze(tmp_path, tmp_path, tmp_path, tmp_path)
    (tmp_path / "attempts").mkdir()
    with pytest.raises(ValueError, match="immutable"):
        run(tmp_path, tmp_path)
    assert sentinel.read_text() == "frozen"


def test_unfamiliar_command_cannot_enter_fixed_runner():
    workload = json.loads((BENCH / "results/own-projects-2026-10-04/workload.json").read_text())
    validate_fixed_tasks(workload)
    workload["tasks"][0]["acceptableInstructions"][0]["command"] = "arbitrary-upstream-command"
    with pytest.raises(ValueError, match="fixed source tasks"):
        validate_fixed_tasks(workload)


def test_retained_live_packet_separates_mismatches_failures_and_unknown_costs():
    packet = BENCH / "results/own-projects-2026-10-04"
    scored = score(packet / "workload.json", packet / "observations.json")
    expected = json.loads((packet / "results.json").read_text())
    assert scored == expected
    source, lookup = (scored["summary"][arm] for arm in ("source-first", "lookup-first"))
    assert source["completedTask"] == lookup["completedTask"] == 5
    assert source["failedAttempts"] == 3
    assert lookup["failedAttempts"] == 5
    assert lookup["policyAcceptedTasks"] == lookup["acceptedWrongAnswer"] == 2
    assert lookup["fallbackAttempts"] == 8
    assert source["transport"]["httpRequests"] == 8
    assert lookup["transport"]["httpRequests"] == 16
    assert lookup["modelUsage"]["cost"] is None
    assert lookup["allocatedMaintenanceCost"] is None
    observations = json.loads((packet / "observations.json").read_text())
    for observation in observations["runs"]:
        if observation["lookup"] and observation["lookup"]["accepted"]:
            attempt = observation["attempts"][0]
            assert attempt["exitCode"] is None
            assert "not executed" in attempt["executionError"]
