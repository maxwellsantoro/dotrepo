#!/usr/bin/env -S uv run python
"""Report build/test/security coverage gaps by ecosystem for quality hardening.

Produces a ranked list of non-complete execution/security records so operators
can prioritize recrawls where parsers already support the ecosystem (manifest
files present in evidence) versus honest absence.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from language_family import LANGUAGE_FAMILIES, inferred_language_family  # noqa: E402

SCHEMA = "dotrepo/coverage-gaps/v0.1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-root", default="index")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--output-json")
    parser.add_argument("--output-md")
    return parser.parse_args()


def present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() != "unknown"
    if isinstance(value, list):
        return len(value) > 0
    return True


def analyze_record(path: Path, document: dict[str, Any]) -> dict[str, Any]:
    # path is .../repos/host/owner/repo/record.toml
    parts = path.parts
    try:
        repos_idx = parts.index("repos")
        host, owner, repo = parts[repos_idx + 1 : repos_idx + 4]
        identity = f"{host}/{owner}/{repo}"
    except (ValueError, IndexError):
        identity = str(path)
        host = owner = repo = ""

    record = document.get("record") or {}
    repo_block = document.get("repo") or {}
    owners = document.get("owners") or {}
    has_build = present(repo_block.get("build"))
    has_test = present(repo_block.get("test"))
    has_security = present(owners.get("security_contact"))
    has_build_candidates = present(repo_block.get("build_candidates"))
    has_test_candidates = present(repo_block.get("test_candidates"))
    toolchain = repo_block.get("toolchain") or {}
    return {
        "identity": identity,
        "host": host,
        "owner": owner,
        "repo": repo,
        "status": record.get("status"),
        "family": inferred_language_family(document),
        "missingBuild": not has_build,
        "missingTest": not has_test,
        "missingSecurity": not has_security,
        "hasBuildCandidates": has_build_candidates,
        "hasTestCandidates": has_test_candidates,
        "honestExecutionAbstention": (not has_build and has_build_candidates)
        or (not has_test and has_test_candidates),
        "toolchainEcosystem": toolchain.get("ecosystem") if isinstance(toolchain, dict) else None,
    }


def build_report(index_root: Path, *, limit: int) -> dict[str, Any]:
    repos_root = index_root / "repos"
    records = []
    for path in sorted(repos_root.glob("*/*/*/record.toml")):
        document = tomllib.loads(path.read_text())
        records.append(analyze_record(path, document))

    totals = {
        "records": len(records),
        "missingBuild": sum(1 for r in records if r["missingBuild"]),
        "missingTest": sum(1 for r in records if r["missingTest"]),
        "missingSecurity": sum(1 for r in records if r["missingSecurity"]),
        "honestExecutionAbstention": sum(1 for r in records if r["honestExecutionAbstention"]),
        "missingToolchainEcosystem": sum(1 for r in records if not present(r.get("toolchainEcosystem"))),
    }

    by_family: dict[str, dict[str, int]] = {}
    for family in LANGUAGE_FAMILIES:
        family_records = [r for r in records if r["family"] == family]
        by_family[family] = {
            "records": len(family_records),
            "missingBuild": sum(1 for r in family_records if r["missingBuild"]),
            "missingTest": sum(1 for r in family_records if r["missingTest"]),
            "missingSecurity": sum(1 for r in family_records if r["missingSecurity"]),
            "honestExecutionAbstention": sum(
                1 for r in family_records if r["honestExecutionAbstention"]
            ),
        }

    # Prioritize: missing both build and test, not honest abstention, verified preferred.
    def priority(entry: dict[str, Any]) -> tuple:
        return (
            0 if entry["missingBuild"] and entry["missingTest"] else 1,
            0 if not entry["honestExecutionAbstention"] else 1,
            0 if entry["status"] == "verified" else 1,
            entry["identity"],
        )

    candidates = [
        r
        for r in records
        if (r["missingBuild"] or r["missingTest"]) and not r["honestExecutionAbstention"]
    ]
    candidates.sort(key=priority)

    return {
        "schema": SCHEMA,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "totals": totals,
        "byFamily": by_family,
        "recrawlCandidates": candidates[:limit],
        "guidance": [
            "Recrawl candidates lack build/test and do not already carry candidate arrays.",
            "Prefer repositories whose evidence mentions manifests the importer already parses.",
            "Security gaps are often honest absence; do not invent contacts to improve rates.",
            "Honest multi-ecosystem abstentions should keep build_candidates/test_candidates.",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    totals = report["totals"]
    lines = [
        "# Coverage gaps",
        "",
        f"- schema: `{report['schema']}`",
        f"- generated at: `{report['generatedAt']}`",
        f"- records: {totals['records']}",
        f"- missing build: {totals['missingBuild']}",
        f"- missing test: {totals['missingTest']}",
        f"- missing security: {totals['missingSecurity']}",
        f"- honest execution abstention: {totals['honestExecutionAbstention']}",
        f"- missing toolchain.ecosystem: {totals['missingToolchainEcosystem']}",
        "",
        "## By language family",
        "",
        "| family | records | missing build | missing test | missing security | abstention |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for family in LANGUAGE_FAMILIES:
        row = report["byFamily"][family]
        lines.append(
            f"| {family} | {row['records']} | {row['missingBuild']} | {row['missingTest']} | "
            f"{row['missingSecurity']} | {row['honestExecutionAbstention']} |"
        )
    lines.extend(["", "## Recrawl candidates", "", "| identity | status | family | missing |", "| --- | --- | --- | --- |"])
    for entry in report["recrawlCandidates"]:
        missing = []
        if entry["missingBuild"]:
            missing.append("build")
        if entry["missingTest"]:
            missing.append("test")
        lines.append(
            f"| `{entry['identity']}` | {entry['status']} | {entry['family']} | {', '.join(missing)} |"
        )
    if not report["recrawlCandidates"]:
        lines.append("| _(none)_ |  |  |  |")
    lines.append("")
    for item in report["guidance"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    report = build_report(Path(args.index_root), limit=args.limit)
    markdown = render_markdown(report)
    if args.output_json:
        path = Path(args.output_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.output_md:
        path = Path(args.output_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown)
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
