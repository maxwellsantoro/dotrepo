#!/usr/bin/env -S uv run python
"""Measure populated fields and fallback-free tasks using the actual consumer policy.

This is policy coverage at a stated time, not factual accuracy or task completion.
Only primary profiles are counted; snapshot copies and command candidates are not.
"""

import argparse
from collections import Counter
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sys

CLIENT = Path(__file__).resolve().parents[1] / "examples/external-consumer/lookup_before_scrape.py"
SPEC = importlib.util.spec_from_file_location("policy_coverage_consumer", CLIENT)
consumer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = consumer
SPEC.loader.exec_module(consumer)

TASKS = {
    "description": ["repo.description"],
    "documentation": ["docs.root"],
    "build": ["repo.build"],
    "test": ["repo.test"],
    "build-and-test": ["repo.build", "repo.test"],
}


def measure(public_root: Path, evaluated_at: str | None = None) -> dict:
    meta = json.loads((public_root / "v0/meta.json").read_text())
    evaluated_at = evaluated_at or meta["generatedAt"]
    now = datetime.fromisoformat(evaluated_at.replace("Z", "+00:00"))
    if now.tzinfo is None:
        raise ValueError("evaluation time must include a timezone")
    rows = []
    counts = {task: Counter() for task in TASKS}
    reasons = {task: Counter() for task in TASKS}
    repos = public_root / "v0/repos"
    for path in sorted(repos.glob("*/*/*/profile.json")):
        identity = path.parent.relative_to(repos).as_posix()
        result = consumer.interpret_http_response(
            identity=identity, status_code=200, body=path.read_bytes()
        )
        decisions = {}
        for task, required in TASKS.items():
            # Preserve a raw presence count separately from type/evidence validation.
            present = all(
                consumer._nonempty(consumer.profile_field(result.profile or {}, field))
                for field in required
            )
            consumer.evaluate_for_task(result, required_fields=required, now=now)
            counts[task]["present"] += int(present)
            counts[task]["acceptable"] += int(result.usable)
            reasons[task].update(set(result.fallback_reasons))
            decisions[task] = {
                "present": present,
                "acceptable": result.usable,
                "fallbackReasons": list(result.fallback_reasons),
            }
        rows.append({"identity": identity, "tasks": decisions})
    total = len(rows)
    tasks = {}
    for task, required in TASKS.items():
        tasks[task] = {
            "requiredFields": required,
            "profileCount": total,
            "presentCount": counts[task]["present"],
            "acceptableCount": counts[task]["acceptable"],
            "presenceRate": counts[task]["present"] / total if total else 0,
            "acceptableRate": counts[task]["acceptable"] / total if total else 0,
            "fallbackReasonCounts": dict(sorted(reasons[task].items())),
            "independentlyCorrectCount": None,
            "completedTaskCount": None,
        }
    return {
        "schema": "dotrepo-policy-coverage/v1",
        "commandPolicy": consumer.COMMAND_POLICY,
        "evaluatedAt": evaluated_at,
        "snapshotDigest": meta["snapshotDigest"],
        "profileCount": total,
        "commandSlots": {
            "total": total * 2,
            "present": sum(counts[t]["present"] for t in ("build", "test")),
            "acceptable": sum(counts[t]["acceptable"] for t in ("build", "test")),
        },
        "tasks": tasks,
        "profiles": rows,
        "limitations": (
            "Presence, policy acceptance, independent correctness, and task completion are separate. "
            "Correctness and completion are unmeasured here (null, not zero). "
            "Commands require explicit high-confidence extracted assessments with a source and "
            "matching check time. Other tasks use the reference client's required-field policy. "
            "No command is executed. No maintainer-authority exemption is implemented."
        ),
    }


def markdown(report: dict) -> str:
    lines = [
        "# Consumer policy coverage",
        "",
        f"Evaluated at {report['evaluatedAt']} against {report['profileCount']} primary profiles.",
        f"Command policy: `{report['commandPolicy']}`.",
        "",
        "| Task | Values present | Policy acceptable | Independently correct | Task completed |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for task, values in report["tasks"].items():
        lines.append(
            f"| {task} | {values['presentCount']} ({values['presenceRate']:.1%}) "
            f"| {values['acceptableCount']} ({values['acceptableRate']:.1%}) "
            "| Not measured | Not measured |"
        )
    lines += ["", report["limitations"], ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument(
        "--evaluated-at", help="Defaults to the export timestamp for reproducibility"
    )
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path)
    args = parser.parse_args()
    report = measure(args.public_root, args.evaluated_at)
    for path, content in [
        (args.output_json, json.dumps(report, indent=2) + "\n"),
        (args.output_md, markdown(report)),
    ]:
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    print(markdown(report))
    return int(report["profileCount"] == 0)


if __name__ == "__main__":
    raise SystemExit(main())
