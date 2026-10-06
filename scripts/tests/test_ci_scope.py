from __future__ import annotations

import json
import ast
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from classify_ci_scope import FULL, SCOPED_JOBS, changed_paths, classify_paths, main  # noqa: E402


def selected(paths):
    result = classify_paths(paths)
    assert set(result) == set(SCOPED_JOBS.values())
    assert set(result.values()) <= {"true", "false"}
    return {job for job, output in SCOPED_JOBS.items() if result[output] == "true"}


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (["README.md"], {"minimal-gate"}),
        (["docs/agent-execution.md", "docs/archive/old-review.md"], {"minimal-gate"}),
        (["scripts/audit_index_sample.py"], {"python-gate"}),
        (["scripts/tests/test_external_consumer_lookup.py"], {"python-gate"}),
        (["benchmarks/head-to-head/bench/own_projects.py"], {"python-gate"}),
        (["benchmarks/head-to-head/results/packet/results.json"], {"python-gate"}),
        (
            ["examples/external-consumer/lookup_before_scrape.py"],
            {"python-gate", "public-surface-gate"},
        ),
        (["scripts/render_public_pages_landing.py"], {"python-gate", "public-surface-gate"}),
        (["scripts/fixtures/public_quality_baseline.json"], {"python-gate", "public-surface-gate"}),
        (["cloudflare/hosted-query/src/index.mjs"], {"python-gate", "public-surface-gate"}),
        (["editors/vscode/extension.js"], {"python-gate", "release-gate"}),
        (["scripts/package_release_binaries.py"], {"python-gate", "release-gate"}),
        (["scripts/check_operator_claim_gate.py"], {"python-gate", "operator-gate"}),
        (["index/repos/github.com/o/r/record.toml"], {"public-surface-gate"}),
        (
            ["index/repos/github.com/o/r/claims/id/events.jsonl"],
            {"public-surface-gate", "operator-gate"},
        ),
        (["crates/dotrepo-core/src/public/export.rs"], FULL),
        (["crates/dotrepo-schema/src/lib.rs"], FULL),
        (["crates/new-crate/src/lib.rs"], FULL),
        (["docs/install.md"], FULL),
        (["docs/public-api-compatibility.md"], FULL),
        (["rfcs/0001-protocol.md"], FULL),
        (["examples/native-minimal/README.md"], FULL),
        ([".github/workflows/ci.yml"], FULL),
        (["scripts/classify_ci_scope.py"], FULL),
        (["uv.lock"], FULL),
        (["pyproject.toml"], FULL),
        (["Cargo.lock"], FULL),
        (["scripts/process_resources.py"], FULL),
        (["new-family/unknown.md"], FULL),
        (["../README.md"], FULL),
        ([], FULL),
        (["README.md", "scripts/audit_index_sample.py"], {"python-gate"}),
        (
            ["scripts/render_public_pages_landing.py", "editors/vscode/extension.js"],
            {"python-gate", "release-gate"},
        ),
    ],
)
def test_owned_routes_unknown_paths_and_mixed_dependencies(paths, expected):
    assert selected(paths) == expected


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def test_real_diff_includes_deleted_and_renamed_paths_and_fails_on_missing_commit(tmp_path):
    git(tmp_path, "init", "--quiet")
    git(tmp_path, "config", "user.name", "CI fixture")
    git(tmp_path, "config", "user.email", "ci@example.invalid")
    (tmp_path / "unknown-contract.toml").write_text("data\n")
    (tmp_path / "README.md").write_text("docs\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "--quiet", "-m", "base")
    base = git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "unknown-contract.toml").rename(tmp_path / "CHANGELOG.md")
    (tmp_path / "README.md").unlink()
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "--quiet", "-m", "rename")
    head = git(tmp_path, "rev-parse", "HEAD")
    assert changed_paths(tmp_path, head, head) == []
    paths = changed_paths(tmp_path, base, head)
    assert set(paths) == {"unknown-contract.toml", "CHANGELOG.md", "README.md"}
    assert selected(paths) == FULL
    with pytest.raises(subprocess.CalledProcessError):
        changed_paths(tmp_path, "f" * 40, head)
    with pytest.raises(ValueError):
        changed_paths(tmp_path, "--unsafe", head)


