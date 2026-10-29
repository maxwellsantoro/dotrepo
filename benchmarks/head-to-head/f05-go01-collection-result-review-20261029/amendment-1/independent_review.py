"""Independent source-data review of third incomplete run; no process/native calls."""

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
                "original or copy changed",
            )
    prior = PACKET.parent
    old = read(prior / "FREEZE.json")
    for name, digest in old["artifactSha256"].items():
        require(sha(prior / name) == digest, "parent history")
    plan = read(PACKET / "bindings/driver/plan.json")
    old_plan = read(prior / "bindings/plan.json")
    require(
        all(
            plan[k] == old_plan[k]
            for k in [
                "commands",
                "cwd",
                "sourceArchiveSha256",
                "imageId",
                "environment",
                "environmentSha256",
                "projection",
                "limits",
            ]
        ),
        "runtime context changed",
    )
    require(
        plan["expectedGoEnv"] == {**old_plan["expectedGoEnv"], "GOENV": ""},
        "query correction scope",
    )
    result = read(PACKET / "evidence/result.json")
    old_result = read(prior / "attempt-2/result.json")
    require(
        result["state"] == "incomplete"
        and result["stage"] == "go-list"
        and result["error"] == "ValueError: package has no selected Go source",
        "actual failure",
    )
    trace = read(PACKET / "evidence/trace.json")["receipts"]
    old_trace = read(prior / "attempt-2/trace.json")["receipts"]
    require(
        set(trace) == set(old_trace) | {"logs/go-list/receipt.json"}, "unexpected command closure"
    )
    input_bytes = output_bytes = 0
    for relative, receipt in trace.items():
        require(receipt == read(PACKET / "evidence" / relative), "trace receipt")
        label = Path(relative).parent.name
        if relative in old_trace:
            expected = [
                part.replace(old_result["ownedContainer"], result["ownedContainer"])
                for part in old_trace[relative]["argv"]
            ]
        else:
            expected = [
                "docker",
                "exec",
                result["ownedContainer"],
                "/bin/sh",
                "-eu",
                "-c",
                "cd " + plan["cwd"] + "; " + plan["commands"][1],
            ]
        require(receipt["argv"] == expected, "actual argv: " + label)
        require(receipt["exitCode"] == (1 if label == "post-cleanup-inspect" else 0), "exit status")
        require(
            receipt["error"] is None
            and receipt["cancelled"] is False
            and receipt["costUsd"] is None,
            "status/cost",
        )
        for stream in ["stdout", "stderr"]:
            raw = PACKET / "evidence/logs" / label / (stream + ".bin")
            require(sha(raw) == receipt[stream + "Sha256"], "raw hash")
            output_bytes += raw.stat().st_size
        input_bytes += receipt["stdinBytes"]
    env = read(PACKET / "evidence/logs/go-env/stdout.bin")
    require(env == plan["expectedGoEnv"], "query check passed")
    inspect = read(PACKET / "evidence/logs/container-inspect/stdout.bin")[0]
    require("GOENV=off" in inspect["Config"]["Env"], "input GOENV")
    for label in [
        "source-provision",
        "cache-provision",
        "initial-source-check",
        "initial-cache-check",
    ]:
        current = trace["logs/" + label + "/receipt.json"]
        previous = old_trace["logs/" + label + "/receipt.json"]
        require(
            current["stdinSha256"] == previous["stdinSha256"]
            and current["stdinBytes"] == previous["stdinBytes"],
            "same provision/manifest",
        )
    require(
        read(PACKET / "evidence/source-tree-before.json")
        == read(prior / "attempt-2/source-tree-before.json"),
        "before source tree",
    )
    raw = (PACKET / "evidence/logs/go-list/stdout.bin").read_bytes()
    require(raw == (PACKET / "evidence/packages.jsonstream").read_bytes(), "lossless raw copy")
    require((PACKET / "evidence/logs/go-list/stderr.bin").read_bytes() == b"", "go-list stderr")
    text = raw.decode("utf-8")
    decoder = json.JSONDecoder(object_pairs_hook=unique)
    position = 0
    rows = []
    while position < len(text):
        while position < len(text) and text[position] in " \t\r\n":
            position += 1
        if position == len(text):
            break
        row, position = decoder.raw_decode(text, position)
        require(isinstance(row, dict), "non-object")
        rows.append(row)
    require(len(rows) == 104 and len({r["ImportPath"] for r in rows}) == 104, "raw package objects")
    only = [r for r in rows if not (r.get("GoFiles") or r.get("CgoFiles"))]
    require(len(only) == 1, "one raw test-only observation")
    testonly = only[0]
    require(
        testonly["ImportPath"] == "github.com/microsoft/TypeScript/tsc/internal/fourslash/tests",
        "test-only identity",
    )
    counts = {
        k: len(testonly.get(k, [])) for k in ["GoFiles", "CgoFiles", "TestGoFiles", "XTestGoFiles"]
    }
    require(
        counts == {"GoFiles": 0, "CgoFiles": 0, "TestGoFiles": 3, "XTestGoFiles": 4368},
        "raw selected file counts",
    )
    require(result["containerAbsent"] is True and result["cleanupExitCode"] == 0, "cleanup")
    require(
        read(PACKET / "evidence/logs/post-cleanup-inspect/stdout.bin") == []
        and (PACKET / "evidence/logs/post-cleanup-list/stdout.bin").read_bytes() == b"",
        "same-attempt absence",
    )
    require(
        not any(
            (PACKET / "evidence" / n).exists()
            for n in [
                "package-inventory.json",
                "collection-events.jsonl",
                "collection-manifest.json",
                "source-tree-after.json",
            ]
        ),
        "accepted or later output",
    )
    require(
        all(
            result[k] is False
            for k in [
                "nativeCollectionAttempted",
                "nativeCollectionOccurred",
                "taskOutcomeObserved",
                "nativeTaskAdmitted",
                "campaignAdmitted",
                "cacheGloballyQualified",
            ]
        ),
        "no native/task admission",
    )
    report = read(PACKET / "report.json")
    effort = report["effort"]
    require(report["state"] == "incomplete-at-go-list-parser", "reported state")
    require(
        effort["daemonCalls"] == len(trace) == 16
        and effort["stdinBytes"] == input_bytes
        and effort["rawOutputBytes"] == output_bytes,
        "current accounting",
    )
    require(
        math.isclose(effort["elapsedSeconds"], result["elapsedSeconds"], rel_tol=1e-14)
        and effort["costUsd"] is None,
        "timing/unknown cost",
    )
    old_effort = read(prior / "report.json")["effort"]
    combined = effort["allThreeInvocations"]
    for key in ["daemonCalls", "stdinBytes", "rawOutputBytes"]:
        require(combined[key] == old_effort[key] + effort[key], "all-three accounting")
    require(
        math.isclose(
            combined["sumDriverElapsedSeconds"],
            old_effort["sumDriverElapsedSeconds"] + effort["elapsedSeconds"],
            rel_tol=1e-14,
        ),
        "all-three timing",
    )
    require(report["cleanup"]["independentAbsenceObservation"] is False, "cleanup limit")
    require(
        report["preservation"]["originalOuterInvocationArgvReceiptAvailable"] is False,
        "outer receipt limit",
    )
    replay = read(HERE / "replay-verification.json")
    require(
        replay["inventoryAccepted"] is False
        and replay["inputArchives"]["sourceTreeBeforeMatchesArchive"] is True,
        "parser/archive replay",
    )
    answer = {
        "state": "independently-verified-incomplete-go-list-parser-result",
        "packetArtifacts": len(frozen["artifactSha256"]),
        "originalCopies": len(ledger),
        "parentArtifactsUnchanged": len(old["artifactSha256"]),
        "actualArgvClosures": len(trace),
        "rawUniquePackageObjects": len(rows),
        "rawTestOnlyFileCounts": counts,
        "inventoryAccepted": False,
        "goTestListExecuted": False,
        "nativeCollectionOccurred": False,
        "taskOutcomeObserved": False,
        "stdinBytes": input_bytes,
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
