#!/usr/bin/env -S uv run python
"""Controlled CLI checks for the 2.0.0-rc.2 preview release; no upstream execution."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib

parser = argparse.ArgumentParser()
parser.add_argument("--bin", type=Path, required=True)
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
binary = args.bin.resolve()
source = args.source.resolve()
version = tomllib.loads((source / "Cargo.toml").read_text())["workspace"]["package"]["version"]
assert version == "2.0.0-rc.2"
results = []


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke(repo, *extra):
    return subprocess.run(
        [
            str(binary),
            "--root",
            str(repo),
            "import",
            "--mode",
            "overlay",
            "--source",
            "https://github.com/example/safety-fixture",
            *extra,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )


fixture_root = source / "crates/dotrepo-core/tests/fixtures/import"
names = {
    "make-diagnostic",
    "make-comment",
    "make-uppercase",
    "make-prerequisite",
    "make-expressions",
    "just-required-argument",
    "just-wrapper",
    "go-compile-only",
    "go-compile-then-runner",
    "rake-root",
    "rake-namespace",
    "rake-nested-namespace",
    "rake-mixed",
    "rake-if-modifier",
    "rake-unless-modifier",
    "rake-if-block",
    "rake-if-quoted-hash",
    "context-repository-tests",
    "context-component-tests",
    "context-component-build",
    "context-wrong-directory",
    "context-prose-prerequisite",
    "context-nextest-selector",
    "command-pagedigest-manifest-path",
    "command-uv-docker",
}
rows = [
    row
    for row in json.loads((fixture_root / "expectations.json").read_text())
    if row["fixture"] in names
]
assert {row["fixture"] for row in rows} == names
for row in rows:
    with tempfile.TemporaryDirectory(prefix="dotrepo-installed-") as tmp:
        repo = Path(tmp)
        shutil.copytree(fixture_root / row["fixture"], repo, dirs_exist_ok=True)
        result = invoke(repo)
        assert result.returncode == 0, result.stderr
        record = tomllib.loads((repo / "record.toml").read_text())["repo"]
        assert record.get("build") == row.get("repo_build"), row["fixture"]
        assert record.get("test") == row.get("repo_test"), row["fixture"]

        def without_nulls(value):
            if isinstance(value, dict):
                return {key: without_nulls(item) for key, item in value.items() if item is not None}
            if isinstance(value, list):
                return [without_nulls(item) for item in value]
            return value

        for field in ["build_candidates", "test_candidates"]:
            assert without_nulls(record.get(field, [])) == without_nulls(
                row.get("repo_" + field, [])
            ), row["fixture"]
        assert "build_context" not in record and "test_context" not in record
        results.append(
            {
                "fixture": row["fixture"],
                "result": "passed",
                "build": record.get("build"),
                "test": record.get("test"),
            }
        )

for name in (
    "readme-escape",
    "readme-contained-link",
    "package-escape",
    "workflow-directory-escape",
    "oversized-readme",
    "directory-readme",
    "fifo-readme",
    "force-symlink",
    "force-hardlink",
):
    with tempfile.TemporaryDirectory(prefix="dotrepo-installed-boundary-") as tmp:
        base = Path(tmp)
        repo = base / "repo"
        repo.mkdir()
        readme = repo / "README.md"
        readme.write_text("# Fixture\n\nOrdinary contained input.\n")
        sentinel = base / "outside"
        sentinel.write_text("# External sentinel\n\nExternal contents must remain unchanged.\n")
        if name.startswith("readme-"):
            readme.unlink()
            if name == "readme-contained-link":
                sentinel = repo / "inside.md"
                sentinel.write_text("# Inside\n\nContained symlinks are unsupported.\n")
            readme.symlink_to(sentinel)
        elif name == "package-escape":
            sentinel.write_text('{"scripts":{"test":"vitest run"}}')
            (repo / "package.json").symlink_to(sentinel)
        elif name == "workflow-directory-escape":
            (repo / ".github").mkdir()
            folder = base / "outside-workflows"
            folder.mkdir()
            (folder / "test.yml").write_text(
                "name: Test\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: pytest -q\n"
            )
            (repo / ".github/workflows").symlink_to(folder)
        elif name == "oversized-readme":
            readme.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
        elif name == "directory-readme":
            readme.unlink()
            readme.mkdir()
        elif name == "fifo-readme":
            readme.unlink()
            os.mkfifo(readme)
        elif name == "force-symlink":
            (repo / "record.toml").symlink_to(sentinel)
        elif name == "force-hardlink":
            os.link(sentinel, repo / "record.toml")
        before = digest(sentinel)
        result = invoke(repo, *(["--force"] if name.startswith("force-") else []))
        assert result.returncode != 0, (name, result.stdout, result.stderr)
        assert digest(sentinel) == before, name
        if not name.startswith("force-"):
            assert not (repo / "record.toml").exists(), name
        results.append(
            {
                "fixture": name,
                "result": "passed",
                "exitCode": result.returncode,
                "sentinelUnchanged": True,
                "diagnostic": result.stderr,
            }
        )

MANIFEST = """schema = "dotrepo/v0.1"
[record]
mode = "native"
status = "draft"
[repo]
name = "fixture"
description = "Fixture project"
[compat.github]
codeowners = "generate"
"""

for kind in ["generate-parent", "generate-leaf", "generate-hardlink", "ci-parent", "init-dangling"]:
    with tempfile.TemporaryDirectory(prefix="dotrepo-installed-output-") as tmp:
        base = Path(tmp)
        repo = base / "checkout"
        outside = base / "outside"
        repo.mkdir()
        outside.mkdir()
        (repo / ".repo").write_text(MANIFEST)
        sentinel = outside / "CODEOWNERS"
        sentinel.write_text("EXTERNAL SENTINEL\n")
        before = digest(sentinel)
        if kind in ["generate-parent", "ci-parent"]:
            (repo / ".github").symlink_to(outside, target_is_directory=True)
        elif kind in ["generate-leaf", "generate-hardlink"]:
            (repo / ".github").mkdir()
            destination = repo / ".github/CODEOWNERS"
            if kind == "generate-leaf":
                destination.symlink_to(sentinel)
            else:
                os.link(sentinel, destination)
        else:
            (repo / ".repo").unlink()
            (repo / ".repo").symlink_to(outside / "missing")
        command = (
            ["ci", "init"]
            if kind == "ci-parent"
            else ["init"]
            if kind == "init-dangling"
            else ["generate"]
        )
        result = subprocess.run(
            [str(binary), "--root", str(repo), *command], capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 1, (kind, result.returncode, result.stderr)
        assert digest(sentinel) == before
        assert not (outside / "workflows").exists()
        assert not (outside / "missing").exists()
        assert not (repo / "README.md").exists()
        results.append(
            {
                "fixture": kind,
                "result": "passed",
                "exitCode": result.returncode,
                "sentinelUnchanged": True,
            }
        )

with tempfile.TemporaryDirectory(prefix="dotrepo-installed-promotion-") as tmp:
    index = Path(tmp) / "index"
    item = index / "repos/github.com/example/sentinel"
    item.mkdir(parents=True)
    (item / "record.toml").write_text("sentinel record")
    (item / "evidence.md").write_text("sentinel evidence")
    before = {path.name: digest(path) for path in item.iterdir()}
    result = subprocess.run(
        [str(binary), "promotion-report", "--index-root", str(index), "--apply"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert before == {path.name: digest(path) for path in item.iterdir()}
    results.append({"fixture": "promotion-no-write", "result": "passed"})

args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(
    json.dumps(
        {
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "binary": str(binary),
            "binarySha256": digest(binary),
            "version": version,
            "versionSource": "Source owner; correlate with package/bundle receipt",
            "sourceCommit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=source, text=True
            ).strip(),
            "results": results,
            "limits": "Controlled local fixtures only; no upstream execution.",
        },
        indent=2,
    )
    + "\n"
)
print(f"{len(results)} controlled installed CLI checks passed")
