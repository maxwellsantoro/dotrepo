import copy
import importlib.util
from pathlib import Path
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "land_autonomous_index.py"
SPEC = importlib.util.spec_from_file_location("autonomous_landing", SCRIPT)
landing = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(landing)
BASE, HEAD = "a" * 40, "b" * 40
REPOSITORY = "example/index"


def pull():
    return {
        "state": "open",
        "draft": False,
        "head": {
            "sha": HEAD,
            "ref": "automation/index-autonomous/batch-1",
            "repo": {"full_name": REPOSITORY},
        },
        "base": {"sha": BASE, "ref": "main"},
    }


@pytest.mark.parametrize("change", ["head", "base", "fork", "branch", "draft"])
def test_changed_or_untrusted_pull_is_rejected(change):
    data = pull()
    if change in {"head", "base"}:
        data[change]["sha"] = "c" * 40
    elif change == "fork":
        data["head"]["repo"]["full_name"] = "someone/fork"
    elif change == "branch":
        data["head"]["ref"] = "unrelated"
    else:
        data["draft"] = True
    with pytest.raises(RuntimeError):
        landing.validate_pull(data, REPOSITORY, "main", HEAD, BASE)


@pytest.mark.parametrize("failure", [None, "ci", "base-advanced", "non-index", "renamed-from-code"])
def test_only_successful_exact_commit_checks_allow_fast_forward(monkeypatch, failure):
    calls = []

    def api(path, *, method="GET", body=None):
        calls.append((path, method, copy.deepcopy(body)))
        if path == "repos/example/index":
            return {"default_branch": "main"}
        if path.endswith("/pulls/1"):
            return pull()
        if "/files?" in path:
            if failure == "non-index":
                return [{"filename": "scripts/tool.py"}]
            if failure == "renamed-from-code":
                return [{"filename": "index/tool.py", "previous_filename": "scripts/tool.py"}]
            return [{"filename": "index/repos/github.com/example/demo/record.toml"}]
        if "/actions/runs?" in path:
            return {"workflow_runs": []}
        if "/actions/variables/" in path:
            return {"value": "true"}
        if path.endswith("/dispatches"):
            return {"workflow_run_id": 10 if "ci.yml" in path else 20}
        if method == "GET" and "/git/refs/" in path:
            return {"object": {"sha": "c" * 40 if failure == "base-advanced" else BASE}}
        if method == "PATCH":
            return {"object": {"sha": body["sha"]}}
        raise AssertionError(path)

    waits = []

    def wait(repository, run_id, head, job):
        waits.append((run_id, head, job))
        if failure == "ci":
            raise RuntimeError("CI failed")

    monkeypatch.setattr(landing, "api", api)
    monkeypatch.setattr(landing, "wait_run", wait)
    if failure:
        with pytest.raises(RuntimeError):
            landing.land(REPOSITORY, 1, HEAD, BASE)
        assert not any(method == "PATCH" for _, method, _ in calls)
        assert not any("public-cloudflare" in path for path, _, _ in calls)
    else:
        landing.land(REPOSITORY, 1, HEAD, BASE)
        patches = [body for _, method, body in calls if method == "PATCH"]
        assert patches == [{"sha": HEAD, "force": False}]
        assert waits == [(10, HEAD, "public-surface-gate"), (20, HEAD, "deploy")]


def test_landing_skips_deploy_when_public_deploy_disabled(monkeypatch):
    def api(path, *, method="GET", body=None):
        if path == "repos/example/index":
            return {"default_branch": "main"}
        if path.endswith("/pulls/1"):
            return pull()
        if "/files?" in path:
            return [{"filename": "index/repos/github.com/example/demo/record.toml"}]
        if "/actions/runs?" in path:
            return {"workflow_runs": []}
        if "/actions/variables/" in path:
            return {"value": "false"}
        if path.endswith("/dispatches"):
            return {"workflow_run_id": 10}
        if method == "GET" and "/git/refs/" in path:
            return {"object": {"sha": BASE}}
        if method == "PATCH":
            return {"object": {"sha": body["sha"]}}
        raise AssertionError(path)

    waits = []
    monkeypatch.setattr(landing, "api", api)
    monkeypatch.setattr(landing, "wait_run", lambda *a: waits.append(a))
    landing.land(REPOSITORY, 1, HEAD, BASE)
    assert waits == [(REPOSITORY, 10, HEAD, "public-surface-gate")]


@pytest.mark.parametrize("enabled", [True, False])
def test_explicit_workflow_switch_bypasses_variable_api_and_controls_deploy(monkeypatch, enabled):
    calls = []

    def api(path, *, method="GET", body=None):
        calls.append((path, method))
        assert "/actions/variables/" not in path
        if path == "repos/example/index":
            return {"default_branch": "main"}
        if path.endswith("/pulls/1"):
            return pull()
        if "/files?" in path:
            return [{"filename": "index/repos/github.com/example/demo/record.toml"}]
        if "/actions/runs?" in path:
            return {"workflow_runs": []}
        if path.endswith("/dispatches"):
            return {"workflow_run_id": 10 if "ci.yml" in path else 20}
        if "/git/refs/" in path:
            return {"object": {"sha": HEAD if method == "PATCH" else BASE}}
        raise AssertionError(path)

    waits = []
    monkeypatch.setattr(landing, "api", api)
    monkeypatch.setattr(landing, "wait_run", lambda *args: waits.append(args))
    receipt = {}
    landing.land(REPOSITORY, 1, HEAD, BASE, receipt=receipt, deployment_enabled=enabled)
    assert receipt["publicDeployment"] == {
        "enabled": enabled,
        "source": "explicit-cli",
        "reason": "explicit-true" if enabled else "explicit-false",
    }
    assert receipt["status"] == ("published" if enabled else "landed-deployment-disabled")
    assert receipt["publicationVerified"] is enabled
    assert any("public-cloudflare" in path for path, _ in calls) is enabled
    assert len(waits) == (2 if enabled else 1)


