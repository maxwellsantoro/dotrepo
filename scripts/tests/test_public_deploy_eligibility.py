import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "deploy_eligibility", ROOT / "scripts/check_public_deploy_eligibility.py"
)
eligibility = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(eligibility)
SOURCE = "a" * 40
OTHER = "b" * 40
REPOSITORY = "example/dotrepo"


def event(source=SOURCE):
    return {
        "workflow_run": {
            "head_sha": source,
            "conclusion": "success",
            "event": "push",
            "head_repository": {"full_name": REPOSITORY},
        }
    }


def mock_api(monkeypatch, current, branch="main"):
    calls = []

    def api(path):
        calls.append(path)
        if path == f"repos/{REPOSITORY}":
            return {"default_branch": branch}
        return {"object": {"sha": current}}

    monkeypatch.setattr(eligibility, "api", api)
    return calls


def test_matching_tested_revision_is_eligible(monkeypatch):
    calls = mock_api(monkeypatch, SOURCE)
    report = eligibility.check_eligibility(REPOSITORY, "workflow_run", event(), OTHER)
    assert report["eligible"] is True
    assert report["sourceSha"] == SOURCE
    assert calls == [f"repos/{REPOSITORY}", f"repos/{REPOSITORY}/git/ref/heads/main"]


def test_stale_event_is_skipped_even_when_top_level_sha_matches_live_main(monkeypatch):
    mock_api(monkeypatch, OTHER)
    report = eligibility.check_eligibility(REPOSITORY, "workflow_run", event(), OTHER)
    assert report["eligible"] is False
    assert report["sourceSha"] == SOURCE
    assert report["currentSha"] == OTHER
    assert "skipped" in report["reason"]


def test_lookup_failure_is_not_publication_permission(monkeypatch):
    def fail(path):
        raise subprocess.CalledProcessError(1, ["gh", "api", path])

    monkeypatch.setattr(eligibility, "api", fail)
    with pytest.raises(subprocess.CalledProcessError):
        eligibility.check_eligibility(REPOSITORY, "workflow_run", event())


@pytest.mark.parametrize("current", [None, "", "not-a-sha"])
def test_invalid_ref_response_fails_closed(monkeypatch, current):
    mock_api(monkeypatch, current)
    with pytest.raises(RuntimeError, match="valid commit SHA"):
        eligibility.check_eligibility(REPOSITORY, "workflow_run", event())


def test_missing_workflow_run_source_never_falls_back_to_context_sha(monkeypatch):
    with pytest.raises(RuntimeError, match="exact source SHA"):
        eligibility.check_eligibility(REPOSITORY, "workflow_run", event(None), SOURCE)


def test_manual_dispatch_preserves_selected_revision_check(monkeypatch):
    mock_api(monkeypatch, SOURCE)
    assert eligibility.check_eligibility(REPOSITORY, "workflow_dispatch", {}, SOURCE)["eligible"]
    assert not eligibility.check_eligibility(REPOSITORY, "workflow_dispatch", {}, OTHER)["eligible"]


def test_live_default_branch_is_not_hard_coded(monkeypatch):
    calls = mock_api(monkeypatch, SOURCE, branch="release/current")
    assert eligibility.check_eligibility(REPOSITORY, "workflow_run", event())["eligible"]
    assert calls[-1].endswith("/git/ref/heads/release%2Fcurrent")


@pytest.mark.parametrize(
    "field,value",
    [
        ("conclusion", "failure"),
        ("event", "pull_request"),
        ("head_repository", {"full_name": "someone/fork"}),
    ],
)
def test_ineligible_events_are_rejected_before_lookups(monkeypatch, field, value):
    payload = event()
    payload["workflow_run"][field] = value
    calls = mock_api(monkeypatch, SOURCE)
    with pytest.raises(RuntimeError, match="eligible"):
        eligibility.check_eligibility(REPOSITORY, "workflow_run", payload)
    assert calls == []


def test_workflow_serializes_and_gates_exact_source_checkout():
    text = (ROOT / ".github/workflows/public-cloudflare.yml").read_text()
    workflow = yaml.safe_load(text)
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"] == {
        "group": "public-cloudflare",
        "cancel-in-progress": False,
        "queue": "max",
    }
    gate = workflow["jobs"]["eligibility"]
    deploy = workflow["jobs"]["deploy"]
    assert deploy["needs"] == "eligibility"
    assert "needs.eligibility.outputs.eligible == 'true'" in deploy["if"]
    for job in (gate, deploy):
        condition = job["if"]
        assert "CLOUDFLARE_PUBLIC_DEPLOY_ENABLED == 'true'" in condition
        assert "github.event.workflow_run.conclusion == 'success'" in condition
        assert "github.event.workflow_run.event == 'push'" in condition
        assert (
            "github.event.workflow_run.head_repository.full_name == github.repository" in condition
        )
        assert "github.event_name == 'workflow_dispatch' && github.ref == format(" in condition
    checkout = deploy["steps"][0]
    assert checkout["with"]["ref"] == "${{ needs.eligibility.outputs.source_sha }}"
    assert "check_public_deploy_eligibility.py" in str(gate["steps"])
    assert "CLOUDFLARE_API_TOKEN" not in str(gate)


def test_source_becoming_stale_during_build_is_rejected_by_second_check(monkeypatch):
    mock_api(monkeypatch, SOURCE)
    assert eligibility.check_eligibility(REPOSITORY, "workflow_run", event())["eligible"]
    mock_api(monkeypatch, OTHER)
    assert not eligibility.check_eligibility(
        REPOSITORY, "workflow_run", event(), checkout_sha=SOURCE
    )["eligible"]


