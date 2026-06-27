#!/usr/bin/env -S uv run python
"""Capture a checked-in runnable regression fixture from a public repository.

This is the "completion" half of the regression-fixture conveyor described in
``ROADMAP.md`` (Milestone 1 execution order) and
``docs/factual-crawl-automation.md``: a recurring autonomous crawl failure is
emitted as a stub by ``run_autonomous_index_batch.py``; this script turns such a
stub (or any repository identity) into a checked-in, offline-runnable fixture
under ``crates/dotrepo-core/tests/fixtures/regression/<slug>/`` that
``regression_fixture_pack.rs`` replays in ``cargo test`` with no network.

The fixture directory contains only source material (the conventional files the
crawler materializes) plus an ``expectation.json`` pinning the current
deterministic import behavior. Expectations are derived by running the import
pipeline in a throwaway temp copy and parsing the generated ``.repo`` with
``tomllib``, so the fixture directory itself stays free of generated artifacts.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
FIXTURE_ROOT_DEFAULT = (
    Path(__file__).resolve().parent.parent
    / "crates"
    / "dotrepo-core"
    / "tests"
    / "fixtures"
    / "regression"
)

# Same conventional README variants the crawler/importer accept.
README_CANDIDATES = ["README.md", "README.MD", "readme.md", "README.mdx", "README.markdown", "README"]

# Root-level manifest / build files used both for capture and ecosystem inference.
MANIFEST_CANDIDATES = [
    "Cargo.toml",
    "package.json",
    "pyproject.toml",
    "go.mod",
    "setup.py",
    "requirements.txt",
    "Gemfile",
    "composer.json",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "Makefile",
    "Justfile",
    "CMakeLists.txt",
    "mix.exs",
    "rebar.config",
]

CONVENTIONAL_PAIRS = [
    ("CODEOWNERS", ".github/CODEOWNERS"),
    ("SECURITY.md", ".github/SECURITY.md"),
    ("CONTRIBUTING.md", ".github/CONTRIBUTING.md"),
]

MAX_WORKFLOW_FILES = 3


def _load_ecosystem_classifier():
    """Reuse the batch runner's deterministic classifier as the single source of truth."""
    module_path = SCRIPTS_DIR / "run_autonomous_index_batch.py"
    spec = importlib.util.spec_from_file_location("run_autonomous_index_batch", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.classify_ecosystem


classify_ecosystem = _load_ecosystem_classifier()


def select_conventional_files(paths: set[str]) -> list[str]:
    """Pick the conventional file set the importer scans, from a repo path tree."""
    selected: list[str] = []
    for candidate in README_CANDIDATES:
        if candidate in paths:
            selected.append(candidate)
            break
    for root_path, github_path in CONVENTIONAL_PAIRS:
        if root_path in paths:
            selected.append(root_path)
        if github_path in paths:
            selected.append(github_path)
    for candidate in MANIFEST_CANDIDATES:
        if candidate in paths:
            selected.append(candidate)
    workflows = sorted(
        p
        for p in paths
        if p.startswith(".github/workflows/") and (p.endswith(".yml") or p.endswith(".yaml"))
    )
    selected.extend(workflows[:MAX_WORKFLOW_FILES])
    return selected


def infer_ecosystem(filenames: list[str]) -> str:
    return classify_ecosystem(" ".join(filenames))


def _opt(value: object) -> object:
    """Drop empty containers/None so expectation.json stays minimal and honest."""
    if value is None:
        return None
    if isinstance(value, (list, dict, str)) and len(value) == 0:
        return None
    return value


def expectation_from_manifest(
    manifest_text: str,
    *,
    slug: str,
    ecosystem: str,
    overlay_status: str | None = None,
    origin: str | None = None,
    fingerprint: str | None = None,
) -> dict:
    """Build a harness expectation by parsing a generated overlay ``record.toml``."""
    document = tomllib.loads(manifest_text)
    repo = document.get("repo") or {}
    record = document.get("record") or {}
    trust = record.get("trust") or {}
    owners = document.get("owners") or {}
    docs = document.get("docs") or {}

    expectation: dict = {
        "fixture": slug,
        "ecosystem": ecosystem,
        "repo_name": repo.get("name"),
        "repo_description": repo.get("description"),
        "repo_build": _opt(repo.get("build")),
        "repo_test": _opt(repo.get("test")),
        "docs_root": _opt(docs.get("root")),
        "docs_getting_started": _opt(docs.get("getting_started")),
        "maintainers": _opt(owners.get("maintainers")),
        "team": _opt(owners.get("team")),
        "security_contact": _opt(owners.get("security_contact")),
        "overlay_status": overlay_status or record.get("status"),
        "trust_provenance": _opt(trust.get("provenance")),
    }
    if origin:
        expectation["origin"] = origin
    if fingerprint:
        expectation["fingerprint"] = fingerprint
    return {key: value for key, value in expectation.items() if value is not None}


def parse_repo_identity(repo: str) -> tuple[str, str, str]:
    parts = repo.strip("/").split("/")
    if len(parts) != 3:
        raise SystemExit(
            f"--repo must be host/owner/repo (e.g. github.com/BurntSushi/ripgrep), got {repo!r}"
        )
    host, owner, name = parts
    if host != "github.com":
        raise SystemExit(f"only github.com is supported today, got host {host!r}")
    return host, owner, name


def gh_json(args: list[str]) -> object:
    proc = subprocess.run(
        ["gh", *args], check=True, text=True, capture_output=True
    )
    return json.loads(proc.stdout)


def gh_tree_paths(owner: str, repo: str, branch: str) -> set[str]:
    """Fetch the recursive file tree and return the set of repository paths."""
    payload = gh_json(
        ["api", f"repos/{owner}/{repo}/git/trees/{branch}?recursive=1"]
    )
    if not isinstance(payload, dict):
        raise SystemExit(f"unexpected tree response: {payload!r}")
    if payload.get("truncated"):
        raise SystemExit(
            "repository tree is truncated by GitHub; this repo is too large to "
            "capture as a minimal fixture"
        )
    return {
        str(entry.get("path"))
        for entry in payload.get("tree") or []
        if isinstance(entry, dict) and entry.get("type") == "blob" and entry.get("path")
    }


def gh_raw(owner: str, repo: str, path: str, branch: str) -> str:
    proc = subprocess.run(
        [
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github.raw",
            f"repos/{owner}/{repo}/contents/{path}?ref={branch}",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    return proc.stdout


def safe_relative_path(path: str) -> Path:
    if path.startswith("/") or ".." in Path(path).parts:
        raise SystemExit(f"refusing unsafe repository path: {path!r}")
    return Path(path)


def write_fixture_files(dest: Path, files: dict[str, str]) -> None:
    for relative, contents in files.items():
        target = dest / safe_relative_path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents)


def build_cli(args: argparse.Namespace) -> str:
    """Ensure the dotrepo CLI is compiled and return its binary path."""
    manifest_path = SCRIPTS_DIR.parent / "Cargo.toml"
    subprocess.run(
        ["cargo", "build", "-q", "--manifest-path", str(manifest_path), "-p", "dotrepo-cli"],
        check=True,
        text=True,
        capture_output=True,
    )
    binary = manifest_path.parent / "target" / "debug" / "dotrepo"
    if not binary.exists():
        raise SystemExit(f"expected built CLI binary at {binary}")
    return str(binary)


def import_overlay_record(
    binary: str, fixture_files: dict[str, str], *, slug: str, source: str
) -> str:
    """Run overlay import in a throwaway temp copy and return the generated record text.

    Uses overlay mode (the autonomous crawler's import path) so the fixture pins
    the same parser behavior the conveyor relies on. The temp copy keeps the
    checked-in fixture directory free of generated artifacts.

    The temp root's basename is the fixture ``slug`` (not a random ``tempfile``
    name) on purpose: when README title signals are weak the importer falls back
    to ``root.file_name()`` for ``repo.name``. Using the slug makes that fallback
    match the harness, which imports from ``<fixture-root>/<slug>/``.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / slug
        root.mkdir()
        write_fixture_files(root, fixture_files)
        command = [
            binary,
            "--root",
            str(root),
            "import",
            "--mode",
            "overlay",
            "--force",
            "--source",
            source,
        ]
        proc = subprocess.run(command, text=True, capture_output=True)
        if proc.returncode != 0:
            raise SystemExit(
                "overlay import failed while deriving expectations:\n"
                f"{(proc.stderr or proc.stdout).strip()}"
            )
        record = root / "record.toml"
        if not record.is_file():
            raise SystemExit("overlay import did not generate a record.toml")
        return record.read_text()


def capture(args: argparse.Namespace) -> dict:
    host, owner, repo = parse_repo_identity(args.repo)
    identity = f"{host}/{owner}/{repo}"

    meta = gh_json(["api", f"repos/{owner}/{repo}", "--jq", "{default_branch,description}"])
    if not isinstance(meta, dict):
        raise SystemExit(f"unexpected repo metadata response: {meta!r}")
    branch = args.branch or str(meta.get("default_branch") or "")
    if not branch:
        raise SystemExit("could not resolve default branch; pass --branch")

    tree = gh_tree_paths(owner, repo, branch)
    paths = tree
    selected = select_conventional_files(paths)
    if not any(p in README_CANDIDATES or p.upper().startswith("README") for p in selected):
        raise SystemExit("no README surface found; cannot build a meaningful fixture")

    fixture_files = {path: gh_raw(owner, repo, path, branch) for path in selected}
    ecosystem = args.ecosystem or infer_ecosystem(selected)

    dest = Path(args.fixture_root) / args.slug
    if dest.exists() and not args.overwrite:
        raise SystemExit(f"fixture already exists at {dest}; pass --overwrite to replace it")

    binary = build_cli(args)
    overlay_source = f"https://example.com/regression/{args.slug}"
    overlay_record = import_overlay_record(
        binary, fixture_files, slug=args.slug, source=overlay_source
    )
    expectation = expectation_from_manifest(
        overlay_record,
        slug=args.slug,
        ecosystem=ecosystem,
        origin=identity,
        fingerprint=args.fingerprint,
    )

    if args.dry_run:
        return {
            "slug": args.slug,
            "ecosystem": ecosystem,
            "branch": branch,
            "selected_files": selected,
            "destination": str(dest),
            "expectation": expectation,
        }

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    write_fixture_files(dest, fixture_files)
    (dest / "expectation.json").write_text(json.dumps(expectation, indent=2) + "\n")
    return {
        "slug": args.slug,
        "ecosystem": ecosystem,
        "branch": branch,
        "selected_files": selected,
        "destination": str(dest),
        "expectation": expectation,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="host/owner/repo to capture")
    parser.add_argument("--slug", required=True, help="fixture directory name")
    parser.add_argument("--ecosystem", help="override inferred ecosystem")
    parser.add_argument("--fingerprint", help="original failure fingerprint for provenance")
    parser.add_argument("--branch", help="repo branch (default: repo default branch)")
    parser.add_argument(
        "--fixture-root", default=str(FIXTURE_ROOT_DEFAULT), help="regression fixtures root"
    )
    parser.add_argument("--overwrite", action="store_true", help="replace an existing fixture")
    parser.add_argument("--dry-run", action="store_true", help="report without writing files")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = capture(args)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