@pytest.mark.parametrize("value,enabled", [("true", True), ("false", False), ("", False)])
def test_manual_switch_fallback_retains_variable_decision(monkeypatch, value, enabled):
    monkeypatch.setattr(landing, "api", lambda path: {"value": value})
    decision = {}
    assert (
        landing.public_deploy_enabled(REPOSITORY, "repos/example/index", decision=decision)
        is enabled
    )
    assert decision["enabled"] is enabled
    assert decision["source"] == "repository-variable-api"
    assert decision["reason"] == ("variable-true" if enabled else "variable-not-true")


@pytest.mark.parametrize("failure", ["404", "403", "network", "malformed", "invalid-value"])
def test_manual_switch_resolution_distinguishes_unset_from_error_before_merge(monkeypatch, failure):
    calls = []

    def api(path, *, method="GET", body=None):
        calls.append((path, method))
        if path == "repos/example/index":
            return {"default_branch": "main"}
        if path.endswith("/pulls/1"):
            return pull()
        if "/actions/variables/" in path:
            if failure in {"404", "403"}:
                raise subprocess.CalledProcessError(
                    1,
                    ["gh", "api", path],
                    output='{"status":"' + failure + '"}',
                    stderr="gh: fixture (HTTP " + failure + ")",
                )
            if failure == "network":
                raise OSError("fixture connection unavailable")
            return {} if failure == "malformed" else {"value": "perhaps"}
        if "/files?" in path:
            return [{"filename": "index/repos/github.com/example/demo/record.toml"}]
        if path.endswith("/dispatches"):
            return {"workflow_run_id": 10}
        if "/actions/runs?" in path:
            return {"workflow_runs": []}
        if "/git/refs/" in path:
            return {"object": {"sha": BASE}}
        raise AssertionError(path)

    monkeypatch.setattr(landing, "api", api)
    monkeypatch.setattr(landing, "wait_run", lambda *args: None)
    receipt = {}
    if failure == "404":
        landing.land(REPOSITORY, 1, HEAD, BASE, receipt=receipt)
        assert receipt["status"] == "landed-deployment-disabled"
        assert receipt["publicDeployment"] == {
            "enabled": False,
            "source": "repository-variable-api",
            "reason": "repository-variable-unset",
            "httpStatus": 404,
        }
    else:
        with pytest.raises(RuntimeError, match="refusing to land"):
            landing.land(REPOSITORY, 1, HEAD, BASE, receipt=receipt)
        assert not any(method == "PATCH" or path.endswith("/dispatches") for path, method in calls)
        assert receipt["publicDeployment"]["enabled"] is None
        assert receipt["publicDeployment"]["reason"] in {
            "variable-read-error",
            "invalid-variable-response",
            "invalid-variable-value",
        }


def test_pending_pull_request_run_is_approved_and_awaited(monkeypatch):
    calls = []

    def api(path, *, method="GET", body=None):
        calls.append((path, method))
        return {"workflow_runs": [{"id": 77, "conclusion": "action_required"}]}

    waits = []
    monkeypatch.setattr(landing, "api", api)
    monkeypatch.setattr(landing, "wait_run", lambda *a: waits.append(a))
    landing.approve_pending_pull_runs(REPOSITORY, "repos/example/index", HEAD)
    assert ("repos/example/index/actions/runs/77/approve", "POST") in calls
    assert waits == [(REPOSITORY, 77, HEAD, "ci-gate")]


@pytest.mark.parametrize("head,job_conclusion", [(BASE, "success"), (HEAD, "skipped")])
def test_success_for_another_commit_or_skipped_job_is_not_publication(
    monkeypatch, head, job_conclusion
):
    monkeypatch.setattr(landing.subprocess, "run", lambda *a, **kw: None)
    monkeypatch.setattr(
        landing,
        "api",
        lambda path: {"jobs": [{"name": "deploy", "conclusion": job_conclusion}]}
        if "/jobs?" in path
        else {"conclusion": "success", "head_sha": head},
    )
    with pytest.raises(RuntimeError):
        landing.wait_run(REPOSITORY, 20, HEAD, "deploy")


@pytest.mark.parametrize(
    "publication,smoke,passed",
    [
        ("success", "success", True),
        ("skipped", "skipped", False),
        ("success", "skipped", False),
        (None, None, False),
    ],
)
def test_green_deploy_job_requires_actual_publication_and_smoke(
    monkeypatch, publication, smoke, passed
):
    monkeypatch.setattr(landing.subprocess, "run", lambda *a, **kw: None)
    steps = (
        []
        if publication is None
        else [
            {"name": "Deploy Worker", "conclusion": publication},
            {"name": "Smoke deployed Worker", "conclusion": smoke},
        ]
    )
    monkeypatch.setattr(
        landing,
        "api",
        lambda path: {"jobs": [{"name": "deploy", "conclusion": "success", "steps": steps}]}
        if "/jobs?" in path
        else {"conclusion": "success", "head_sha": HEAD},
    )
    if passed:
        landing.wait_run(REPOSITORY, 20, HEAD, "deploy")
    else:
        with pytest.raises(RuntimeError, match="Publication step"):
            landing.wait_run(REPOSITORY, 20, HEAD, "deploy")
