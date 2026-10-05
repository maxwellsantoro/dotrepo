"""Paired scoring controls use frozen operator logs, not arbitrary execution."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parents[2] / "benchmarks/head-to-head"
sys.path.insert(0, str(BENCH))
from bench.tasks import score  # noqa: E402

FIXTURE = BENCH / "results/task-controls-2026-10-05"


@pytest.fixture
def packet(tmp_path):
    import shutil

    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    workload = json.loads((tmp_path / "workload.json").read_text())
    observations = json.loads((tmp_path / "observations.json").read_text())
    return tmp_path, workload, observations


def save(packet, *, bind_workload=True):
    root, workload, observations = packet
    (root / "workload.json").write_text(json.dumps(workload, indent=2) + "\n")
    if bind_workload:
        observations["workloadSha256"] = hashlib.sha256(
            (root / "workload.json").read_bytes()
        ).hexdigest()
    (root / "observations.json").write_text(json.dumps(observations, indent=2) + "\n")
    return root / "workload.json", root / "observations.json"


def update_log(root, attempt, task_id):
    path = root / attempt["log"]["path"]
    data = json.loads(path.read_text())
    data.update({key: attempt[key] for key in ("instruction", "oraclePassed", "exitCode")})
    data["taskId"] = task_id
    path.write_text(json.dumps(data, indent=2) + "\n")
    attempt["log"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


def test_completed_task_is_separate_from_policy_and_failed_profile_attempts(packet):
    report = score(*save(packet))
    source, lookup = report["summary"]["source-first"], report["summary"]["lookup-first"]
    assert source["completedTask"] == lookup["completedTask"] == 10
    assert source["acceptedWrongAnswer"] == 0
    assert lookup["acceptedWrongAnswer"] == lookup["failedAttempts"] == 2
    assert lookup["correctFallback"] == 5
    assert lookup["policyAcceptedTasks"] == 5
    assert lookup["transport"]["httpRequests"] == 17
    assert source["transport"]["httpRequests"] == 10
    assert lookup["modelUsage"]["cost"] is None
    assert lookup["allocatedMaintenanceCost"] is None
    assert not report["externalAdoption"]
    assert report["independentlyVerifiedObservations"] is None


def test_successful_compilation_is_not_completion(packet):
    root, _, observations = packet
    run = next(
        r
        for r in observations["runs"]
        if r["taskId"] == "accepted-non-running-command" and r["arm"] == "lookup-first"
    )
    run["attempts"] = run["attempts"][:1]
    assert run["attempts"][0]["exitCode"] == 0
    report = score(*save(packet))
    row = next(r for r in report["rows"] if r["taskId"] == run["taskId"] and r["arm"] == run["arm"])
    assert not row["completedTask"]
    assert row["acceptedWrongAnswer"] == 1


@pytest.mark.parametrize(
    "key,value",
    [
        ("workingDirectory", "."),
        ("environment", {}),
        ("component", "other"),
        ("parameters", {"target": "other"}),
        ("prerequisites", ["undeclared setup"]),
    ],
)
def test_zero_exit_and_oracle_cannot_erase_changed_source_context(packet, key, value):
    root, _, observations = packet
    run = next(
        r
        for r in observations["runs"]
        if r["taskId"] == "component-scope" and r["arm"] == "source-first"
    )
    attempt = run["attempts"][0]
    attempt["instruction"][key] = value
    assert attempt["oraclePassed"] and attempt["exitCode"] == 0
    update_log(root, attempt, run["taskId"])
    report = score(*save(packet))
    row = next(r for r in report["rows"] if r["taskId"] == run["taskId"] and r["arm"] == run["arm"])
    assert not row["completedTask"]


@pytest.mark.parametrize(
    "mutation,error",
    [
        ("workload", "workload changed"),
        ("missing-run", "missing or extra"),
        ("order", "order must alternate"),
        ("environment", "environment mismatch"),
        ("revision", "revision/environment mismatch"),
        ("cache", "cache mismatch"),
        ("snapshot", "lookup version mismatch"),
        ("source-revision", "source evidence"),
        ("time", "predates freeze"),
        ("negative-cost", "maintenance cost"),
        ("boolean-count", "invalid httpRequests"),
        ("nan-time", "invalid elapsedMs"),
        ("log", "artifact hash mismatch"),
        ("escape", "escapes observations root"),
        ("missing-oracle", "completion oracle"),
    ],
)
def test_invalid_or_mismatched_observations_fail_closed(packet, mutation, error):
    root, workload, observations = packet
    run = observations["runs"][0]
    bind = True
    if mutation == "workload":
        workload["tasks"][0]["id"] = "changed-after-freeze"
        bind = False
    elif mutation == "missing-run":
        observations["runs"].pop()
    elif mutation == "order":
        observations["runs"][:2] = reversed(observations["runs"][:2])
    elif mutation == "environment":
        run["environmentId"] = "different"
    elif mutation == "revision":
        run["revision"] = "f" * 40
    elif mutation == "cache":
        run["cacheState"] = "warm"
    elif mutation == "snapshot":
        observations["runs"][1]["lookup"]["snapshotId"] = "f" * 64
    elif mutation == "source-revision":
        workload["tasks"][0]["evidence"][0]["sourceRevision"] = "f" * 40
    elif mutation == "time":
        run["startedAt"] = "2000-01-01T00:00:00Z"
    elif mutation == "negative-cost":
        run["allocatedMaintenanceCost"] = -1
    elif mutation == "boolean-count":
        run["transport"]["httpRequests"] = True
    elif mutation == "nan-time":
        run["elapsedMs"] = float("nan")
    elif mutation == "log":
        (root / run["attempts"][0]["log"]["path"]).write_text("tampered")
    elif mutation == "escape":
        run["attempts"][0]["log"]["path"] = "../outside.json"
    elif mutation == "missing-oracle":
        run["attempts"][0]["oraclePassed"] = None
        update_log(root, run["attempts"][0], run["taskId"])
    with pytest.raises(ValueError, match=error):
        score(*save(packet, bind_workload=bind))


def test_honest_source_abstention_can_complete_an_inspection_task(packet):
    root, workload, observations = packet
    task = workload["tasks"][0]
    task["acceptableInstructions"] = []
    for run in observations["runs"][:2]:
        attempt = run["attempts"][0]
        attempt["instruction"], attempt["exitCode"] = None, None
        attempt["oraclePassed"] = True
        if run["lookup"]:
            run["lookup"].update(
                accepted=False,
                valuePresent=False,
                instruction=None,
                fallbackReasons=["missing:repo.build"],
            )
            attempt["origin"] = "fallback"
        update_log(root, attempt, run["taskId"])
    report = score(*save(packet))
    assert all(row["completedTask"] for row in report["rows"][:2])
    assert report["rows"][1]["correctFallback"]


def test_reusing_one_execution_artifact_for_both_arms_is_rejected(packet):
    _, _, observations = packet
    observations["runs"][1]["attempts"][0]["log"] = observations["runs"][0]["attempts"][0]["log"]
    with pytest.raises(ValueError, match="artifact reused"):
        score(*save(packet))


def test_elapsed_time_cannot_omit_fallback_work(packet):
    _, _, observations = packet
    observations["runs"][0]["elapsedMs"] = 0
    with pytest.raises(ValueError, match="elapsed time excludes work"):
        score(*save(packet))


def test_reference_runner_preserves_partial_and_completed_packets(tmp_path):
    from bench.task_reference import run_controls

    sentinel = tmp_path / "workload.json"
    sentinel.write_text("partial retained run")
    with pytest.raises(ValueError, match="new output directory"):
        run_controls(tmp_path)
    assert sentinel.read_text() == "partial retained run"
