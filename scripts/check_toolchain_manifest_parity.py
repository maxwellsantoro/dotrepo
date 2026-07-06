#!/usr/bin/env python3
"""Check that dotrepo's native manifest agrees with Cargo's MSRV metadata."""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path


def load_toml(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing required file: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise SystemExit(f"invalid TOML in {path}: {exc}") from exc


def workspace_rust_version(cargo_toml: dict) -> str | None:
    workspace = cargo_toml.get("workspace")
    if not isinstance(workspace, dict):
        return None
    package = workspace.get("package")
    if not isinstance(package, dict):
        return None
    value = package.get("rust-version")
    return value if isinstance(value, str) and value.strip() else None


def manifest_toolchain_min(manifest: dict) -> str | None:
    repo = manifest.get("repo")
    if not isinstance(repo, dict):
        return None
    toolchain = repo.get("toolchain")
    if not isinstance(toolchain, dict):
        return None
    value = toolchain.get("min")
    return value if isinstance(value, str) and value.strip() else None


def check(root: Path) -> list[str]:
    cargo_msrv = workspace_rust_version(load_toml(root / "Cargo.toml"))
    repo_msrv = manifest_toolchain_min(load_toml(root / ".repo"))

    errors: list[str] = []
    if cargo_msrv is None:
        errors.append("Cargo.toml is missing workspace.package.rust-version")
    if repo_msrv is None:
        errors.append(".repo is missing repo.toolchain.min")
    if cargo_msrv is not None and repo_msrv is not None and cargo_msrv != repo_msrv:
        errors.append(
            "Cargo.toml workspace.package.rust-version "
            f"({cargo_msrv}) does not match .repo repo.toolchain.min ({repo_msrv})"
        )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Repository root containing Cargo.toml and .repo.",
    )
    args = parser.parse_args(argv)

    errors = check(args.root)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    cargo_msrv = workspace_rust_version(load_toml(args.root / "Cargo.toml"))
    print(f"toolchain metadata matches: {cargo_msrv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
