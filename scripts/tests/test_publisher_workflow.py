"""Actual native import/preview/adoption and recurring source review, without execution."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import publisher_workflow as workflow  # noqa: E402

CLI = ROOT / "target/debug/dotrepo"
MCP = ROOT / "target/debug/dotrepo-mcp"


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "minimal"
    root.mkdir()
    (root / "README.md").write_text("# Example\n\nA local example library.\n")
    (root / "package.json").write_text(
        json.dumps({"name": "example", "description": "A local example library.", "license": "MIT"})
    )
    return root


def test_first_setup_and_no_change_use_actual_importer(project):
    before = {path.name: path.read_bytes() for path in project.iterdir()}
    plan = workflow.review(project, CLI, MCP)
    assert plan["state"] == "ready-to-adopt"
    assert plan["derivedFacts"]["repo.name"]
    assert {path.name: path.read_bytes() for path in project.iterdir()} == before
    adopted = workflow.review(project, CLI, MCP, adopt=True)
    assert adopted["adopted"] is True
    native = (project / ".repo").read_bytes()
    repeated = workflow.review(project, CLI, MCP)
    assert repeated["state"] == "unchanged"
    assert repeated["changes"] == []
    assert repeated["checks"]["doctor"]["exitCode"] == 0
    assert repeated["checks"]["preview"]["exitCode"] == 0
    assert (project / ".repo").read_bytes() == native
    for name, body in before.items():
        assert (project / name).read_bytes() == body


def test_source_update_is_reviewed_without_overwriting_native(project):
    workflow.review(project, CLI, MCP, adopt=True)
    native = (project / ".repo").read_bytes()
    (project / "README.md").write_text("# Example\n\nA changed local example library.\n")
    result = workflow.review(project, CLI, MCP)
    assert result["state"] == "needs-review"
    assert any(item["field"] == "repo.description" for item in result["changes"])
    assert (project / ".repo").read_bytes() == native
    with pytest.raises(ValueError, match="absent .repo"):
        workflow.review(project, CLI, MCP, adopt=True)


def test_manifest_scripts_are_derived_without_running_them(project):
    (project / "package.json").write_text(
        json.dumps(
            {
                "name": "acorn-tools",
                "scripts": {"build": "tsc", "test": "node --test"},
                "engines": {"node": ">=22"},
            }
        )
    )
    result = workflow.review(project, CLI, MCP, required=["repo.build", "repo.test"])
    assert "package.json" in result["sourceInputs"]
    assert result["derivedFacts"]["repo.build"] == "npm run build"
    assert result["derivedFacts"]["repo.test"] == "npm test"
    assert not list(project.glob("*.js"))
    assert result["clarifications"] == []


def test_only_required_missing_fields_request_clarification(project):
    result = workflow.review(project, CLI, MCP)
    assert result["clarifications"] == []
    result = workflow.review(project, CLI, MCP, required=["repo.test"])
    assert result["state"] == "needs-clarification"
    assert [item["field"] for item in result["clarifications"]] == ["repo.test"]
    with pytest.raises(ValueError, match="ambiguity"):
        workflow.review(project, CLI, MCP, required=["repo.test"], adopt=True)
    assert not (project / ".repo").exists()


def test_conflicting_documentation_remains_explicit(project):
    (project / "README.md").write_text(
        "# Example\n\nA local example library.\n\n"
        "[Documentation](https://one.example/docs/)\n"
        "[Documentation](https://two.example/docs/)\n"
    )
    result = workflow.review(project, CLI, MCP)
    assert result["state"] == "needs-clarification"
    assert "docs.root" in [item["field"] for item in result["clarifications"]]
    assert not (project / ".repo").exists()


def test_ci_check_reports_unresolved_setup_and_source_drift(project, capsys):
    args = ["--root", str(project), "--check"]
    assert workflow.main(args) == 1
    workflow.review(project, CLI, MCP, adopt=True)
    assert workflow.main(args) == 0
    (project / "README.md").write_text("# Example\n\nChanged purpose.\n")
    assert workflow.main(args) == 1
    capsys.readouterr()
