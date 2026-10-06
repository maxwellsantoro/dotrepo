"""The live follow-up freezes setup separately from public instructions."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parents[2] / "benchmarks/head-to-head"
sys.path.insert(0, str(BENCH))
from bench import own_projects as study  # noqa: E402


def workload():
    value = json.loads((BENCH / "results/own-projects-2026-10-04/workload.json").read_bytes())
    value["study"] = "contextual-campaign"
    revisions, cases = study.study_inputs(value["study"])
    for task, case in zip(value["tasks"], cases, strict=True):
        repo, name, command, cwd, component, source, prerequisites, setup = case
        task["revision"] = revisions[repo]
        task["timeoutSecondsPerCommand"] = 900
        task["setupCommands"] = setup
        task["preparationEnvironment"] = study.preparation_environment(value["study"], repo)
        plan = task["acceptableInstructions"][0]
        plan.update(component=component, prerequisites=prerequisites, environment={})
        task["instructionRequest"] = {
            "scope": plan["scope"],
            "component": component,
            "workingDirectory": cwd,
        }
    return value


def test_campaign_keeps_commands_and_binds_preparation_outside_instructions():
    value = workload()
    study.validate_fixed_tasks(value)
    assert len(value["tasks"]) == 8
    for task in value["tasks"]:
        assert task["acceptableInstructions"][0]["environment"] == {}
        assert bool(task["preparationEnvironment"]) == ("atlas" in task["identity"])
    value["tasks"][2]["acceptableInstructions"][0]["environment"] = study.study_environment(
        "atlas-sdk-scoped"
    )
    with pytest.raises(ValueError, match="fixed source tasks"):
        study.validate_fixed_tasks(value)


def test_campaign_refuses_missing_preparation():
    value = workload()
    value["tasks"][2]["preparationEnvironment"] = {}
    with pytest.raises(ValueError, match="frozen preparation"):
        study.validate_fixed_tasks(value)


@pytest.mark.parametrize("runtime", ["python", "uv"])
def test_runtime_change_refuses_before_http_or_execution(tmp_path, monkeypatch, runtime):
    value = workload()
    value["consumerPolicy"] = study.consumer.INSTRUCTION_POLICY
    value["executionSources"] = study.retain_execution_sources(tmp_path)
    value["runnerSha256"] = hashlib.sha256(Path(study.__file__).read_bytes()).hexdigest()
    value["runtimeVersions"] = {"python": "frozen-python", "uv": "frozen-uv"}
    current = {**value["runtimeVersions"], runtime: "changed"}
    monkeypatch.setattr(study, "runtime_versions", lambda: current)
    (tmp_path / "workload.json").write_text(json.dumps(value))
    with pytest.raises(ValueError, match="runtime changed"):
        study.run(tmp_path, tmp_path)
    assert not (tmp_path / "attempts").exists()
    assert not (tmp_path / "http").exists()
