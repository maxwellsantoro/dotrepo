"""Offline review of retained bytes only; no imports from acquisition code."""

import ast
import base64
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

PILOT = Path(__file__).resolve().parent.parent / "pilot-20261029"
EXPECTED = "9b936d71ccb748bd46a69bf482ae942cde23de28c936bc6a2f77e6b9e35de8bc"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(name):
    return json.loads((PILOT / name).read_bytes())


def main():
    assert sha((PILOT / "freeze.json").read_bytes()) == EXPECTED
    freeze = load("freeze.json")
    for item in freeze["files"]:
        data = (PILOT / item["path"]).read_bytes()
        assert sha(data) == item["sha256"] and len(data) == item["bytes"]
    pre = load("pre-api-freeze.json")
    for item in pre["files"]:
        assert sha((PILOT / item["path"]).read_bytes()) == item["sha256"]
    plan = load("plan.json")
    ledger = load("request-ledger.json")
    assert datetime.fromisoformat(plan["frozenAt"]).timestamp() < ledger[0]["startedAtUnix"]
    assert len(ledger) == 22 <= plan["limits"]["publicApiRequestsTotal"] == 30
    raw_jobs = {}
    raw_runs = {}
    contents = 0
    log_errors = 0
    for number, request in enumerate(ledger, 1):
        data = (PILOT / request["bodyPath"]).read_bytes()
        assert request["number"] == number
        assert request["authenticated"] is False and request["overLimit"] is False
        assert sha(data) == request["sha256"] and len(data) == request["bytesRetained"]
        assert len(data) <= request["limitBytes"]
        assert "redirectHost" not in request
        body = json.loads(data)
        if "workflow_runs" in body:
            assert body["total_count"] == len(body["workflow_runs"]) <= 100
            raw_runs.update({r["id"]: r for r in body["workflow_runs"]})
        if "jobs" in body:
            assert body["total_count"] == len(body["jobs"]) <= 100
            raw_jobs.update({j["id"]: j for j in body["jobs"]})
        if "/contents/" in request["url"]:
            decoded = base64.b64decode(body["content"])
            blob = hashlib.sha1(b"blob " + str(len(decoded)).encode() + b"\0" + decoded).hexdigest()
            assert blob == body["sha"]
            contents += 1
        if request["bodyPath"].endswith(".log"):
            assert (
                request["status"] == 403
                and body["message"] == "Must have admin rights to Repository."
            )
            log_errors += 1
    selected = load("run-selection.json")
    run_count = 0
    for case in selected:
        for run in case["selected"]:
            observed = raw_runs[run["id"]]
            assert observed["head_sha"] == case["revision"] == run["headSha"]
            assert observed["run_attempt"] == run["runAttempt"] == 1
            assert (
                observed["path"] == run["path"]
                and observed["conclusion"] == run["conclusion"] == "success"
            )
            source = run["workflowSource"]
            data = (PILOT / source["path"]).read_bytes()
            assert sha(data) == source["sha256"] and source["ref"] == case["revision"]
            assert (
                hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
                == source["gitBlobSha"]
            )
            run_count += 1
    observations = load("observations.json")
    steps = 0
    job_conclusions = Counter()
    for case in observations["cases"]:
        for job in case["jobs"]:
            raw = raw_jobs[job["jobId"]]
            for field, api in [
                ("runId", "run_id"),
                ("runAttempt", "run_attempt"),
                ("headSha", "head_sha"),
                ("name", "name"),
                ("status", "status"),
                ("conclusion", "conclusion"),
            ]:
                assert job[field] == raw[api]
            assert job["headSha"] == case["revision"]
            assert len(job["steps"]) == len(raw["steps"])
            for step, original in zip(job["steps"], raw["steps"], strict=True):
                for field, api in [
                    ("number", "number"),
                    ("name", "name"),
                    ("status", "status"),
                    ("conclusion", "conclusion"),
                    ("startedAt", "started_at"),
                    ("completedAt", "completed_at"),
                ]:
                    assert step[field] == original[api]
                steps += 1
            job_conclusions[job["conclusion"]] += 1
    for item in load("source-bindings.json")["sources"]:
        data = (PILOT / item["path"]).read_bytes()
        assert sha(data) == item["sha256"] and len(data) == item["bytes"]
        assert len(data.splitlines()) == item["lineCount"]
    assert ast.dump(ast.parse((PILOT / "collect.py").read_text())) == ast.dump(
        ast.parse((PILOT / "raw/collector-executed.py.txt").read_text())
    )
    assert (run_count, len(raw_jobs), steps, contents, log_errors) == (4, 54, 829, 11, 4)
    assert job_conclusions == {"success": 47, "skipped": 7}
    print(
        json.dumps(
            {
                "result": "pass",
                "freezeFiles": len(freeze["files"]),
                "preApiFiles": len(pre["files"]),
                "preApiTimestampPrecedesFirstRequest": True,
                "requests": len(ledger),
                "responseBytes": sum(r["bytesRetained"] for r in ledger),
                "runs": run_count,
                "jobs": len(raw_jobs),
                "jobConclusions": job_conclusions,
                "stepEntries": steps,
                "apiGitBlobs": contents,
                "logs403": log_errors,
                "collectorAstEqual": True,
                "newNetworkRequests": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
