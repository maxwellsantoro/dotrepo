"""Synthetic failure/score controls; prohibit every daemon/helper command."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
PACKET = HERE.parent / "f05-offline-requalification-20261029"
sys.path.insert(0, str(PACKET))
spec = importlib.util.spec_from_file_location("independent_offline_v3", PACKET / "driver.v3.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def main():
    plan = json.loads((PACKET / "plan.v3.json").read_bytes())
    attempted = []

    def forbidden(*args, **kwargs):
        attempted.append("forbidden-daemon")
        raise AssertionError("No daemon calls authorized")

    driver.command = driver.checked = forbidden
    findings = []
    with tempfile.TemporaryDirectory(
        prefix="dotrepo-f05-offline-requalification-review-", dir="/tmp"
    ) as d:
        root = Path(d)
        approvals = {}
        for task in plan["tasks"]:
            row = {
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
            raw = json.dumps(row).encode()
            path = root / (task + "-synthetic-audit.json")
            path.write_bytes(raw)
            approvals[task] = {"path": str(path), "sha256": driver.sha(raw)}
        acceptance = {
            "state": "accepted-for-three-scope-offline-requalification",
            "planSha256": driver.file_sha(PACKET / "plan.v3.json"),
            "imageId": plan["imageId"],
            "cacheAudits": approvals,
        }
        approval_path = root / "synthetic-acceptance.json"
        approval_path.write_text(json.dumps(acceptance))

        def fail_preflight(*args, **kwargs):
            raise ValueError("synthetic archive hash mismatch")

        driver.archive_input = fail_preflight
        output = root / "preflight-failure"
        try:
            driver.run(plan, "rust-02", approval_path, output)
        except ValueError as error:
            assert str(error) == "synthetic archive hash mismatch"
        else:
            raise AssertionError("preflight failure not raised")
        assert not output.exists() and not attempted
        findings.append(
            {
                "case": "accepted-preflight-archive-error",
                "resultDirectoryCreated": output.exists(),
                "resultJsonRetained": (output / "result.json").exists(),
                "dockerCalls": len(attempted),
                "finding": "Input validation failure happens before output/result/try-finally creation; preflight time and failure reason are not retained by driver.",
            }
        )
    rust = plan["tasks"]["rust-02"]
    native = (
        "".join("test link_type::tests::" + name + " ... ok\n" for name in rust["expectedTests"])
        + "\ntest result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s\n"
    )
    score = driver.score(rust, native, "", {})
    assert score["qualified"]
    findings.append(
        {
            "case": "rust-unit-terminal-before-default-doc-stage-failure",
            "stdout": native,
            "nativeExitCode": 101,
            "nativeError": None,
            "stderrClassification": "rustdoc compile/setup failure after unit summary, no terminal doc-stage report",
            "oracle": score,
            "driverTaskOutcomeObserved": score["qualified"],
            "finding": "Rust oracle accepts first expected-unit summary without requiring remaining cargo test phases terminal; stderr/phase failure is not scored.",
        }
    )
    # Exercise the complete downstream driver classification with owned input
    # placeholders and fake Docker responses; no external command is called.
    with tempfile.TemporaryDirectory(
        prefix="dotrepo-f05-offline-requalification-review-", dir="/tmp"
    ) as directory:
        root = Path(directory)
        archive = root / "synthetic-placeholder.tar"
        archive.write_bytes(b"synthetic source/cache placeholder")
        driver.archive_input = lambda *args, **kwargs: (archive, {}, 0)
        image = {
            "Id": plan["imageId"],
            "Os": "linux",
            "Architecture": "arm64",
            "Config": {"Env": []},
        }
        env = [key + "=" + value for key, value in plan["environment"].items()]
        container = {
            "Image": plan["imageId"],
            "Mounts": [],
            "Config": {"User": "1000:1000", "Env": env},
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

        def mocked(folder, label, argv, **kwargs):
            value = {"exitCode": 0, "error": None, "stdout": "", "stderr": ""}
            if label == "image-inspect":
                value["stdout"] = json.dumps([image])
            elif label == "container-inspect":
                value["stdout"] = json.dumps([container])
            elif label == "native-tests":
                value.update(
                    exitCode=101,
                    stdout=native,
                    stderr="error: doctest failed, to rerun pass --doc\nCaused by: rustdoc compile failed\n",
                )
            return value

        driver.command = driver.checked = mocked
        approvals = {}
        for task in plan["tasks"]:
            row = {
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
            raw = json.dumps(row).encode()
            path = root / (task + "-synthetic-audit.json")
            path.write_bytes(raw)
            approvals[task] = {"path": str(path), "sha256": driver.sha(raw)}
        acceptance = {
            "state": "accepted-for-three-scope-offline-requalification",
            "planSha256": driver.file_sha(PACKET / "plan.v3.json"),
            "imageId": plan["imageId"],
            "cacheAudits": approvals,
        }
        path = root / "synthetic-acceptance.json"
        path.write_text(json.dumps(acceptance))
        output = root / "post-unit-doc-stage-failure"
        driver.run(plan, "rust-02", path, output)
        observed = json.loads((output / "result.json").read_bytes())
        assert observed["taskOutcomeObserved"] is True and observed["testsPassed"] is False
        assert observed["state"] == "offline-outcome-observed-pending-independent-review"
        findings.append(
            {
                "case": "full-mocked-driver-post-unit-doc-failure",
                "result": observed,
                "allDockerResponsesSynthetic": True,
                "finding": "Actual run() state classifies post-unit rustdoc compile failure as complete observed task outcome.",
            }
        )
    print(
        json.dumps(
            {
                "driverSha256": driver.file_sha(PACKET / "driver.v3.py"),
                "syntheticOnly": True,
                "findings": findings,
                "dockerCalls": len(attempted),
                "upstreamSourceBytesRead": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
