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
    pr_meta = workflow.index("- name: Prepare pull request metadata")
    create_pr = workflow.index("- name: Create pull request for index updates")
    propagate = workflow.index("- name: Preserve autonomous batch failure result")
    strict_fail = workflow.index("- name: Fail closed on strict telemetry gate")

    assert batch < gate < validate < upload < pr_meta < create_pr < propagate < strict_fail
    assert "id: autonomous_batch\n        continue-on-error: true" in workflow
    assert "--warn-only" not in workflow[gate:validate]
    assert "check_autonomous_telemetry_gate.py" in workflow[gate:validate]
    assert "steps.telemetry_gate.outcome == 'success'" in workflow[pr_meta:create_pr]
    assert "steps.validate_index.outcome == 'success'" in workflow[pr_meta:create_pr]
    assert "peter-evans/create-pull-request@" in workflow[create_pr:propagate]
    assert "draft: false" in workflow[create_pr:propagate]
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


def test_refresh_landing_is_not_gated_on_public_freshness() -> None:
    # Regression: gating refresh landing on the public freshness gate deadlocked
    # the index (refresh could not land because the index was stale; the index
    # stayed stale because refresh could not land). Freshness gates publication
    # (public-cloudflare), not landing.
    workflow = WORKFLOW.read_text()
    advisory = workflow.index("- name: Check public surface (advisory, non-blocking)")
    pr_meta = workflow.index("- name: Prepare pull request metadata")
    create_pr = workflow.index("- name: Create pull request for index updates")

    assert "continue-on-error: true" in workflow[advisory:pr_meta]
    landing = workflow[pr_meta:create_pr] + workflow[create_pr:]
    assert "steps.public_surface_gate.outcome" not in landing
    assert "steps.telemetry_gate.outcome == 'success'" in landing
    assert "steps.validate_index.outcome == 'success'" in landing


def test_publication_is_freshness_gated_in_cloudflare_deploy() -> None:
    workflow = (
        Path(__file__).resolve().parents[2] / ".github" / "workflows" / "public-cloudflare.yml"
    ).read_text()
    build = workflow.index("- name: Build reviewed public tree for Cloudflare")
    gate = workflow.index("check_public_record_freshness.py")
    deploy = workflow.index("- name: Deploy Worker")

    assert build < gate < deploy
    assert "--max-stale-or-unknown-rate" in workflow[gate:deploy]


def test_scheduled_refresh_plans_over_the_full_index() -> None:
    workflow = WORKFLOW.read_text()
    assert 'limit="1000"' in workflow
    assert "autonomous-refresh failing" in workflow


def test_daily_capacity_and_automatic_landing_do_not_require_routine_human_review():
    workflow = WORKFLOW.read_text()
    assert 'cron: "0 6 * * *"' in workflow
    assert "steps.refresh_params.outputs.batch_size" in workflow
    assert "--disable-discovery" in workflow
    assert "scripts/land_autonomous_index.py" in workflow
    assert "actions: write" in workflow
    assert "secrets.GITHUB_TOKEN" in workflow
    assert "INDEX_AUTOMATION_TOKEN" not in workflow
    assert "steps.autonomous_pr.outputs.pull-request-head-sha" in workflow


def test_landing_receives_explicit_public_deployment_switch_without_variable_api_permission():
    workflow = WORKFLOW.read_text()
    start = workflow.index("- name: Check, land, and deploy the exact automation commit")
    end = workflow.index("- name: Retain refresh publication and budget receipt")
    step = workflow[start:end]
    assert (
        "PUBLIC_DEPLOY_ENABLED: ${{ vars.CLOUDFLARE_PUBLIC_DEPLOY_ENABLED == 'true' && 'true' || 'false' }}"
        in step
    )
    assert '--public-deploy-enabled "$PUBLIC_DEPLOY_ENABLED"' in step
    assert "variables: write" not in workflow and "variables: read" not in workflow
