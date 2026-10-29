"""Frozen source-only Rust E1 slice evaluation. Run with uv run python.

freeze writes the prospective execution/scoring contract before any import.
run verifies every binding, imports only retained bounded source bytes, exports
actual public profiles and calls the reference contextual consumer without gold.
Only then does it join consumer observations with frozen source gold.
No upstream command, setup script, network call or model call is executed.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
COMMIT = "f79d05a27b31f281ab04a23cd269e927a25833e4"
SOURCE_FREEZE_SHA256 = "de16bbd397558679033140543e24cf7ad45d0804552b2a0c2efe5356dd182205"
CLI = ROOT / "target/debug/dotrepo"
FREEZE = HERE / "execution-freeze.json"
SOURCE_LIMIT = 2 * 1024 * 1024
TOTAL_LIMIT = 10 * 1024 * 1024

METHOD = {
    "selection": "Reference own_projects.select_profile_instruction called with identity, actual exported profile bytes, test purpose and task scope/component only; no gold command/prerequisite filtering or repairs.",
    "candidateRecovery": "Retain raw repo.test, test_context and every test_candidates item. A structurally complete candidate has matching context.command, directory, scope, explicit prerequisite list, source and component iff component scope; this does not establish applicability or consumer acceptance.",
    "supportedMissingSelection": "supported-miss regardless of missing record assessment or upstream fallback availability; source gold establishes an instruction exists.",
    "requiredAbstentionMissingSelection": "correct-abstention against frozen source-gold; no fallback execution is observed.",
    "unresolvedGold": "unresolved-gold; excluded from correctness numerator, retained in six-task denominator and separate unresolved count.",
    "acceptedTuple": "Compare command, working_directory, scope, component and prerequisite list with each frozen alternative after selection. Exact tuple match supports applicable acceptance. Otherwise retain accepted-unresolved-requires-source-adjudication; unlisted or paraphrased alternatives are not automatically wrong.",
    "scopeAggregation": "Report all six tasks and repository/component breakdown; the other eighteen planned qualification tasks are not evaluated here.",
    "consumerPolicy": "value-bound-contextual-instruction-v1",
    "sourceMaterialization": "Only frozen sources/ files are copied, byte-identically, to new temporary repository roots. This is not a full checkout and absence of unretained files limits extraction completeness.",
    "executionBoundary": "Only our Git inspection, import and public export binaries run. No upstream command, bootstrap, build, test, network request, model call, execution-success or consumer-benefit observation.",
    "limits": {
        "perSourceBytes": SOURCE_LIMIT,
        "totalSourceBytes": TOTAL_LIMIT,
        "importTimeoutSeconds": 60,
        "exportTimeoutSeconds": 120,
    },
    "timestampLimit": "CLI import uses its actual timestamp; a replay may have different record timestamps. Export timestamps are fixed to this execution freeze.",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def read(path):
    return json.loads(path.read_bytes())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def source_integrity():
    path = PACKET / "freeze-rust.json"
    require(sha(path) == SOURCE_FREEZE_SHA256, "source-gold freeze changed")
    frozen = read(path)
    require(
        len(frozen["artifacts"]) == 50 and len(frozen["selectionInputs"]) == 5,
        "unexpected source-gold freeze inventory",
    )
    for base, items in ((ROOT, frozen["selectionInputs"]), (PACKET, frozen["artifacts"])):
        for item in items:
            path = base / item["path"]
            require(
                not path.is_symlink() and sha(path) == item["sha256"],
                f"source-gold binding changed: {item['path']}",
            )
    return frozen


def executable_inputs():
    require(git("rev-parse", "HEAD") == COMMIT, "evaluated revision changed")
    paths = git(
        "ls-files",
        "crates",
        "Cargo.toml",
        "Cargo.lock",
        "uv.lock",
        "pyproject.toml",
        "benchmarks/head-to-head/bench",
        "examples/external-consumer/lookup_before_scrape.py",
    ).splitlines()
    # Tracked source must match the named revision, not a later working-tree patch.
    require(not git("diff", COMMIT, "--", *paths), "evaluated source differs from commit")
    return {path: sha(ROOT / path) for path in paths}


def freeze():
    source_integrity()
    inputs = executable_inputs()
    require(CLI.is_file(), "prebuilt CLI is missing")
    # No command-producing import/export has run when this file is created.
    write(
        FREEZE,
        {
            "schema": "dotrepo-e1-rust-execution-freeze/v1",
            "frozenAt": now(),
            "evaluatedCommit": COMMIT,
            "sourceFreezeSha256": SOURCE_FREEZE_SHA256,
            "sourceHashes": inputs,
            "cliPath": str(CLI.relative_to(ROOT)),
            "cliSha256": sha(CLI),
            "evaluatorAndScorerSha256": sha(Path(__file__)),
            "scoringMethod": METHOD,
            "runtime": {
                "python": sys.version,
                "executable": sys.executable,
                "platform": platform.platform(),
            },
            "binaryRevisionAttestation": "Coordinator reports target/debug/dotrepo built from the evaluated core; this packet binds its bytes, not a reproducible-build proof.",
            "goldIsolation": "Source-gold curator is not the extraction operator and receives no extraction outputs.",
        },
    )


def verify():
    frozen = read(FREEZE)
    source_integrity()
    require(frozen["sourceHashes"] == executable_inputs(), "execution source binding changed")
    require(frozen["cliSha256"] == sha(CLI), "CLI binary changed")
    require(frozen["evaluatorAndScorerSha256"] == sha(Path(__file__)), "evaluator changed")
    require(frozen["scoringMethod"] == METHOD, "scoring method changed")
    require(frozen["runtime"]["python"] == sys.version, "Python runtime changed")
    return frozen


def command(args, cwd, output, timeout):
    start = now()
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, timeout=timeout, check=False)
        stdout, stderr, code, error = result.stdout, result.stderr, result.returncode, None
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, code, error = exc.stdout or b"", exc.stderr or b"", None, "timeout"
    output.mkdir(parents=True, exist_ok=False)
    (output / "stdout.txt").write_bytes(stdout)
    (output / "stderr.txt").write_bytes(stderr)
    receipt = {
        "argv": [str(x) for x in args],
        "cwd": str(cwd),
        "startedAt": start,
        "endedAt": now(),
        "exitCode": code,
        "error": error,
        "stdoutSha256": sha(output / "stdout.txt"),
        "stderrSha256": sha(output / "stderr.txt"),
    }
    write(output / "receipt.json", receipt)
    return receipt


def recovered(repo):
    result = []
    if repo.get("test"):
        result.append(
            {"origin": "scalar", "command": repo["test"], "context": repo.get("test_context")}
        )
    result += [{"origin": "candidate", **item} for item in repo.get("test_candidates", [])]
    for item in result:
        context = item.get("context")
        item["structurallyComplete"] = bool(
            isinstance(context, dict)
            and context.get("command") == item["command"]
            and context.get("working_directory")
            and context.get("source")
            and isinstance(context.get("prerequisites"), list)
            and context.get("scope") in {"repository", "component"}
            and (context.get("scope") != "component" or context.get("component"))
        )
    return result


def score_task(task, observation):
    instruction = observation["consumerSelection"]["instruction"]
    state = task["goldState"]
    if state == "unresolved":
        return "unresolved-gold"
    if instruction is None:
        return "supported-miss" if state == "supported" else "correct-abstention"
    if state == "required-abstention":
        return "accepted-unresolved-requires-source-adjudication"
    for alternative in task["alternatives"]:
        same = all(
            instruction[k] == alternative[g]
            for k, g in (
                ("command", "command"),
                ("workingDirectory", "working_directory"),
                ("scope", "scope"),
                ("prerequisites", "prerequisites"),
            )
        )
        if same and instruction.get("component") == alternative.get("component"):
            return "applicable-accepted"
    return "accepted-unresolved-requires-source-adjudication"


def run(output):
    frozen = verify()
    require(not output.exists(), "choose a new run directory; retained results cannot be rewritten")
    output.mkdir(parents=True)
    write(output / "run-start.json", {"startedAt": now(), "executionFreezeSha256": sha(FREEZE)})
    # Restrict the consumer's initial task data to declared request identity and scope.
    roster = [
        {key: task[key] for key in ("id", "repository", "revision", "scope", "component")}
        for task in read(PACKET / "gold-rust.json")["tasks"]
    ]
    sys.path.insert(0, str(ROOT / "benchmarks/head-to-head"))
    from bench.own_projects import select_profile_instruction
    from bench.arms.lookup_first import consumer

    require(consumer.INSTRUCTION_POLICY == METHOD["consumerPolicy"], "consumer policy changed")
    imported, observations = {}, []
    with tempfile.TemporaryDirectory(prefix="dotrepo-e1-rust-") as directory:
        temporary = Path(directory)
        index = temporary / "index"
        for identity in dict.fromkeys(task["repository"] for task in roster):
            verify()
            source = PACKET / "sources" / identity
            root = temporary / "sources" / identity
            size = 0
            files = []
            frozen_source_paths = [
                PACKET / item["path"]
                for item in read(PACKET / "freeze-rust.json")["artifacts"]
                if item["path"].startswith(f"sources/{identity}/")
            ]
            for path in sorted(frozen_source_paths):
                if path.is_file():
                    relative = path.relative_to(source)
                    require(
                        not path.is_symlink() and path.stat().st_size <= SOURCE_LIMIT,
                        "unsafe source",
                    )
                    size += path.stat().st_size
                    require(size <= TOTAL_LIMIT, "source materialization budget exceeded")
                    target = root / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, target)
                    files.append({"path": str(relative), "sha256": sha(target)})
            log = output / "imports" / identity
            receipt = command(
                [
                    str(CLI),
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
            imported[identity] = {
                "receipt": receipt,
                "materializedFiles": files,
                "record": None,
                "recovered": [],
            }
            if receipt["exitCode"] == 0 and record.is_file():
                imported[identity]["record"] = tomllib.loads(record.read_text())
                imported[identity]["recovered"] = recovered(imported[identity]["record"]["repo"])
                for name in ("record.toml", "evidence.md"):
                    path = root / name
                    if path.is_file():
                        shutil.copyfile(path, log / name)
                        destination = index / "repos" / identity / name
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(path, destination)
            # Parsing must never alter the retained source bytes.
            for item in files:
                require(sha(root / item["path"]) == item["sha256"], "import mutated a source")
        verify()
        stamp = datetime.fromisoformat(frozen["frozenAt"])
        export = command(
            [
                str(CLI),
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
            selection = select_profile_instruction(
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
                    "consumerSelection": selection,
                    "recoveredInstructions": imported[identity]["recovered"],
                    "profileSha256": sha(profile) if profile.is_file() else None,
                    "importExitCode": imported[identity]["receipt"]["exitCode"],
                    "exportExitCode": export["exitCode"],
                }
            )
    # Gold alternatives are joined only after every independent consumer selection.
    gold = {task["id"]: task for task in read(PACKET / "gold-rust.json")["tasks"]}
    for observation in observations:
        task = gold[observation["id"]]
        observation["goldState"] = task["goldState"]
        observation["applicabilityDisposition"] = score_task(task, observation)
    report = {
        "schema": "dotrepo-e1-rust-evaluation/v1",
        "finishedAt": now(),
        "executionFreezeSha256": sha(FREEZE),
        "evaluatedTasks": 6,
        "plannedTasks": 24,
        "fullQualificationPassed": False,
        "upstreamCommandsExecuted": False,
        "modelCalls": 0,
        "consumerBenefitMeasured": False,
        "scoringMethod": METHOD,
        "rows": observations,
        "byScope": {
            scope: dict(
                Counter(
                    row["applicabilityDisposition"] for row in observations if row["scope"] == scope
                )
            )
            for scope in ("repository", "component")
        },
        "summary": dict(Counter(row["applicabilityDisposition"] for row in observations)),
    }
    write(output / "results.json", report)
    write(
        output / "materialization.json",
        {key: value["materializedFiles"] for key, value in imported.items()},
    )
    # Bind every retained output without overwriting earlier observations.
    verify()
    inventory = {
        str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()
    }
    write(output / "artifact-hashes.json", inventory)
    print(
        json.dumps(
            {
                "evaluatedTasks": 6,
                "plannedTasks": 24,
                "summary": report["summary"],
                "byScope": report["byScope"],
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "verify", "run"))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.action == "freeze":
        freeze()
    elif args.action == "verify":
        verify()
    else:
        require(args.out is not None, "run requires --out")
        run(args.out.resolve())


if __name__ == "__main__":
    main()
