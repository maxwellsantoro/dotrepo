#!/usr/bin/env -S uv run python
"""Keep one durable canary report; unchanged results never create notifications."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any


TITLE = "Public edge consistency canary is failing"
MARKER = "<!-- dotrepo-public-edge-canary-report:v1 -->"
STATE_PREFIX = "<!-- dotrepo-public-edge-canary-state:"
BOT_LOGIN = "github-actions[bot]"


class GitHub:
    def request(self, method: str, endpoint: str, payload=None, *, paginate=False):
        command = ["gh", "api", "--method", method, endpoint]
        if paginate:
            command.extend(["--paginate", "--slurp"])
        if payload is not None:
            command.extend(["--input", "-"])
        # Do not retry a mutation with an uncertain result. The next serialized run
        # rediscovers the issue and marked comment before deciding what to change.
        result = subprocess.run(
            command,
            input=json.dumps(payload) if payload is not None else None,
            text=True,
            capture_output=True,
            check=True,
        )
        data = json.loads(result.stdout)
        if paginate:
            return [item for page in data for item in page]
        return data


def read_state(body: str) -> dict[str, Any] | None:
    for line in body.splitlines():
        if line.startswith(STATE_PREFIX) and line.endswith(" -->"):
            try:
                state = json.loads(line[len(STATE_PREFIX) : -4])
            except json.JSONDecodeError:
                return None
            if (
                isinstance(state, dict)
                and state.get("status") in {"success", "failure"}
                and isinstance(state.get("fingerprint"), str)
                and type(state.get("runNumber")) is int
                and type(state.get("runAttempt")) is int
            ):
                return state
    return None


def failure_summary(log: str) -> str:
    prefix = "public edge canary failed:"
    messages = [line.split(prefix, 1)[1].strip() for line in log.splitlines() if prefix in line]
    summary = messages[-1] if messages else "The canary command failed; see the workflow log."
    # The canary appends a random cache-buster. It is not a new failure reason.
    summary = re.sub(r"([?&])_canary=[^\s&]+", r"\1_canary=<request>", summary)
    return summary[:2000]


def report_body(state: dict[str, Any], repository: str, run_id: str, summary: str) -> str:
    status = "Failing" if state["status"] == "failure" else "Recovered"
    run_url = f"https://github.com/{repository}/actions/runs/{run_id}"
    lines = [
        MARKER,
        STATE_PREFIX + json.dumps(state, sort_keys=True, separators=(",", ":")) + " -->",
        "## Public edge canary status",
        "",
        f"Status: **{status}**",
        f"Last status change: [workflow run]({run_url}) (attempt {state['runAttempt']})",
        "",
    ]
    if summary:
        lines.extend(["Failure summary:", "```text", summary.replace("`", "'"), "```", ""])
    lines.append(
        "This single report is updated only when the result changes. "
        "Repeated identical failures add no comments. Workflow failures remain visible in Actions."
    )
    return "\n".join(lines) + "\n"


def publish_report(
    github: GitHub,
    *,
    repository: str,
    status: str,
    run_id: str,
    run_number: int,
    run_attempt: int,
    log: str = "",
) -> str:
    root = f"repos/{repository}"
    # Comment state intentionally changes only on transitions. Ask Actions for
    # its independent high-water mark so old reruns cannot overwrite a newer
    # unchanged result without adding a notification/write on every run.
    runs = github.request(
        "GET", f"{root}/actions/workflows/public-edge-canary.yml/runs?per_page=1"
    ).get("workflow_runs", [])
    if not runs:
        raise RuntimeError("Cannot establish latest canary run; refusing report mutation")
    latest = runs[0]
    latest_sequence = (int(latest["run_number"]), int(latest["run_attempt"]))
    if latest_sequence > (run_number, run_attempt):
        return "ignored stale workflow result"
    if latest_sequence != (run_number, run_attempt):
        raise RuntimeError("Current canary run is not visible yet; refusing report mutation")
    issues = github.request("GET", f"{root}/issues?state=all&per_page=100", paginate=True)
    matches = [
        issue
        for issue in issues
        if issue.get("title") == TITLE
        and issue.get("user", {}).get("login") == BOT_LOGIN
        and "pull_request" not in issue
    ]
    # Reuse an open report first, then the original closed report on recurrence.
    # Never create another issue just because somebody closed the previous one.
    issue = (
        min(matches, key=lambda value: (value["state"] != "open", value["number"]))
        if matches
        else None
    )
    if issue is None and status == "success":
        return "healthy; no issue needed"

    summary = failure_summary(log) if status == "failure" else ""
    state = {
        "status": status,
        "fingerprint": hashlib.sha256(summary.encode()).hexdigest(),
        "runNumber": run_number,
        "runAttempt": run_attempt,
    }
    body = report_body(state, repository, run_id, summary)
    if issue is None:
        issue = github.request("POST", f"{root}/issues", {"title": TITLE, "body": body})

    comments = github.request(
        "GET", f"{root}/issues/{issue['number']}/comments?per_page=100", paginate=True
    )
    reports = [
        comment
        for comment in comments
        if comment.get("user", {}).get("login") == BOT_LOGIN
        and comment.get("body", "").startswith(MARKER + "\n")
    ]
    report = min(reports, key=lambda value: value["id"]) if reports else None
    # Issue bodies may contain copied or user-edited state; never trust them.
    previous = read_state(report["body"]) if report else None
    if previous:
        old_sequence = (previous["runNumber"], previous["runAttempt"])
        if old_sequence > (run_number, run_attempt):
            return "ignored stale result"
        unchanged = all(previous[key] == state[key] for key in ("status", "fingerprint"))
        if unchanged and report:
            # Closing an ongoing unchanged outage intentionally suppresses it.
            # A recovery followed by a new failure still reopens the same issue.
            return "unchanged; no notification"

    if status == "failure" and issue["state"] == "closed":
        github.request("PATCH", f"{root}/issues/{issue['number']}", {"state": "open"})
    # Recovery never closes the issue: an operator can verify and close it explicitly.
    if report:
        github.request("PATCH", f"{root}/issues/comments/{report['id']}", {"body": body})
        return "updated existing report"
    github.request("POST", f"{root}/issues/{issue['number']}/comments", {"body": body})
    return "created single report comment"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"), required=False)
    parser.add_argument("--status", choices=("success", "failure"), required=True)
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID"), required=False)
    parser.add_argument("--run-number", type=int, default=os.environ.get("GITHUB_RUN_NUMBER", "0"))
    parser.add_argument(
        "--run-attempt", type=int, default=os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    )
    parser.add_argument("--details-file", type=Path)
    args = parser.parse_args()
    if not args.repository or not re.fullmatch(r"[\w.-]+/[\w.-]+", args.repository):
        parser.error("--repository must be owner/repo")
    if not args.run_id or not args.run_id.isdecimal():
        parser.error("--run-id must be a numeric GitHub Actions run ID")
    if args.run_number < 1 or args.run_attempt < 1:
        parser.error("--run-number and --run-attempt must be positive")
    log = args.details_file.read_text() if args.details_file and args.details_file.is_file() else ""
    print(
        publish_report(
            GitHub(),
            repository=args.repository,
            status=args.status,
            run_id=args.run_id,
            run_number=args.run_number,
            run_attempt=args.run_attempt,
            log=log,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
