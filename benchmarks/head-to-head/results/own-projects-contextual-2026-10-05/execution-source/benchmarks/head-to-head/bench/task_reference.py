"""Run paired measurement controls against our harmless local fixture project.

Not an independent holdout: source decisions are scripted. Only this module's
fixed commands are executed; the task scorer itself never executes commands.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

from .arms.lookup_first import consumer
from .tasks import ARMS, markdown, score

PROJECT = Path(__file__).resolve().parents[1] / "task-fixtures/project"


def now():
    return datetime.now(timezone.utc).isoformat()


def plan(command, *, cwd=".", scope="repository", parameters=None, prerequisites=None):
    return {
        "command": command,
        "workingDirectory": cwd,
        "scope": scope,
        "component": "widget" if scope == "component" else None,
        "parameters": parameters or {},
        "prerequisites": prerequisites or [],
        "environment": {"DEMO_CONTEXT": "widget"} if scope == "component" else {},
        "sourcePaths": ["components/widget/README.md"] if scope == "component" else ["README.md"],
        "purpose": "test" if "build" not in command else "build",
    }


def run_controls(output):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("choose a new output directory; retained observations are immutable")
    output.mkdir(parents=True, exist_ok=True)
    checked = now()
    revision = hashlib.sha256(
        b"".join(p.read_bytes() for p in sorted(PROJECT.rglob("*")) if p.is_file())
    ).hexdigest()[:40]
    unit = plan("make unit")
    cases = [
        ("root-build", plan("make build"), "make build", "README.md", 200),
        ("root-unit-test", unit, "make unit", "README.md", 200),
        (
            "prerequisite-test",
            plan("make test", prerequisites=["Make target setup"]),
            "make test",
            "Makefile",
            200,
        ),
        (
            "required-argument",
            plan("just test unit", parameters={"target": "unit"}),
            "just test {{target}}",
            "justfile",
            200,
        ),
        (
            "component-scope",
            plan(
                "uv run python ../../runner.py component",
                cwd="components/widget",
                scope="component",
            ),
            "uv run python runner.py component",
            "components/widget/README.md",
            200,
        ),
        ("compile-only-fallback", unit, "go test -c", "README.md", 200),
        ("absent-command", unit, None, "README.md", 200),
        ("unindexed-fallback", plan("make build"), None, "README.md", 404),
        (
            "accepted-prerequisite-loss",
            plan("make test", prerequisites=["Make target setup"]),
            "uv run python runner.py test",
            "README.md",
            200,
        ),
        ("accepted-non-running-command", unit, "uv run python runner.py compile", "README.md", 200),
    ]
    snapshot = hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest()
    tasks = [
        {
            "id": name,
            "taskClass": name,
            "identity": f"github.com/fixture/{name}",
            "revision": revision,
            "revisionKind": "fixture-content",
            "environmentId": "local-controlled-fixture",
            "acceptableInstructions": [gold],
            "evidence": [
                {
                    "url": "fixture://task-fixtures/project/README.md",
                    "locator": name,
                    "checkedAt": checked,
                    "sourceRevision": revision,
                }
            ],
        }
        for name, gold, *_ in cases
    ]
    workload = {
        "version": 1,
        "frozenAt": checked,
        "selectionBeforeCoverageInspection": True,
        "consumerClass": "operator-controlled",
        "cacheState": "cold",
        "snapshotId": snapshot,
        "consumerPolicy": consumer.COMMAND_POLICY,
        "tasks": tasks,
    }
    workload_path = output / "workload.json"
    workload_path.write_text(json.dumps(workload, indent=2) + "\n")
    sources = {}
    for task, (_, gold, command, source, status) in zip(tasks, cases, strict=True):
        payload = {
            "apiVersion": "v0",
            "identity": {"host": "github.com", "owner": "fixture", "repo": task["id"]},
            "record": {"generatedAt": checked},
            "execution": {},
            "fieldEvidence": {},
        }
        field = "repo.build" if gold["purpose"] == "build" else "repo.test"
        if command:
            payload["execution"][field.split(".")[1]] = command
            payload["fieldEvidence"][field] = {
                "state": "present",
                "method": "extracted",
                "confidence": "high",
                "source": source,
                "checkedAt": checked,
            }
        sources[f"/profile/{task['id']}"] = (status, json.dumps(payload).encode())
        sources[f"/source/{task['id']}"] = (200, json.dumps(gold).encode())

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status, body = sources[self.path]
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    runs = []
    try:
        for index, task in enumerate(tasks):
            for arm in ARMS if index % 2 == 0 else reversed(ARMS):
                started = now()
                timer = time.perf_counter()
                transport = {"httpRequests": 0, "decodedBytes": 0, "cacheHits": 0}

                def fetch(path):
                    from urllib.error import HTTPError

                    transport["httpRequests"] += 1
                    try:
                        with urlopen(base + path, timeout=10) as response:
                            status, body = response.status, response.read()
                    except HTTPError as error:
                        status, body = error.code, error.read()
                    transport["decodedBytes"] += len(body)
                    return status, body

                lookup = None
                if arm == "lookup-first":
                    status, body = fetch(f"/profile/{task['id']}")
                    result = consumer.interpret_http_response(
                        identity=task["identity"], status_code=status, body=body
                    )
                    field = (
                        "repo.build"
                        if task["acceptableInstructions"][0]["purpose"] == "build"
                        else "repo.test"
                    )
                    consumer.evaluate_for_task(result, required_fields=[field])
                    value = consumer.profile_field(result.profile or {}, field)
                    selected = plan(value) if result.usable else None
                    # Retain the known Make prerequisite when its wrapper is intact.
                    if selected and value == "make test":
                        selected["prerequisites"] = ["Make target setup"]
                    lookup = {
                        "snapshotId": snapshot,
                        "policy": consumer.COMMAND_POLICY,
                        "valuePresent": value is not None,
                        "accepted": result.usable,
                        "instruction": selected,
                        "fallbackReasons": result.fallback_reasons,
                    }
                else:
                    selected = None
                attempts = []
                plans = []
                if selected:
                    plans.append(("profile", selected))
                else:
                    _, body = fetch(f"/source/{task['id']}")
                    plans.append(
                        ("source" if arm == "source-first" else "fallback", json.loads(body))
                    )
                for origin, selected in plans:
                    with tempfile.TemporaryDirectory(prefix="dotrepo-task-control-") as temporary:
                        local = Path(temporary)
                        shutil.copytree(PROJECT, local, dirs_exist_ok=True)
                        process = subprocess.run(
                            shlex.split(selected["command"]),
                            cwd=local / selected["workingDirectory"],
                            env={**os.environ, **selected["environment"]},
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                    lines = process.stdout.splitlines()
                    completed = any('"completed": true' in line for line in lines)
                    # Setup output alone is not the task completion oracle.
                    if selected["command"] == "make test":
                        completed = process.returncode == 0 and any(
                            '"mode": "test", "completed": true' in line for line in lines
                        )
                    transcript = {
                        "taskId": task["id"],
                        "instruction": selected,
                        "exitCode": process.returncode,
                        "oraclePassed": completed,
                        "stdout": process.stdout,
                        "stderr": process.stderr,
                    }
                    name = f"logs/{task['id']}-{arm}-{len(attempts)}.json"
                    path = output / name
                    path.parent.mkdir(exist_ok=True)
                    path.write_text(json.dumps(transcript, indent=2) + "\n")
                    attempts.append(
                        {k: transcript[k] for k in ("instruction", "exitCode", "oraclePassed")}
                        | {
                            "origin": origin,
                            "log": {
                                "path": name,
                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            },
                        }
                    )
                    if not completed and origin == "profile":
                        _, body = fetch(f"/source/{task['id']}")
                        plans.append(("fallback", json.loads(body)))
                runs.append(
                    {
                        "taskId": task["id"],
                        "arm": arm,
                        "revision": revision,
                        "environmentId": task["environmentId"],
                        "cacheState": "cold",
                        "startedAt": started,
                        "endedAt": now(),
                        "elapsedMs": round((time.perf_counter() - timer) * 1000, 3),
                        "transport": transport,
                        "lookup": lookup,
                        "attempts": attempts,
                        "modelUsage": {"inputTokens": None, "outputTokens": None, "cost": None},
                        "allocatedMaintenanceCost": None,
                    }
                )
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    observations = {
        "version": 1,
        "workloadSha256": hashlib.sha256(workload_path.read_bytes()).hexdigest(),
        "runs": runs,
    }
    observations_path = output / "observations.json"
    observations_path.write_text(json.dumps(observations, indent=2) + "\n")
    report = score(workload_path, observations_path)
    (output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "report.md").write_text(markdown(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run_controls(args.out)


if __name__ == "__main__":
    main()
