#!/usr/bin/env -S uv run python
"""Read-only owner preflight for the scheduled refresh's GitHub PR prerequisite.

Run with an existing owner/admin session before enabling automation, after an
organization transfer, or when PR creation fails. GITHUB_TOKEN cannot generally
read the administration endpoint; do not grant it more access for this probe.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess


def api(path):
    return json.loads(subprocess.check_output(["gh", "api", path], stderr=subprocess.PIPE))


def inspect(repository, fetch=api):
    if not isinstance(repository, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", repository
    ):
        raise ValueError("expected owner/repository")
    actions = fetch(f"repos/{repository}/actions/permissions")
    workflow = fetch(f"repos/{repository}/actions/permissions/workflow")
    if not isinstance(actions, dict) or not isinstance(workflow, dict):
        raise ValueError("GitHub workflow-permissions response must be an object")
    if (
        type(actions.get("enabled")) is not bool
        or type(workflow.get("can_approve_pull_request_reviews")) is not bool
        or workflow.get("default_workflow_permissions") not in {"read", "write"}
    ):
        raise ValueError("malformed GitHub workflow-permissions response")
    blockers = []
    if not actions["enabled"]:
        blockers.append("github-actions-disabled")
    if not workflow["can_approve_pull_request_reviews"]:
        blockers.append("actions-pr-creation-disabled")
    return {
        "schema": "dotrepo/refresh-readiness/v1",
        "repository": repository,
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "ready": not blockers,
        "blockers": blockers,
        "observedWorkflowPermissions": workflow,
        "proposedWorkflowPermissions": {
            "default_workflow_permissions": workflow["default_workflow_permissions"],
            "can_approve_pull_request_reviews": True,
        },
        "meaning": "Settings observation only; no mutation, PR, crawl, merge, publication or future-run guarantee. The creation/approval switch is coupled by GitHub; changing it requires owner authorization.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default="lazy-collective/dotrepo")
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = inspect(args.repository)
        code = 0 if report["ready"] else 2
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        report = {"repository": args.repository, "ready": None, "error": str(error)}
        code = 1
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
