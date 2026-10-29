"""Evaluate frozen E1 slices without changing source gold or executing upstream code.

freeze --slices python typescript go preregisters source/materialization/selection/
scoring bindings before any imports. run verifies them, copies only retained source
bytes into fresh temporary roots, imports overlays, exports actual public profiles,
and calls the contextual consumer using task scope/component without gold answers.
Gold is joined after all selections. Earlier Rust results are hash-bound and reused
unchanged in the combined report. New runs require new output directories.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
COHORT_SHA256 = "8d44598ba00725fac046ca8da50fdbc1252d2440eb6ec04d690a1129cecb0c63"
SLICES = ("python", "typescript", "go")
FREEZE = HERE / "execution-freeze.json"
SPEC = importlib.util.spec_from_file_location(
    "immutable_rust_evaluator", PACKET / "evaluation-rust/evaluate.py"
)
rust = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rust)
METHOD = {
    **rust.METHOD,
    "unresolvedGold": "unresolved-gold; retained in full task denominator and separate unresolved count, never scored as correct abstention or error.",
    "scopeAggregation": "Report all assigned remaining tasks by slice/scope and combine with the immutable six-task Rust report. Full observation coverage does not imply full source-gold resolution or a passed qualification gate.",
    "originalRustResults": "Reuse immutable Rust consumer observations and dispositions; do not rerun or rewrite its packet.",
    "importFailure": "Retain failed import/export receipts and absent profiles. Missing selection against supported source gold remains a supported miss, with infrastructure failure separately visible.",
}


def integrity():
    cohort_path = PACKET / "cohort-manifest.json"
    rust.require(rust.sha(cohort_path) == COHORT_SHA256, "cohort manifest changed")
    cohort = rust.read(cohort_path)
    rust.require(
        cohort["taskCount"] == 24 and cohort["repositoryCount"] == 12, "cohort counts changed"
    )
    artifact_count, selection_count = 0, 0
    for binding in cohort["sliceFreezes"]:
        path = PACKET / binding["path"]
        rust.require(rust.sha(path) == binding["sha256"], "slice freeze changed")
        frozen = rust.read(path)
        for base, items in ((ROOT, frozen["selectionInputs"]), (PACKET, frozen["artifacts"])):
            for item in items:
                path = base / item["path"]
                rust.require(
                    not path.is_symlink() and rust.sha(path) == item["sha256"],
                    f"source binding changed: {item['path']}",
                )
        artifact_count += len(frozen["artifacts"])
        selection_count += len(frozen["selectionInputs"])
    rust.require(
        artifact_count == 219 and selection_count == 20, "source binding inventory changed"
    )
    old_freeze = rust.read(PACKET / "evaluation-rust/execution-freeze.json")
    rust.require(
        rust.sha(PACKET / "evaluation-rust/evaluate.py") == old_freeze["evaluatorAndScorerSha256"],
        "immutable Rust helper/scorer changed",
    )
    inventory = rust.read(PACKET / "evaluation-rust/run-001/artifact-hashes.json")
    for name, digest in inventory.items():
        rust.require(
            rust.sha(PACKET / "evaluation-rust/run-001" / name) == digest,
            "immutable Rust result changed",
        )
    return cohort, old_freeze


def controls():
    rust.require(
        rust.score_task({"goldState": "supported"}, {"consumerSelection": {"instruction": None}})
        == "supported-miss",
        "supported-miss control failed",
    )
    rust.require(
        rust.score_task(
            {"goldState": "required-abstention"}, {"consumerSelection": {"instruction": None}}
        )
        == "correct-abstention",
        "abstention control failed",
    )
    rust.require(
        rust.score_task({"goldState": "unresolved"}, {"consumerSelection": {"instruction": None}})
        == "unresolved-gold",
        "unresolved control failed",
    )
    rust.require(
        not rust.recovered({"test": "fixture scalar"})[0]["structurallyComplete"],
        "incomplete-context control failed",
    )
    return {
        "syntheticControlsOnly": True,
        "passed": 4,
        "supportedMissingSelection": "supported-miss",
        "requiredAbstentionMissingSelection": "correct-abstention",
        "unresolvedGold": "unresolved-gold",
        "scalarWithoutContextComplete": False,
        "upstreamCodeExecuted": False,
    }


def freeze(slices):
    rust.require(
        slices and len(set(slices)) == len(slices) and set(slices) <= set(SLICES), "invalid slices"
    )
    _, old = integrity()
    inputs = rust.executable_inputs()
    rust.require(
        len(inputs) == 503 and inputs == old["sourceHashes"],
        "evaluated source differs from Rust packet",
    )
    rust.require(rust.sha(rust.CLI) == old["cliSha256"], "CLI differs from Rust packet")
    control_result = controls()
    rust.write(HERE / "scorer-controls.json", control_result)
    rust.write(
        FREEZE,
        {
            "schema": "dotrepo-e1-remaining-execution-freeze/v1",
            "frozenAt": rust.now(),
            "evaluatedCommit": rust.COMMIT,
            "cohortManifestSha256": COHORT_SHA256,
            "evaluatedSlices": slices,
            "sourceHashes": inputs,
            "cliSha256": rust.sha(rust.CLI),
            "evaluatorSha256": rust.sha(Path(__file__)),
            "scorerAndHelperSha256": rust.sha(PACKET / "evaluation-rust/evaluate.py"),
            "scorerControlsSha256": rust.sha(HERE / "scorer-controls.json"),
            "rustExecutionFreezeSha256": rust.sha(PACKET / "evaluation-rust/execution-freeze.json"),
            "rustResultSha256": rust.sha(PACKET / "evaluation-rust/run-001/results.json"),
            "scoringMethod": METHOD,
            "runtime": old["runtime"],
            "binaryRevisionAttestation": old["binaryRevisionAttestation"],
            "goldIsolation": "The source-gold curator receives no extraction outputs; all source gold remains immutable.",
        },
    )


def verify():
    _, old = integrity()
    frozen = rust.read(FREEZE)
    rust.require(
        frozen["sourceHashes"] == old["sourceHashes"] == rust.executable_inputs(),
        "evaluated source changed",
    )
    rust.require(frozen["cliSha256"] == old["cliSha256"] == rust.sha(rust.CLI), "CLI changed")
    rust.require(frozen["evaluatorSha256"] == rust.sha(Path(__file__)), "evaluator changed")
    rust.require(
        frozen["scorerAndHelperSha256"] == rust.sha(PACKET / "evaluation-rust/evaluate.py"),
        "scorer changed",
    )
    rust.require(
        frozen["scorerControlsSha256"] == rust.sha(HERE / "scorer-controls.json"),
        "controls changed",
    )
    rust.require(
        frozen["rustExecutionFreezeSha256"]
        == rust.sha(PACKET / "evaluation-rust/execution-freeze.json"),
        "Rust execution freeze changed",
    )
    rust.require(
        frozen["rustResultSha256"] == rust.sha(PACKET / "evaluation-rust/run-001/results.json"),
        "Rust results changed",
    )
    rust.require(frozen["scoringMethod"] == METHOD, "scoring method changed")
    rust.require(frozen["runtime"]["python"] == sys.version, "runtime changed")
    return frozen


def summarize(rows):
    return {
        "evaluatedTasks": len(rows),
        "repositoryCount": len({r["repository"] for r in rows}),
        "summary": dict(Counter(row["applicabilityDisposition"] for row in rows)),
        "acceptedInstructions": sum(
            r["consumerSelection"]["instruction"] is not None for r in rows
        ),
        "byScope": {
            scope: dict(Counter(r["applicabilityDisposition"] for r in rows if r["scope"] == scope))
            for scope in ("repository", "component")
        },
    }


def run_slice(slice_name, frozen, output):
    cohort = rust.read(PACKET / "cohort-manifest.json")
    ecosystem = "javascript-typescript" if slice_name == "typescript" else slice_name
    roster = [
        {
            key: task[key]
            for key in ("id", "repository", "revision", "ecosystem", "scope", "component")
        }
        for task in cohort["tasks"]
        if task["ecosystem"] == ecosystem
    ]
    rust.require(len(roster) == 6, "slice task count differs")
    # Consumer selection gets only frozen request identity/scope, not alternatives.
    from bench.own_projects import select_profile_instruction
    from bench.arms.lookup_first import consumer

    rust.require(consumer.INSTRUCTION_POLICY == METHOD["consumerPolicy"], "consumer policy changed")
    observations, imported, materialization = [], {}, {}
    slice_freeze = rust.read(PACKET / f"freeze-{slice_name}.json")
    with tempfile.TemporaryDirectory(prefix=f"dotrepo-e1-{slice_name}-") as directory:
        temporary, index = Path(directory), Path(directory) / "index"
        for identity in dict.fromkeys(task["repository"] for task in roster):
            verify()
            prefix = f"{slice_name}/sources/{identity}/"
            source_root, root = (
                PACKET / slice_name / "sources" / identity,
                temporary / "sources" / identity,
            )
            files, size = [], 0
            for item in slice_freeze["artifacts"]:
                if not item["path"].startswith(prefix):
                    continue
                path = PACKET / item["path"]
                relative = path.relative_to(source_root)
                rust.require(
                    not path.is_symlink() and path.stat().st_size <= rust.SOURCE_LIMIT,
                    "unsafe source",
                )
                size += path.stat().st_size
                rust.require(size <= rust.TOTAL_LIMIT, "materialization budget exceeded")
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
                rust.require(rust.sha(target) == item["sha256"], "source copy changed")
                files.append({"path": str(relative), "sha256": item["sha256"]})
            rust.require(files, "empty materialized source")
            materialization[identity] = files
            log = output / "imports" / identity
            receipt = rust.command(
                [
                    str(rust.CLI),
                    "--root",
                    str(root),
                    "import",
                    "--mode",
                    "overlay",
                    "--source",
                    f"https://{identity}",
                ],
                ROOT,
                log,
                60,
            )
            record = root / "record.toml"
            imported[identity] = {"exitCode": receipt["exitCode"], "recovered": []}
            if receipt["exitCode"] == 0 and record.is_file():
                manifest = tomllib.loads(record.read_text())
                imported[identity]["recovered"] = rust.recovered(manifest["repo"])
                for name in ("record.toml", "evidence.md"):
                    path = root / name
                    if path.is_file():
                        shutil.copyfile(path, log / name)
                        destination = index / "repos" / identity / name
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(path, destination)
            for item in files:
                rust.require(
                    rust.sha(root / item["path"]) == item["sha256"], "import mutated source"
                )
        verify()
        stamp = datetime.fromisoformat(frozen["frozenAt"])
        export = rust.command(
            [
                str(rust.CLI),
                "public",
                "export",
                "--index-root",
                str(index),
                "--out-dir",
                str(output / "public"),
                "--generated-at",
                stamp.isoformat(),
                "--stale-after",
                (stamp + timedelta(days=1)).isoformat(),
            ],
            ROOT,
            output / "export",
            120,
        )
        for task in roster:
            identity = task["repository"]
            profile = output / "public/v0/repos" / identity / "profile.json"
            request = {"scope": task["scope"]}
            if task["component"] is not None:
                request["component"] = task["component"]
            selected = select_profile_instruction(
                identity,
                200 if profile.is_file() else 404,
                profile.read_bytes() if profile.is_file() else b"",
                "test",
                request=request,
            )
            observations.append(
                {
                    **task,
                    "request": request,
                    "consumerSelection": selected,
                    "recoveredInstructions": imported[identity]["recovered"],
                    "profileSha256": rust.sha(profile) if profile.is_file() else None,
                    "profilePath": str(profile.relative_to(output)) if profile.is_file() else None,
                    "importExitCode": imported[identity]["exitCode"],
                    "exportExitCode": export["exitCode"],
                }
            )
    # All six independent consumer decisions are retained before the gold join.
    rust.write(output / "consumer-observations.json", observations)
    gold = {task["id"]: task for task in rust.read(PACKET / slice_name / "gold.json")["tasks"]}
    for observation in observations:
        task = gold[observation["id"]]
        observation["goldState"] = task["goldState"]
        observation["applicabilityDisposition"] = rust.score_task(task, observation)
    report = {
        "schema": "dotrepo-e1-slice-evaluation/v1",
        "slice": slice_name,
        "finishedAt": rust.now(),
        "executionFreezeSha256": rust.sha(FREEZE),
        "scoringMethod": METHOD,
        "rows": observations,
        **summarize(observations),
        "plannedTasks": 24,
        "fullQualificationPassed": False,
        "upstreamCommandsExecuted": False,
        "modelCalls": 0,
        "consumerBenefitMeasured": False,
    }
    rust.write(output / "results.json", report)
    rust.write(output / "materialization.json", materialization)
    rust.write(
        output / "artifact-hashes.json",
        {str(p.relative_to(output)): rust.sha(p) for p in sorted(output.rglob("*")) if p.is_file()},
    )
    return observations


def run(output):
    frozen = verify()
    rust.require(not output.exists(), "choose a new run directory; retained results are immutable")
    output.mkdir(parents=True)
    rust.write(
        output / "run-start.json",
        {"startedAt": rust.now(), "executionFreezeSha256": rust.sha(FREEZE)},
    )
    sys.path.insert(0, str(ROOT / "benchmarks/head-to-head"))
    rows = []
    for slice_name in frozen["evaluatedSlices"]:
        rows.extend(run_slice(slice_name, frozen, output / slice_name))
    rust.write(
        output / "remaining-results.json",
        {"rows": rows, **summarize(rows), "plannedTasks": 24, "fullQualificationPassed": False},
    )
    original = rust.read(PACKET / "evaluation-rust/run-001/results.json")
    combined = original["rows"] + rows
    combined_report = {
        "schema": "dotrepo-e1-cohort-evaluation/v1",
        "finishedAt": rust.now(),
        "rows": combined,
        **summarize(combined),
        "plannedTasks": 24,
        "fullQualificationPassed": False,
        "cohortObservationComplete": len(combined) == 24,
        "sourceGoldUnresolved": sum(r["goldState"] == "unresolved" for r in combined),
        "upstreamCommandsExecuted": False,
        "modelCalls": 0,
        "consumerBenefitMeasured": False,
        "byEcosystem": {
            ecosystem: summarize([r for r in combined if r.get("ecosystem", "rust") == ecosystem])
            for ecosystem in ("rust", "python", "javascript-typescript", "go")
        },
        "originalRustResultSha256": frozen["rustResultSha256"],
        "executionFreezeSha256": rust.sha(FREEZE),
        "scoringMethod": METHOD,
    }
    rust.write(output / "combined-results.json", combined_report)
    verify()
    rust.write(
        output / "artifact-hashes.json",
        {str(p.relative_to(output)): rust.sha(p) for p in sorted(output.rglob("*")) if p.is_file()},
    )
    print(
        json.dumps(
            {
                key: combined_report[key]
                for key in (
                    "evaluatedTasks",
                    "plannedTasks",
                    "summary",
                    "byScope",
                    "sourceGoldUnresolved",
                )
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "verify", "run"))
    parser.add_argument("--slices", nargs="+", choices=SLICES, default=list(SLICES))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.action == "freeze":
        freeze(args.slices)
    elif args.action == "verify":
        verify()
    else:
        rust.require(args.out is not None, "run requires --out")
        run(args.out.resolve())


if __name__ == "__main__":
    main()
