from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "check_release_version.py"
SPEC = importlib.util.spec_from_file_location("check_release_version", SCRIPT)
release_version = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(release_version)


def write_root(
    root: Path,
    *,
    workspace_version: str = "2.0.0-alpha.0",
    dependency_version: str | None = None,
    alias_version: str | None = None,
    alias_dependency_version: str | None = None,
) -> None:
    dependency_version = dependency_version or workspace_version
    alias_version = alias_version or workspace_version
    alias_dependency_version = alias_dependency_version or workspace_version
    members = ["dotrepo-schema", "dotrepo-core", "dotrepo-crawler"]

    root.joinpath("Cargo.toml").write_text(
        f"""
[workspace]
members = [{", ".join(f'"crates/{member}"' for member in members)}]

[workspace.package]
version = "{workspace_version}"

[workspace.dependencies]
dotrepo-core = {{ version = "{dependency_version}", path = "crates/dotrepo-core" }}
dotrepo-schema = {{ version = "{dependency_version}", path = "crates/dotrepo-schema" }}
dotrepo-transport = {{ version = "{dependency_version}", path = "crates/dotrepo-transport" }}
""".lstrip(),
        encoding="utf-8",
    )

    for member in members:
        member_root = root / "crates" / member
        member_root.mkdir(parents=True)
        member_root.joinpath("Cargo.toml").write_text(
            f"""
[package]
name = "{member}"
version.workspace = true
""".lstrip(),
            encoding="utf-8",
        )

    alias_root = root / "crates/dotrepo"
    alias_root.mkdir(parents=True)
    alias_root.joinpath("Cargo.toml").write_text(
        f"""
[package]
name = "dotrepo"
version = "{alias_version}"

[dependencies]
dotrepo-cli = {{ version = "{alias_dependency_version}", path = "../dotrepo-cli" }}
""".lstrip(),
        encoding="utf-8",
    )


def test_check_accepts_aligned_prerelease_and_tag(tmp_path: Path) -> None:
    write_root(tmp_path)

    version, errors = release_version.check(tmp_path, tag="v2.0.0-alpha.0")

    assert version == "2.0.0-alpha.0"
    assert errors == []


def test_check_reports_internal_and_alias_version_drift(tmp_path: Path) -> None:
    write_root(
        tmp_path,
        dependency_version="1.0.1",
        alias_version="1.0.1",
        alias_dependency_version="1.0.1",
    )

    _, errors = release_version.check(tmp_path)

    assert len(errors) == 5
    assert all("does not match workspace version (2.0.0-alpha.0)" in error for error in errors)


def test_check_requires_workspace_version_inheritance(tmp_path: Path) -> None:
    write_root(tmp_path)
    manifest = tmp_path / "crates/dotrepo-core/Cargo.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "version.workspace = true", 'version = "2.0.0-alpha.0"'
        ),
        encoding="utf-8",
    )

    _, errors = release_version.check(tmp_path)

    assert errors == ["crates/dotrepo-core/Cargo.toml must set package.version.workspace = true"]


def test_check_rejects_tag_mismatch(tmp_path: Path) -> None:
    write_root(tmp_path)

    _, errors = release_version.check(tmp_path, tag="v1.0.1")

    assert errors == ["release tag (v1.0.1) does not match workspace version (v2.0.0-alpha.0)"]


def test_check_rejects_non_semver_workspace_version(tmp_path: Path) -> None:
    write_root(tmp_path, workspace_version="next")

    _, errors = release_version.check(tmp_path)

    assert errors == ["workspace version is not valid SemVer: next"]
