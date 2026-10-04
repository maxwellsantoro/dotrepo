import copy
import json
from pathlib import Path
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_ci_gate import SCOPED_JOBS, check_results, main


def needs_for(*selected):
    return {
        "change-scope": {
            "result": "success",
            "outputs": {
                output: str(job in selected).lower() for job, output in SCOPED_JOBS.items()
            },
        },
        **{job: {"result": "success" if job in selected else "skipped"} for job in SCOPED_JOBS},
    }


@pytest.mark.parametrize(
    "selected",
    [
        ("minimal-gate",),
        ("public-surface-gate",),
        ("public-surface-gate", "operator-gate"),
        ("rust-and-index", "release-gate"),
        tuple(SCOPED_JOBS),
    ],
)
def test_intentionally_skipped_jobs_do_not_block_valid_scopes(selected):
    assert check_results(needs_for(*selected)) == []


@pytest.mark.parametrize("result", ["failure", "cancelled", "skipped", None])
def test_selected_job_must_succeed(result):
    needs = needs_for("rust-and-index", "release-gate")
    needs["release-gate"]["result"] = result
    assert check_results(needs)


def test_classifier_failure_missing_outputs_and_empty_scope_fail_closed():
    needs = needs_for("minimal-gate")
    variants = []
    for result in ["failure", "cancelled", "skipped"]:
        variant = copy.deepcopy(needs)
        variant["change-scope"]["result"] = result
        variants.append(variant)
    variant = copy.deepcopy(needs)
    del variant["change-scope"]["outputs"]["run_release_gate"]
    variants.extend([variant, needs_for(), {}])
    assert all(check_results(variant) for variant in variants)


def test_unplanned_failed_job_is_not_ignored():
    needs = needs_for("minimal-gate")
    needs["operator-gate"]["result"] = "failure"
    assert check_results(needs)


def test_main_rejects_malformed_needs(monkeypatch):
    for payload in ["invalid", "null", "[]", json.dumps({"change-scope": []})]:
        monkeypatch.setenv("CI_NEEDS", payload)
        assert main() == 1


def test_workflow_gate_always_runs_and_covers_every_scoped_job():
    workflow = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml").read_text()
    )
    gate = workflow["jobs"]["ci-gate"]
    assert gate["if"] == "always()"
    assert set(gate["needs"]) == {"change-scope", *SCOPED_JOBS}
    step = next(step for step in gate["steps"] if "check_ci_gate.py" in step.get("run", ""))
    assert step["env"]["CI_NEEDS"] == "${{ toJSON(needs) }}"
    assert step["run"].startswith("uv run python ")
