"""Read-only replay of the declared reference consumer; no transport or execution."""

from __future__ import annotations

import copy
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path("/Users/maxwell/projects/agent/dotrepo")
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    declaration = json.loads((HERE / "INPUT_FREEZE.json").read_bytes())
    for entry in declaration["inputs"]:
        path = ROOT / entry["path"]
        assert path.stat().st_size == entry["bytes"] and sha(path) == entry["sha256"], entry["path"]
    spec = importlib.util.spec_from_file_location(
        "fixed_f05_reference", ROOT / "examples/external-consumer/lookup_before_scrape.py"
    )
    consumer = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = consumer
    spec.loader.exec_module(consumer)
    task_root = ROOT / "benchmarks/head-to-head/f05-agent-tasks-20261029"
    capture_root = ROOT / "benchmarks/head-to-head/f05-snapshot-20261029/profile-capture"
    tasks = json.loads((task_root / "tasks.json").read_bytes())["tasks"]
    receipts = {r["taskId"]: r for r in json.loads((capture_root / "receipts.json").read_bytes())}
    rows = []
    for task in tasks:
        receipt = receipts[task["id"]]
        body = (capture_root / receipt["body"]).read_bytes()
        assert (
            len(body) == receipt["decodedBytes"]
            and hashlib.sha256(body).hexdigest() == receipt["sha256"]
        )
        now = datetime.fromisoformat(receipt["observedAt"])
        result = consumer.interpret_http_response(
            identity=task["repository"], status_code=receipt["status"], body=body
        )
        scalar = consumer.evaluate_for_task(result, required_fields=["repo.test"], now=now)
        scalar_observation = {
            "accepted": scalar.usable,
            "fallbackReasons": list(scalar.fallback_reasons),
        }
        profile = result.profile or {}
        request = {"scope": task["scope"], "component": task["component"]}
        contextual = consumer.select_instruction(result, "test", request=request, now=now)
        gold = json.loads((task_root / task["gold"]).read_bytes())
        oracle = json.loads((task_root / task["oracle"]).read_bytes())
        record = profile.get("record", {})
        execution = profile.get("execution", {})
        rows.append(
            {
                "taskId": task["id"],
                "repository": task["repository"],
                "ecosystem": task["ecosystem"],
                "scope": task["scope"],
                "component": task["component"],
                "startingState": task["startingState"],
                "taskRevision": task["revision"],
                "captureObservedAt": receipt["observedAt"],
                "httpStatus": receipt["status"],
                "capturedBodySha256": receipt["sha256"],
                "recordRevision": record.get("sourceRevision"),
                "recordRevisionMatchesTask": record.get("sourceRevision") == task["revision"]
                if result.hit
                else None,
                "recordGeneratedAt": record.get("generatedAt"),
                "recordAgeDaysAtCapture": result.record_age_days,
                "profileConflicts": profile.get("conflicts"),
                "scalarTest": execution.get("test"),
                "scalarAssessment": profile.get("fieldEvidence", {}).get("repo.test"),
                "scalarPolicy": scalar_observation,
                "testContextPresent": "testContext" in execution,
                "testCandidatesCount": len(execution.get("testCandidates", [])),
                "contextRequest": request,
                "contextualPolicy": contextual,
                "originalGoldStatus": gold["status"],
                "originalGoldReason": gold["reason"],
                "originalGoldCompleteAlternatives": gold["supportedCompleteAlternatives"],
                "originalOracleState": oracle["state"],
                "taskSupportedDirectCompleteInstruction": False,
                "finalTaskCompletion": None,
                "fallbackAttempted": False,
            }
        )
    controls = []
    now = datetime.fromisoformat(receipts["rust-01"]["observedAt"])
    base = json.loads((capture_root / receipts["rust-01"]["body"]).read_bytes())
    stamp = base["record"]["generatedAt"]
    context = {
        "command": "cargo test",
        "workingDirectory": ".",
        "scope": "repository",
        "component": None,
        "prerequisites": ["Rust toolchain", "Install documented dependencies"],
        "source": "CONTRIBUTING.md",
    }
    base["execution"] = {"test": "cargo test", "testContext": context}
    assessment = {
        "state": "present",
        "method": "extracted",
        "confidence": "high",
        "source": "CONTRIBUTING.md",
        "checkedAt": stamp,
    }
    base["fieldEvidence"] = {"repo.test": assessment.copy(), "repo.test_context": assessment.copy()}

    def check(name, mutate, request, scalar_expected, context_expected):
        p = copy.deepcopy(base)
        mutate(p)
        result = consumer.LookupResult(
            identity="github.com/tauri-apps/tauri", status_code=200, hit=True, miss=False, profile=p
        )
        consumer.evaluate_for_task(result, required_fields=["repo.test"], now=now)
        accepted, reasons = result.usable, list(result.fallback_reasons)
        selected = consumer.select_instruction(result, "test", request=request, now=now)
        assert (
            accepted == scalar_expected
            and (selected["instruction"] is not None) == context_expected
        ), name
        controls.append(
            {
                "name": name,
                "synthetic": True,
                "scalarAccepted": accepted,
                "scalarReasons": reasons,
                "contextSelected": selected["instruction"] is not None,
                "contextReasons": selected["fallbackReasons"],
                "actualTaskAdmission": False,
            }
        )

    check(
        "complete-high-repository-tuple-accepted",
        lambda p: None,
        {"scope": "repository"},
        True,
        True,
    )
    check(
        "same-root-scalar-does-not-answer-component-context-request",
        lambda p: None,
        {"scope": "component", "component": "owned/component"},
        True,
        False,
    )
    check(
        "missing-prerequisite-member-abstains-context",
        lambda p: p["execution"]["testContext"].pop("prerequisites"),
        {"scope": "repository"},
        True,
        False,
    )
    check(
        "medium-assessment-abstains-both",
        lambda p: p["fieldEvidence"]["repo.test"].update(confidence="medium"),
        {"scope": "repository"},
        False,
        False,
    )
    check(
        "record-conflict-abstains-both",
        lambda p: p.update(conflicts=[{"field": "repo.test"}]),
        {"scope": "repository"},
        False,
        False,
    )
    check(
        "candidate-command-context-mismatch-abstains",
        lambda p: p["execution"]["testContext"].update(command="cargo test -p other"),
        {"scope": "repository"},
        True,
        False,
    )
    check(
        "missing-context-legacy-scalar-still-accepted",
        lambda p: p["execution"].pop("testContext"),
        {"scope": "repository"},
        True,
        False,
    )
    assert len(rows) == 12 and sum(r["httpStatus"] == 200 for r in rows) == 5
    assert sum(r["httpStatus"] == 404 for r in rows) == 7
    summary = {
        "inputFreezeSha256": sha(HERE / "INPUT_FREEZE.json"),
        "policyRevision": declaration["codeRevision"],
        "newDiagnosticPolicyNotFrozenCampaignPolicy": True,
        "tasks": len(rows),
        "hits": 5,
        "misses": 7,
        "scalarPolicyAccepted": sum(r["scalarPolicy"]["accepted"] for r in rows),
        "contextPolicySelected": sum(
            r["contextualPolicy"]["instruction"] is not None for r in rows
        ),
        "taskSupportedDirectCompleteInstructions": 0,
        "profileTaskRevisionMatches": sum(r["recordRevisionMatchesTask"] is True for r in rows),
        "profileTaskRevisionMismatches": sum(r["recordRevisionMatchesTask"] is False for r in rows),
        "controlledPolicyCases": len(controls),
        "actualFallbackAttempts": 0,
        "agentSessions": 0,
        "finalCompletionMeasured": False,
        "causalBenefitMeasured": False,
    }
    return {"summary": summary, "rows": rows, "controls": controls}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
