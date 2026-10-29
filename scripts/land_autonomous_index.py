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
from pathlib import Path
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
    successful = [
        job for job in jobs if job["name"] == required_job and job.get("conclusion") == "success"
    ]
    if not successful:
        raise RuntimeError(f"Required job {required_job} did not run successfully")
    if required_job == "deploy":
        for step_name in ("Deploy Worker", "Smoke deployed Worker"):
            if not any(
                step.get("name") == step_name and step.get("conclusion") == "success"
                for job in successful
                for step in job.get("steps", [])
            ):
                raise RuntimeError(f"Publication step {step_name} did not run successfully")


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


def approve_pending_pull_runs(repository, root, expected_head):
    """Approve pull_request runs stuck at action_required for this head.

    PRs created by GITHUB_TOKEN get a pull_request CI run that waits for
    approval; its pending ci-gate supersedes the dispatched run's success
    in branch-protection evaluation, so the exact-commit PATCH is rejected
    with 'Required status check ci-gate is expected' unless that run is
    approved and green. Best effort: approval can require a human, in
    which case the PATCH result decides and the failure stays visible.
    """
    try:
        runs = api(f"{root}/actions/runs?head_sha={expected_head}&event=pull_request&per_page=20")
    except Exception as error:  # noqa: BLE001 - best effort, see docstring
        print(f"warning: could not list pull_request runs: {error}", flush=True)
        return
    for run in runs.get("workflow_runs", []):
        if run.get("conclusion") != "action_required":
            continue
        run_id = run.get("id")
        try:
            api(f"{root}/actions/runs/{run_id}/approve", method="POST")
        except Exception as error:  # noqa: BLE001 - human approval fallback
            print(f"warning: could not approve run {run_id}: {error}", flush=True)
            continue
        print(f"Approved pending pull_request run {run_id}; waiting for ci-gate", flush=True)
        wait_run(repository, run_id, expected_head, "ci-gate")


def public_deploy_enabled(repository, root, *, explicit=None, decision=None):
    """Resolve the switch before landing; a failed read is not a disabled switch."""
    decision = decision if decision is not None else {}
    decision.update(
        enabled=None, source="explicit-cli" if explicit is not None else "repository-variable-api"
    )
    if explicit is not None:
        if type(explicit) is not bool:
            raise ValueError("Explicit public deployment switch must be boolean")
        decision.update(enabled=explicit, reason="explicit-true" if explicit else "explicit-false")
        return explicit
    try:
        variable = api(f"{root}/actions/variables/CLOUDFLARE_PUBLIC_DEPLOY_ENABLED")
    except Exception as error:  # noqa: BLE001 - retain config-read failure before landing
        not_found = False
        if isinstance(error, subprocess.CalledProcessError):
            try:
                response = json.loads(error.stdout or "null")
            except (ValueError, TypeError):
                response = None
            not_found = (
                isinstance(response, dict) and response.get("status") in (404, "404")
            ) or "(HTTP 404)" in (error.stderr or "")
        if not_found:
            decision.update(enabled=False, reason="repository-variable-unset", httpStatus=404)
            return False
        decision.update(reason="variable-read-error", errorType=type(error).__name__)
        raise RuntimeError("Could not read public deployment switch; refusing to land") from error
    if not isinstance(variable, dict) or not isinstance(variable.get("value"), str):
        decision.update(reason="invalid-variable-response")
        raise RuntimeError("Invalid public deployment switch response; refusing to land")
    value = variable["value"].lower()
    if value not in {"true", "false", ""}:
        decision.update(reason="invalid-variable-value")
        raise RuntimeError("Public deployment switch must be true or false; refusing to land")
    enabled = value == "true"
    decision.update(enabled=enabled, reason="variable-true" if enabled else "variable-not-true")
    return enabled


def land(
    repository, number, expected_head, expected_base, *, receipt=None, deployment_enabled=None
):
    receipt = receipt if receipt is not None else {}
    receipt.update(
        repository=repository,
        pullRequest=number,
        headSha=expected_head,
        baseSha=expected_base,
        status="checking",
        publicationVerified=False,
    )
    root = f"repos/{repository}"
    default_branch = api(root)["default_branch"]
    pull_path = f"{root}/pulls/{number}"
    pull = api(pull_path)
    validate_pull(pull, repository, default_branch, expected_head, expected_base)
    deployment_decision = {}
    receipt["publicDeployment"] = deployment_decision
    deploy_enabled = public_deploy_enabled(
        repository, root, explicit=deployment_enabled, decision=deployment_decision
    )
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
    receipt["ciRunId"] = dispatch["workflow_run_id"]
    approve_pending_pull_runs(repository, root, expected_head)
    validate_pull(api(pull_path), repository, default_branch, expected_head, expected_base)
    ref = f"{root}/git/refs/heads/{quote(default_branch, safe='')}"
    if api(ref)["object"]["sha"] != expected_base:
        raise RuntimeError("Default branch advanced during CI; regenerate the batch")
    # The server enforces ancestry atomically. Never force or bypass protections.
    api(ref, method="PATCH", body={"sha": expected_head, "force": False})
    receipt["status"] = "landed"
    print(f"Published tested commit {expected_head}", flush=True)
    if not deploy_enabled:
        print(
            "CLOUDFLARE_PUBLIC_DEPLOY_ENABLED is not 'true'; "
            "landing complete, public deployment skipped (operator switch).",
            flush=True,
        )
        receipt["status"] = "landed-deployment-disabled"
        return receipt
    deploy = api(
        f"{root}/actions/workflows/public-cloudflare.yml/dispatches",
        method="POST",
        body={"ref": default_branch, "return_run_details": True},
    )
    wait_run(repository, deploy["workflow_run_id"], expected_head, "deploy")
    receipt.update(
        status="published", deployRunId=deploy["workflow_run_id"], publicationVerified=True
    )
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-base", required=True)
    parser.add_argument(
        "--public-deploy-enabled",
        choices=("true", "false"),
        help="Explicit workflow switch; omitted manual calls read the repository variable",
    )
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        parser.error("invalid repository")
    if args.pr_number <= 0 or any(
        not re.fullmatch(r"[0-9a-f]{40}", sha) for sha in (args.expected_head, args.expected_base)
    ):
        parser.error("invalid PR number or commit")
    receipt = {}
    try:
        land(
            args.repository,
            args.pr_number,
            args.expected_head,
            args.expected_base,
            receipt=receipt,
            deployment_enabled=None
            if args.public_deploy_enabled is None
            else args.public_deploy_enabled == "true",
        )
    finally:
        if args.output_json:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