def test_github_entrypoint_writes_complete_plan_and_does_not_hide_diff_failure(
    tmp_path, monkeypatch
):
    import classify_ci_scope

    event = tmp_path / "event.json"
    event.write_text(json.dumps({"before": "1" * 40}))
    output, summary = tmp_path / "output", tmp_path / "summary"
    for key, value in {
        "GITHUB_EVENT_PATH": str(event),
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_SHA": "2" * 40,
        "GITHUB_OUTPUT": str(output),
        "GITHUB_STEP_SUMMARY": str(summary),
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(sys, "argv", ["classify_ci_scope.py", "--github"])
    monkeypatch.setattr(classify_ci_scope, "changed_paths", lambda *args: ["README.md"])
    assert main() == 0
    assert output.read_text().splitlines() == [
        f"{key}={value}" for key, value in classify_paths(["README.md"]).items()
    ]
    output.unlink()

    def failed(*args):
        raise subprocess.CalledProcessError(1, ["git", "diff"])

    monkeypatch.setattr(classify_ci_scope, "changed_paths", failed)
    with pytest.raises(subprocess.CalledProcessError):
        main()
    assert not output.exists()


def test_workflow_scheduling_cache_and_narrow_jobs_preserve_required_checks():
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    assert "github.event.pull_request.number || github.run_id" in workflow["concurrency"]["group"]
    assert (
        workflow["concurrency"]["cancel-in-progress"]
        == "${{ github.event_name == 'pull_request' }}"
    )
    jobs = workflow["jobs"]
    assert set(jobs["change-scope"]["outputs"]) == set(SCOPED_JOBS.values())
    for job in SCOPED_JOBS:
        assert jobs[job]["needs"] == "change-scope"
    minimal = "\n".join(step.get("run", "") for step in jobs["minimal-gate"]["steps"])
    assert "--root . validate" in minimal
    assert "cargo test" not in minimal and "clippy" not in minimal and "pytest" not in minimal
    python = "\n".join(step.get("run", "") for step in jobs["python-gate"]["steps"])
    rust = "\n".join(step.get("run", "") for step in jobs["rust-and-index"]["steps"])
    assert (
        "uv run pytest --durations=15" in python and "cargo build --locked -p dotrepo-cli" in python
    )
    assert "uv run pytest" not in rust and "cargo test --workspace" in rust
    release = jobs["release-gate"]
    cache = next(
        step for step in release["steps"] if step.get("name") == "Cache pinned Playwright browsers"
    )
    assert "runner.os" in cache["with"]["key"] and "runner.arch" in cache["with"]["key"]
    assert "env.PLAYWRIGHT_VERSION" in cache["with"]["key"]
    install = next(
        step for step in release["steps"] if step.get("name") == "Install pinned browser test tools"
    )
    assert '"playwright@$PLAYWRIGHT_VERSION"' in install["run"]
    assert "install --with-deps chromium" in install["run"]
    assert "if" not in install  # System dependencies are installed even on a cache hit.
    for job in ["release-gate", "public-surface-gate"]:
        timing = next(
            step for step in jobs[job]["steps"] if step.get("name") == "Upload gate timings"
        )
        assert timing["if"] == "always()"


def test_release_entrypoints_and_their_local_imports_require_public_validation():
    # Detect drift when a release command gains a helper but the path router
    # still treats changes to that dependency as Python-only.
    pending = [ROOT / "scripts/check_release_gate.py"]
    seen = set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        assert selected([path.relative_to(ROOT).as_posix()]) & {
            "release-gate",
            "public-surface-gate",
        }
        module = ast.parse(path.read_text())
        for node in ast.walk(module):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value.startswith("scripts/") and node.value.endswith(".py"):
                    pending.append(ROOT / node.value)
            names = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            elif isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            for name in names:
                local = ROOT / "scripts" / (name.replace(".", "/") + ".py")
                if local.is_file():
                    pending.append(local)
