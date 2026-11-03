"""Review source-derived repository metadata using the existing native toolchain.

The default path is read-only. --adopt bootstraps an absent .repo with the native
importer; existing maintainer declarations are never overwritten by this helper.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_OUTPUT = 2 * 1024 * 1024
FACT_TABLES = ("repo", "docs", "toolchain", "owners")


def run(command, root, *, input_text=None):
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        result = subprocess.run(
            [str(part) for part in command],
            input=None if input_text is None else input_text.encode(),
            cwd=root,
            stdout=stdout,
            stderr=stderr,
            timeout=30,
            check=False,
        )
        if stdout.tell() + stderr.tell() > MAX_OUTPUT:
            raise ValueError("native tool output exceeded the 2 MiB review bound")
        stdout.seek(0)
        stderr.seek(0)
        return {
            "exitCode": result.returncode,
            "stdout": stdout.read().decode(),
            "stderr": stderr.read().decode(),
        }


def import_preview(root, mcp):
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "dotrepo.import_preview",
                "arguments": {"root": ".", "mode": "native"},
            },
        },
    ]
    result = run([mcp], root, input_text="\n".join(map(json.dumps, messages)) + "\n")
    if result["exitCode"]:
        raise ValueError("import preview failed: " + result["stderr"])
    responses = [json.loads(line) for line in result["stdout"].splitlines() if line.strip()]
    response = next((item for item in responses if item.get("id") == 2), {})
    if "error" in response or "result" not in response:
        raise ValueError("import preview failed: " + json.dumps(response))
    tool_result = response["result"]
    if tool_result.get("isError"):
        raise ValueError("import preview failed: " + json.dumps(tool_result))
    return tool_result["structuredContent"]


def facts(manifest):
    """Compare user-facing imported facts, excluding authority and generated evidence."""
    result = {}

    def visit(prefix, value):
        if isinstance(value, dict):
            for key, child in value.items():
                visit(prefix + "." + key, child)
        else:
            result[prefix] = value

    for table in FACT_TABLES:
        visit(table, manifest.get(table, {}))
    return result


def review(root, cli, mcp, *, required=(), adopt=False):
    root, cli, mcp = root.resolve(), cli.resolve(), mcp.resolve()
    if not root.is_dir():
        raise ValueError("repository root must be a directory")
    native = root / ".repo"
    if native.is_symlink():
        raise ValueError("refusing a symlinked native manifest")
    if adopt and native.exists():
        raise ValueError(
            "--adopt only bootstraps an absent .repo; review existing changes manually"
        )
    preview = import_preview(root, mcp)
    derived = facts(preview["manifest"])
    score = preview["fieldScores"]
    unresolved = set(score["unresolved"]) | set(score["suspect"])
    explicit = preview["manifest"].get("x", {}).get("dotrepo", {}).get("field_evidence", {})
    ambiguous = {field for field, value in explicit.items() if value.get("state") == "unresolved"}
    clarifications = []
    for field in sorted(set(required) | ambiguous | set(score["suspect"])):
        if field in ambiguous or field in unresolved or derived.get(field) in (None, "", []):
            clarifications.append(
                {
                    "field": field,
                    "reason": explicit.get(field, {}).get(
                        "reason", "Required fact is missing or unresolved in inspected source."
                    ),
                    "action": "Clarify the owning manifest, CI or documentation; then review again.",
                }
            )
    adopted = False
    if adopt:
        if clarifications:
            raise ValueError("resolve the reported source ambiguity before --adopt")
        imported = run([cli, "--root", root, "import", "--mode", "native"], root)
        if imported["exitCode"]:
            raise ValueError("native import failed: " + imported["stderr"])
        adopted = True
    current = None
    if native.exists():
        with native.open("rb") as stream:
            native_body = stream.read(MAX_OUTPUT + 1)
        if len(native_body) > MAX_OUTPUT:
            raise ValueError("native manifest exceeds the 2 MiB review bound")
        current = tomllib.loads(native_body.decode())
    current_facts = facts(current) if current is not None else {}
    changes = [
        {"field": key, "declared": current_facts.get(key), "sourceDerived": derived.get(key)}
        for key in sorted(set(current_facts) | set(derived))
        if current is not None and current_facts.get(key) != derived.get(key)
    ]
    checks = {}
    if current is not None:
        for name, args in (
            ("doctor", ["doctor", "--json"]),
            ("preview", ["preview", "--all", "--json"]),
            ("drift", ["generate", "--check"]),
        ):
            check = run([cli, "--root", root, *args], root)
            checks[name] = check
            if name != "drift" and check["exitCode"] == 0:
                check["report"] = json.loads(check.pop("stdout"))
    failed = any(check["exitCode"] for check in checks.values())
    state = (
        "needs-clarification"
        if clarifications
        else "needs-review"
        if changes or failed
        else "ready-to-adopt"
        if current is None
        else "unchanged"
    )
    return {
        "schemaVersion": 1,
        "state": state,
        "root": str(root),
        "adopted": adopted,
        "sourceInputs": preview["importedSources"],
        "sourceCoverage": "Bounded importer sources only; omitted facts are not proved absent.",
        "sourceAssessment": score,
        "derivedFacts": derived,
        "proposedManifest": preview["manifestText"] if current is None else None,
        "changes": changes,
        "clarifications": clarifications,
        "checks": checks,
        "meaning": (
            "Source-derived orientation, not execution qualification. Existing declarations remain "
            "author-owned; a missing derived value does not request deletion. Resolve disagreements "
            "in the owning source or retain a deliberate native override. No source code, model, "
            "network request, generated-document write or publication is performed."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--cli", type=Path, default=ROOT / "target/debug/dotrepo")
    parser.add_argument("--mcp", type=Path, default=ROOT / "target/debug/dotrepo-mcp")
    parser.add_argument("--require-field", action="append", default=[])
    parser.add_argument("--adopt", action="store_true")
    parser.add_argument(
        "--check", action="store_true", help="Exit 1 unless adopted state is unchanged"
    )
    args = parser.parse_args(argv)
    try:
        result = review(
            args.root,
            args.cli,
            args.mcp,
            required=args.require_field,
            adopt=args.adopt,
        )
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"state": "blocked", "error": str(error)}))
        return 2
    print(json.dumps(result, indent=2))
    return int(args.check and result["state"] != "unchanged")


if __name__ == "__main__":
    raise SystemExit(main())
