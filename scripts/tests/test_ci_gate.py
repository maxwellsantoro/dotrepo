import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_ci_gate import SCOPED_JOBS, check_results, main


def needs_for(*selected):
    return {
        "change-scope": {
            "result": "success",
            "outputs": {
                output: str(job in selected).lower()
                for job, output in SCOPED_JOBS.items()
            },
        },
        **{
            job: {"result": "success" if job in selected else "skipped"}
            for job in SCOPED_JOBS
        },
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
    workflow = (
        Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml"
    ).read_text()
    gate = workflow.split("  ci-gate:", 1)[1].split("  change-scope:", 1)[0]
    needs_line = next(
        line for line in gate.splitlines() if line.strip().startswith("needs:")
    )
    needs = needs_line.partition("[")[2].partition("]")[0]
    assert {name.strip() for name in needs.split(",")} == {"change-scope", *SCOPED_JOBS}
    assert "if: always()" in gate
    assert "CI_NEEDS: ${{ toJSON(needs) }}" in gate
    assert "run: uv run python scripts/check_ci_gate.py" in gate
