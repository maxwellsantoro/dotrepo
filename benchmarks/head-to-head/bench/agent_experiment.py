"""Prepare and verify F-05 independent-session assignments; never execute tasks.

A version-1 manifest contains experimentId, frozenAt, selectedAt,
coverageInspectedAt, hypothesis, selectionBeforeCoverageInspection=true,
repeats=3, seed (integer), model {provider, id, version, inferenceSettings},
environment {id, imageDigest}, budgets {wallTimeSeconds, toolCalls, inputTokens,
outputTokens, monetaryUsd}, campaignBudgetUsd, cacheState, personnel
{development, gold, operator, scorer}, artifacts, and twelve tasks.

Artifacts map REQUIRED_ARTIFACTS roles to {path, sha256}, relative to the
manifest directory. assignmentScript and analysisScript bind this module.
source, prompt, gold, and oracle bindings on tasks use the same convention.
Tasks contain id, repository (canonical host/owner/repo), revision (Git SHA),
ecosystem, scope, startingState, request, sourceCheckedAt, and those bindings.
The splitLedger artifact is JSON {entries: [{set, repository, taskIds,
relatedRepositories}]}; sets are historical, e1-development, e1-qualification,
and f05. Repository and declared related identities cannot cross sets.

prepare emits only requests and a deterministic assignment, never source gold
or oracles. verify rechecks every frozen byte and request before a session.
The runner must enforce isolation, budgets, model identity and permissions;
this offline tool cannot establish live controls or execute a paid campaign.
Optional summarize validates hash-bound post-run scoring and traces for every
assigned session; it does not derive truth from exit status or reject an agent
choice using hidden gold. See tests for a complete synthetic manifest example.

Each normalized usage receipt is exactly {sessionId, requestSha256, model,
environment, runtimeSha256, effort}. Model and environment are observed runtime
identities; runtimeSha256 binds the frozen runtime artifact. effort contains
every EFFORT measurement, including provider charges for failed calls and null
for unavailable measurements. The receipt must agree with the observation row;
null values require row measurementExclusions. Consistency does not authenticate
provider provenance. Preserve native usage evidence separately when available.

campaignBudgetUsd bounds the sum of retained provider, preparation and allocated
maintenance costs. Report known subtotal and nullable total separately. A known
subtotal above the ceiling requires nonempty observations.campaignProtocolDeviations;
otherwise summarization refuses. Unknown costs leave budget compliance unresolved
unless the known subtotal already proves overrun. No sessions are removed.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import random
import re


ARMS = ("source-first", "dotrepo-access")
REQUIRED_ARTIFACTS = {
    "eligibilityFrame",
    "selectionRule",
    "splitLedger",
    "commonPrompt",
    "accessInstructions",
    "tools",
    "permissions",
    "dependencies",
    "runtime",
    "extractor",
    "consumer",
    "scorer",
    "integration",
    "snapshot",
    "responses",
    "policy",
    "assignmentScript",
    "analysisScript",
    "cache",
    "costRates",
    "costAllocation",
    "stopRules",
    "retryRules",
    "errorRubric",
    "accessControls",
}
BUDGETS = {"wallTimeSeconds", "toolCalls", "inputTokens", "outputTokens", "monetaryUsd"}
METRICS = (
    "correctCompletion",
    "incorrectAction",
    "incorrectInstructionAccepted",
    "directApplicableInstruction",
    "correctAbstentionFallback",
    "policySelectionError",
)
EFFORT = (
    "elapsedSeconds",
    "toolCalls",
    "httpRequests",
    "decodedBytes",
    "inputTokens",
    "outputTokens",
    "cachedTokens",
    "reasoningTokens",
    "providerCostUsd",
    "preparationCostUsd",
    "maintenanceCostUsd",
    "sourceVerificationToolCalls",
)
COST_FIELDS = ("providerCostUsd", "preparationCostUsd", "maintenanceCostUsd")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def read_json(path):
    def duplicate_free(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(Path(path).read_bytes(), object_pairs_hook=duplicate_free)


def resolved(value, label="manifest"):
    """Reject unfinished preregistration placeholders, including nested settings."""
    require(value is not None, f"unresolved {label}")
    if isinstance(value, str):
        require(bool(value.strip()), f"empty {label}")
        require(
            not re.search(r"\b(?:TODO|TBD|FIXME|UNRESOLVED|PLACEHOLDER)\b|<[^>]+>", value, re.I),
            f"unresolved {label}",
        )
    elif isinstance(value, float):
        require(math.isfinite(value), f"nonfinite {label}")
    elif isinstance(value, dict):
        for key, item in value.items():
            resolved(item, f"{label}.{key}")
    elif isinstance(value, list):
        for item in value:
            resolved(item, label)


def timestamp(value):
    require(isinstance(value, str), "timestamp must be text")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "timestamps need a timezone")
    return parsed


def positive(value, label, *, integer=False):
    require(
        type(value) in (int, float)
        and math.isfinite(value)
        and value > 0
        and (not integer or type(value) is int),
        f"invalid {label}",
    )


def safe_path(root, relative):
    require(isinstance(relative, str) and relative, "missing artifact path")
    path = Path(relative)
    require(
        not path.is_absolute() and ".." not in path.parts and path.parts,
        "artifact path must stay within packet",
    )
    current = root
    for part in path.parts:
        current /= part
        require(not current.is_symlink(), "symlink artifact paths are forbidden")
    require(current.is_file(), f"missing artifact: {relative}")
    return current


def artifact(root, binding):
    require(isinstance(binding, dict) and set(binding) == {"path", "sha256"}, "invalid binding")
    require(re.fullmatch(r"[0-9a-f]{64}", binding["sha256"]) is not None, "invalid SHA-256")
    path = safe_path(root, binding["path"])
    raw = path.read_bytes()
    require(digest(raw) == binding["sha256"], f"artifact hash mismatch: {binding['path']}")
    return raw


def repository(value):
    require(
        isinstance(value, str)
        and re.fullmatch(r"[a-z0-9.-]+/[a-z0-9_.-]+/[a-z0-9_.-]+", value) is not None
        and not value.endswith(".git")
        and all(part not in {".", ".."} for part in value.split("/")),
        "repository must be canonical lowercase host/owner/repo",
    )
    return value


def validate_splits(ledger, tasks):
    expected = {(task["repository"], task["id"]) for task in tasks}
    actual, identities = set(), {}
    require(isinstance(ledger.get("entries"), list), "split ledger needs entries")
    for entry in ledger["entries"]:
        group = entry["set"]
        require(
            group in {"historical", "e1-development", "e1-qualification", "f05"},
            "unknown split set",
        )
        repo = repository(entry["repository"])
        require(isinstance(entry["relatedRepositories"], list), "missing related identities")
        for identity in [repo, *entry["relatedRepositories"]]:
            repository(identity)
            require(
                identity not in identities or identities[identity] == group,
                f"repository leakage across sets: {identity}",
            )
            identities[identity] = group
        require(
            isinstance(entry["taskIds"], list) and bool(entry["taskIds"]),
            "split entry needs task identities",
        )
        for task_id in entry["taskIds"]:
            require(isinstance(task_id, str) and task_id.strip(), "invalid split task")
            if group == "f05":
                require((repo, task_id) not in actual, "duplicate f05 split task")
                actual.add((repo, task_id))
    require(actual == expected, "F-05 roster differs from split ledger")


def validate_manifest(path):
    path = Path(path)
    manifest = read_json(path)
    resolved(manifest)
    require(manifest["version"] == 1, "unsupported manifest version")
    require(
        re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", manifest["experimentId"]) is not None,
        "invalid experiment identity",
    )
    frozen = timestamp(manifest["frozenAt"])
    require(
        timestamp(manifest["selectedAt"]) < timestamp(manifest["coverageInspectedAt"]) <= frozen
        and manifest["selectionBeforeCoverageInspection"] is True,
        "roster must be frozen before coverage inspection",
    )
    require(
        type(manifest["seed"]) is int and manifest["repeats"] == 3, "need seed and three repeats"
    )
    require(isinstance(manifest["hypothesis"], str), "missing hypothesis")
    model = manifest["model"]
    require(set(model) == {"provider", "id", "version", "inferenceSettings"}, "incomplete model")
    require(
        all(isinstance(model[key], str) for key in ("provider", "id", "version")),
        "model identities must be text",
    )
    require(isinstance(model["inferenceSettings"], dict), "inference settings must be explicit")
    require(model["inferenceSettings"], "missing inference settings")
    environment = manifest["environment"]
    require(set(environment) == {"id", "imageDigest"}, "incomplete environment")
    require(
        re.fullmatch(r"sha256:[0-9a-f]{64}", environment["imageDigest"]) is not None,
        "environment requires an immutable image digest",
    )
    require(set(manifest["budgets"]) == BUDGETS, "incomplete budgets")
    for key, value in manifest["budgets"].items():
        positive(value, key, integer=key not in {"monetaryUsd", "wallTimeSeconds"})
    positive(manifest["campaignBudgetUsd"], "campaign budget")
    require(manifest["cacheState"] in {"cold", "frozen-warm"}, "invalid cache state")
    require(
        set(manifest["personnel"]) == {"development", "gold", "operator", "scorer"},
        "declare development, gold, operator and scorer responsibility",
    )
    require(
        manifest["personnel"]["development"] != manifest["personnel"]["gold"],
        "gold assessment must be separate from extractor tuning",
    )
    require(
        all(isinstance(value, str) for value in manifest["personnel"].values()),
        "personnel identities must be text",
    )
    bindings = manifest["artifacts"]
    require(set(bindings) == REQUIRED_ARTIFACTS, "incomplete frozen artifact roles")
    root = path.parent.resolve()
    for binding in bindings.values():
        artifact(root, binding)
    script_hash = digest(Path(__file__).read_bytes())
    for role in ("assignmentScript", "analysisScript"):
        require(bindings[role]["sha256"] == script_hash, f"{role} differs from executing script")
    tasks = manifest["tasks"]
    require(isinstance(tasks, list) and len(tasks) == 12, "F-05 requires twelve tasks")
    require(len({task["id"] for task in tasks}) == 12, "duplicate task identity")
    for task in tasks:
        require(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", task["id"]) is not None, "invalid task id")
        repository(task["repository"])
        require(re.fullmatch(r"[0-9a-f]{40}", task["revision"]) is not None, "need Git revision")
        require(isinstance(task["request"], str), "missing task request")
        require(timestamp(task["sourceCheckedAt"]) <= frozen, "source check postdates freeze")
        for role in ("source", "prompt", "gold", "oracle"):
            artifact(root, task[role])
        require(
            len({task[role]["path"] for role in ("source", "prompt", "gold", "oracle")}) == 4,
            "source, prompt, gold and oracle must be separate artifacts",
        )
    # A role allowlist is insufficient if an allowed binding aliases hidden gold.
    hidden = [task[role] for task in tasks for role in ("gold", "oracle")]
    visible = [*bindings.values(), *(task["prompt"] for task in tasks)]
    require(
        not any(
            h["path"] == v["path"] or h["sha256"] == v["sha256"] for h in hidden for v in visible
        ),
        "gold/oracle aliases a potentially agent-visible artifact",
    )
    for key, expected in (
        ("ecosystem", {"rust": 3, "python": 3, "javascript-typescript": 3, "go": 3}),
        ("scope", {"repository": 6, "component": 6}),
        ("startingState", {"pre-clone": 6, "local-checkout": 6}),
    ):
        require(Counter(task[key] for task in tasks) == expected, f"task {key} quota mismatch")
    repositories = Counter(task["repository"] for task in tasks)
    require(len(repositories) >= 8 and max(repositories.values()) <= 2, "repository quota mismatch")
    validate_splits(read_json(safe_path(root, bindings["splitLedger"]["path"])), tasks)
    return manifest


def assignment(manifest, manifest_sha256):
    """Sorted task identities avoid JSON roster order silently altering assignment."""
    rng = random.Random(manifest["seed"])
    blocks = [
        (task["id"], repeat)
        for task in sorted(manifest["tasks"], key=lambda task: task["id"])
        for repeat in range(1, 4)
    ]
    rng.shuffle(blocks)
    sessions = []
    for task_id, repeat in blocks:
        arms = list(ARMS)
        rng.shuffle(arms)
        for arm in arms:
            sessions.append(
                {
                    "sessionId": f"{task_id}-r{repeat}-{arm}",
                    "taskId": task_id,
                    "repeat": repeat,
                    "arm": arm,
                    "order": len(sessions) + 1,
                }
            )
    return {
        "version": 1,
        "experimentId": manifest["experimentId"],
        "manifestSha256": manifest_sha256,
        "seed": manifest["seed"],
        "sessions": sessions,
    }


def session_request(manifest, session):
    """Only this allowlist crosses the agent boundary; gold is never consulted."""
    task = next(task for task in manifest["tasks"] if task["id"] == session["taskId"])
    roles = [
        "commonPrompt",
        "tools",
        "permissions",
        "runtime",
        "dependencies",
        "cache",
        "stopRules",
    ]
    if session["arm"] == "dotrepo-access":
        roles += [
            "accessInstructions",
            "integration",
            "snapshot",
            "responses",
            "policy",
            "consumer",
        ]
    return {
        "version": 1,
        "experimentId": manifest["experimentId"],
        **session,
        "task": {
            key: task[key]
            for key in (
                "id",
                "repository",
                "revision",
                "scope",
                "startingState",
                "request",
                "prompt",
            )
        },
        "model": manifest["model"],
        "environment": manifest["environment"],
        "budgets": manifest["budgets"],
        "cacheState": manifest["cacheState"],
        "workspaceKey": f"{manifest['experimentId']}/{session['sessionId']}",
        "cacheKey": f"{manifest['experimentId']}/{session['sessionId']}",
        "artifacts": {role: manifest["artifacts"][role] for role in roles},
    }


def prepare(manifest_path, out):
    manifest_path, out = Path(manifest_path), Path(out)
    manifest = validate_manifest(manifest_path)
    plan = assignment(manifest, digest(manifest_path.read_bytes()))
    out.mkdir(parents=True, exist_ok=False)
    (out / "assignment.json").write_bytes(encode(plan))
    (out / "requests").mkdir()
    for session in plan["sessions"]:
        request = session_request(manifest, session)
        (out / "requests" / f"{session['sessionId']}.json").write_bytes(encode(request))
    return plan


def verify(manifest_path, assignment_path):
    manifest_path, assignment_path = Path(manifest_path), Path(assignment_path)
    manifest = validate_manifest(manifest_path)
    actual = read_json(assignment_path)
    expected = assignment(manifest, digest(manifest_path.read_bytes()))
    require(actual == expected, "assignment changed or manifest changed after preparation")
    for session in expected["sessions"]:
        path = assignment_path.parent / "requests" / f"{session['sessionId']}.json"
        require(not path.is_symlink(), "symlink session request")
        require(read_json(path) == session_request(manifest, session), "session request changed")
    return manifest, expected


def _mean_known(values):
    return sum(values) / len(values) if all(value is not None for value in values) else None


def _task_summary(tasks, rows):
    return {
        arm: {
            "assignedSessions": 3 * len(tasks),
            "tasks": len(tasks),
            "statusCounts": dict(Counter(r["status"] for r in rows if r["arm"] == arm)),
            **{key: _mean_known([r["arms"][arm][key] for r in tasks]) for key in METRICS},
            "effort": {
                key: _mean_known([r["arms"][arm]["effort"][key] for r in tasks]) for key in EFFORT
            },
            "effortTotals": {
                key: (
                    sum(r["effort"][key] for r in rows if r["arm"] == arm)
                    if all(r["effort"][key] is not None for r in rows if r["arm"] == arm)
                    else None
                )
                for key in EFFORT
            },
        }
        for arm in ARMS
    }


def summarize(manifest_path, assignment_path, observations_path):
    """Post-run scored observations remain assertions, never execution permission."""
    manifest, plan = verify(manifest_path, assignment_path)
    path = Path(observations_path)
    observations = read_json(path)
    require(observations["version"] == 1, "unsupported observation version")
    require(
        observations["assignmentSha256"] == digest(Path(assignment_path).read_bytes()),
        "observations bind a different assignment",
    )
    runs = observations["runs"]
    require(len(runs) == 72, "all 72 assigned sessions must remain in ledger")
    require(len({run["sessionId"] for run in runs}) == 72, "duplicate observed session")
    by_id = {run["sessionId"]: run for run in runs}
    require(set(by_id) == {s["sessionId"] for s in plan["sessions"]}, "unknown assigned session")
    previous_end = timestamp(manifest["frozenAt"])
    used_paths, workspaces = set(), set()
    rows = []
    for session in plan["sessions"]:
        run = by_id[session["sessionId"]]
        request = session_request(manifest, session)
        for key in ("model", "environment", "budgets", "cacheState", "workspaceKey", "cacheKey"):
            require(
                encode(run[key]) == encode(request[key]),
                f"runtime {key} differs from frozen session",
            )
        require(run["workspaceKey"] not in workspaces, "workspace reused")
        workspaces.add(run["workspaceKey"])
        require(
            run["requestSha256"] == digest(encode(request)),
            "runtime request binding mismatch",
        )
        start, end = timestamp(run["startedAt"]), timestamp(run["endedAt"])
        require(previous_end <= start <= end, "runs must follow serialized assignment order")
        previous_end = end
        require(
            run["status"]
            in {
                "completed",
                "noncompletion",
                "budget-exhausted",
                "infrastructure-failure",
                "unresolved",
            },
            "invalid run status",
        )
        for key in ("protocolDeviations", "measurementExclusions"):
            require(
                isinstance(run[key], list)
                and all(isinstance(item, str) and item.strip() for item in run[key]),
                f"{key} must be a list of explanations",
            )
        for control in (
            "freshSession",
            "goldInaccessible",
            "otherSessionsInaccessible",
            "cacheConditionEnforced",
            "armAccessEnforced",
            "budgetsEnforced",
        ):
            require(
                type(run["controls"][control]) is bool, f"missing control observation: {control}"
            )
            require(
                run["controls"][control] or bool(run["protocolDeviations"]),
                "failed control requires a protocol deviation",
            )
        for role in ("trace", "usage", "score"):
            binding = run[role]
            artifact(path.parent.resolve(), binding)
            require(binding["path"] not in used_paths, "observation evidence reused")
            used_paths.add(binding["path"])
        for role in ("trace", "usage"):
            receipt = read_json(safe_path(path.parent.resolve(), run[role]["path"]))
            require(receipt["sessionId"] == session["sessionId"], f"{role} session mismatch")
            require(
                receipt["requestSha256"] == run["requestSha256"], f"{role} request binding mismatch"
            )
            if role == "usage":
                require(
                    set(receipt)
                    == {
                        "sessionId",
                        "requestSha256",
                        "model",
                        "environment",
                        "runtimeSha256",
                        "effort",
                    },
                    "usage receipt must follow the normalized measurement contract",
                )
                for key in ("model", "environment"):
                    require(
                        encode(receipt[key]) == encode(run[key]),
                        f"usage observed {key} differs from run",
                    )
                require(
                    receipt["runtimeSha256"] == manifest["artifacts"]["runtime"]["sha256"],
                    "usage observed runtime differs from freeze",
                )
                require(
                    encode(receipt["effort"]) == encode(run["effort"]),
                    "usage measurements differ from reported effort",
                )
        score = read_json(safe_path(path.parent.resolve(), run["score"]["path"]))
        require(score["sessionId"] == session["sessionId"], "score session mismatch")
        require(score["traceSha256"] == run["trace"]["sha256"], "score binds different trace")
        require(
            score["scorerSha256"] == manifest["artifacts"]["scorer"]["sha256"],
            "scorer version changed",
        )
        task = next(task for task in manifest["tasks"] if task["id"] == session["taskId"])
        require(score["oracleSha256"] == task["oracle"]["sha256"], "task oracle changed")
        require(score["goldSha256"] == task["gold"]["sha256"], "task gold changed")
        require(
            score["errorRubricSha256"] == manifest["artifacts"]["errorRubric"]["sha256"],
            "error rubric changed",
        )
        for metric in METRICS:
            require(type(score[metric]) is bool or score[metric] is None, f"invalid {metric}")
            require(
                score[metric] is not None or run["status"] == "unresolved",
                "unknown scoring needs unresolved status",
            )
        require(
            run["status"] != "completed" or score["correctCompletion"] is True,
            "completed status needs correct oracle completion",
        )
        require(
            run["status"] == "completed" or score["correctCompletion"] is not True,
            "noncompletion cannot have oracle completion",
        )
        if session["arm"] == "source-first":
            require(
                not score["directApplicableInstruction"] and not score["policySelectionError"],
                "source-first cannot receive dotrepo instruction or policy selection",
            )
        require(
            isinstance(score["rationale"], str) and score["rationale"].strip(),
            "scoring needs a rationale",
        )
        effort = run["effort"]
        require(set(effort) == set(EFFORT), "incomplete effort/cost accounting")
        for key, value in effort.items():
            require(
                value is None
                or (type(value) in (int, float) and math.isfinite(value) and value >= 0),
                f"invalid effort {key}",
            )
            if value is None:
                require(bool(run["measurementExclusions"]), "missing measurement needs exclusion")
            elif key not in {
                "elapsedSeconds",
                "providerCostUsd",
                "preparationCostUsd",
                "maintenanceCostUsd",
            }:
                require(type(value) is int, f"count must be integer: {key}")
        require(
            effort["elapsedSeconds"] is not None and effort["toolCalls"] is not None,
            "wall time and tool calls must be observed",
        )
        require(
            abs(effort["elapsedSeconds"] - (end - start).total_seconds()) <= 0.01,
            "elapsed time must include whole session",
        )
        for measured, ceiling in (
            ("elapsedSeconds", "wallTimeSeconds"),
            ("toolCalls", "toolCalls"),
            ("inputTokens", "inputTokens"),
            ("outputTokens", "outputTokens"),
            ("providerCostUsd", "monetaryUsd"),
        ):
            require(
                effort[measured] is None
                or effort[measured] <= manifest["budgets"][ceiling]
                or bool(run["protocolDeviations"]),
                "budget overrun requires a protocol deviation",
            )
        rows.append(
            {
                **session,
                "repository": task["repository"],
                "scope": task["scope"],
                "ecosystem": task["ecosystem"],
                "startingState": task["startingState"],
                "status": run["status"],
                "protocolDeviations": run["protocolDeviations"],
                "measurementExclusions": run["measurementExclusions"],
                **{key: score[key] for key in METRICS},
                "effort": effort,
            }
        )
    task_rows = []
    for task in manifest["tasks"]:
        arm_rows = {}
        for arm in ARMS:
            selected = [r for r in rows if r["taskId"] == task["id"] and r["arm"] == arm]
            arm_rows[arm] = {
                **{key: _mean_known([r[key] for r in selected]) for key in METRICS},
                "effort": {
                    key: _mean_known([r["effort"][key] for r in selected]) for key in EFFORT
                },
            }
        task_rows.append(
            {
                "taskId": task["id"],
                "repository": task["repository"],
                "scope": task["scope"],
                "ecosystem": task["ecosystem"],
                "startingState": task["startingState"],
                "arms": arm_rows,
                "completionDifference": (
                    arm_rows[ARMS[1]]["correctCompletion"] - arm_rows[ARMS[0]]["correctCompletion"]
                    if all(arm_rows[a]["correctCompletion"] is not None for a in ARMS)
                    else None
                ),
            }
        )
    summary = _task_summary(task_rows, rows)
    costs = [row["effort"][key] for row in rows for key in COST_FIELDS]
    known_subtotal = sum(cost for cost in costs if cost is not None)
    missing_costs = sum(cost is None for cost in costs)
    campaign_deviations = observations.get("campaignProtocolDeviations", [])
    require(
        isinstance(campaign_deviations, list)
        and all(isinstance(item, str) and item.strip() for item in campaign_deviations),
        "campaignProtocolDeviations must be a list of explanations",
    )
    over_budget = known_subtotal > manifest["campaignBudgetUsd"]
    require(
        not over_budget or bool(campaign_deviations),
        "campaign budget overrun requires a campaign protocol deviation",
    )
    campaign_budget = {
        "limitUsd": manifest["campaignBudgetUsd"],
        "knownSubtotalUsd": known_subtotal,
        "totalCostUsd": None if missing_costs else known_subtotal,
        "missingMeasurements": missing_costs,
        "status": "exceeded" if over_budget else "unresolved" if missing_costs else "within",
        "protocolDeviations": campaign_deviations,
    }
    breakdowns = {
        key: {
            value: _task_summary(
                [t for t in task_rows if t[key] == value], [r for r in rows if r[key] == value]
            )
            for value in sorted({task[key] for task in task_rows})
        }
        for key in ("repository", "scope", "ecosystem", "startingState")
    }
    return {
        "version": 1,
        "experimentId": manifest["experimentId"],
        "assignedSessions": 72,
        "independentlyVerified": False,
        "externalAdoption": False,
        "limitations": "Supplied scores and controls are assertions bound to retained evidence; "
        "this tool does not witness execution or establish causal population benefit.",
        "summary": summary,
        "campaignBudget": campaign_budget,
        "breakdowns": breakdowns,
        "tasks": task_rows,
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "verify", "summarize"):
        sub = commands.add_parser(name)
        sub.add_argument("--manifest", type=Path, required=True)
        if name != "prepare":
            sub.add_argument("--assignment", type=Path, required=True)
        if name != "verify":
            sub.add_argument("--out", type=Path, required=True)
        if name == "summarize":
            sub.add_argument("--observations", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            plan = prepare(args.manifest, args.out)
            print(
                f"Prepared {len(plan['sessions'])} independent session requests; no runs launched."
            )
        elif args.command == "verify":
            verify(args.manifest, args.assignment)
            print(
                "Frozen artifacts, assignment and session requests match; live controls remain runner obligations."
            )
        else:
            report = summarize(args.manifest, args.assignment, args.observations)
            args.out.mkdir(parents=True, exist_ok=False)
            (args.out / "summary.json").write_bytes(encode(report))
            print("Validated 72 supplied session observations; task-weighted summary written.")
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
