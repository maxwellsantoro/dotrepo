#!/usr/bin/env -S uv run python
"""Allow publication only for the event's exact, still-current default-branch revision."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import quote


def api(path: str) -> dict:
    result = subprocess.run(
        ["gh", "api", "--method", "GET", path], text=True, capture_output=True, check=True
    )
    return json.loads(result.stdout)


def source_revision(event_name: str, event: dict, repository: str, dispatch_sha: str) -> str:
    if event_name == "workflow_run":
        run = event.get("workflow_run", {})
        if (
            run.get("conclusion") != "success"
            or run.get("event") != "push"
            or run.get("head_repository", {}).get("full_name") != repository
        ):
            raise RuntimeError("Workflow event is not an eligible same-repository successful push")
        # workflow_run's top-level GITHUB_SHA may identify a newer default-branch
        # revision. Only the triggering CI run's head_sha identifies its tested code.
        source = run.get("head_sha")
    elif event_name == "workflow_dispatch":
        # For manual dispatch GITHUB_SHA is the selected event revision; it is
        # never a fallback for a missing workflow_run.head_sha.
        source = dispatch_sha
    else:
        raise RuntimeError(f"Unsupported publication event: {event_name}")
    if not isinstance(source, str) or re.fullmatch(r"[0-9a-f]{40}", source) is None:
        raise RuntimeError("Publication event has no valid exact source SHA")
    return source


def check_eligibility(
    repository: str,
    event_name: str,
    event: dict,
    dispatch_sha: str = "",
    checkout_sha: str | None = None,
) -> dict:
    source = source_revision(event_name, event, repository, dispatch_sha)
    if checkout_sha is not None and checkout_sha != source:
        raise RuntimeError("Actual checkout differs from the event source revision")
    metadata = api(f"repos/{repository}")
    default_branch = metadata.get("default_branch")
    if not isinstance(default_branch, str) or not default_branch:
        raise RuntimeError("Live repository metadata has no default branch")
    live_ref = api(f"repos/{repository}/git/ref/heads/{quote(default_branch, safe='')}")
    current = live_ref.get("object", {}).get("sha")
    if not isinstance(current, str) or re.fullmatch(r"[0-9a-f]{40}", current) is None:
        raise RuntimeError("Live default-branch lookup did not return a valid commit SHA")
    return {
        "eligible": source == current,
        "sourceSha": source,
        "currentSha": current,
        "defaultBranch": default_branch,
        "reason": "current tested revision"
        if source == current
        else "superseded revision; skipped",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--event-name", default=os.environ.get("GITHUB_EVENT_NAME"))
    parser.add_argument("--event-path", type=Path, default=os.environ.get("GITHUB_EVENT_PATH"))
    parser.add_argument("--dispatch-sha", default=os.environ.get("GITHUB_SHA", ""))
    parser.add_argument("--checkout-sha")
    parser.add_argument("--github-output", type=Path, default=os.environ.get("GITHUB_OUTPUT"))
    args = parser.parse_args()
    if not args.repository or not re.fullmatch(r"[\w.-]+/[\w.-]+", args.repository):
        parser.error("repository must be owner/repo")
    if not args.event_path:
        parser.error("an event payload path is required")
    report = check_eligibility(
        args.repository,
        args.event_name,
        json.loads(args.event_path.read_text()),
        args.dispatch_sha,
        args.checkout_sha,
    )
    # Lookup/parse failures raise before any eligible output can be emitted.
    if args.github_output:
        with args.github_output.open("a") as output:
            output.write(f"eligible={str(report['eligible']).lower()}\n")
            output.write(f"source_sha={report['sourceSha']}\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
