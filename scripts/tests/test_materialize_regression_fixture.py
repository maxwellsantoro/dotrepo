from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "materialize_regression_fixture.py"
SPEC = importlib.util.spec_from_file_location("materialize_regression_fixture", SCRIPT)
capture = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(capture)


def test_select_conventional_files_picks_readme_codeowners_security_manifests() -> None:
    paths = {
        "README.md",
        ".github/CODEOWNERS",
        ".github/SECURITY.md",
        ".github/workflows/ci.yml",
        ".github/workflows/release.yml",
        ".github/workflows/nightly.yaml",
        ".github/workflows/extra.yml",
        "Cargo.toml",
        "src/main.rs",
        "docs/something.md",
    }

    selected = capture.select_conventional_files(paths)

    assert "README.md" in selected
    assert ".github/CODEOWNERS" in selected
    assert ".github/SECURITY.md" in selected
    assert "Cargo.toml" in selected
    # Workflow capture is capped so the fixture stays small.
    workflow_selected = [p for p in selected if p.startswith(".github/workflows/")]
    assert len(workflow_selected) == capture.MAX_WORKFLOW_FILES
    assert "src/main.rs" not in selected
    assert "docs/something.md" not in selected


def test_select_conventional_files_takes_first_available_readme_only() -> None:
    selected = capture.select_conventional_files({"README", "README.md", "package.json"})
    assert selected.count("README") + selected.count("README.md") == 1
    assert "package.json" in selected


def test_infer_ecosystem_uses_manifest_signals() -> None:
    assert capture.infer_ecosystem(["Cargo.toml", "README.md"]) == "rust"
    assert capture.infer_ecosystem(["package.json"]) == "node"
    assert capture.infer_ecosystem(["pyproject.toml", "setup.py"]) == "python"
    assert capture.infer_ecosystem(["go.mod"]) == "go"
    assert capture.infer_ecosystem(["README.md"]) == "unknown"


def test_expectation_from_manifest_pins_present_fields_and_drops_absent() -> None:
    manifest = """
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "draft"

[record.trust]
confidence = "medium"
provenance = ["imported"]

[repo]
name = "ripgrep"
description = "recursively search directories"

[owners]
maintainers = ["@burntsushi"]
security_contact = "unknown"
"""
    expectation = capture.expectation_from_manifest(
        manifest,
        slug="rust-readme-only",
        ecosystem="rust",
        overlay_status="imported",
        origin="github.com/BurntSushi/ripgrep",
        fingerprint="Cargo.toml parse error",
        captured_at="2026-03-18T12:00:00Z",
        captured_files=["README.md", "Cargo.toml"],
    )

    assert expectation["fixture"] == "rust-readme-only"
    assert expectation["ecosystem"] == "rust"
    assert expectation["repo_name"] == "ripgrep"
    assert expectation["repo_description"] == "recursively search directories"
    assert "native_status" not in expectation
    assert expectation["overlay_status"] == "imported"
    assert expectation["trust_provenance"] == ["imported"]
    assert expectation["maintainers"] == ["@burntsushi"]
    # Absent fields are omitted entirely so the harness only asserts what exists.
    assert "repo_build" not in expectation
    assert "repo_test" not in expectation
    assert "team" not in expectation
    # security_contact "unknown" is a real string value, not dropped.
    assert expectation["security_contact"] == "unknown"
    assert expectation["origin"] == "github.com/BurntSushi/ripgrep"
    assert expectation["fingerprint"] == "Cargo.toml parse error"
    assert expectation["captured_at"] == "2026-03-18T12:00:00Z"
    assert expectation["captured_files"] == ["README.md", "Cargo.toml"]


def test_parse_repo_identity_rejects_bad_shapes() -> None:
    assert capture.parse_repo_identity("github.com/BurntSushi/ripgrep") == (
        "github.com",
        "BurntSushi",
        "ripgrep",
    )
    try:
        capture.parse_repo_identity("BurntSushi/ripgrep")
    except SystemExit:
        return
    raise AssertionError("expected SystemExit for two-part identity")
