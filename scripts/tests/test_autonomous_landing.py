import copy
import importlib.util
from pathlib import Path

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
