"""Verify/retain actual bounded outputs; execute no project code or Docker calls."""

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
PACKET = HERE.parent / "f05-offline-requalification-20261029"
sys.path.insert(0, str(PACKET))
spec = importlib.util.spec_from_file_location("frozen_offline_v5", PACKET / "driver.v5.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def sha(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while raw := stream.read(1024**2):
            value.update(raw)
    return value.hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    before = json.loads((HERE / "BEFORE.v2.json").read_text())
    for path, digest in before["bindings"].items():
        assert sha(Path(path)) == digest, path
    plan = driver.verify_plan()
    rows, bindings, receipt_count = [], [], 0
    for attempt in before["attempts"]:
        task_id = attempt["task"]
        task = plan["tasks"][task_id]
        folder, raw = HERE / task_id, HERE / task_id / "raw"
        outcome = json.loads((folder / "outcome.json").read_text())
        result = outcome["driverResult"]
        assert result == json.loads((raw / "result.json").read_text())
        assert result["imageId"] == plan["imageId"] and result["sourceRevision"] == task["revision"]
        native = {
            role: (raw / f"logs/native-tests/{role}.txt").read_text()
            for role in ["stdout", "stderr"]
        }
        native_receipt = json.loads((raw / "logs/native-tests/receipt.json").read_text())
        native.update(exitCode=native_receipt["exitCode"], error=native_receipt["error"])
        listing = (
            (raw / "logs/native-list/stdout.txt").read_text() if task.get("listCommand") else ""
        )
        report = (
            json.loads((raw / "logs/vitest-native-report/stdout.txt").read_text())
            if task["kind"] == "vitest"
            else {}
        )
        assert driver.score(task, native, listing, report) == result["oracle"], task_id
        for receipt in folder.glob("**/logs/*/receipt.json"):
            value = json.loads(receipt.read_text())
            for role in ["stdout", "stderr"]:
                assert sha(receipt.parent / (role + ".txt")) == value[role + "Sha256"], receipt
            assert value["costUsd"] is None
            receipt_count += 1
        for name in [
            "initial-source-byte-check",
            "initial-cache-byte-check",
            "tracked-source-after-tests",
        ]:
            receipt = json.loads((raw / f"logs/{name}/receipt.json").read_text())
            assert receipt["exitCode"] == 0 and receipt["error"] is None
        container = json.loads((raw / "logs/container-inspect/stdout.txt").read_text())[0]
        assert not container["Mounts"] and container["HostConfig"]["NetworkMode"] == "none"
        assert container["HostConfig"]["ReadonlyRootfs"] and container["HostConfig"]["CapDrop"] == [
            "ALL"
        ]
        assert (
            container["HostConfig"]["Memory"]
            == container["HostConfig"]["MemorySwap"]
            == 4 * 1024**3
        )
        assert (
            container["HostConfig"]["NanoCpus"] == 3 * 10**9
            and container["HostConfig"]["PidsLimit"] == 256
        )
        assert outcome["postCleanupContainerAbsent"] is True and result["cleanupExitCode"] == 0
        native_list_seconds = (
            json.loads((raw / "logs/native-list/receipt.json").read_text())["elapsedSeconds"]
            if task.get("listCommand")
            else None
        )
        rows.append(
            {
                "taskId": task_id,
                "repository": task["repository"],
                "revision": task["revision"],
                "scope": task["scope"],
                "component": task["component"],
                "attempts": 1,
                "state": result["state"],
                "taskOutcomeObserved": result["taskOutcomeObserved"],
                "testsPassed": result["testsPassed"],
                "nativeExitCode": result["testExitCode"],
                "nativeError": result["executionError"],
                "oracle": result["oracle"],
                "preflightSeconds": result["preflightSeconds"],
                "offlineSetupSeconds": result["offlineSetupSeconds"],
                "nativeDiscoverySeconds": native_list_seconds,
                "nativeTestsSeconds": native_receipt["elapsedSeconds"],
                "driverWorkSeconds": result["workElapsedSeconds"],
                "cleanupSeconds": result["cleanupSeconds"],
                "driverElapsedSeconds": result["elapsedSeconds"],
                "metadataVerification": result["metadataVerification"],
                "totalMeasuredOperatorSeconds": result["totalMeasuredOperatorSeconds"],
                "outerInvocationSeconds": json.loads(
                    (folder / "logs/driver-invocation/receipt.json").read_text()
                )["elapsedSeconds"],
                "trackedSourceIntact": result["trackedSourceIntact"],
                "ownedContainer": outcome["ownedContainer"],
                "independentPostCleanupAbsence": outcome["postCleanupContainerAbsent"],
                "sourceArchiveSha256": task["source"]["archive"]["sha256"],
                "cacheArchiveSha256": task["cache"]["archive"]["sha256"],
                "resultSha256": sha(raw / "result.json"),
                "costUsd": None,
            }
        )
        bindings.append(
            {
                "taskId": task_id,
                "revision": task["revision"],
                "source": task["source"],
                "cache": task["cache"],
                "originalTestCommand": task["originalTestCommand"],
                "nativeTestCommand": task["testCommand"],
                "expectedScope": {key: task[key] for key in ["scope", "component"]},
                "rawAttempt": str(raw.relative_to(HERE)),
                "toolHashReceipt": str(
                    (raw / "logs/source-free-tool-byte-hashes/receipt.json").relative_to(HERE)
                ),
            }
        )
    inputs = HERE / "inputs"
    inputs.mkdir()
    for name in [
        "acceptance.json",
        "FREEZE.json",
        "rust-02-cache-audit.json",
        "typescript-02-cache-audit.json",
        "go-03-cache-audit.json",
    ]:
        shutil.copyfile(HERE.parent / "f05-offline-acceptance-20261029" / name, inputs / name)
    write(
        HERE / "source-bindings.json",
        {
            "planSha256": sha(PACKET / "plan.v5.json"),
            "imageId": plan["imageId"],
            "bindings": bindings,
        },
    )
    write(
        HERE / "report.json",
        {
            "identity": "three-known-scopes-offline-requalification-actual-v1",
            "reportedAt": datetime.now(timezone.utc).isoformat(),
            "beforeSha256": sha(HERE / "BEFORE.v2.json"),
            "planSha256": sha(PACKET / "plan.v5.json"),
            "driverSha256": sha(PACKET / "driver.v5.py"),
            "oracleSha256": sha(PACKET / "oracle_v5.py"),
            "imageId": plan["imageId"],
            "tasks": rows,
            "verifiedCommandReceipts": receipt_count,
            "scope": "Three previously successful native scopes on common image/frozen warm caches; one actual serialized attempt each, independently reviewed before and subject to independent result review.",
            "actualTaskAttempts": 3,
            "retried": False,
            "codeCommandsInputsResourcesChanged": False,
            "all12EnvironmentQualified": False,
            "agentCampaignExecuted": False,
            "modelCalls": 0,
            "indexConsulted": False,
            "vmChanged": False,
            "costUsd": None,
            "costExclusions": [
                "Host/container dollar meter unavailable; external image/cache preparation retained separately, not charged zero."
            ],
            "limits": [
                "Operator execution qualification, not autonomous72session campaign or consumerbenefit evidence.",
                "Other9task environments remain unqualified by this packet.",
                "Npm offline --ignore-scripts setup does not establish ordinary npmci/hook equivalence.",
                "Source archives do not fabricate Git checkout metadata.",
                "Zero-case Rust doc phase is process-phase completion, not exercised documentation behavior.",
            ],
        },
    )


if __name__ == "__main__":
    main()
