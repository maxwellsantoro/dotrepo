"""Completion must require observed work, including the named host proof."""

from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parents[2] / "benchmarks/head-to-head"
sys.path.insert(0, str(BENCH))
from bench.own_projects import (  # noqa: E402
    REPEAT_REVISIONS,
    freeze,
    oracle,
    python_shim,
    run,
    sdk_shim,
    study_environment,
    study_inputs,
    validate_fixed_tasks,
    zig_shim,
)
from bench.tasks import score, timestamp  # noqa: E402


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


def test_repeat_keeps_all_tasks_and_binds_proposed_wrapper_prerequisite():
    workload = json.loads((BENCH / "results/own-projects-2026-10-04/workload.json").read_text())
    workload["study"] = "readiness-repeat"
    for task in workload["tasks"]:
        task["revision"] = REPEAT_REVISIONS[task["identity"].split("/")[-1]]
        task["timeoutSecondsPerCommand"] = 900
    plan = workload["tasks"][1]["acceptableInstructions"][0]
    plan["prerequisites"].insert(0, "just codegen (included by wrapper)")
    validate_fixed_tasks(workload)
    plan["prerequisites"].pop(0)
    with pytest.raises(ValueError, match="fixed source tasks"):
        validate_fixed_tasks(workload)
    with pytest.raises(ValueError, match="unknown fixed study"):
        study_inputs("substitute-easier-tasks")


def test_uv_shim_uses_project_environment_and_falls_back_for_no_venv(tmp_path):
    project = tmp_path / ".venv"
    subprocess.run(["uv", "venv", "--python", sys.executable, str(project)], check=True)
    shim = tmp_path / "python"
    shim.write_text(python_shim())
    shim.chmod(0o755)
    env = {**os.environ, "DOTREPO_STUDY_PROJECT_PYTHON": str(project / "bin/python")}
    command = [str(shim), "-c", "import sys; print(sys.prefix)"]
    assert subprocess.check_output(command, env=env, text=True).strip() == str(project)
    env["DOTREPO_STUDY_PROJECT_PYTHON"] = str(tmp_path / "absent")
    assert subprocess.check_output(command, env=env, text=True).strip() == sys.prefix


def test_sdk_followup_keeps_the_two_failed_tasks_and_requires_declared_setup():
    workload = json.loads((BENCH / "results/own-projects-2026-10-04/workload.json").read_text())
    workload["study"] = "atlas-sdk-followup"
    workload["tasks"] = workload["tasks"][2:4]
    for task in workload["tasks"]:
        task["timeoutSecondsPerCommand"] = 900
        plan = task["acceptableInstructions"][0]
        plan["prerequisites"].append("task-local Zig 0.14 compatible SDK selection")
        plan["environment"] = study_environment("atlas-sdk-followup")
    validate_fixed_tasks(workload)
    workload["tasks"][0]["acceptableInstructions"][0]["environment"] = {}
    with pytest.raises(ValueError, match="fixed source tasks"):
        validate_fixed_tasks(workload)


def test_sdk_selector_overrides_only_the_declared_sdk_query(tmp_path):
    shim = tmp_path / "xcrun"
    shim.write_text(sdk_shim())
    shim.chmod(0o755)
    env = {**os.environ, "DOTREPO_STUDY_ZIG_SDK": str(tmp_path / "explicit-sdk")}
    assert (
        subprocess.check_output(
            [str(shim), "--sdk", "macosx", "--show-sdk-path"], env=env, text=True
        ).strip()
        == env["DOTREPO_STUDY_ZIG_SDK"]
    )
    if sys.platform == "darwin":
        expected = subprocess.check_output(["/usr/bin/xcrun", "--show-sdk-path"], text=True)
        assert (
            subprocess.check_output([str(shim), "--show-sdk-path"], env=env, text=True) == expected
        )


def test_readiness_packet_replays_without_erasing_its_sdk_failures():
    packet = BENCH / "results/own-projects-readiness-2026-10-05"
    scored = score(packet / "workload.json", packet / "observations.json")
    assert scored == json.loads((packet / "results.json").read_bytes())
    for arm in ("source-first", "lookup-first"):
        summary = scored["summary"][arm]
        assert summary["completedTask"] == 6
        assert summary["failedAttempts"] == 2
        assert summary["acceptedWrongAnswer"] == summary["policyAcceptedTasks"] == 0
    assert scored["summary"]["lookup-first"]["fallbackAttempts"] == 8


