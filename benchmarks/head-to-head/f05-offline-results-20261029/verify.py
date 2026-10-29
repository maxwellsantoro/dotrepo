"""Read-only receipt verification; no Docker, upstream, network or provider calls."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from finalize import HERE, PACKET, driver, sha


def load(path):
    return json.loads(path.read_text())


def verify():
    before = load(HERE / "BEFORE.v2.json")
    for name, digest in before["bindings"].items():
        assert sha(Path(name)) == digest, name
    plan = driver.verify_plan()
    report = load(HERE / "report.json")
    assert report["beforeSha256"] == sha(HERE / "BEFORE.v2.json")
    assert report["planSha256"] == sha(PACKET / "plan.v5.json")
    assert report["actualTaskAttempts"] == 3 and report["retried"] is False
    count, rows = 0, []
    for attempt, row in zip(before["attempts"], report["tasks"], strict=True):
        task_id = attempt["task"]
        task, folder = plan["tasks"][task_id], HERE / task_id
        raw = folder / "raw"
        leaf = load(HERE / f"{task_id}-FREEZE.json")
        assert leaf["beforeSha256"] == sha(HERE / "BEFORE.v2.json")
        for name, digest in leaf["files"].items():
            assert sha(folder / name) == digest, name
        outcome, result = load(folder / "outcome.json"), load(raw / "result.json")
        assert result == outcome["driverResult"]
        assert row["taskId"] == task_id and row["resultSha256"] == sha(raw / "result.json")
        assert result["sourceRevision"] == task["revision"]
        assert result["imageId"] == plan["imageId"]
        assert result["workElapsedSeconds"] <= 1800 and result["cleanupSeconds"] <= 60
        assert result["costUsd"] is None and result["costExclusions"]
        assert result["trackedSourceIntact"] and result["cleanupExitCode"] == 0
        assert result["modelCalls"] == 0 and result["indexConsulted"] is False
        assert result["metadataVerification"]["outsideTaskDeadline"] is True
        for receipt in folder.glob("**/logs/*/receipt.json"):
            value = load(receipt)
            for role in ["stdout", "stderr"]:
                assert sha(receipt.parent / f"{role}.txt") == value[f"{role}Sha256"]
            assert value["costUsd"] is None and value["costExclusions"]
            count += 1
        assert load(folder / "logs/driver-invocation/receipt.json")["argv"] == attempt["argv"]
        for kind in ["source", "cache"]:
            receipt = load(raw / f"logs/{kind}-provision/receipt.json")
            assert receipt["stdinSha256"] == task[kind]["archive"]["sha256"]
            assert receipt["exitCode"] == 0 and receipt["error"] is None
        for name in [
            "initial-source-byte-check",
            "initial-cache-byte-check",
            "tracked-source-after-tests",
        ]:
            receipt = load(raw / f"logs/{name}/receipt.json")
            assert receipt["exitCode"] == 0 and receipt["error"] is None
            assert (raw / f"logs/{name}/stdout.txt").read_text() == ""
        receipt = load(raw / "logs/native-tests/receipt.json")
        assert receipt["argv"][-1] == "cd /workspace/repository; " + task["testCommand"]
        native = {
            role: (raw / f"logs/native-tests/{role}.txt").read_text()
            for role in ["stdout", "stderr"]
        }
        native.update(exitCode=receipt["exitCode"], error=receipt["error"])
        listing = (
            (raw / "logs/native-list/stdout.txt").read_text() if task.get("listCommand") else ""
        )
        native_json = (
            load(raw / "logs/vitest-native-report/stdout.txt") if task["kind"] == "vitest" else {}
        )
        assert driver.score(task, native, listing, native_json) == result["oracle"] == row["oracle"]
        assert result["taskOutcomeObserved"] and result["testsPassed"]
        container = load(raw / "logs/container-inspect/stdout.txt")[0]
        host = container["HostConfig"]
        assert container["Image"] == plan["imageId"] and not container["Mounts"]
        assert container["Config"]["User"] == "1000:1000"
        assert host["NetworkMode"] == "none" and host["ReadonlyRootfs"]
        assert host["CapDrop"] == ["ALL"] and not host["Privileged"]
        assert host["SecurityOpt"] == ["no-new-privileges"] and not host["Binds"]
        assert host["Memory"] == host["MemorySwap"] == 4 * 1024**3
        assert host["NanoCpus"] == 3 * 10**9 and host["PidsLimit"] == 256
        assert "exec" in host["Tmpfs"]["/tmp"].split(",")
        assert "exec" in host["Tmpfs"]["/workspace"].split(",")
        assert "size=8g" in host["Tmpfs"]["/workspace"].split(",")
        inspect = load(folder / "logs/post-cleanup-owned-inspect/receipt.json")
        listing_receipt = load(folder / "logs/post-cleanup-owned-list/receipt.json")
        assert inspect["exitCode"] != 0 and inspect["error"] is None
        assert listing_receipt["exitCode"] == 0 and listing_receipt["error"] is None
        assert outcome["ownedContainer"] in inspect["argv"]
        assert f"name={outcome['ownedContainer']}" in listing_receipt["argv"]
        assert (folder / "logs/post-cleanup-owned-list/stdout.txt").read_text() == ""
        assert outcome["postCleanupContainerAbsent"] is True
        rows.append(
            {
                "taskId": task_id,
                "leafFreezeSha256": sha(HERE / f"{task_id}-FREEZE.json"),
                "passed": True,
            }
        )
    assert count == report["verifiedCommandReceipts"] == 60
    return {
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "state": "passed",
        "reportSha256": sha(HERE / "report.json"),
        "verifiedCommandReceipts": count,
        "tasks": rows,
        "newDockerOrUpstreamOrNetworkOrProviderCalls": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    checks = verify()
    with args.output.open("x") as stream:
        json.dump(checks, stream, indent=2)
        stream.write("\n")
