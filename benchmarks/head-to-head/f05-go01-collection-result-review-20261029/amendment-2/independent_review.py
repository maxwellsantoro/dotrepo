"""Independent static failure/receipt/event checks; no driver/native execution."""

from collections import Counter
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKET = Path(json.loads((HERE / "author-binding.json").read_text())["packet"])


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(value, reason):
    if not value:
        raise ValueError(reason)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def main():
    frozen = read(PACKET / "FREEZE.json")
    for name, digest in frozen["artifactSha256"].items():
        require(sha(PACKET / name) == digest, name)
    ledger = read(PACKET / "origin-ledger.json")["files"]
    for row in ledger:
        for path in [PACKET / row["retained"], Path(row["source"])]:
            require(
                path.stat().st_size == row["bytes"] and sha(path) == row["sha256"],
                "original/copy changed",
            )
    histories = []
    for history in [PACKET.parent, PACKET.parent / "amendment-1"]:
        f = read(history / "FREEZE.json")
        for name, digest in f["artifactSha256"].items():
            require(sha(history / name) == digest, "history changed")
        histories.append(len(f["artifactSha256"]))
    previous = PACKET.parent / "amendment-1"
    old_result = read(previous / "evidence/result.json")
    result = read(PACKET / "evidence/result.json")
    plan = read(PACKET / "bindings/driver/plan.json")
    old_plan = read(previous / "bindings/driver/plan.json")
    require(
        all(
            plan[k] == old_plan[k]
            for k in [
                "commands",
                "cwd",
                "limits",
                "environment",
                "environmentSha256",
                "expectedGoEnv",
                "imageId",
                "sourceArchiveSha256",
                "projection",
            ]
        ),
        "runtime context changed",
    )
    trace = read(PACKET / "evidence/trace.json")["receipts"]
    old_trace = read(previous / "evidence/trace.json")["receipts"]
    require(set(trace) == set(old_trace) | {"logs/go-test-list/receipt.json"}, "command closure")
    stdin_bytes = output_bytes = 0
    for relative, receipt in trace.items():
        label = Path(relative).parent.name
        require(receipt == read(PACKET / "evidence" / relative), "trace/receipt")
        expected = (
            [
                value.replace(old_result["ownedContainer"], result["ownedContainer"])
                for value in old_trace[relative]["argv"]
            ]
            if relative in old_trace
            else [
                "docker",
                "exec",
                result["ownedContainer"],
                "/bin/sh",
                "-eu",
                "-c",
                "cd " + plan["cwd"] + "; " + plan["commands"][2],
            ]
        )
        require(receipt["argv"] == expected, "unexpected argv: " + label)
        require(
            receipt["exitCode"] == (1 if label in ["go-test-list", "post-cleanup-inspect"] else 0),
            "exit status",
        )
        require(
            receipt["error"] is None
            and receipt["cancelled"] is False
            and receipt["costUsd"] is None,
            "transport/cost",
        )
        for stream in ["stdout", "stderr"]:
            raw = PACKET / "evidence/logs" / label / (stream + ".bin")
            require(sha(raw) == receipt[stream + "Sha256"], "raw hash")
            output_bytes += raw.stat().st_size
        stdin_bytes += receipt["stdinBytes"]
    require(
        result["state"] == "incomplete"
        and result["stage"] == "go-test-list"
        and result["nativeCollectionAttempted"] is True,
        "attempted failure",
    )
    require(
        all(
            result[k] is False
            for k in [
                "nativeCollectionOccurred",
                "collectionObserved",
                "taskOutcomeObserved",
                "nativeTaskAdmitted",
                "campaignAdmitted",
                "cacheGloballyQualified",
            ]
        ),
        "no completion/admission",
    )
    require(
        result["workBudgetExceeded"] is False and result["cancelled"] is False,
        "recorded timeout/cancel",
    )
    inventory = read(PACKET / "evidence/package-inventory.json")
    decoder = json.JSONDecoder(object_pairs_hook=unique)
    text = (PACKET / "evidence/packages.jsonstream").read_text()
    position = 0
    packages = []
    while position < len(text):
        while position < len(text) and text[position] in " \t\r\n":
            position += 1
        if position == len(text):
            break
        row, position = decoder.raw_decode(text, position)
        packages.append(row)
    require(
        len(packages) == len(inventory) == 104
        and {r["ImportPath"]: r for r in packages} == inventory,
        "accepted inventory/raw",
    )
    raw = (PACKET / "evidence/logs/go-test-list/stdout.bin").read_bytes()
    events = [json.loads(line, object_pairs_hook=unique) for line in raw.splitlines()]
    require(
        len(raw) == 127015
        and (PACKET / "evidence/logs/go-test-list/stderr.bin").read_bytes() == b"",
        "listing bytes",
    )
    counts = Counter(row["Action"] for row in events)
    expected_counts = {
        "build-output": 2,
        "build-fail": 2,
        "start": 104,
        "output": 520,
        "fail": 61,
        "pass": 25,
        "skip": 18,
    }
    require(len(events) == 732 and counts == expected_counts, "partial action counts")
    require(not any("Test" in row for row in events), "no per-test events")
    terminals = {}
    starts = set()
    for row in events:
        action = row["Action"]
        if action in ["build-output", "build-fail"]:
            continue
        package = row["Package"]
        require(package in inventory, "package outside inventory")
        if action == "start":
            require(package not in starts, "duplicate start")
            starts.add(package)
        if action in ["pass", "fail", "skip"]:
            require(package not in terminals, "duplicate terminal")
            terminals[package] = action
    require(set(terminals) == starts == set(inventory), "all package terminals")
    diagnostics = [r for r in events if r["Action"] == "build-output"]
    require(
        all("compile: signal: killed" in r["Output"] for r in diagnostics), "compiler diagnostics"
    )
    require(
        {r["ImportPath"] for r in diagnostics}
        == {
            "github.com/microsoft/TypeScript/tsc/internal/compiler [github.com/microsoft/TypeScript/tsc/cmd/tsc]",
            "github.com/microsoft/TypeScript/tsc/internal/ast",
        },
        "build identities",
    )
    require(
        not any(
            (PACKET / "evidence" / name).exists()
            for name in [
                "collection-events.jsonl",
                "collection-manifest.json",
                "source-tree-after.json",
            ]
        ),
        "no complete/later files",
    )
    require(
        "logs/offline-final-inspect/receipt.json" not in trace
        and "logs/tools-after/receipt.json" not in trace,
        "no after observations",
    )
    require(result["containerAbsent"] is True and result["cleanupExitCode"] == 0, "cleanup status")
    require(
        read(PACKET / "evidence/logs/post-cleanup-inspect/stdout.bin") == []
        and b"no such object"
        in (PACKET / "evidence/logs/post-cleanup-inspect/stderr.bin").read_bytes()
        and (PACKET / "evidence/logs/post-cleanup-list/stdout.bin").read_bytes() == b"",
        "same-attempt absence",
    )
    report = read(PACKET / "report.json")
    effort = report["effort"]
    require(
        report["terminationCause"] is None
        and report["oomProven"] is False
        and report["initializationExecutionExtent"] == "unresolved",
        "cause/init limits",
    )
    require(
        report["collectionCompleted"] is False
        and report["fullCollectionManifestExists"] is False
        and report["taskOutcomeObserved"] is False,
        "report no completion",
    )
    require(
        report["cleanup"]["independentAbsenceObservation"] is False
        and report["preservation"]["completeOriginalOuterArgvReceiptAvailable"] is False,
        "receipt limits",
    )
    require(
        effort["daemonCalls"] == len(trace) == 17
        and effort["stdinBytes"] == stdin_bytes
        and effort["rawOutputBytes"] == output_bytes,
        "current accounting",
    )
    require(
        math.isclose(effort["elapsedSeconds"], result["elapsedSeconds"], rel_tol=1e-14)
        and effort["costUsd"] is None,
        "time/unknown cost",
    )
    old_all = read(previous / "report.json")["effort"]["allThreeInvocations"]
    all_four = effort["allFourInvocations"]
    for k in ["daemonCalls", "stdinBytes", "rawOutputBytes"]:
        require(all_four[k] == old_all[k] + effort[k], "four-invocation accounting")
    require(
        math.isclose(
            all_four["sumDriverElapsedSeconds"],
            old_all["sumDriverElapsedSeconds"] + effort["elapsedSeconds"],
            rel_tol=1e-14,
        ),
        "four-invocation time",
    )
    answer = {
        "state": "independently-verified-incomplete-build-failure",
        "artifacts": len(frozen["artifactSha256"]),
        "originalCopies": len(ledger),
        "parentAndSiblingArtifactsUnchanged": histories,
        "actualArgvClosures": len(trace),
        "acceptedPackageInventory": len(inventory),
        "partialEvents": len(events),
        "actions": dict(counts),
        "packageTerminals": len(terminals),
        "perTestEvents": 0,
        "compilerKilledDiagnostics": len(diagnostics),
        "cause": None,
        "oomProven": False,
        "initializationExtent": "unresolved",
        "nativeCollectionAttempted": True,
        "completeManifest": False,
        "taskOutcomeObserved": False,
        "stdinBytes": stdin_bytes,
        "rawOutputBytes": output_bytes,
        "elapsedSeconds": result["elapsedSeconds"],
        "costUsd": None,
        "cleanupEvidence": "same-attempt only",
        "afterIntegrity": "not established",
        "newLiveActions": 0,
    }
    with (HERE / "independent-checks.json").open("x") as f:
        json.dump(answer, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps(answer))


if __name__ == "__main__":
    main()
