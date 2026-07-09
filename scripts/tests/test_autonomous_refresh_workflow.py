from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "index-autonomous-refresh.yml"
)


def test_scheduled_refresh_retains_telemetry_before_propagating_batch_failure() -> None:
    workflow = WORKFLOW.read_text()

    batch = workflow.index("- name: Run autonomous refresh batch")
    gate = workflow.index("- name: Evaluate autonomous telemetry gate")
    validate = workflow.index("- name: Validate autonomous index state")
    upload = workflow.index("- name: Upload batch telemetry")
    pr_meta = workflow.index("- name: Prepare draft pull request metadata")
    create_pr = workflow.index("- name: Create draft pull request for index updates")
    propagate = workflow.index("- name: Preserve autonomous batch failure result")
    strict_fail = workflow.index("- name: Fail closed on strict telemetry gate")

    assert batch < gate < validate < upload < pr_meta < create_pr < propagate < strict_fail
    assert "id: autonomous_batch\n        continue-on-error: true" in workflow
    assert "--warn-only" not in workflow[gate:validate]
    assert "check_autonomous_telemetry_gate.py" in workflow[gate:validate]
    assert "steps.telemetry_gate.outcome == 'success'" in workflow[pr_meta:create_pr]
    assert "steps.validate_index.outcome == 'success'" in workflow[pr_meta:create_pr]
    assert "peter-evans/create-pull-request@" in workflow[create_pr:propagate]
    assert "draft: true" in workflow[create_pr:propagate]
    assert "add-paths: |" in workflow[create_pr:propagate]
    assert "index/**" in workflow[create_pr:propagate]
    assert "git push" not in workflow
    assert "steps.autonomous_batch.outcome == 'failure'" in workflow[propagate:]
    assert "steps.telemetry_gate.outcome == 'failure'" in workflow[strict_fail:]
    assert "--skip-automation-enabled-check" not in workflow[batch:gate]


def test_scheduled_refresh_is_fail_closed_on_automation_enablement() -> None:
    workflow = WORKFLOW.read_text()

    assert "vars.INDEX_AUTOMATION_ENABLED == 'true'" in workflow
    assert "vars.INDEX_AUTOMATION_ENABLED != 'false'" not in workflow
    assert "INDEX_AUTOMATION_ENABLED || 'true'" not in workflow
    assert "INDEX_AUTOMATION_ENABLED: ${{ vars.INDEX_AUTOMATION_ENABLED }}" in workflow
    assert "pull-requests: write" in workflow


def test_gate_report_is_created_before_batch_artifact_upload() -> None:
    workflow = WORKFLOW.read_text()
    gate = workflow.index("- name: Evaluate autonomous telemetry gate")
    upload = workflow.index("- name: Upload batch telemetry")

    assert gate < upload
    assert "autonomous-telemetry-gate.json" in workflow[gate:upload]
    assert "autonomous-telemetry-gate.md" in workflow[gate:upload]
