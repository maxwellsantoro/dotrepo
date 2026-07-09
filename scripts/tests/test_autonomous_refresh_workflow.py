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
    commit = workflow.index("- name: Commit and push index updates")
    propagate = workflow.index("- name: Preserve autonomous batch failure result")

    assert batch < gate < validate < upload < commit < propagate
    assert "id: autonomous_batch\n        continue-on-error: true" in workflow
    assert "--warn-only" in workflow[gate:validate]
    assert "steps.telemetry_gate.outcome == 'success'" in workflow[commit:propagate]
    assert "steps.validate_index.outcome == 'success'" in workflow[commit:propagate]
    assert "index-autonomous-batch/telemetry.json" in workflow[commit:propagate]
    assert "steps.autonomous_batch.outcome == 'failure'" in workflow[propagate:]
    assert "--skip-automation-enabled-check" not in workflow[batch:gate]


def test_scheduled_refresh_is_fail_closed_on_automation_enablement() -> None:
    workflow = WORKFLOW.read_text()

    assert "vars.INDEX_AUTOMATION_ENABLED == 'true'" in workflow
    assert "vars.INDEX_AUTOMATION_ENABLED != 'false'" not in workflow
    assert "INDEX_AUTOMATION_ENABLED || 'true'" not in workflow
    assert "INDEX_AUTOMATION_ENABLED: ${{ vars.INDEX_AUTOMATION_ENABLED }}" in workflow


def test_gate_report_is_created_before_batch_artifact_upload() -> None:
    workflow = WORKFLOW.read_text()
    gate = workflow.index("- name: Evaluate autonomous telemetry gate")
    upload = workflow.index("- name: Upload batch telemetry")

    assert gate < upload
    assert "autonomous-telemetry-gate.json" in workflow[gate:upload]
    assert "autonomous-telemetry-gate.md" in workflow[gate:upload]