def test_sdk_selection_is_private_to_the_zig_child(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    selector = private / "xcrun"
    selector.write_text(sdk_shim())
    selector.chmod(0o755)
    probe = tmp_path / "probe-zig"
    probe.write_text("#!/bin/sh\nexec xcrun --sdk macosx --show-sdk-path\n")
    probe.chmod(0o755)
    public = tmp_path / "public"
    public.mkdir()
    wrapper = public / "zig"
    wrapper.write_text(zig_shim(probe, private))
    wrapper.chmod(0o755)
    env = {**os.environ, "DOTREPO_STUDY_ZIG_SDK": "declared-compat-sdk"}
    env["PATH"] = str(public) + os.pathsep + env["PATH"]
    assert (
        subprocess.check_output([str(wrapper)], env=env, text=True).strip() == "declared-compat-sdk"
    )
    if sys.platform == "darwin":
        command = ["xcrun", "--sdk", "macosx", "--show-sdk-path"]
        expected = subprocess.check_output(["/usr/bin/xcrun", *command[1:]], text=True)
        assert subprocess.check_output(command, env=env, text=True) == expected


@pytest.mark.parametrize(
    ("packet_name", "completed"),
    [("own-projects-atlas-sdk-2026-10-05", 0), ("own-projects-atlas-scoped-sdk-2026-10-05", 2)],
)
def test_sdk_packets_replay_separately_with_the_complete_cohort(packet_name, completed):
    packet = BENCH / "results" / packet_name
    scored = score(packet / "workload.json", packet / "observations.json")
    assert scored == json.loads((packet / "results.json").read_bytes())
    for arm in ("source-first", "lookup-first"):
        assert scored["summary"][arm]["completedTask"] == completed
        assert scored["summary"][arm]["policyAcceptedTasks"] == 0
    assert scored["summary"]["lookup-first"]["fallbackAttempts"] == 2
    if completed:
        for arm in ("source-first", "lookup-first"):
            attempt = json.loads(
                (
                    packet / "attempts" / f"sha256-benchmark-atlas-correctness-{arm}-0.json"
                ).read_bytes()
            )
            report = json.loads(attempt["commands"][-1]["stdout"])
            assert report["passed"] and report["case_count"] >= 1000
            assert len({item["id"] for item in report["implementations"]}) == 19
            assert all(
                item["ok"] and item["checked"] == report["case_count"] and item["failed"] == 0
                for item in report["implementations"]
            )


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


def test_contextual_packet_replays_completions_without_rewriting_history():
    packet = BENCH / "results/own-projects-contextual-2026-10-05"
    scored = score(packet / "workload.json", packet / "observations.json")
    assert scored == json.loads((packet / "results.json").read_bytes())
    source, lookup = (scored["summary"][arm] for arm in ("source-first", "lookup-first"))
    assert source["completedTask"] == lookup["completedTask"] == 8
    assert lookup["policyAcceptedTasks"] == 6 and lookup["fallbackAttempts"] == 2
    assert source["failedAttempts"] == lookup["failedAttempts"] == 0
    assert lookup["acceptedWrongAnswer"] == 0
    assert source["transport"] == {"httpRequests": 8, "decodedBytes": 46020, "cacheHits": 0}
    assert lookup["transport"] == {"httpRequests": 10, "decodedBytes": 49970, "cacheHits": 0}
    assert lookup["modelUsage"]["cost"] is None
    workload = json.loads((packet / "workload.json").read_bytes())
    for relative, digest in workload["executionSources"].items():
        assert (
            hashlib.sha256((packet / "execution-source" / relative).read_bytes()).hexdigest()
            == digest
        )
    for receipt in (packet / "http").glob("*.receipt.json"):
        raw = (packet / "http" / receipt.name.removesuffix(".receipt.json")).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == json.loads(receipt.read_bytes())["sha256"]


def test_retained_public_profiles_reselect_actual_instructions_at_frozen_clock():
    from bench.own_projects import consumer

    packet = BENCH / "results/own-projects-contextual-2026-10-05"
    workload = json.loads((packet / "workload.json").read_bytes())
    observations = json.loads((packet / "observations.json").read_bytes())
    for task in workload["tasks"]:
        body = (packet / "http" / (task["id"] + "-lookup-first-profile")).read_bytes()
        result = consumer.interpret_http_response(
            identity=task["identity"], status_code=200, body=body
        )
        selection = consumer.select_instruction(
            result,
            task["acceptableInstructions"][0]["purpose"],
            request=task["instructionRequest"],
            now=timestamp(workload["frozenAt"]),
        )
        lookup = next(
            run["lookup"]
            for run in observations["runs"]
            if run["taskId"] == task["id"] and run["arm"] == "lookup-first"
        )
        assert selection["instruction"] == lookup["instruction"]
        if lookup["accepted"]:
            assert selection["instruction"] in task["acceptableInstructions"]
            assert not (packet / "http" / (task["id"] + "-lookup-first-source")).exists()


@pytest.mark.parametrize(
    "dependency",
    [
        "examples/external-consumer/lookup_before_scrape.py",
        "benchmarks/head-to-head/bench/tasks.py",
        "uv.lock",
    ],
)
def test_frozen_dependency_changes_refuse_before_http_or_execution(
    tmp_path, monkeypatch, dependency
):
    import bench.own_projects as runner
    import shutil

    source = tmp_path / "source"
    for relative in runner.execution_sources():
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(runner.EXECUTION_ROOT / relative, target)
    monkeypatch.setattr(runner, "EXECUTION_ROOT", source)
    output = tmp_path / "packet"
    output.mkdir()
    workload = json.loads((BENCH / "results/own-projects-2026-10-04/workload.json").read_bytes())
    workload["consumerPolicy"] = runner.consumer.INSTRUCTION_POLICY
    workload["executionSources"] = runner.retain_execution_sources(output)
    workload["runnerSha256"] = runner.execution_sources()[
        "benchmarks/head-to-head/bench/own_projects.py"
    ]
    (output / "workload.json").write_text(json.dumps(workload))
    # Validation succeeds for the complete frozen bundle, then fails when only
    # an imported dependency changes (the top-level runner remains identical).
    runner.validate_execution_sources(workload, output)
    changed = source / dependency
    changed.write_bytes(changed.read_bytes() + b"\n# changed after freeze\n")

    def forbidden(*args, **kwargs):
        pytest.fail("freeze mismatch reached HTTP or task execution")

    monkeypatch.setattr(runner, "fetch", forbidden)
    monkeypatch.setattr(runner, "execute", forbidden)
    with pytest.raises(ValueError, match="execution dependency changed"):
        runner.run(output, tmp_path)
    assert not (output / "http").exists() and not (output / "attempts").exists()
