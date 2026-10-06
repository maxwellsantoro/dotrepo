#!/usr/bin/env -S uv run python
"""Select CI checks by owned paths; unknown inputs require the full gate."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess

SCOPED_JOBS = {
    "rust-and-index": "run_rust_ci",
    "python-gate": "run_python_gate",
    "operator-gate": "run_operator_gate",
    "public-surface-gate": "run_public_surface_gate",
    "release-gate": "run_release_gate",
    "minimal-gate": "run_minimal_gate",
}
FULL = {"rust-and-index", "python-gate", "operator-gate", "release-gate"}
RUST = {"rust-and-index", "python-gate", "release-gate"}
PYTHON = {"python-gate"}
PUBLIC = {"python-gate", "public-surface-gate"}
RELEASE = {"python-gate", "release-gate"}

# Only explicitly owned prose takes the minimal route. Protocol/installation
# docs, native examples, shared dependencies and new path families remain broad.
PROSE = {
    "README.md",
    "ROADMAP.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/README.md",
    "docs/agent-execution.md",
    "docs/toolchain-maintainability.md",
    "docs/ai-tool-interviews.md",
    "scripts/README.md",
    "benchmarks/head-to-head/README.md",
}
SHARED = {"Cargo.toml", "Cargo.lock", "pyproject.toml", "uv.lock", ".python-version"}
PUBLIC_SCRIPTS = {
    "public_site_content.py",
    "public_product_content.py",
    "language_family.py",
    "sync_cloudflare_public_snapshot.py",
    "restore_cloudflare_public_state.py",
    "archive_public_snapshot_r2.py",
    "render_hosted_query_config.py",
    "recover_public_snapshot_history.py",
    "ensure_public_archive_bucket.py",
    "fetch_pagedigest_baseline.py",
    "public_deploy_http.py",
    "smoke_cloudflare_public_deploy.py",
    "package_public_export.py",
    "diff_public_export_files.py",
    "plan_index_growth_tranche.py",
    "render_index_growth_status.py",
}
RELEASE_SCRIPTS = {
    "check_release_gate.py",
    "gate_timings.py",
    "check_release_version.py",
    "check_toolchain_manifest_parity.py",
    "package_release_binaries.py",
    "package_vscode_extension.py",
    "package_mcpb_bundle.py",
}


def jobs_for_path(path: str) -> set[str]:
    parts = PurePosixPath(path).parts
    if not path or path.startswith("/") or ".." in parts or "\\" in path:
        return FULL.copy()
    if path in SHARED or path.startswith((".cargo/", ".github/workflows/", "rfcs/")):
        return FULL.copy()
    if path in {"scripts/classify_ci_scope.py", "scripts/check_ci_gate.py"}:
        return FULL.copy()
    if path.startswith(("crates/dotrepo-core/", "crates/dotrepo-cli/", "crates/dotrepo-schema/")):
        return FULL.copy()
    if path.startswith(
        (
            "crates/dotrepo-transport/",
            "crates/dotrepo-mcp/",
            "crates/dotrepo-lsp/",
            "crates/dotrepo-crawler/",
            "crates/dotrepo/",
        )
    ):
        return RUST.copy()
    if path in PROSE or (path.startswith("docs/archive/") and path.endswith(".md")):
        return {"minimal-gate"}
    if path.startswith("index/"):
        jobs = {"public-surface-gate"}
        if len(parts) >= 6 and parts[:2] == ("index", "repos") and parts[5] == "claims":
            jobs.add("operator-gate")
        return jobs
    if path.startswith("scripts/tests/") and path.endswith(".py"):
        return PYTHON.copy()
    if path.startswith("scripts/fixtures/"):
        return PUBLIC.copy()
    if path.startswith("scripts/") and path.endswith(".py"):
        name = parts[-1]
        if name in RELEASE_SCRIPTS:
            return RELEASE.copy()
        if name == "check_operator_claim_gate.py":
            return {"python-gate", "operator-gate"}
        if name in PUBLIC_SCRIPTS or name.startswith(
            ("check_public_", "render_public_", "measure_public_", "build_public_")
        ):
            return PUBLIC.copy()
        # Shared subprocess/resource policy is consumed by multiple entrypoints.
        if name in {
            "process_resources.py",
            "materialize_regression_fixture.py",
            "adjudication_openrouter_sidecar.py",
            "openrouter_request_policy.py",
        }:
            return FULL.copy()
        return PYTHON.copy()
    if path == "scripts/check_public_presentation.cjs" or path.startswith("editors/"):
        return RELEASE.copy()
    if path.startswith("cloudflare/"):
        return PUBLIC.copy()
    if path.startswith("examples/external-consumer/"):
        return PUBLIC.copy()
    if path.startswith("benchmarks/head-to-head/"):
        return PYTHON.copy()
    # Remaining docs own executable/protocol contracts; examples can change
    # generated/native fixtures. Do not infer safety from a Markdown suffix.
    return FULL.copy()


def classify_paths(paths: list[str]) -> dict[str, str]:
    selected = set().union(*(jobs_for_path(path) for path in paths)) if paths else FULL.copy()
    if "release-gate" in selected:
        selected.discard("public-surface-gate")  # Complete release includes the public checks.
    if selected != {"minimal-gate"}:
        selected.discard("minimal-gate")  # Every substantive job validates root metadata too.
    return {output: str(job in selected).lower() for job, output in SCOPED_JOBS.items()}


def changed_paths(root: Path, base: str, head: str) -> list[str]:
    for value in (base, head):
        if value and not re.fullmatch(r"[0-9a-f]{40}", value):
            raise ValueError("CI revisions must be full lowercase commit SHAs")
    if not head:
        raise ValueError("missing CI head revision")
    command = (
        ["git", "ls-files", "-z"]
        if not base or base == "0" * 40
        else ["git", "diff", "--no-renames", "--name-only", "-z", base, head]
    )
    # A failed diff must fail classification, never silently select a narrow gate.
    raw = subprocess.check_output(command, cwd=root).decode()
    return raw.rstrip("\0").split("\0") if raw else []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--github", action="store_true")
    args = parser.parse_args()
    base, head = args.base or "", args.head or ""
    if args.github:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
        kind = os.environ["GITHUB_EVENT_NAME"]
        head = os.environ["GITHUB_SHA"]
        if kind == "pull_request":
            base = event["pull_request"]["base"]["sha"]
            head = event["pull_request"]["head"]["sha"]
        elif kind == "workflow_dispatch":
            base = os.environ.get("DISPATCH_BASE_SHA", "")
        elif kind == "push":
            base = event["before"]
        else:
            raise ValueError(f"unsupported CI event: {kind}")
    paths = changed_paths(Path(__file__).resolve().parents[1], base, head)
    outputs = classify_paths(paths)
    print(json.dumps({"changedFiles": paths, "outputs": outputs}, indent=2))
    if args.github:
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as stream:
            stream.writelines(f"{name}={value}\n" for name, value in outputs.items())
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
            stream.write("### Planned validation\n\n")
            stream.writelines(
                f"- `{job}`: {outputs[output]}\n" for job, output in SCOPED_JOBS.items()
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