def test_late_check_rejects_actual_checkout_mismatch_before_lookups(monkeypatch):
    calls = mock_api(monkeypatch, SOURCE)
    with pytest.raises(RuntimeError, match="Actual checkout"):
        eligibility.check_eligibility(REPOSITORY, "workflow_run", event(), checkout_sha=OTHER)
    assert calls == []


def test_late_guard_precedes_all_mutable_publication_and_smoke_steps():
    workflow = yaml.safe_load((ROOT / ".github/workflows/public-cloudflare.yml").read_text())
    steps = workflow["jobs"]["deploy"]["steps"]
    gate_index = next(i for i, step in enumerate(steps) if step.get("id") == "publish_revision")
    assert "--checkout-sha" in steps[gate_index]["run"]
    publication = [
        "Archive immutable snapshots to R2",
        "Deploy Worker",
        "Select smoke origin",
        "Smoke deployed Worker",
    ]
    for name in publication:
        index = next(i for i, step in enumerate(steps) if step.get("name") == name)
        assert index > gate_index
        assert "steps.publish_revision.outputs.eligible == 'true'" in steps[index]["if"]


def test_publication_requires_matching_archive_before_restoration_and_never_skips_upload():
    workflow = yaml.safe_load((ROOT / ".github/workflows/public-cloudflare.yml").read_text())
    steps = workflow["jobs"]["deploy"]["steps"]
    named = {step.get("name"): step for step in steps}
    preflight = named["Require and render snapshot archive binding"]
    assert "--require-archive" in preflight["run"]
    assert (
        "vars.DOTREPO_PUBLIC_R2_ARCHIVE_BUCKET"
        in preflight["env"]["DOTREPO_PUBLIC_R2_ARCHIVE_BUCKET"]
    )
    assert steps.index(preflight) < steps.index(
        named["Restore deployed snapshot and append-only history"]
    )
    archive = named["Archive immutable snapshots to R2"]
    assert archive["if"] == "steps.publish_revision.outputs.eligible == 'true'"
    assert "--require-complete-history" in archive["run"]
    assert '--config "$RUNNER_TEMP/dotrepo-wrangler.json"' in named["Deploy Worker"]["run"]
    retained = named["Retain reviewed publication inputs"]
    assert retained["if"] == "always()"
    assert "release-gate/public/v0/snapshots/" in retained["with"]["path"]


def test_history_recovery_binds_original_exporters_and_serializes_with_publication():
    workflow = yaml.safe_load((ROOT / ".github/workflows/public-archive-recovery.yml").read_text())
    public = yaml.safe_load((ROOT / ".github/workflows/public-cloudflare.yml").read_text())
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"] == public["concurrency"]
    job = workflow["jobs"]["recover"]
    assert "github.event.repository.default_branch" in job["if"]
    assert "vars.DOTREPO_PUBLIC_R2_ARCHIVE_BUCKET != ''" in job["if"]
    steps = {step.get("name"): step for step in job["steps"]}
    build = steps["Build each original deployment exporter"]["run"]
    assert "entryExporters" in build and '"--locked"' in build
    assert "cwd=source" in build and "Path(sys.argv[1]).resolve()" in build
    recover = steps["Reconstruct and validate every frozen published payload"]["run"]
    assert "--exporter-root" in recover and "--dotrepo-bin" not in recover
    assert steps["Retain recovery evidence and verified payloads"]["if"] == "always()"
    root = ROOT / "docs/archive/public-history-recovery-20261006"
    plan = json.loads((root / "plan.json").read_bytes())
    log_bytes = (root / "published-log.json").read_bytes()
    assert hashlib.sha256(log_bytes).hexdigest() == plan["publishedLogSha256"]
    entries = json.loads(log_bytes)["entries"]
    assert set(plan["entryExporters"]) == {entry["snapshotId"] for entry in entries}
    for entry in entries:
        pin = plan["entryExporters"][entry["snapshotId"]]
        assert len(pin["commit"]) == 40 and all(ch in "0123456789abcdef" for ch in pin["commit"])
        assert pin["runUrl"].endswith(f"/actions/runs/{pin['runId']}")
        assert entry["snapshotDigest"] in plan["sources"]


@pytest.mark.parametrize("result", ["matched", "stale", "lookup-failure"])
def test_cli_outputs_verified_sha_and_never_allows_lookup_failure(monkeypatch, tmp_path, result):
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event()))
    output_path = tmp_path / "outputs"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_public_deploy_eligibility.py",
            "--repository",
            REPOSITORY,
            "--event-name",
            "workflow_run",
            "--event-path",
            str(event_path),
            "--dispatch-sha",
            OTHER,
            "--github-output",
            str(output_path),
        ],
    )
    if result == "lookup-failure":

        def fail(path):
            raise subprocess.CalledProcessError(1, ["gh", "api", path])

        monkeypatch.setattr(eligibility, "api", fail)
        with pytest.raises(subprocess.CalledProcessError):
            eligibility.main()
        assert not output_path.exists()
    else:
        mock_api(monkeypatch, SOURCE if result == "matched" else OTHER)
        assert eligibility.main() == 0
        outputs = output_path.read_text()
        assert f"source_sha={SOURCE}" in outputs
        assert ("eligible=true" if result == "matched" else "eligible=false") in outputs
