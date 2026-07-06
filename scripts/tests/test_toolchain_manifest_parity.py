from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "check_toolchain_manifest_parity.py"
SPEC = importlib.util.spec_from_file_location("check_toolchain_manifest_parity", SCRIPT)
parity = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(parity)


def write_root(root: Path, *, cargo_msrv: str | None, repo_msrv: str | None) -> None:
    cargo_version = f'rust-version = "{cargo_msrv}"\n' if cargo_msrv is not None else ""
    root.joinpath("Cargo.toml").write_text(
        f"""
[workspace]

[workspace.package]
version = "0.0.0"
edition = "2021"
{cargo_version}
""".lstrip(),
        encoding="utf-8",
    )

    repo_toolchain = (
        f"""
[repo.toolchain]
min = "{repo_msrv}"
ecosystem = "Rust"
""".rstrip()
        if repo_msrv is not None
        else ""
    )
    root.joinpath(".repo").write_text(
        f"""
schema = "dotrepo/v0.1"

[repo]
name = "dotrepo"
description = "test"
{repo_toolchain}
""".lstrip(),
        encoding="utf-8",
    )


def test_check_accepts_matching_msrv(tmp_path: Path) -> None:
    write_root(tmp_path, cargo_msrv="1.90.0", repo_msrv="1.90.0")

    assert parity.check(tmp_path) == []


def test_check_reports_mismatched_msrv(tmp_path: Path) -> None:
    write_root(tmp_path, cargo_msrv="1.90.0", repo_msrv="1.89.0")

    assert parity.check(tmp_path) == [
        "Cargo.toml workspace.package.rust-version (1.90.0) does not match "
        ".repo repo.toolchain.min (1.89.0)"
    ]


def test_check_requires_both_sources(tmp_path: Path) -> None:
    write_root(tmp_path, cargo_msrv=None, repo_msrv=None)

    assert parity.check(tmp_path) == [
        "Cargo.toml is missing workspace.package.rust-version",
        ".repo is missing repo.toolchain.min",
    ]
