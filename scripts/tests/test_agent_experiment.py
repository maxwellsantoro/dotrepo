"""Synthetic controls for offline F-05 preparation; no model or upstream execution."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

BENCH = Path(__file__).resolve().parents[2] / "benchmarks/head-to-head"
sys.path.insert(0, str(BENCH))
from bench import agent_experiment as experiment  # noqa: E402


def write(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = value if isinstance(value, bytes) else experiment.encode(value)
    path.write_bytes(raw)
    return {"path": name, "sha256": hashlib.sha256(raw).hexdigest()}


@pytest.fixture
def packet(tmp_path):
    """This is test data, not a frozen empirical workload or evidence packet."""
    artifacts = {
        role: write(tmp_path, f"artifacts/{role}.json", {"testFixtureRole": role})
        for role in experiment.REQUIRED_ARTIFACTS
    }
    script = Path(experiment.__file__).read_bytes()
    for role in ("assignmentScript", "analysisScript"):
        artifacts[role] = write(tmp_path, f"artifacts/{role}.py", script)
    tasks = []
    for index in range(12):
        task_id = f"task-{index:02}"
        tasks.append(
            {
                "id": task_id,
                "repository": f"example.test/fixtures/repo-{index % 8}",
                "revision": f"{index + 1:040x}",
                "ecosystem": ("rust", "python", "javascript-typescript", "go")[index // 3],
                "scope": "repository" if index % 2 == 0 else "component",
                "startingState": "pre-clone" if index < 6 else "local-checkout",
                "request": f"Investigate test task {index}",
                "sourceCheckedAt": "2026-10-28T10:00:00Z",
                **{
                    role: write(
                        tmp_path,
                        f"tasks/{task_id}/{role}.json",
                        {
                            "testFixtureRole": role,
                            "taskId": task_id,
                        },
                    )
                    for role in ("source", "prompt", "gold", "oracle")
                },
            }
        )
    entries = [
        {
            "set": "f05",
            "repository": t["repository"],
            "taskIds": [t["id"]],
            "relatedRepositories": [],
        }
        for t in tasks
    ]
    entries += [
        {
            "set": group,
            "repository": f"example.test/fixtures/{group}",
            "taskIds": [group],
            "relatedRepositories": [],
        }
        for group in ("historical", "e1-development", "e1-qualification")
    ]
    artifacts["splitLedger"] = write(tmp_path, "artifacts/splitLedger.json", {"entries": entries})
    manifest = {
        "version": 1,
        "experimentId": "synthetic-control-only",
        "seed": 5481,
        "repeats": 3,
        "frozenAt": "2026-10-29T10:00:00Z",
        "selectedAt": "2026-10-28T09:00:00Z",
        "coverageInspectedAt": "2026-10-28T11:00:00Z",
        "hypothesis": "Synthetic validation control",
        "selectionBeforeCoverageInspection": True,
        "model": {
            "provider": "fixture",
            "id": "fixture-model",
            "version": "fixture-v1",
            "inferenceSettings": {"temperature": 0, "reasoning": "fixed"},
        },
        "environment": {"id": "fixture-image", "imageDigest": "sha256:" + "a" * 64},
        "budgets": {
            "wallTimeSeconds": 600,
            "toolCalls": 100,
            "inputTokens": 20000,
            "outputTokens": 10000,
            "monetaryUsd": 1,
        },
        "campaignBudgetUsd": 72,
        "cacheState": "cold",
        "personnel": {
            "development": "developer",
            "gold": "assessor",
            "operator": "operator",
            "scorer": "assessor",
        },
        "artifacts": artifacts,
        "tasks": tasks,
    }
    path = tmp_path / "manifest.json"
    path.write_bytes(experiment.encode(manifest))
    return path, manifest


def save(packet):
    path, manifest = packet
    path.write_bytes(experiment.encode(manifest))
    return path


def prepare(packet):
    path = save(packet)
    out = path.parent / "prepared"
    plan = experiment.prepare(path, out)
    return path, out / "assignment.json", plan


def observed(packet):
    path, assignment_path, plan = prepare(packet)
    manifest = packet[1]
    runs = []
    start = datetime(2026, 10, 29, 11, tzinfo=timezone.utc)
    for index, session in enumerate(plan["sessions"]):
        request = experiment.session_request(manifest, session)
        prefix = f"observed/{session['sessionId']}"
        receipt = {
            "sessionId": session["sessionId"],
            "requestSha256": experiment.digest(experiment.encode(request)),
        }
        trace = write(path.parent, f"{prefix}/trace.json", receipt)
        effort = {
            key: 1 if key in {"elapsedSeconds", "toolCalls"} else 0 for key in experiment.EFFORT
        }
        usage = write(
            path.parent,
            f"{prefix}/usage.json",
            {
                **receipt,
                "model": request["model"],
                "environment": request["environment"],
                "runtimeSha256": manifest["artifacts"]["runtime"]["sha256"],
                "effort": effort,
            },
        )
        task = next(t for t in manifest["tasks"] if t["id"] == session["taskId"])
        score = {
            "sessionId": session["sessionId"],
            "traceSha256": trace["sha256"],
            "scorerSha256": manifest["artifacts"]["scorer"]["sha256"],
            "oracleSha256": task["oracle"]["sha256"],
            "goldSha256": task["gold"]["sha256"],
            "errorRubricSha256": manifest["artifacts"]["errorRubric"]["sha256"],
            "rationale": "Synthetic control",
            **{metric: metric == "correctCompletion" for metric in experiment.METRICS},
        }
        score_binding = write(path.parent, f"{prefix}/score.json", score)
        end = start + timedelta(seconds=1)
        runs.append(
            {
                "sessionId": session["sessionId"],
                **{
                    key: request[key]
                    for key in (
                        "model",
                        "environment",
                        "budgets",
                        "cacheState",
                        "workspaceKey",
                        "cacheKey",
                    )
                },
                "requestSha256": experiment.digest(experiment.encode(request)),
                "startedAt": start.isoformat(),
                "endedAt": end.isoformat(),
                "status": "completed",
                "protocolDeviations": [],
                "measurementExclusions": [],
                "controls": {
                    key: True
                    for key in (
                        "freshSession",
                        "goldInaccessible",
                        "otherSessionsInaccessible",
                        "cacheConditionEnforced",
                        "armAccessEnforced",
                        "budgetsEnforced",
                    )
                },
                "trace": trace,
                "usage": usage,
                "score": score_binding,
                "effort": effort,
            }
        )
        start = end + timedelta(seconds=1)
    observations = {
        "version": 1,
        "assignmentSha256": experiment.digest(assignment_path.read_bytes()),
        "runs": runs,
    }
    observations_path = path.parent / "observations.json"
    observations_path.write_bytes(experiment.encode(observations))
    return path, assignment_path, observations_path, observations


def rescore(root, run, **changes):
    score = experiment.read_json(root / run["score"]["path"])
    score.update(changes)
    run["score"] = write(root, run["score"]["path"], score)


def bind_usage(root, run):
    receipt = experiment.read_json(root / run["usage"]["path"])
    receipt["effort"] = deepcopy(run["effort"])
    run["usage"] = write(root, run["usage"]["path"], receipt)


def test_reproducible_randomized_72_fresh_sessions_with_hidden_gold(packet):
    path, assignment_path, plan = prepare(packet)
    manifest, actual = experiment.verify(path, assignment_path)
    assert actual == plan
    assert len(plan["sessions"]) == len({s["sessionId"] for s in plan["sessions"]}) == 72
    assert {s["repeat"] for s in plan["sessions"]} == {1, 2, 3}
    first_arms = [plan["sessions"][i]["arm"] for i in range(0, 72, 2)]
    assert set(first_arms) == set(experiment.ARMS)
    assert [plan["sessions"][i]["taskId"] for i in range(0, 72, 2)] != sorted(
        plan["sessions"][i]["taskId"] for i in range(0, 72, 2)
    )
    requests = [experiment.session_request(manifest, s) for s in plan["sessions"]]
    assert len({r["workspaceKey"] for r in requests}) == 72
    for request in requests:
        text = json.dumps(request)
        assert '"gold"' not in text and '"oracle"' not in text and '"scorer"' not in text
        assert ("snapshot" in request["artifacts"]) == (request["arm"] == "dotrepo-access")
    assert experiment.assignment(manifest, plan["manifestSha256"]) == plan
    changed = deepcopy(manifest)
    changed["seed"] += 1
    assert experiment.assignment(changed, plan["manifestSha256"])["sessions"] != plan["sessions"]


@pytest.mark.parametrize(
    "mutation,message",
    [
        (lambda m: m["model"].update(version="TBD"), "unresolved"),
        (lambda m: m["model"]["inferenceSettings"].update(temperature=None), "unresolved"),
        (lambda m: m["environment"].update(imageDigest="latest"), "immutable image"),
        (lambda m: m["budgets"].update(toolCalls=True), "invalid toolCalls"),
        (lambda m: m.update(repeats=1), "three repeats"),
        (lambda m: m.update(selectionBeforeCoverageInspection=False), "before coverage"),
        (lambda m: m.update(selectedAt=m["coverageInspectedAt"]), "before coverage"),
        (lambda m: m["tasks"][0].update(revision="main"), "Git revision"),
        (lambda m: m["tasks"][0].update(ecosystem="go"), "ecosystem quota"),
        (lambda m: m["tasks"][0].update(scope="component"), "scope quota"),
        (lambda m: m["tasks"][0].update(startingState="local-checkout"), "startingState quota"),
        (lambda m: m["tasks"][0].update(sourceCheckedAt="2027-01-01T00:00:00Z"), "postdates"),
        (lambda m: m["personnel"].update(gold=m["personnel"]["development"]), "separate"),
        (lambda m: m["artifacts"].pop("policy"), "artifact roles"),
    ],
)
def test_incomplete_or_unfrozen_manifest_fails_closed(packet, mutation, message):
    mutation(packet[1])
    with pytest.raises(ValueError, match=message):
        experiment.validate_manifest(save(packet))


@pytest.mark.parametrize("related", [False, True])
def test_repository_and_fork_leakage_rejected(packet, related):
    path, manifest = packet
    ledger_path = path.parent / manifest["artifacts"]["splitLedger"]["path"]
    ledger = experiment.read_json(ledger_path)
    entry = ledger["entries"][-1]
    if related:
        entry["relatedRepositories"] = [manifest["tasks"][0]["repository"]]
    else:
        entry["repository"] = manifest["tasks"][0]["repository"]
    manifest["artifacts"]["splitLedger"] = write(path.parent, "artifacts/splitLedger.json", ledger)
    with pytest.raises(ValueError, match="leakage"):
        experiment.validate_manifest(save(packet))


@pytest.mark.parametrize("unsafe", ["../outside.json", "/tmp/outside.json"])
def test_artifact_traversal_rejected(packet, unsafe):
    packet[1]["artifacts"]["snapshot"]["path"] = unsafe
    with pytest.raises(ValueError, match="stay within"):
        experiment.validate_manifest(save(packet))


def test_symlink_even_within_packet_rejected(packet):
    path, manifest = packet
    original = path.parent / manifest["artifacts"]["snapshot"]["path"]
    linked = path.parent / "snapshot-link"
    linked.symlink_to(original)
    manifest["artifacts"]["snapshot"]["path"] = linked.name
    with pytest.raises(ValueError, match="symlink"):
        experiment.validate_manifest(save(packet))


def test_changed_artifact_and_rehashed_manifest_rejected_after_prepare(packet):
    path, assignment_path, _ = prepare(packet)
    artifact_path = path.parent / packet[1]["artifacts"]["policy"]["path"]
    artifact_path.write_text("changed policy")
    with pytest.raises(ValueError, match="hash mismatch"):
        experiment.verify(path, assignment_path)
    packet[1]["artifacts"]["policy"]["sha256"] = experiment.digest(artifact_path.read_bytes())
    save(packet)
    with pytest.raises(ValueError, match="manifest changed"):
        experiment.verify(path, assignment_path)


def test_assignment_order_and_agent_request_tampering_rejected(packet):
    path, assignment_path, plan = prepare(packet)
    changed = deepcopy(plan)
    changed["sessions"][0], changed["sessions"][1] = changed["sessions"][1], changed["sessions"][0]
    assignment_path.write_bytes(experiment.encode(changed))
    with pytest.raises(ValueError, match="assignment changed"):
        experiment.verify(path, assignment_path)
    assignment_path.write_bytes(experiment.encode(plan))
    request_path = assignment_path.parent / "requests" / f"{plan['sessions'][0]['sessionId']}.json"
    request = experiment.read_json(request_path)
    request["budgets"]["monetaryUsd"] += 1
    request_path.write_bytes(experiment.encode(request))
    with pytest.raises(ValueError, match="session request changed"):
        experiment.verify(path, assignment_path)


def test_output_immutability_and_cli_failure(packet):
    path, assignment_path, _ = prepare(packet)
    with pytest.raises(FileExistsError):
        experiment.prepare(path, assignment_path.parent)
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "bench.agent_experiment",
            "verify",
            "--manifest",
            str(path),
            "--assignment",
            str(assignment_path),
        ],
        cwd=BENCH,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "live controls remain runner obligations" in result.stdout


def test_duplicate_json_keys_rejected(packet):
    path, _ = packet
    path.write_text('{"version": 1, "version": 2}')
    with pytest.raises(ValueError, match="duplicate JSON key"):
        experiment.validate_manifest(path)


def test_summary_keeps_nonuse_failures_and_equal_task_weight(packet):
    path, assignment_path, observations_path, observations = observed(packet)
    # All access repeats of one task fail. Every assigned task still weighs 1/12.
    for run in observations["runs"]:
        if run["sessionId"].startswith("task-00-") and run["sessionId"].endswith("dotrepo-access"):
            run["status"] = "budget-exhausted"
            rescore(path.parent, run, correctCompletion=False, incorrectAction=True)
    observations_path.write_bytes(experiment.encode(observations))
    report = experiment.summarize(path, assignment_path, observations_path)
    assert report["assignedSessions"] == 72
    assert report["summary"]["dotrepo-access"]["correctCompletion"] == pytest.approx(11 / 12)
    assert report["summary"]["dotrepo-access"]["incorrectAction"] == pytest.approx(1 / 12)
    assert report["summary"]["dotrepo-access"]["directApplicableInstruction"] == 0
    assert report["summary"]["dotrepo-access"]["assignedSessions"] == 36
    assert not report["independentlyVerified"] and not report["externalAdoption"]
    assert report["breakdowns"]["ecosystem"]["rust"]["dotrepo-access"]["tasks"] == 3
    assert report["breakdowns"]["scope"]["component"]["source-first"]["assignedSessions"] == 18
    assert report["summary"]["source-first"]["effortTotals"]["toolCalls"] == 36


@pytest.mark.parametrize("field", ["model", "environment", "budgets", "workspaceKey", "cacheKey"])
def test_runtime_binding_changes_abort_scoring(packet, field):
    path, assignment_path, observations_path, observations = observed(packet)
    observations["runs"][0][field] = "changed"
    observations_path.write_bytes(experiment.encode(observations))
    with pytest.raises(ValueError, match=f"runtime {field}"):
        experiment.summarize(path, assignment_path, observations_path)


def test_all_assigned_sessions_required_and_trace_score_bound(packet):
    path, assignment_path, observations_path, observations = observed(packet)
    removed = observations["runs"].pop()
    observations_path.write_bytes(experiment.encode(observations))
    with pytest.raises(ValueError, match="72 assigned"):
        experiment.summarize(path, assignment_path, observations_path)
    observations["runs"].append(removed)
    rescore(path.parent, removed, traceSha256="0" * 64)
    observations_path.write_bytes(experiment.encode(observations))
    with pytest.raises(ValueError, match="different trace"):
        experiment.summarize(path, assignment_path, observations_path)


def test_unknown_cost_and_unresolved_outcome_not_zeroed_or_deleted(packet):
    path, assignment_path, observations_path, observations = observed(packet)
    run = observations["runs"][0]
    run["status"] = "unresolved"
    rescore(path.parent, run, correctCompletion=None)
    run["effort"]["providerCostUsd"] = None
    bind_usage(path.parent, run)
    run["measurementExclusions"] = ["Provider receipt unavailable"]
    observations_path.write_bytes(experiment.encode(observations))
    report = experiment.summarize(path, assignment_path, observations_path)
    arm = "dotrepo-access" if run["sessionId"].endswith("dotrepo-access") else "source-first"
    assert report["summary"][arm]["correctCompletion"] is None
    assert report["summary"][arm]["effort"]["providerCostUsd"] is None
    assert len(report["rows"]) == 72


@pytest.mark.parametrize("role", ["prompt", "commonPrompt", "permissions"])
def test_hidden_gold_cannot_alias_agent_visible_binding(packet, role):
    _, manifest = packet
    gold = deepcopy(manifest["tasks"][0]["gold"])
    if role == "prompt":
        # Cross-task alias defeats only checking the current task's four paths.
        manifest["tasks"][1][role] = gold
    else:
        manifest["artifacts"][role] = gold
    with pytest.raises(ValueError, match="aliases"):
        experiment.validate_manifest(save(packet))


def test_duplicate_hidden_bytes_under_different_path_still_rejected(packet):
    path, manifest = packet
    raw = (path.parent / manifest["tasks"][0]["oracle"]["path"]).read_bytes()
    manifest["artifacts"]["commonPrompt"] = write(path.parent, "copied-oracle.json", raw)
    with pytest.raises(ValueError, match="aliases"):
        experiment.validate_manifest(save(packet))


def test_missing_measurements_and_undeclared_control_failure_rejected(packet):
    path, assignment_path, observations_path, observations = observed(packet)
    run = observations["runs"][0]
    run["effort"]["providerCostUsd"] = None
    bind_usage(path.parent, run)
    observations_path.write_bytes(experiment.encode(observations))
    with pytest.raises(ValueError, match="missing measurement"):
        experiment.summarize(path, assignment_path, observations_path)
    run["measurementExclusions"] = ["Provider receipt unavailable"]
    run["controls"]["goldInaccessible"] = False
    observations_path.write_bytes(experiment.encode(observations))
    with pytest.raises(ValueError, match="protocol deviation"):
        experiment.summarize(path, assignment_path, observations_path)
    # A control failure remains in the ledger rather than disappearing from ITT.
    run["protocolDeviations"] = ["Operator found gold readable after this run"]
    observations_path.write_bytes(experiment.encode(observations))
    report = experiment.summarize(path, assignment_path, observations_path)
    assert len(report["rows"]) == 72
    assert report["rows"][0]["protocolDeviations"]


def test_budget_overrun_must_be_visible_and_never_erases_session(packet):
    path, assignment_path, observations_path, observations = observed(packet)
    run = observations["runs"][0]
    run["effort"]["toolCalls"] = packet[1]["budgets"]["toolCalls"] + 1
    bind_usage(path.parent, run)
    observations_path.write_bytes(experiment.encode(observations))
    with pytest.raises(ValueError, match="budget overrun"):
        experiment.summarize(path, assignment_path, observations_path)
    run["protocolDeviations"] = ["One tool completion arrived after stop signal"]
    observations_path.write_bytes(experiment.encode(observations))
    report = experiment.summarize(path, assignment_path, observations_path)
    assert report["assignedSessions"] == 72


def test_changed_oracle_and_scorer_score_binding_rejected(packet):
    path, assignment_path, observations_path, observations = observed(packet)
    run = observations["runs"][0]
    rescore(path.parent, run, oracleSha256="0" * 64)
    observations_path.write_bytes(experiment.encode(observations))
    with pytest.raises(ValueError, match="oracle changed"):
        experiment.summarize(path, assignment_path, observations_path)


def test_scoring_observations_join_ids_without_historical_alternation(packet):
    path, assignment_path, observations_path, observations = observed(packet)
    observations["runs"].reverse()
    observations_path.write_bytes(experiment.encode(observations))
    report = experiment.summarize(path, assignment_path, observations_path)
    assert all(report["summary"][arm]["correctCompletion"] == 1 for arm in experiment.ARMS)


@pytest.mark.parametrize(
    "key,value",
    [
        ("providerCostUsd", 0.75),
        ("inputTokens", 1500),
        ("toolCalls", 99),
        ("reasoningTokens", None),
    ],
)
def test_usage_measurement_receipt_contradiction_rejected(packet, key, value):
    path, assignment_path, observations_path, observations = observed(packet)
    run = observations["runs"][0]
    receipt = experiment.read_json(path.parent / run["usage"]["path"])
    receipt["effort"][key] = value
    run["usage"] = write(path.parent, run["usage"]["path"], receipt)
    observations_path.write_bytes(experiment.encode(observations))
    with pytest.raises(ValueError, match="usage measurements differ"):
        experiment.summarize(path, assignment_path, observations_path)


@pytest.mark.parametrize("key", ["model", "environment", "runtimeSha256"])
def test_observed_usage_runtime_must_match_campaign_freeze(packet, key):
    path, assignment_path, observations_path, observations = observed(packet)
    run = observations["runs"][0]
    receipt = experiment.read_json(path.parent / run["usage"]["path"])
    if key == "runtimeSha256":
        receipt[key] = "0" * 64
    else:
        receipt[key]["id"] = "different-observed-runtime"
    run["usage"] = write(path.parent, run["usage"]["path"], receipt)
    observations_path.write_bytes(experiment.encode(observations))
    with pytest.raises(ValueError, match="usage observed"):
        experiment.summarize(path, assignment_path, observations_path)


def test_unnormalized_usage_cannot_hide_conflicting_top_level_measurements(packet):
    path, assignment_path, observations_path, observations = observed(packet)
    run = observations["runs"][0]
    receipt = experiment.read_json(path.parent / run["usage"]["path"])
    receipt["providerCostUsd"] = 0.75
    receipt["inputTokens"] = 1500
    run["usage"] = write(path.parent, run["usage"]["path"], receipt)
    observations_path.write_bytes(experiment.encode(observations))
    with pytest.raises(ValueError, match="normalized measurement contract"):
        experiment.summarize(path, assignment_path, observations_path)


@pytest.mark.parametrize("unknown_cost", [False, True])
def test_campaign_known_subtotal_overrun_requires_visible_disposition(packet, unknown_cost):
    # All individual sessions satisfy their $1 ceiling, but violate the campaign ceiling.
    packet[1]["campaignBudgetUsd"] = 0.01
    path, assignment_path, observations_path, observations = observed(packet)
    for run in observations["runs"]:
        run["effort"]["providerCostUsd"] = 0.50
        bind_usage(path.parent, run)
    if unknown_cost:
        run = observations["runs"][0]
        run["effort"]["providerCostUsd"] = None
        run["measurementExclusions"] = ["Provider billing receipt unavailable"]
        bind_usage(path.parent, run)
    observations_path.write_bytes(experiment.encode(observations))
    with pytest.raises(ValueError, match="campaign budget overrun"):
        experiment.summarize(path, assignment_path, observations_path)
    observations["campaignProtocolDeviations"] = ["Campaign stop monitor failed; retain all costs"]
    observations_path.write_bytes(experiment.encode(observations))
    report = experiment.summarize(path, assignment_path, observations_path)
    budget = report["campaignBudget"]
    assert budget["status"] == "exceeded"
    assert budget["knownSubtotalUsd"] == (35.5 if unknown_cost else 36)
    assert budget["totalCostUsd"] == (None if unknown_cost else 36)
    assert budget["missingMeasurements"] == int(unknown_cost)
    assert budget["protocolDeviations"] == observations["campaignProtocolDeviations"]
    assert len(report["rows"]) == report["assignedSessions"] == 72


def test_unknown_campaign_cost_cannot_be_reported_as_within_budget(packet):
    path, assignment_path, observations_path, observations = observed(packet)
    run = observations["runs"][0]
    run["effort"]["maintenanceCostUsd"] = None
    run["measurementExclusions"] = ["Allocated maintenance labor unavailable"]
    bind_usage(path.parent, run)
    observations_path.write_bytes(experiment.encode(observations))
    budget = experiment.summarize(path, assignment_path, observations_path)["campaignBudget"]
    assert budget["status"] == "unresolved"
    assert budget["knownSubtotalUsd"] == 0
    assert budget["totalCostUsd"] is None
    assert budget["missingMeasurements"] == 1


def test_all_retained_monetary_costs_count_toward_campaign_ceiling(packet):
    packet[1]["campaignBudgetUsd"] = 1
    path, assignment_path, observations_path, observations = observed(packet)
    run = observations["runs"][0]
    run["effort"].update(providerCostUsd=0.25, preparationCostUsd=0.50, maintenanceCostUsd=0.50)
    bind_usage(path.parent, run)
    observations_path.write_bytes(experiment.encode(observations))
    with pytest.raises(ValueError, match="campaign budget overrun"):
        experiment.summarize(path, assignment_path, observations_path)


def test_rehashed_usage_false_is_not_numeric_zero(packet):
    path, assignment_path, observations_path, observations = observed(packet)
    run = observations["runs"][0]
    assert run["effort"]["inputTokens"] == 0
    receipt = experiment.read_json(path.parent / run["usage"]["path"])
    receipt["effort"]["inputTokens"] = False
    run["usage"] = write(path.parent, run["usage"]["path"], receipt)
    observations_path.write_bytes(experiment.encode(observations))
    with pytest.raises(ValueError, match="usage measurements differ"):
        experiment.summarize(path, assignment_path, observations_path)


@pytest.mark.parametrize("alter_reported_model", [False, True])
def test_observed_model_boolean_setting_cannot_alias_frozen_numeric_setting(
    packet, alter_reported_model
):
    path, assignment_path, observations_path, observations = observed(packet)
    run = observations["runs"][0]
    assert run["model"]["inferenceSettings"]["temperature"] == 0
    receipt = experiment.read_json(path.parent / run["usage"]["path"])
    receipt["model"]["inferenceSettings"]["temperature"] = False
    run["usage"] = write(path.parent, run["usage"]["path"], receipt)
    if alter_reported_model:
        run["model"]["inferenceSettings"]["temperature"] = False
    observations_path.write_bytes(experiment.encode(observations))
    message = "runtime model differs" if alter_reported_model else "usage observed model differs"
    with pytest.raises(ValueError, match=message):
        experiment.summarize(path, assignment_path, observations_path)
