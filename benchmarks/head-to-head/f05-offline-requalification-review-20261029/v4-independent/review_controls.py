"""Independent synthetic v4 amendment review; every external process is forbidden."""

import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
PACKET = HERE.parent.parent / "f05-offline-requalification-20261029"
sys.path.insert(0, str(PACKET))
spec = importlib.util.spec_from_file_location("independent_offline_v4", PACKET / "driver.v4.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def approval(plan, root):
    receipts = {}
    for task in plan["tasks"]:
        raw = json.dumps(
            {
                "syntheticOnly": True,
                "state": "qualified-download-cache",
                **driver.audit_binding(plan, task),
                **dict.fromkeys(
                    (
                        "downloadOnly",
                        "buildOutputsExcluded",
                        "taskSourceExcluded",
                        "credentialsExcluded",
                        "protectedEvaluationAliasesExcluded",
                    ),
                    True,
                ),
            }
        ).encode()
        path = root / (task + "-synthetic-audit.json")
        path.write_bytes(raw)
        receipts[task] = {"path": str(path), "sha256": driver.sha(raw)}
    path = root / "synthetic-acceptance.json"
    path.write_text(
        json.dumps(
            {
                "syntheticOnly": True,
                "state": "accepted-for-three-scope-offline-requalification",
                "planSha256": driver.file_sha(PACKET / "plan.v4.json"),
                "imageId": plan["imageId"],
                "cacheAudits": receipts,
            }
        )
    )
    return path


def owned_archive(root, label, name):
    path = root / (label + ".tar")
    raw = b"synthetic reviewer-owned bytes only\n"
    with tarfile.open(path, "w:") as archive:
        member = tarfile.TarInfo(name)
        member.size = len(raw)
        member.mode = 0o644
        archive.addfile(member, io.BytesIO(raw))
    inventory = root / (label + "-inventory.json")
    inventory.write_text(json.dumps({"files": {name: driver.sha(raw)}}))
    return {
        "archive": {"path": str(path), "sha256": driver.file_sha(path)},
        "inventory": {"path": str(inventory), "sha256": driver.file_sha(inventory)},
    }


def main():
    actual_processes = []

    def forbidden(*args, **kwargs):
        actual_processes.append(str(args[:1]))
        raise AssertionError("real process/daemon forbidden in independent synthetic review")

    subprocess.Popen = forbidden
    driver.command = driver.checked = forbidden
    plan = driver.verify_plan()
    prior = json.loads((PACKET / "plan.v3.json").read_text())
    comparisons = {}
    for field in ("imageId", "environment", "resources", "toolHashCommand", "isolation"):
        assert plan[field] == prior[field], field
        comparisons[field] = "unchanged"
    for task_id, task in plan["tasks"].items():
        comparable = copy.deepcopy(task)
        comparable.pop("rustDefaultPolicy", None)
        assert comparable == prior["tasks"][task_id], task_id
        comparisons[task_id] = "unchanged task/source/cache/commands/offline setup"
    task = plan["tasks"]["rust-02"]
    names = task["expectedTests"]
    stdout = (PACKET / "source-bindings-v4/historical-rust-stdout.txt").read_text()
    stderr = (PACKET / "source-bindings-v4/historical-rust-stderr.txt").read_text()
    good = {"stdout": stdout, "stderr": stderr, "exitCode": 0, "error": None}
    unit = stdout.split("\n\nrunning 0 tests", 1)[0] + "\n"
    marker = "     Running unittests src/lib.rs (/synthetic/parser)\n"
    failure = {
        "stdout": unit.replace(names[0] + " ... ok", names[0] + " ... FAILED").replace(
            "test result: ok. 2 passed; 0 failed", "test result: FAILED. 1 passed; 1 failed"
        ),
        "stderr": marker + "error: test failed, to rerun pass `--lib`\n",
        "exitCode": 101,
        "error": None,
    }
    cases = [
        ("normal-two-unit-zero-doc-terminal", good, True),
        ("terminal-assertion-default-stop", failure, True),
        (
            "unit-pass-later-doc-compile-failure",
            {
                "stdout": unit,
                "stderr": marker
                + "   Doc-tests sniffnet_packet_parser\nerror: doctest failed, to rerun pass --doc\nCaused by: rustdoc compile failed\n",
                "exitCode": 101,
                "error": None,
            },
            False,
        ),
        ("unit-only-no-doc-terminal", {**good, "stdout": unit}, False),
        ("wrong-success-exit", {**good, "exitCode": 101}, False),
        ("timeout-after-terminal-output", {**good, "error": "timeout"}, False),
        ("bool-exit-identity", {**good, "exitCode": False}, False),
        ("missing-unit-marker", {**good, "stderr": "   Doc-tests sniffnet_packet_parser\n"}, False),
        ("duplicate-unit-marker", {**good, "stderr": marker + stderr}, False),
        ("missing-doc-marker", {**good, "stderr": marker}, False),
        ("doc-not-zero", {**good, "stdout": stdout.replace("ok. 0 passed", "ok. 1 passed")}, False),
        (
            "unit-filtered",
            {**good, "stdout": stdout.replace("0 filtered out", "1 filtered out", 1)},
            False,
        ),
        (
            "unit-case-missing",
            {
                **good,
                "stdout": stdout.replace("test link_type::tests::" + names[0] + " ... ok\n", ""),
            },
            False,
        ),
        (
            "assertion-summary-contradiction",
            {**failure, "stdout": failure["stdout"].replace(" ... FAILED", " ... ok")},
            False,
        ),
        ("assertion-wrong-exit", {**failure, "exitCode": 1}, False),
        (
            "assertion-followed-doc-marker",
            {**failure, "stderr": failure["stderr"] + "   Doc-tests sniffnet_packet_parser\n"},
            False,
        ),
        (
            "assertion-compiler-error",
            {**failure, "stderr": failure["stderr"] + "error[E0308]: mismatched types\n"},
            False,
        ),
        (
            "assertion-setup-error",
            {
                **failure,
                "stderr": failure["stderr"]
                + "error: failed to run custom build command for pcap\n",
            },
            False,
        ),
        (
            "assertion-unknown-diagnostic",
            {**failure, "stderr": failure["stderr"] + "error: unknown execution failure\n"},
            False,
        ),
    ]
    outcomes = []
    for label, native, expected in cases:
        observed = driver.score(task, native, "", {})
        assert observed["qualified"] is expected, (label, observed)
        if label == "terminal-assertion-default-stop":
            assert observed["docPhase"] == {
                "state": "unexecuted-default-stop",
                "exercised": False,
                "terminal": False,
                "testCases": None,
            }
            assert not observed["phaseCoverageComplete"]
        outcomes.append({"case": label, "expectedQualified": expected, "oracle": observed})
    disabled = copy.deepcopy(task)
    disabled["rustDefaultPolicy"]["unitAssertionFailureStopsDefault"] = False
    assert not driver.score(disabled, failure, "", {})["qualified"]
    preflights, downstream = [], []
    with tempfile.TemporaryDirectory(
        prefix="dotrepo-f05-offline-requalification-v4-independent-", dir="/tmp"
    ) as directory:
        root = Path(directory)
        for label, target in [("source-hash", "source"), ("cache-hash", "cache")]:
            folder = root / label
            folder.mkdir()
            synthetic = copy.deepcopy(plan)
            synthetic["tasks"]["rust-02"]["source"] = owned_archive(folder, "source", "README.md")
            synthetic["tasks"]["rust-02"]["cache"].update(
                owned_archive(folder, "cache", "cargo/registry/owned")
            )
            synthetic["tasks"]["rust-02"][target]["archive"]["sha256"] = "0" * 64
            approval_path = approval(synthetic, folder)
            output = folder / "attempt"
            try:
                driver.run(
                    synthetic,
                    "rust-02",
                    approval_path,
                    output,
                    {"state": "synthetic metadata pass", "elapsedSeconds": 0.125},
                )
            except ValueError as error:
                assert "archive hash mismatch" in str(error)
            else:
                raise AssertionError("accepted invalid owned archive")
            result = json.loads((output / "result.json").read_text())
            assert (output / "attempt.json").exists()
            assert (output / "acceptance-binding.json").exists()
            assert result["failureStage"] == "accepted-" + target + "-preflight"
            assert result["preflightSeconds"] >= 0
            assert result["totalMeasuredOperatorSeconds"] >= result["preflightSeconds"] + 0.125
            assert result["dockerCalls"] == 0 and not result["containerCreateAttempted"]
            assert not result["cleanupAttempted"] and result["cleanupSeconds"] == 0
            assert result["costUsd"] is None and result["testsPassed"] is None
            assert result["taskOutcomeObserved"] is False
            preflights.append({"case": label, "result": result})
        original_archive = driver.archive_input
        placeholder = root / "owned-placeholder.tar"
        placeholder.write_bytes(b"synthetic owned placeholder only")
        driver.archive_input = lambda *args, **kwargs: (placeholder, {}, 0)
        image = {
            "Id": plan["imageId"],
            "Os": "linux",
            "Architecture": "arm64",
            "Config": {"Env": []},
        }
        container = {
            "Image": plan["imageId"],
            "Mounts": [],
            "Config": {
                "User": "1000:1000",
                "Env": [k + "=" + v for k, v in plan["environment"].items()],
            },
            "NetworkSettings": {"Networks": {"none": {}}},
            "HostConfig": {
                "NetworkMode": "none",
                "Privileged": False,
                "ReadonlyRootfs": True,
                "CapDrop": ["ALL"],
                "SecurityOpt": ["no-new-privileges"],
                "PidMode": "",
                "Memory": 4 * 1024**3,
                "MemorySwap": 4 * 1024**3,
                "PidsLimit": 256,
                "NanoCpus": 3 * 10**9,
            },
        }
        live = {"native": None, "cleanupExit": 0, "calls": []}

        def fake(folder, label, argv, **kwargs):
            live["calls"].append(
                {"label": label, "argv": argv, "stdinBytes": len(kwargs.get("data", b""))}
            )
            value = {"exitCode": 0, "error": None, "stdout": "", "stderr": ""}
            if label == "image-inspect":
                value["stdout"] = json.dumps([image])
            elif label == "container-inspect":
                value["stdout"] = json.dumps([container])
            elif label == "native-tests":
                value.update(live["native"])
            elif label == "cleanup":
                value["exitCode"] = live["cleanupExit"]
            return value

        driver.command = driver.checked = fake
        approval_path = approval(plan, root)
        for label, native, expected in cases[:3]:
            live.update(native=native, cleanupExit=0, calls=[])
            output = root / ("driver-" + label)
            driver.run(plan, "rust-02", approval_path, output)
            result = json.loads((output / "result.json").read_text())
            assert result["taskOutcomeObserved"] is expected
            assert result["testsPassed"] is (native["exitCode"] == 0 if expected else None)
            assert result["cleanupAttempted"] and result["cleanupExitCode"] == 0
            assert result["dockerCalls"] == len(live["calls"])
            assert [r["label"] for r in live["calls"]].count("cleanup") == 1
            tests = next(r for r in live["calls"] if r["label"] == "native-tests")
            assert tests["argv"][-1] == "cd /workspace/repository; " + task["testCommand"]
            create = next(r for r in live["calls"] if r["label"] == "create")["argv"]
            assert (
                "--network=none" in create and "--read-only" in create and "--pull=never" in create
            )
            assert not any(v.startswith(("--mount", "--volume", "--privileged")) for v in create)
            downstream.append({"case": label, "result": result, "syntheticCalls": live["calls"]})
        live.update(native=good, cleanupExit=1, calls=[])
        output = root / "driver-cleanup-failed"
        driver.run(plan, "rust-02", approval_path, output)
        result = json.loads((output / "result.json").read_text())
        assert result["state"] == "cleanup-unresolved"
        downstream.append(
            {"case": "cleanup-failed", "result": result, "syntheticCalls": live["calls"]}
        )
        driver.archive_input = original_archive
    assert not actual_processes
    print(
        json.dumps(
            {
                "syntheticOnly": True,
                "inputBindings": {
                    name: hashlib.sha256((PACKET / name).read_bytes()).hexdigest()
                    for name in (
                        "driver.v4.py",
                        "oracle_v4.py",
                        "plan.v4.json",
                        "root-policy-v4.json",
                    )
                },
                "unchangedBindings": comparisons,
                "oracleCases": outcomes,
                "disabledFailFastPolicyRejected": True,
                "acceptedPreflightCases": preflights,
                "fullMockedDriverCases": downstream,
                "actualExternalProcesses": actual_processes,
                "actualDockerCalls": 0,
                "upstreamExecution": False,
                "modelCalls": 0,
                "indexConsulted": False,
                "actualTaskOutcomes": None,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
