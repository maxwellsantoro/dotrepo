from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "materialize_regression_fixture.py"
SPEC = importlib.util.spec_from_file_location("materialize_regression_fixture", SCRIPT)
capture = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(capture)


def assert_exits_with(message: str, func, *args: object) -> None:
    try:
        func(*args)
    except SystemExit as exc:
        assert message in str(exc)
    else:
        raise AssertionError("expected SystemExit")


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
        "Rakefile",
        "CMakePresets.json",
        "Orbit.Tests.csproj",
        "Zeta.csproj",
        "src/Nested.csproj",
        "src/main.rs",
        "docs/something.md",
    }

    selected = capture.select_conventional_files(paths)

    assert "README.md" in selected
    assert ".github/CODEOWNERS" in selected
    assert ".github/SECURITY.md" in selected
    assert "Cargo.toml" in selected
    assert "Rakefile" in selected
    assert "CMakePresets.json" in selected
    assert "Orbit.Tests.csproj" in selected
    assert "Zeta.csproj" not in selected
    assert "src/Nested.csproj" not in selected
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
    assert capture.infer_ecosystem(["pom.xml"]) == "jvm"
    assert capture.infer_ecosystem(["composer.json"]) == "php"
    assert capture.infer_ecosystem(["Orbit.Tests.csproj"]) == "dotnet"
    assert capture.infer_ecosystem(["mix.exs"]) == "elixir"
    assert capture.infer_ecosystem(["rebar.config"]) == "erlang"
    assert capture.infer_ecosystem(["CMakePresets.json"]) == "cpp"
    assert capture.infer_ecosystem(["README.md"]) == "unknown"


def test_captured_file_sha256_hashes_utf8_contents_deterministically() -> None:
    digests = capture.captured_file_sha256({"README.md": "hello"})

    assert digests == {
        "README.md": "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    }


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
        captured_file_sha256={
            "README.md": "a" * 64,
            "Cargo.toml": "b" * 64,
        },
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
    assert expectation["captured_file_sha256"] == {
        "README.md": "a" * 64,
        "Cargo.toml": "b" * 64,
    }


def test_parse_repo_identity_rejects_bad_shapes() -> None:
    assert capture.parse_repo_identity("github.com/BurntSushi/ripgrep") == (
        "github.com",
        "BurntSushi",
        "ripgrep",
    )
    assert_exits_with("host/owner/repo", capture.parse_repo_identity, "BurntSushi/ripgrep")


def test_parse_repo_identity_rejects_unsafe_segments() -> None:
    assert_exits_with(
        "owner must be a safe path segment",
        capture.parse_repo_identity,
        "github.com/../orbit",
    )
    assert_exits_with(
        "repo must be a safe path segment",
        capture.parse_repo_identity,
        "github.com/example/.",
    )
    assert_exits_with(
        "repo must be a safe path segment",
        capture.parse_repo_identity,
        "github.com/example/orbit\\escape",
    )


def test_resolve_capture_args_rejects_unsafe_explicit_slug() -> None:
    assert_exits_with(
        "fixture slug must be nonempty",
        capture.resolve_capture_args,
        capture.parse_args(["--repo", "github.com/example/orbit", "--slug", "../escape"]),
    )


def test_safe_relative_path_rejects_uncontained_capture_paths() -> None:
    assert capture.safe_relative_path(".github/workflows/ci.yml") == Path(
        ".github/workflows/ci.yml"
    )
    for unsafe in ("", "/tmp/escape.yml", "../escape.yml", ".github/../escape.yml"):
        assert_exits_with("refusing unsafe repository path", capture.safe_relative_path, unsafe)


def write_stub(tmp_path: Path, **overrides: object) -> Path:
    stub = tmp_path / "cargo-toml-parse-error"
    stub.mkdir(parents=True)
    metadata = {
        "schema": capture.STUB_SCHEMA,
        "fixture": "cargo-toml-parse-error",
        "failureClass": "parser",
        "ecosystem": "rust",
        "fixtureEligible": True,
        "fingerprint": "Cargo.toml parse error",
        "observedRuns": 2,
        "repositories": ["github.com/example/orbit"],
        "status": "needs_materialization",
    }
    metadata.update(overrides)
    (stub / "metadata.json").write_text(json.dumps(metadata))
    return stub


def test_resolve_capture_args_hydrates_unique_stub_repository(tmp_path: Path) -> None:
    stub = write_stub(tmp_path)

    args = capture.resolve_capture_args(capture.parse_args(["--stub", str(stub)]))

    assert args.repo == "github.com/example/orbit"
    assert args.slug == "cargo-toml-parse-error"
    assert args.ecosystem == "rust"
    assert args.fingerprint == "Cargo.toml parse error"


def test_resolve_capture_args_requires_matching_repository_for_ambiguous_stub(
    tmp_path: Path,
) -> None:
    stub = write_stub(
        tmp_path,
        repositories=[
            "github.com/example/another",
            "github.com/example/orbit",
        ],
    )

    try:
        capture.resolve_capture_args(capture.parse_args(["--stub", str(stub)]))
    except SystemExit as exc:
        assert "lists multiple repositories" in str(exc)
    else:
        raise AssertionError("expected ambiguous stub to require --repo")

    args = capture.resolve_capture_args(
        capture.parse_args(["--stub", str(stub), "--repo", "github.com/example/another"])
    )
    assert args.repo == "github.com/example/another"


def test_resolve_capture_args_rejects_stub_conflicts_and_ineligible_stubs(
    tmp_path: Path,
) -> None:
    stub = write_stub(tmp_path)
    try:
        capture.resolve_capture_args(
            capture.parse_args(["--stub", str(stub), "--ecosystem", "python"])
        )
    except SystemExit as exc:
        assert "conflicts with stub value" in str(exc)
    else:
        raise AssertionError("expected conflicting override to fail")

    ineligible = write_stub(tmp_path / "other", fixtureEligible=False)
    try:
        capture.resolve_capture_args(capture.parse_args(["--stub", str(ineligible)]))
    except SystemExit as exc:
        assert "not eligible" in str(exc)
    else:
        raise AssertionError("expected ineligible stub to fail")
