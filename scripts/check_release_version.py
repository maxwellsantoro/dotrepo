#!/usr/bin/env python3
"""Verify that every Rust release surface identifies the same source version."""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path


SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
INTERNAL_DEPENDENCIES = ("dotrepo-core", "dotrepo-schema", "dotrepo-transport")


def load_toml(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing required file: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise SystemExit(f"invalid TOML in {path}: {exc}") from exc


def nonempty_string(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def dependency_version(value: object) -> str | None:
    if isinstance(value, dict):
        return nonempty_string(value.get("version"))
    return nonempty_string(value)


def check(root: Path, *, tag: str | None = None) -> tuple[str | None, list[str]]:
    root_manifest = load_toml(root / "Cargo.toml")
    workspace = root_manifest.get("workspace")
    workspace = workspace if isinstance(workspace, dict) else {}
    package = workspace.get("package")
    package = package if isinstance(package, dict) else {}
    version = nonempty_string(package.get("version"))

    errors: list[str] = []
    if version is None:
        errors.append("Cargo.toml is missing workspace.package.version")
        return None, errors
    if SEMVER.fullmatch(version) is None:
        errors.append(f"workspace version is not valid SemVer: {version}")

    dependencies = workspace.get("dependencies")
    dependencies = dependencies if isinstance(dependencies, dict) else {}
    for name in INTERNAL_DEPENDENCIES:
        actual = dependency_version(dependencies.get(name))
        if actual != version:
            errors.append(
                f"Cargo.toml workspace dependency {name} version ({actual or 'missing'}) "
                f"does not match workspace version ({version})"
            )

    members = workspace.get("members")
    members = members if isinstance(members, list) else []
    for member in members:
        if not isinstance(member, str):
            errors.append("Cargo.toml workspace.members contains a non-string entry")
            continue
        member_manifest = load_toml(root / member / "Cargo.toml")
        member_package = member_manifest.get("package")
        member_package = member_package if isinstance(member_package, dict) else {}
        inherited = member_package.get("version")
        if inherited != {"workspace": True}:
            errors.append(f"{member}/Cargo.toml must set package.version.workspace = true")

    alias_manifest = load_toml(root / "crates/dotrepo/Cargo.toml")
    alias_package = alias_manifest.get("package")
    alias_package = alias_package if isinstance(alias_package, dict) else {}
    alias_version = nonempty_string(alias_package.get("version"))
    if alias_version != version:
        errors.append(
            "crates/dotrepo/Cargo.toml package version "
            f"({alias_version or 'missing'}) does not match workspace version ({version})"
        )

    alias_dependencies = alias_manifest.get("dependencies")
    alias_dependencies = alias_dependencies if isinstance(alias_dependencies, dict) else {}
    alias_cli_version = dependency_version(alias_dependencies.get("dotrepo-cli"))
    if alias_cli_version != version:
        errors.append(
            "crates/dotrepo/Cargo.toml dotrepo-cli dependency version "
            f"({alias_cli_version or 'missing'}) does not match workspace version ({version})"
        )

    if tag is not None and tag != f"v{version}":
        errors.append(f"release tag ({tag}) does not match workspace version (v{version})")

    return version, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Repository root containing the workspace and standalone alias package.",
    )
    parser.add_argument(
        "--tag",
        help="Optional release tag, which must exactly equal v<workspace version>.",
    )
    args = parser.parse_args(argv)

    version, errors = check(args.root, tag=args.tag)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    suffix = f" and release tag {args.tag}" if args.tag is not None else ""
    print(f"release version surfaces match: {version}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
