#!/usr/bin/env -S uv run python
"""Land an index-only PR after explicit CI, then explicitly deploy with GITHUB_TOKEN.

The normal token does not trigger push workflows. Dispatch responses identify
the exact runs to wait for. A non-forced fast-forward publishes the tested commit
and fails if the default branch has diverged; branch protections still apply.
"""

import argparse
import json
import re
import subprocess
from urllib.parse import quote


def api(path, *, method="GET", body=None):
    command = ["gh", "api", "--method", method, path]
    if body is not None:
        command += ["--input", "-"]
    result = subprocess.run(
        command,
        input=json.dumps(body) if body is not None else None,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout) if result.stdout.strip() else None


def wait_run(repository, run_id, expected_head, required_job):
    if not isinstance(run_id, int) or run_id <= 0:
        raise RuntimeError("Dispatch did not return a workflow run ID")
    print(f"https://github.com/{repository}/actions/runs/{run_id}", flush=True)
    subprocess.run(
        [
            "gh",
            "run",
            "watch",
            str(run_id),
            "--repo",
            repository,
            "--exit-status",
            "--interval",
            "15",
        ],
        check=True,
        timeout=3000,
    )
    run = api(f"repos/{repository}/actions/runs/{run_id}")
    if run.get("conclusion") != "success" or run.get("head_sha") != expected_head:
        raise RuntimeError("Workflow did not succeed for the expected commit")
    jobs = api(f"repos/{repository}/actions/runs/{run_id}/jobs?per_page=100")["jobs"]
    if not any(job["name"] == required_job and job.get("conclusion") == "success" for job in jobs):
        raise RuntimeError(f"Required job {required_job} did not run successfully")


def validate_pull(pull, repository, default_branch, expected_head, expected_base):
    if (
        pull.get("state") != "open"
        or pull.get("draft")
        or pull["head"]["repo"]["full_name"] != repository
        or not pull["head"]["ref"].startswith("automation/index-autonomous/")
        or pull["head"]["sha"] != expected_head
        or pull["base"]["ref"] != default_branch
        or pull["base"]["sha"] != expected_base
    ):
        raise RuntimeError("PR identity, head, or base differs from the checked automation input")


def land(repository, number, expected_head, expected_base):
    root = f"repos/{repository}"
    default_branch = api(root)["default_branch"]
    pull_path = f"{root}/pulls/{number}"
    pull = api(pull_path)
    validate_pull(pull, repository, default_branch, expected_head, expected_base)
    files = []
    for page in range(1, 32):
        batch = api(f"{pull_path}/files?per_page=100&page={page}")
        files.extend(batch)
        if len(batch) < 100:
            break
    else:
        raise RuntimeError("PR exceeds the bounded file inspection limit")
    if not files or any(
        not item["filename"].startswith("index/")
        or (item.get("previous_filename") and not item["previous_filename"].startswith("index/"))
        for item in files
    ):
        raise RuntimeError("Automatic landing is restricted to index-only changes")
    dispatch = api(
        f"{root}/actions/workflows/ci.yml/dispatches",
        method="POST",
        body={
            "ref": pull["head"]["ref"],
            "inputs": {"base_sha": expected_base},
            "return_run_details": True,
        },
    )
    wait_run(repository, dispatch["workflow_run_id"], expected_head, "public-surface-gate")
    validate_pull(api(pull_path), repository, default_branch, expected_head, expected_base)
    ref = f"{root}/git/refs/heads/{quote(default_branch, safe='')}"
    if api(ref)["object"]["sha"] != expected_base:
        raise RuntimeError("Default branch advanced during CI; regenerate the batch")
    # The server enforces ancestry atomically. Never force or bypass protections.
    api(ref, method="PATCH", body={"sha": expected_head, "force": False})
    print(f"Published tested commit {expected_head}", flush=True)
    deploy = api(
        f"{root}/actions/workflows/public-cloudflare.yml/dispatches",
        method="POST",
        body={"ref": default_branch, "return_run_details": True},
    )
    wait_run(repository, deploy["workflow_run_id"], expected_head, "deploy")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-base", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        parser.error("invalid repository")
    if args.pr_number <= 0 or any(
        not re.fullmatch(r"[0-9a-f]{40}", sha) for sha in (args.expected_head, args.expected_base)
    ):
        parser.error("invalid PR number or commit")
    land(args.repository, args.pr_number, args.expected_head, args.expected_base)


if __name__ == "__main__":
    main()
