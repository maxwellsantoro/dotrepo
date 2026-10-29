"""Synthetic regression controls for accepted preflight and Cargo phase failures."""

import json
from pathlib import Path
import tempfile

from oracle_v5 import rust_default_outcome

HERE = Path(__file__).resolve().parent


def approval(driver, plan, root):
    audits = {}
    for task in plan["tasks"]:
        receipt = {
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
        raw = json.dumps(receipt).encode()
        path = root / (task + "-synthetic-audit.json")
        path.write_bytes(raw)
        audits[task] = {"path": str(path), "sha256": driver.sha(raw)}
    path = root / "synthetic-acceptance.json"
    path.write_text(
        json.dumps(
            {
                "syntheticOnly": True,
                "state": "accepted-for-three-scope-offline-requalification",
                "planSha256": driver.file_sha(HERE / "plan.v5.json"),
                "imageId": plan["imageId"],
                "cacheAudits": audits,
            }
        )
    )
    return path


def amendment_controls(driver, plan):
    task = plan["tasks"]["rust-02"]
    historical_stdout = (HERE / "source-bindings-v4/historical-rust-stdout.txt").read_text()
    historical_stderr = (HERE / "source-bindings-v4/historical-rust-stderr.txt").read_text()
    good = {"stdout": historical_stdout, "stderr": historical_stderr, "exitCode": 0, "error": None}
    policy = task["rustDefaultPolicy"]
    passing = rust_default_outcome(good, task["expectedTests"], policy)
    assert (
        passing["qualified"]
        and passing["phaseCoverageComplete"]
        and passing["docPhase"]["testCases"] == 0
    )
    names = task["expectedTests"]
    unit_only = (
        "".join("test link_type::tests::" + name + " ... ok\n" for name in names)
        + "test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s\n"
    )
    marker = "     Running unittests src/lib.rs (/synthetic/parser)\n"
    late_compile = {
        "stdout": unit_only,
        "stderr": marker
        + "   Doc-tests sniffnet_packet_parser\nerror: doctest failed, to rerun pass --doc\nCaused by: rustdoc compile failed\n",
        "exitCode": 101,
        "error": None,
    }
    unit_failure = {
        "stdout": unit_only.replace(names[0] + " ... ok", names[0] + " ... FAILED").replace(
            "test result: ok. 2 passed; 0 failed", "test result: FAILED. 1 passed; 1 failed"
        ),
        "stderr": marker + "error: test failed, to rerun pass `--lib`\n",
        "exitCode": 101,
        "error": None,
    }
    assertion_outcome = rust_default_outcome(unit_failure, names, policy)
    assert assertion_outcome["qualified"] and not assertion_outcome["phaseCoverageComplete"]
    assert assertion_outcome["docPhase"] == {
        "state": "unexecuted-default-stop",
        "exercised": False,
        "terminal": False,
        "testCases": None,
    }
    negatives = {
        "wrong-prefixed-unit-case-id": {
            **good,
            "stdout": good["stdout"].replace(
                "link_type::tests::" + names[0], "link_type::tests::unrelated_" + names[0]
            ),
        },
        "wrong-module-same-basename": {
            **good,
            "stdout": good["stdout"].replace(
                "link_type::tests::" + names[0], "unrelated::tests::" + names[0]
            ),
        },
        "duplicate-unit-case-id": {
            **good,
            "stdout": good["stdout"].replace(
                "link_type::tests::" + names[1], "link_type::tests::" + names[0]
            ),
        },
        "unit-pass-later-doc-compile-failure": late_compile,
        "all-pass-but-exit101": {**good, "exitCode": 101},
        "unit-pass-missing-doc-phase": {
            "stdout": unit_only,
            "stderr": marker,
            "exitCode": 0,
            "error": None,
        },
        "doc-marker-without-terminal-summary": {
            "stdout": unit_only,
            "stderr": marker + "   Doc-tests sniffnet_packet_parser\n",
            "exitCode": 0,
            "error": None,
        },
        "native-timeout": {**good, "error": "timeout"},
        "assertion-failure-summary-with-all-cases-ok": {
            **unit_failure,
            "stdout": unit_failure["stdout"].replace(" ... FAILED", " ... ok"),
        },
        "assertion-failure-plus-compiler-error": {
            **unit_failure,
            "stderr": unit_failure["stderr"] + "error[E0308]: mismatched types\n",
        },
        "unknown-unit-failure-diagnostic": {
            **unit_failure,
            "stderr": marker + "error: unknown failure\n",
        },
    }
    for label, native in negatives.items():
        assert not rust_default_outcome(native, names, policy)["qualified"], label
    assert not rust_default_outcome(
        unit_failure, names, {"unitAssertionFailureStopsDefault": False}
    )["qualified"]
    original_archive, original_checked, original_command = (
        driver.archive_input,
        driver.checked,
        driver.command,
    )
    actual_calls = []

    def forbidden(*args, **kwargs):
        actual_calls.append("forbidden")
        raise AssertionError("real Docker/subprocess forbidden")

    try:
        driver.checked = driver.command = forbidden
        with tempfile.TemporaryDirectory(
            prefix="dotrepo-f05-offline-requalification-v4-controls-", dir="/tmp"
        ) as directory:
            root = Path(directory)
            acceptance = approval(driver, plan, root)

            def fail_preflight(*args, **kwargs):
                raise ValueError("synthetic archive hash mismatch")

            driver.archive_input = fail_preflight
            output = root / "accepted-preflight-failure"
            try:
                driver.run(plan, "rust-02", acceptance, output)
            except ValueError as error:
                assert str(error) == "synthetic archive hash mismatch"
            else:
                raise AssertionError("accepted preflight should fail")
            result = json.loads((output / "result.json").read_text())
            assert (output / "attempt.json").exists() and (
                output / "acceptance-binding.json"
            ).exists()
            assert (
                result["failureStage"] == "accepted-source-preflight"
                and result["error"] == "synthetic archive hash mismatch"
            )
            assert (
                result["preflightSeconds"] >= 0
                and result["elapsedSeconds"] >= result["preflightSeconds"]
            )
            assert result["costUsd"] is None and result["testsPassed"] is None
            assert (
                result["dockerCalls"] == 0
                and result["cleanupAttempted"] is False
                and not actual_calls
            )
            retained_failure = result
            placeholder = root / "synthetic-placeholder.tar"
            placeholder.write_bytes(b"synthetic placeholder only")
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
                    "Env": [key + "=" + value for key, value in plan["environment"].items()],
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
            simulated = []

            def fake(folder, label, argv, **kwargs):
                simulated.append(label)
                value = {"exitCode": 0, "error": None, "stdout": "", "stderr": ""}
                if label == "image-inspect":
                    value["stdout"] = json.dumps([image])
                elif label == "container-inspect":
                    value["stdout"] = json.dumps([container])
                elif label == "native-tests":
                    value.update(current_native)
                return value

            driver.command = driver.checked = fake
            downstream = []
            for label, current_native, expected in [
                ("late-doc-compile", late_compile, False),
                ("terminal-unit-assertion", unit_failure, True),
            ]:
                output = root / label
                driver.run(plan, "rust-02", acceptance, output)
                observed = json.loads((output / "result.json").read_text())
                assert observed["taskOutcomeObserved"] is expected
                assert observed["testsPassed"] is (False if expected else None)
                assert observed["oracle"]["docPhase"]["exercised"] is False
                downstream.append({"case": label, "syntheticResult": observed})
    finally:
        driver.archive_input, driver.checked, driver.command = (
            original_archive,
            original_checked,
            original_command,
        )
    return {
        "state": "passed",
        "syntheticOnly": True,
        "historicalSuccessRecognized": True,
        "phaseNegativeControls": list(negatives),
        "policyDisabledRejectsDefaultStop": True,
        "acceptedPreflightFailureRetained": retained_failure,
        "fullMockedDriver": downstream,
        "actualDockerCalls": len(actual_calls),
        "actualUpstreamExecution": False,
        "actualTaskOutcomes": None,
    }
