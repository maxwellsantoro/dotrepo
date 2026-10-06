#!/usr/bin/env -S uv run python
"""Validate refresh inputs and refuse stale-base PR creation without rebasing."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


def nonnegative_budget(value: object) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value.strip()):
        raise ValueError("adjudication_call_budget must be a nonnegative integer")
    budget = int(value.strip())
    if budget > 2**31 - 1:
        raise ValueError("adjudication_call_budget exceeds the supported integer range")
    return budget


def resolve_budget(event: dict, event_name: str, default: str, providers_enabled: bool) -> int:
    if event_name not in {"schedule", "workflow_dispatch"}:
        raise ValueError("unsupported autonomous refresh event")
    if event_name == "workflow_dispatch":
        inputs = event.get("inputs", {})
        if not isinstance(inputs, dict):
            raise ValueError("workflow_dispatch inputs must be an object")
        requested = inputs.get("adjudication_call_budget", "")
        if requested != "":
            return nonnegative_budget(requested)
    return nonnegative_budget(default) if providers_enabled else 0


def api(path: str) -> dict:
    result = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=True)
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError("GitHub response must be an object")
    return value


def check_base(repository: str, expected: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("invalid repository")
    if not re.fullmatch(r"[0-9a-f]{40}", expected):
        raise ValueError("invalid expected base SHA")
    branch = api(f"repos/{repository}").get("default_branch")
    if not isinstance(branch, str) or not branch or any(ord(c) < 32 for c in branch):
        raise ValueError("invalid default branch response")
    response = api(f"repos/{repository}/git/ref/heads/{quote(branch, safe='')}")
    if response.get("ref") != f"refs/heads/{branch}" or not isinstance(
        response.get("object"), dict
    ):
        raise ValueError("invalid default branch reference response")
    current = response["object"].get("sha")
    if not isinstance(current, str) or not re.fullmatch(r"[0-9a-f]{40}", current):
        raise ValueError("invalid default branch SHA response")
    return {
        "schema": "dotrepo/autonomous-refresh-base/v0.1",
        "repository": repository,
        "defaultBranch": branch,
        "expectedBase": expected,
        "currentBase": current,
        "passed": current == expected,
        "disposition": "base-matches" if current == expected else "regenerate-on-current-main",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    budget = commands.add_parser("budget")
    budget.add_argument("--event-path", type=Path, required=True)
    budget.add_argument("--event-name", required=True)
    budget.add_argument("--default-budget", required=True)
    budget.add_argument("--providers-enabled", choices=["true", "false"], required=True)
    budget.add_argument("--github-output", type=Path, required=True)
    base = commands.add_parser("base")
    base.add_argument("--repository", required=True)
    base.add_argument("--expected-base", required=True)
    base.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "budget":
        try:
            event = json.loads(args.event_path.read_text())
            if not isinstance(event, dict):
                raise ValueError("event must be an object")
            value = resolve_budget(
                event, args.event_name, args.default_budget, args.providers_enabled == "true"
            )
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
        with args.github_output.open("a") as output:
            output.write(f"adjudication_call_budget={value}\n")
            output.write(f"adjudication_enabled={'true' if value else 'false'}\n")
        print(json.dumps({"adjudicationCallBudget": value, "adjudicationEnabled": bool(value)}))
        return 0
    try:
        report = check_base(args.repository, args.expected_base)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        report = {"passed": False, "error": str(exc), "expectedBase": args.expected_base}
    report["checkedAt"] = datetime.now(timezone.utc).isoformat()
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    if not report["passed"]:
        print(
            "Refusing PR creation: base could not be verified; regenerate the batch on current main."
        )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
