"""Score frozen paired task observations; never execute supplied commands.

Observed logs are supplied by the task runner/participant. This validates their
binding and consistency, not the truth of externally asserted observations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path


ARMS = ("source-first", "lookup-first")
CONTEXT = {
    "command",
    "workingDirectory",
    "scope",
    "component",
    "prerequisites",
    "parameters",
    "environment",
    "sourcePaths",
    "purpose",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def timestamp(value):
    require(isinstance(value, str), "timestamp must be text")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "timestamps need a timezone")
    return parsed


def number(value, label, *, nullable=False, integer=False):
    if value is None and nullable:
        return
    require(
        type(value) in (int, float)
        and math.isfinite(value)
        and value >= 0
        and (not integer or type(value) is int),
        f"invalid {label}",
    )


def instruction(value):
    require(isinstance(value, dict) and set(value) == CONTEXT, "incomplete execution context")
    for key in ("command", "workingDirectory", "scope", "purpose"):
        require(isinstance(value[key], str) and bool(value[key].strip()), f"invalid {key}")
    require(value["scope"] in {"repository", "component"}, "invalid scope")
    require(
        value["component"] is None
        if value["scope"] == "repository"
        else isinstance(value["component"], str) and bool(value["component"].strip()),
        "invalid component",
    )
    for key in ("prerequisites", "sourcePaths"):
        require(
            isinstance(value[key], list) and all(isinstance(x, str) for x in value[key]),
            f"invalid {key}",
        )
    require(bool(value["sourcePaths"]), "instruction needs source paths")
    for key in ("parameters", "environment"):
        require(
            isinstance(value[key], dict)
            and all(isinstance(k, str) and isinstance(v, str) for k, v in value[key].items()),
            f"invalid {key}",
        )


def artifact(root, binding):
    require(isinstance(binding, dict), "missing artifact binding")
    relative = Path(binding["path"])
    path = (root / relative).resolve()
    require(
        not relative.is_absolute() and path.is_relative_to(root.resolve()),
        "artifact escapes observations root",
    )
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == binding["sha256"], "artifact hash mismatch")
    return json.loads(raw)


def score(workload_path, observations_path):
    workload_path, observations_path = Path(workload_path), Path(observations_path)
    raw = workload_path.read_bytes()
    workload = json.loads(raw)
    observations = json.loads(observations_path.read_text())
    digest = hashlib.sha256(raw).hexdigest()
    require(workload["version"] == 1 and observations["version"] == 1, "unsupported version")
    require(observations["workloadSha256"] == digest, "workload changed after freeze")
    frozen = timestamp(workload["frozenAt"])
    require(workload["selectionBeforeCoverageInspection"] is True, "workload selection not frozen")
    require(
        workload["consumerClass"] in {"operator-controlled", "participant-supplied"},
        "invalid consumer class",
    )
    require(workload["cacheState"] in {"cold", "warm", "replay"}, "invalid cache state")
    require(
        len(workload["snapshotId"]) == 64
        and all(c in "0123456789abcdef" for c in workload["snapshotId"]),
        "invalid snapshot identity",
    )
    require(bool(workload["consumerPolicy"]), "missing consumer policy")
    tasks = workload["tasks"]
    require(bool(tasks), "empty workload")
    require(len({task["id"] for task in tasks}) == len(tasks), "duplicate task")
    runs = observations["runs"]
    require(len(runs) == 2 * len(tasks), "missing or extra paired runs")
    rows = []
    previous_end = frozen
    attempt_paths = set()
    for index, task in enumerate(tasks):
        require(
            len(task["revision"]) == 40 and all(c in "0123456789abcdef" for c in task["revision"]),
            "task needs immutable upstream revision",
        )
        require(
            task.get("revisionKind", "git-commit") in {"git-commit", "fixture-content"}
            and (
                task.get("revisionKind") != "fixture-content"
                or workload["consumerClass"] == "operator-controlled"
            ),
            "synthetic revisions cannot identify participant tasks",
        )
        require(
            task["evidence"]
            and all(
                all(item.get(k) for k in ("url", "locator", "checkedAt"))
                for item in task["evidence"]
            ),
            "task lacks source evidence",
        )
        require(
            all(
                item["sourceRevision"] == task["revision"]
                and timestamp(item["checkedAt"]) <= frozen
                for item in task["evidence"]
            ),
            "source evidence does not bind frozen revision/check time",
        )
        gold = task["acceptableInstructions"]
        for plan in gold:
            instruction(plan)
        order = ARMS if index % 2 == 0 else tuple(reversed(ARMS))
        for arm, run in zip(order, runs[2 * index : 2 * index + 2], strict=True):
            require(
                run["taskId"] == task["id"] and run["arm"] == arm, "paired order must alternate"
            )
            require(
                run["revision"] == task["revision"]
                and run["environmentId"] == task["environmentId"],
                "paired revision/environment mismatch",
            )
            require(run["cacheState"] == workload["cacheState"], "paired cache mismatch")
            start, end = timestamp(run["startedAt"]), timestamp(run["endedAt"])
            require(frozen <= start <= end, "run predates freeze or has reversed timestamps")
            require(start >= previous_end, "paired run timestamps do not follow declared order")
            previous_end = end
            number(run["elapsedMs"], "elapsedMs")
            wall_ms = (end - start).total_seconds() * 1000
            require(
                abs(wall_ms - run["elapsedMs"]) <= max(5, wall_ms * 0.01),
                "elapsed time excludes work or disagrees with run interval",
            )
            for key in ("httpRequests", "decodedBytes", "cacheHits"):
                number(run["transport"][key], key, integer=True)
            for key in ("inputTokens", "outputTokens", "cost"):
                number(run["modelUsage"][key], key, nullable=True, integer=key != "cost")
            number(run["allocatedMaintenanceCost"], "maintenance cost", nullable=True)
            lookup = run["lookup"]
            if arm == "source-first":
                require(lookup is None, "source-first includes lookup")
            else:
                require(
                    lookup["snapshotId"] == workload["snapshotId"]
                    and lookup["policy"] == workload["consumerPolicy"],
                    "lookup version mismatch",
                )
                require(
                    type(lookup["accepted"]) is bool and type(lookup["valuePresent"]) is bool,
                    "invalid policy observation",
                )
                require(not lookup["accepted"] or lookup["valuePresent"], "accepted absent value")
                if lookup["accepted"]:
                    instruction(lookup["instruction"])
                else:
                    require(
                        lookup["instruction"] is None and bool(lookup["fallbackReasons"]),
                        "rejection needs fallback reasons",
                    )
            attempts = run["attempts"]
            require(bool(attempts), "run needs an observed task attempt, including abstention")
            if lookup and lookup["accepted"]:
                require(
                    attempts[0]["origin"] == "profile"
                    and attempts[0]["instruction"] == lookup["instruction"],
                    "accepted profile was not attempted",
                )
            accepted_wrong = int(
                bool(lookup and lookup["accepted"] and lookup["instruction"] not in gold)
            )
            failed = 0
            completed = False
            for attempt in attempts:
                plan = attempt["instruction"]
                if plan is not None:
                    instruction(plan)
                origin = attempt["origin"]
                require(origin in {"source", "profile", "fallback"}, "invalid attempt origin")
                require(
                    (arm != "source-first" or origin == "source")
                    and (arm != "lookup-first" or origin != "source"),
                    "invalid arm origin",
                )
                require(
                    origin != "profile" or (lookup["accepted"] and plan == lookup["instruction"]),
                    "rejected or replaced profile was executed",
                )
                log = artifact(observations_path.parent, attempt["log"])
                log_path = (observations_path.parent / attempt["log"]["path"]).resolve()
                require(log_path not in attempt_paths, "execution artifact reused across attempts")
                attempt_paths.add(log_path)
                for key in ("instruction", "exitCode", "oraclePassed", "taskId"):
                    expected = task["id"] if key == "taskId" else attempt[key]
                    require(log[key] == expected, "execution log does not match observation")
                require(type(attempt["oraclePassed"]) is bool, "completion oracle must be observed")
                require(
                    (plan is None and attempt["exitCode"] is None)
                    or (plan is not None and type(attempt["exitCode"]) is int),
                    "missing exit status",
                )
                semantic = plan in gold if plan is not None else not gold
                completed = (
                    semantic
                    and attempt["oraclePassed"]
                    and (plan is None or attempt["exitCode"] == 0)
                )
                failed += not completed
            rows.append(
                {
                    "taskId": task["id"],
                    "taskClass": task["taskClass"],
                    "arm": arm,
                    "completedTask": completed,
                    "failedAttempts": failed,
                    "acceptedWrongAnswer": accepted_wrong,
                    "policyAccepted": lookup["accepted"] if lookup else None,
                    "valuePresent": lookup["valuePresent"] if lookup else None,
                    "fallbackAttempts": sum(a["origin"] == "fallback" for a in attempts),
                    "correctFallback": bool(lookup and not lookup["accepted"] and completed),
                    "elapsedMs": run["elapsedMs"],
                    "transport": run["transport"],
                    "modelUsage": run["modelUsage"],
                    "allocatedMaintenanceCost": run["allocatedMaintenanceCost"],
                }
            )
    return {
        "version": 1,
        "workloadSha256": digest,
        "consumerClass": workload["consumerClass"],
        "snapshotId": workload["snapshotId"],
        "consumerPolicy": workload["consumerPolicy"],
        "cacheState": workload["cacheState"],
        "externalAdoption": False,
        "independentlyVerifiedObservations": None,
        "observationLimit": "Hashes bind supplied logs; this scorer does not independently witness external execution.",
        "rows": rows,
        "summary": {arm: summarize([r for r in rows if r["arm"] == arm]) for arm in ARMS},
    }


def total_known(values):
    return sum(values) if all(value is not None for value in values) else None


def summarize(rows):
    return {
        "attemptedTasks": len(rows),
        **{
            key: sum(row[key] for row in rows)
            for key in (
                "completedTask",
                "failedAttempts",
                "acceptedWrongAnswer",
                "fallbackAttempts",
                "correctFallback",
            )
        },
        "policyAcceptedTasks": sum(row["policyAccepted"] is True for row in rows),
        "elapsedMs": sum(row["elapsedMs"] for row in rows),
        "transport": {
            key: sum(row["transport"][key] for row in rows)
            for key in ("httpRequests", "decodedBytes", "cacheHits")
        },
        "modelUsage": {
            key: total_known([row["modelUsage"][key] for row in rows])
            for key in ("inputTokens", "outputTokens", "cost")
        },
        "allocatedMaintenanceCost": total_known([row["allocatedMaintenanceCost"] for row in rows]),
    }


def markdown(report):
    lines = [
        "# Paired task observations",
        "",
        f"Consumer class: {report['consumerClass']}.",
        "",
        report["observationLimit"],
        "No external adoption or net cost benefit is inferred.",
        "",
        "| Metric | Source first | Lookup first |",
        "| --- | ---: | ---: |",
    ]
    for key in (
        "attemptedTasks",
        "completedTask",
        "failedAttempts",
        "acceptedWrongAnswer",
        "policyAcceptedTasks",
        "fallbackAttempts",
        "correctFallback",
        "elapsedMs",
    ):
        values = [report["summary"][arm][key] for arm in ARMS]
        lines.append(f"| {key} | {values[0]} | {values[1]} |")
    lines += [
        "",
        "Unknown model usage/cost or maintenance allocations remain null in results.json.",
        "Replay elapsed time is not live latency. See per-task rows and bound execution logs.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = score(args.workload, args.observations)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.out / "report.md").write_text(markdown(report))


if __name__ == "__main__":
    main()
