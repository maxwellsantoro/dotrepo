"""Static audit of the third incomplete invocation; no daemon or upstream actions."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
PARENT_FREEZE = "3d88c025332c325a17d3fe95a3b55aebcd9e67e75992950525727d84f1d7eca6"
PARENT_VERIFIER = "1ad914bce00db23f2bd638d8b4f571b62fb52315b7874f2c32291c30187e0992"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


if sha(PARENT / "verify.py") != PARENT_VERIFIER:
    raise ValueError("changed parent static verifier")
spec = importlib.util.spec_from_file_location("parent_result_verifier", PARENT / "verify.py")
parent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent)
require, read, digest = parent.require, parent.read, parent.digest


def closure(root):
    require(digest(PARENT / "FREEZE.json") == PARENT_FREEZE, "parent freeze changed")
    old = read(PARENT, "FREEZE.json")["artifactSha256"]
    require(len(old) == 91, "parent artifact count")
    for name, expected in old.items():
        require(digest(PARENT / name) == expected, f"parent changed: {name}")
    for row in read(root, "origin-ledger.json")["files"]:
        path = root / row["retained"]
        require(path.resolve().is_relative_to(root.resolve()), "copy path escapes")
        require(
            path.stat().st_size == row["bytes"] and digest(path) == row["sha256"],
            "original byte mismatch",
        )
    plan = read(root, "bindings/driver/plan.json")
    frozen = read(root, "bindings/driver/FREEZE.json")
    subject = {
        "driverPlanSha256": digest(root / "bindings/driver/plan.json"),
        "authorFreezeSha256": digest(root / "bindings/driver/FREEZE.json"),
        "packetIdentity": plan["identity"],
    }
    require(
        frozen["identity"] == plan["identity"]
        and frozen["driverPlanSha256"] == subject["driverPlanSha256"],
        "author subject",
    )
    for name, expected in {**plan["scripts"], **plan["localFiles"]}.items():
        require(
            digest(root / "bindings/driver" / name) == frozen["artifactSha256"][name] == expected,
            "author closure",
        )
    old_plan = read(PARENT, "bindings/plan.json")
    for key in [
        "commands",
        "cwd",
        "sourceArchiveSha256",
        "imageId",
        "environment",
        "environmentSha256",
        "projection",
        "limits",
    ]:
        require(plan[key] == old_plan[key], f"runtime input changed: {key}")
    require(
        plan["expectedGoEnv"] == {**old_plan["expectedGoEnv"], "GOENV": ""},
        "query correction exceeded scope",
    )
    acceptance = read(root, "authorization/acceptance.json")
    auth = read(root, "authorization/authorization.json")
    for name, expected in read(root, "authorization/FREEZE.json")["artifactSha256"].items():
        require(digest(root / "authorization" / name) == expected, "authorization freeze")
    require(
        auth["planSha256"] == subject["driverPlanSha256"]
        and auth["authorFreezeSha256"] == subject["authorFreezeSha256"],
        "authorization subject",
    )
    require(
        auth["commands"] == plan["commands"]
        and auth["limits"] == plan["limits"]
        and auth["maxAttempts"] == 1,
        "authorization limits",
    )
    require(
        auth["collectionAcceptance"]["sha256"] == digest(root / "authorization/acceptance.json"),
        "acceptance bytes",
    )
    require(acceptance["driverSubject"] == subject, "acceptance subject")
    for key in ["nativeTaskAdmitted", "campaignAdmitted", "cacheGloballyQualified"]:
        require(acceptance[key] is False, "broader acceptance")
    require(
        acceptance["synthetic"] is False and acceptance["initAndTestMainExecutionAccepted"] is True,
        "actual scoped acceptance",
    )
    review = read(root, "bindings/review/passed-review.json")
    require(
        review["subject"] == subject
        and review["findings"] == []
        and review["state"] == "independent-go01-collection-driver-review-passed",
        "current passed review",
    )
    require(
        review["report"]["sha256"] == digest(root / "bindings/review/review.json"), "review report"
    )
    require(
        acceptance["driverReviewFreeze"]["sha256"]
        == digest(root / "bindings/review/passed-review.json"),
        "accepted review",
    )
    require(
        read(root, "authorization/FREEZE.json")["driverReviewFreezeSha256"]
        == digest(root / "bindings/review/FREEZE.json"),
        "accepted review freeze",
    )
    for name in ["passed-review.json", "review.json"]:
        require(
            read(root, "bindings/review/FREEZE.json")["artifacts"][name]["sha256"]
            == digest(root / "bindings/review" / name),
            "review closure",
        )
    require(
        auth["priorResult"]["sha256"] == digest(PARENT / "attempt-2/result.json"),
        "prior failure retained",
    )
    return plan, auth


def observations(root, plan, auth):
    result = read(root, "evidence/result.json")
    require(read(root, "outer/driver.log") == result, "outer log differs")
    require(
        result["state"] == "incomplete"
        and result["stage"] == "go-list"
        and result["error"] == "ValueError: package has no selected Go source",
        "different failure",
    )
    require(
        result["synthetic"] is False and result["costUsd"] is None and result["modelCalls"] == 0,
        "actual/cost state",
    )
    for key in [
        "nativeCollectionAttempted",
        "nativeCollectionOccurred",
        "collectionObserved",
        "taskOutcomeObserved",
        "nativeTaskAdmitted",
        "campaignAdmitted",
        "cacheGloballyQualified",
    ]:
        require(result[key] is False, f"unsupported outcome: {key}")
    require(
        result["authorizationSha256"] == digest(root / "authorization/authorization.json")
        and result["collectionAcceptance"]["authorization"] == auth,
        "actual authorization",
    )
    labels = {
        "image-inspect",
        "create",
        "start",
        "container-inspect",
        "initialize",
        "source-provision",
        "cache-provision",
        "initial-source-check",
        "initial-cache-check",
        "tools-before",
        "source-tree-before",
        "go-env",
        "go-list",
        "cleanup",
        "post-cleanup-inspect",
        "post-cleanup-list",
    }
    trace = read(root, "evidence/trace.json")["receipts"]
    require(
        set(trace) == {f"logs/{name}/receipt.json" for name in labels}
        and result["daemonCalls"] == len(trace) == 16,
        "command/daemon count",
    )
    stdin_bytes = raw_bytes = 0
    for name, receipt in trace.items():
        p = root / "evidence" / name
        require(read(root, f"evidence/{name}") == receipt, "trace/receipt mismatch")
        size = 0
        for stream in ["stdout", "stderr"]:
            stream_path = p.parent / f"{stream}.bin"
            require(digest(stream_path) == receipt[f"{stream}Sha256"], "raw stream changed")
            size += stream_path.stat().st_size
        require(size <= plan["limits"]["combinedStdoutStderrPerCommandBytes"], "output cap")
        require(
            receipt["error"] is None
            and receipt["cancelled"] is False
            and receipt["costUsd"] is None,
            "transport/cost state",
        )
        require(
            receipt["exitCode"] == (1 if name == "logs/post-cleanup-inspect/receipt.json" else 0),
            "exit mismatch",
        )
        stdin_bytes += receipt["stdinBytes"]
        raw_bytes += size

    def raw(name, stream="stdout"):
        return (root / f"evidence/logs/{name}/{stream}.bin").read_bytes()

    parent.isolation(
        json.loads(raw("container-inspect"))[0], json.loads(raw("image-inspect"))[0], plan
    )
    require(
        json.loads(raw("go-env"))
        == plan["expectedGoEnv"]
        == read(root, "evidence/go-environment.json"),
        "Go env mismatch",
    )
    require(raw("tools-before").decode() == plan["expectedToolOutput"], "tools before")
    require(
        json.loads(raw("source-tree-before")) == read(root, "evidence/source-tree-before.json"),
        "source tree raw observation",
    )
    for label in ["initial-source-check", "initial-cache-check"]:
        prior_receipt = read(PARENT, f"attempt-2/logs/{label}/receipt.json")
        current = trace[f"logs/{label}/receipt.json"]
        require(
            current["stdinSha256"] == prior_receipt["stdinSha256"]
            and current["stdinBytes"] == prior_receipt["stdinBytes"],
            "checksum manifest changed",
        )
    require(
        read(root, "evidence/source-tree-before.json")
        == read(PARENT, "attempt-2/source-tree-before.json"),
        "initial source tree differs",
    )
    for label, expected in [
        ("source-provision", plan["sourceArchiveSha256"]),
        ("cache-provision", plan["projection"]["archive"]["sha256"]),
    ]:
        require(trace[f"logs/{label}/receipt.json"]["stdinSha256"] == expected, "provision binding")
    for i, label in enumerate(["go-env", "go-list"]):
        require(
            trace[f"logs/{label}/receipt.json"]["argv"][-1]
            == f"cd {plan['cwd']}; {plan['commands'][i]}",
            "command changed",
        )
        require(raw(label, "stderr") == b"", "unexpected stderr")
    require(
        raw("go-list") == (root / "evidence/packages.jsonstream").read_bytes(), "raw package copy"
    )
    require(result["cleanupExitCode"] == 0 and result["containerAbsent"] is True, "cleanup state")
    require(
        json.loads(raw("post-cleanup-inspect")) == []
        and b"no such object" in raw("post-cleanup-inspect", "stderr")
        and raw("post-cleanup-list") == b"",
        "same-attempt absence",
    )
    require(
        not any(
            (root / "evidence" / name).exists()
            for name in [
                "package-inventory.json",
                "collection-events.jsonl",
                "collection-manifest.json",
                "source-tree-after.json",
            ]
        ),
        "unexpected accepted/later artifact",
    )
    # Decode only for raw-observation diagnosis; never accept a package inventory.
    text = raw("go-list").decode("utf-8", errors="strict")
    decoder, position, rows = json.JSONDecoder(), 0, []
    while position < len(text):
        while position < len(text) and text[position].isspace():
            position += 1
        if position == len(text):
            break
        value, position = decoder.raw_decode(text, position)
        require(isinstance(value, dict), "nonobject raw package")
        rows.append(value)
    require(len(rows) == 104, "raw object count changed")
    only_tests = [row for row in rows if not (row.get("GoFiles") or row.get("CgoFiles"))]
    require(len(only_tests) == 1, "different rejection candidate")
    row = only_tests[0]
    require(
        row["ImportPath"] == "github.com/microsoft/TypeScript/tsc/internal/fourslash/tests"
        and len(row["TestGoFiles"]) == 3
        and len(row["XTestGoFiles"]) == 4368,
        "test-only raw observation differs",
    )
    # Reproduce only the frozen owned parser rejection, no upstream module imports.
    p = root / "bindings/driver/listing.py"
    require(digest(p) == plan["scripts"]["listing.py"], "parser binding")
    spec = importlib.util.spec_from_file_location("frozen_owned_listing_parser", p)
    listing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(listing)
    try:
        listing.packages(raw("go-list"))
    except ValueError as exc:
        require(str(exc) == "package has no selected Go source", "different parser rejection")
    else:
        raise ValueError("frozen parser unexpectedly accepted inventory")
    return {
        "state": "verified-retained-incomplete-go-list-result",
        "rawPackageObjectCount": 104,
        "rawTestOnlyPackage": {
            "importPath": row["ImportPath"],
            "GoFiles": 0,
            "CgoFiles": 0,
            "TestGoFiles": 3,
            "XTestGoFiles": 4368,
        },
        "inventoryAccepted": False,
        "goTestListExecuted": False,
        "taskOutcomeObserved": False,
        "daemonCalls": 16,
        "stdinBytes": stdin_bytes,
        "rawOutputBytes": raw_bytes,
        "elapsedSeconds": result["elapsedSeconds"],
        "costUsd": None,
        "sourceAndToolsAfterObserved": False,
        "independentAbsenceObservation": False,
    }


def verify(root, input_archives=False):
    plan, auth = closure(root)
    report = observations(root, plan, auth)
    report["inputArchives"] = (
        parent.archives(PARENT, read(PARENT, "bindings/plan.json"))
        if input_archives
        else "not reread"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-archives", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(HERE, args.input_archives), indent=2, allow_nan=False))
