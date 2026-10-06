from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from run_autonomous_index_batch import (  # noqa: E402
    adjudication_enabled,
    crawl_env_for_remaining_budget,
)

WORKFLOW = ROOT / ".github/workflows/index-autonomous-refresh.yml"
SCRIPT = ROOT / "scripts/check_autonomous_refresh_base.py"


def steps():
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]["autonomous-refresh"]["steps"]


def budget_step(tmp_path, inputs, *, event="workflow_dispatch", providers="true", default="4"):
    event_path, output = tmp_path / "event.json", tmp_path / "output"
    event_path.write_text(json.dumps({"inputs": inputs}))
    step = next(item for item in steps() if item.get("id") == "refresh_budget")
    env = os.environ | {
        "GITHUB_EVENT_PATH": str(event_path),
        "GITHUB_EVENT_NAME": event,
        "GITHUB_OUTPUT": str(output),
        "DEFAULT_ADJUDICATION_CALL_BUDGET": default,
        "PROVIDERS_ENABLED": providers,
    }
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", step["run"]],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    values = (
        dict(line.split("=", 1) for line in output.read_text().splitlines())
        if output.exists()
        else {}
    )
    return result, values


def test_dispatch_zero_blocks_sidecars_and_all_crawl_adjudication_tiers(tmp_path):
    result, output = budget_step(tmp_path, {"adjudication_call_budget": "0"})
    assert result.returncode == 0
    assert output == {"adjudication_call_budget": "0", "adjudication_enabled": "false"}
    sidecars = next(item for item in steps() if item.get("name") == "Start adjudication sidecars")
    assert sidecars["if"] == (
        "env.OPENROUTER_API_KEY != '' && steps.refresh_budget.outputs.adjudication_enabled == 'true'"
    )
    batch = next(item for item in steps() if item.get("id") == "autonomous_batch")
    assert batch["env"]["ADJUDICATION_CALL_BUDGET"] == (
        "${{ steps.refresh_budget.outputs.adjudication_call_budget }}"
    )
    assert '--adjudication-call-budget "$ADJUDICATION_CALL_BUDGET"' in batch["run"]
    configured = {
        "DOTREPO_ADJUDICATION_URL": "https://primary.invalid/adjudicate",
        "DOTREPO_ADJUDICATION_SECOND_OPINION_URL": "https://second.invalid/adjudicate",
        "DOTREPO_ADJUDICATION_API_URL": "https://tail.invalid/adjudicate",
        "INDEX_MAX_ADJUDICATION_CALLS": "2",
    }
    crawl = crawl_env_for_remaining_budget(configured, int(output["adjudication_call_budget"]))
    assert not adjudication_enabled(crawl)
    assert crawl["INDEX_MAX_ADJUDICATION_CALLS"] == "0"
    assert not any(key.endswith("_URL") for key in crawl)


@pytest.mark.parametrize("value", ["-1", "1.5", "false", "$(touch unexpected)", "1\n2", None, True])
def test_malformed_dispatch_budget_fails_actual_step_before_sidecars_or_materialization(
    tmp_path, value
):
    result, output = budget_step(tmp_path, {"adjudication_call_budget": value})
    assert result.returncode != 0
    assert output == {}
    assert "nonnegative integer" in result.stderr
    workflow_steps = steps()
    ids = [step.get("id") or step.get("name") for step in workflow_steps]
    assert ids.index("refresh_budget") < ids.index("Start adjudication sidecars")
    assert ids.index("refresh_budget") < ids.index("autonomous_batch")
    assert (
        not next(step for step in workflow_steps if step.get("id") == "autonomous_batch")
        .get("if", "")
        .startswith("always()")
    )


