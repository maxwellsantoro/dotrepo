#!/usr/bin/env -S uv run python
"""Retain and assess scheduled refresh, publication, and budget evidence.

A green run alone is insufficient. Report mode is read-only and checks actual
GitHub conclusions and deployment steps; missing/expired evidence fails closed.
"""

import argparse
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from pathlib import Path
import subprocess
import zipfile

WORKFLOW = ".github/workflows/index-autonomous-refresh.yml"
SCHEMA = "dotrepo-refresh-receipt/v1"
BUDGET_FIELDS = ("adjudicationCallBudget", "adjudicationCalls", "tokensUsed", "failed", "crawled")


def api(path, *, binary=False):
    result = subprocess.run(["gh", "api", path], capture_output=True, check=True)
    return result.stdout if binary else json.loads(result.stdout)


def read_json(path):
    return json.loads(path.read_text()) if path.is_file() else None


def record(args):
    run = api(f"repos/{args.repository}/actions/runs/{args.run_id}")
    telemetry = read_json(args.batch_dir / "telemetry.json") or {}
    return {
        "schema": SCHEMA,
        "runId": run["id"],
        "runAttempt": run["run_attempt"],
        "event": run["event"],
        "startedAt": run["created_at"],
        "checks": dict(item.split("=", 1) for item in args.check),
        "budget": {key: telemetry.get(key) for key in BUDGET_FIELDS},
        "landing": read_json(args.batch_dir / "landing.json"),
    }


def problems(run, receipt):
    reasons = []
    if run.get("event") != "schedule" or run.get("run_attempt") != 1:
        reasons.append("not-an-unattended-first-attempt")
    if run.get("conclusion") != "success":
        reasons.append("workflow-not-successful")
    if not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA:
        return reasons + ["receipt-unavailable"]
    if any(
        receipt.get(key) != run.get(source)
        for key, source in (
            ("runId", "id"),
            ("runAttempt", "run_attempt"),
            ("event", "event"),
            ("startedAt", "created_at"),
        )
    ):
        reasons.append("receipt-run-mismatch")
    if any(
        receipt.get("checks", {}).get(key) != "success"
        for key in ("batch", "telemetry", "index", "base", "landing")
    ):
        reasons.append("required-refresh-check-missing-or-failed")
    budget = receipt.get("budget") or {}
    if any(type(budget.get(key)) is not int or budget[key] < 0 for key in BUDGET_FIELDS):
        reasons.append("budget-evidence-missing")
    elif budget["adjudicationCalls"] > budget["adjudicationCallBudget"] or budget["failed"] != 0:
        reasons.append("budget-exceeded-or-refresh-failed")
    landing = receipt.get("landing") or {}
    if (
        landing.get("status") != "published"
        or landing.get("publicationVerified") is not True
        or type(landing.get("deployRunId")) is not int
        or not landing.get("headSha")
    ):
        reasons.append("publication-not-verified")
    return reasons


def assess(entries, *, now=None, required=7):
    now = now or datetime.now(timezone.utc)
    entries = sorted(entries, key=lambda e: e["run"]["created_at"], reverse=True)
    days, rows, previous = [], [], None
    for entry in entries:
        run = entry["run"]
        if run.get("event") != "schedule":
            continue
        timestamp = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
        day = timestamp.date()
        reasons = problems(run, entry.get("receipt")) + entry.get("verificationErrors", [])
        if not days and (timestamp > now or now - timestamp > timedelta(hours=36)):
            reasons.append("latest-scheduled-receipt-not-current")
        if previous is not None and day not in (previous, previous - timedelta(days=1)):
            reasons.append("missing-scheduled-day")
        rows.append({"runId": run["id"], "date": day.isoformat(), "reasons": reasons})
        if reasons:
            break
        if day != previous:
            days.append(day.isoformat())
        previous = day
    return {
        "schema": "dotrepo-refresh-streak/v1",
        "evaluatedAt": now.isoformat(),
        "requiredDays": required,
        "qualifiedDays": len(days),
        "passed": len(days) >= required,
        "days": days,
        "runs": rows,
        "limitations": "Requires completed scheduled first attempts, retained budgets, exact-commit publication and smoke. Missing evidence is not success.",
    }


def collect(repository):
    root = f"repos/{repository}"
    runs = api(
        f"{root}/actions/workflows/index-autonomous-refresh.yml/runs?event=schedule&per_page=30"
    )
    entries = []
    for run in runs["workflow_runs"]:
        if run.get("path") != WORKFLOW or run.get("status") != "completed":
            continue
        entry = {"run": run, "receipt": None, "verificationErrors": []}
        entries.append(entry)
        try:
            artifacts = api(f"{root}/actions/runs/{run['id']}/artifacts?per_page=100")
            matches = [
                a
                for a in artifacts["artifacts"]
                if a["name"] == "refresh-receipt" and not a["expired"]
            ]
            if len(matches) != 1:
                break
            payload = api(f"{root}/actions/artifacts/{matches[0]['id']}/zip", binary=True)
            with zipfile.ZipFile(BytesIO(payload)) as archive:
                if archive.getinfo("refresh-receipt.json").file_size > 65536:
                    raise ValueError("receipt exceeds size bound")
                receipt = json.loads(archive.read("refresh-receipt.json"))
            entry["receipt"] = receipt
            if problems(run, receipt):
                break
            landing = receipt["landing"]
            deployment = api(f"{root}/actions/runs/{landing['deployRunId']}")
            jobs = api(f"{root}/actions/runs/{landing['deployRunId']}/jobs?per_page=100")["jobs"]
            steps = [
                s
                for j in jobs
                if j.get("name") == "deploy" and j.get("conclusion") == "success"
                for s in j.get("steps", [])
            ]
            if (
                deployment.get("conclusion") != "success"
                or deployment.get("head_sha") != landing["headSha"]
                or deployment.get("path") != ".github/workflows/public-cloudflare.yml"
                or any(
                    not any(
                        s.get("name") == name and s.get("conclusion") == "success" for s in steps
                    )
                    for name in ("Deploy Worker", "Smoke deployed Worker")
                )
            ):
                entry["verificationErrors"].append("deployment-receipt-not-corroborated")
                break
        except (subprocess.CalledProcessError, ValueError, KeyError, zipfile.BadZipFile):
            entry["verificationErrors"].append("receipt-verification-unavailable")
            break
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    writer = sub.add_parser("record")
    writer.add_argument("--repository", required=True)
    writer.add_argument("--run-id", type=int, required=True)
    writer.add_argument("--batch-dir", type=Path, required=True)
    writer.add_argument("--check", action="append", default=[])
    writer.add_argument("--output", type=Path, required=True)
    reader = sub.add_parser("report")
    reader.add_argument("--repository", required=True)
    reader.add_argument("--output", type=Path, required=True)
    reader.add_argument("--require-pass", action="store_true")
    args = parser.parse_args()
    result = record(args) if args.command == "record" else assess(collect(args.repository))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return int(args.command == "report" and args.require_pass and not result["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