@pytest.mark.parametrize(
    ("inputs", "event", "providers", "default", "expected"),
    [
        ({}, "schedule", "true", "4", "4"),
        ({"adjudication_call_budget": "0"}, "schedule", "true", "4", "4"),
        ({}, "schedule", "false", "4", "0"),
        ({"adjudication_call_budget": ""}, "workflow_dispatch", "true", "2", "2"),
        ({"adjudication_call_budget": "3"}, "workflow_dispatch", "true", "2", "3"),
    ],
)
def test_actual_event_budget_defaults_preserve_scheduled_policy(
    tmp_path, inputs, event, providers, default, expected
):
    result, output = budget_step(
        tmp_path, inputs, event=event, providers=providers, default=default
    )
    assert result.returncode == 0
    assert output["adjudication_call_budget"] == expected


def fake_gh(tmp_path, *, current="a" * 40, branch="main", failure=False):
    executable = tmp_path / "gh"
    executable.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$*" >> "$API_CALLS_FILE"\n'
        'if [ "$API_FAIL" = true ]; then exit 1; fi\n'
        'case "$2" in\n'
        '  repos/team/project) printf "%s" "$REPO_RESPONSE" ;;\n'
        '  *) printf "%s" "$REF_RESPONSE" ;;\n'
        "esac\n"
    )
    executable.chmod(0o755)
    return os.environ | {
        "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
        "API_CALLS_FILE": str(tmp_path / "calls"),
        "API_FAIL": "true" if failure else "false",
        "REPO_RESPONSE": json.dumps({"default_branch": branch}),
        "REF_RESPONSE": json.dumps({"ref": f"refs/heads/{branch}", "object": {"sha": current}}),
    }


@pytest.mark.parametrize("current", ["a" * 40, "b" * 40])
def test_actual_base_command_records_match_or_drift_without_live_base_substitution(
    tmp_path, current
):
    output = tmp_path / "base.json"
    result = subprocess.run(
        [
            "uv",
            "run",
            "--no-project",
            "python",
            str(SCRIPT),
            "base",
            "--repository",
            "team/project",
            "--expected-base",
            "a" * 40,
            "--output-json",
            str(output),
        ],
        env=fake_gh(tmp_path, current=current, branch="release/main"),
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    report = json.loads(output.read_text())
    assert report["expectedBase"] == "a" * 40
    assert report["currentBase"] == current
    assert report["passed"] == (current == "a" * 40)
    assert result.returncode == (0 if report["passed"] else 1)
    assert (tmp_path / "calls").read_text().splitlines() == [
        "api repos/team/project",
        "api repos/team/project/git/ref/heads/release%2Fmain",
    ]


def test_api_failure_does_not_fallback_to_checkout_or_create_pr(tmp_path):
    output = tmp_path / "base.json"
    result = subprocess.run(
        [
            "uv",
            "run",
            "--no-project",
            "python",
            str(SCRIPT),
            "base",
            "--repository",
            "team/project",
            "--expected-base",
            "a" * 40,
            "--output-json",
            str(output),
        ],
        env=fake_gh(tmp_path, failure=True),
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 1
    report = json.loads(output.read_text())
    assert not report["passed"] and "currentBase" not in report
    assert len((tmp_path / "calls").read_text().splitlines()) == 1


def test_workflow_preflight_controls_pr_creation_and_keeps_late_exact_base_guard():
    workflow_steps = steps()
    ids = [step.get("id") or step.get("name") for step in workflow_steps]
    assert ids.index("refresh_base") < ids.index("Upload batch telemetry")
    assert ids.index("refresh_base") < ids.index("pr_meta") < ids.index("autonomous_pr")
    for identifier in ["pr_meta", "autonomous_pr"]:
        step = next(item for item in workflow_steps if item.get("id") == identifier)
        assert "steps.refresh_base.outcome == 'success'" in step["if"]
    late = next(
        item
        for item in workflow_steps
        if item.get("name") == "Check, land, and deploy the exact automation commit"
    )
    assert late["env"]["EXPECTED_BASE"] == "${{ github.sha }}"
    assert '--expected-base "$EXPECTED_BASE"' in late["run"]
