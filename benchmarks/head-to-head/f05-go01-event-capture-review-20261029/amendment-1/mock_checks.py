"""Independent mutations of the frozen owned fake boundary; no Docker calls."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "scripts/tests"))
sys.path.insert(0, str(ROOT / "benchmarks/head-to-head"))


def main():
    files = {
        "benchmarks/head-to-head/bench/agent_runtime.py": "dc585e08f24e1a20da9d9ccdafac4af3f4e10cb8451de7ca3a74c05ecc985fa0",
        "benchmarks/head-to-head/bench/event_capture.py": "ffe5b5e27aaca28bceae83aac15bfeb5e83963eef63a3b2f41c97833787b4a12",
        "scripts/tests/test_agent_event_capture.py": "ff5393313566aba40a7a883ea99b1640889af43e67d0b26b3fac54753af49756",
    }
    for name, digest in files.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    from bench import event_capture as capture
    import test_agent_event_capture as owned

    bundle = SimpleNamespace(files={"README.md": b"owned local source fixture"})
    context = {"imageDigest": "sha256:" + "f" * 64, "containerUser": "1000:1000"}
    checks = []
    with tempfile.TemporaryDirectory(
        prefix="dotrepo-capture-mock-review-", dir="/tmp"
    ) as directory:
        for case in [
            "positive",
            "changed-container-id",
            "changed-env",
            "source-link",
            "nonbyte-transport",
            "process-receipt-mismatch",
            "before-cancellation",
            "after-cancellation",
            "generated-tool-observation",
        ]:
            spec = owned.spec(bundle)
            if case == "generated-tool-observation":
                spec["toolPaths"][owned.TOOL] = None

            class Boundary(owned.Boundary):
                def call(self, argv, timeout, **kwargs):
                    if case == "after-cancellation" and self.executed and "xargs" in argv:
                        raise KeyboardInterrupt("owned synthetic cancellation")
                    value = super().call(argv, timeout, **kwargs)
                    if case == "before-cancellation" and not self.executed and argv[0] == "inspect":
                        value["cancelled"] = True
                    if (
                        case in ["changed-container-id", "changed-env"]
                        and self.executed
                        and argv[0] == "inspect"
                    ):
                        rows = json.loads(value["stdout"])
                        if case == "changed-container-id":
                            rows[0]["Id"] = "b" * 64
                        else:
                            rows[0]["Config"]["Env"] = ["HOME=/changed"]
                        value["stdout"] = json.dumps(rows).encode()
                    if "xargs" in argv:
                        if case == "nonbyte-transport":
                            value["stdout"] = "wrongly decoded fixture"
                        if case == "source-link":
                            parts = value["stdout"].split(b"\0")
                            for i in range(0, len(parts) - 1, 2):
                                if b"/workspace/repository/" in parts[i + 1]:
                                    parts[i] = b"link"
                            value["stdout"] = b"\0".join(parts)
                    return value

            backend = Boundary(
                spec,
                bundle,
                context,
                failure="tool-generated" if case == "generated-tool-observation" else None,
            )
            observer = capture.Capture(spec, bundle, context, Path(directory) / case, backend.call)
            command = "arbitrary chosen command"

            def execute(remaining):
                result = backend.execute(remaining)
                observer.record["processTransportBytesComplete"] = True
                observer.record["processTransportBytes"] = len(result["stdout"].encode())
                observer.record["processReceipt"] = {
                    "argv": [
                        "docker",
                        "exec",
                        "--workdir=/workspace/repository",
                        "owned-container",
                        "/bin/sh",
                        "-c",
                        command + (" mismatch" if case == "process-receipt-mismatch" else ""),
                    ],
                    "exitCode": result["exitCode"],
                    "error": result["error"],
                }
                return result

            result, record = observer.run("owned-container", command, 10, execute)
            assert record["oracleQualified"] is False and record["taskOutcomeObserved"] is False
            assert record["wholeSourceTreeIntegrityEstablished"] is False
            expected_complete = case in ["positive", "generated-tool-observation"]
            assert (
                record["state"] == "captured-unqualified-event-association"
            ) is expected_complete, (case, record)
            assert backend.executed is (case != "before-cancellation")
            if case in ["before-cancellation", "after-cancellation"]:
                assert result["cancelled"] is True
            elif backend.executed:
                assert result["stdout"] == "chosen output" and result["exitCode"] == 0
            if case in ["nonbyte-transport", "after-cancellation"]:
                assert record["transportBytesComplete"] is False
            if case == "generated-tool-observation":
                assert record["witness-before"][owned.TOOL]["kind"] == "absent"
                assert record["witness-after"][owned.TOOL]["kind"] == "file"
                assert "post-run" in record["limitation"]
            if expected_complete:
                assert (Path(directory) / case / "events.bin").read_bytes() == owned.PAYLOAD
                assert backend.labels.index("chosen-command") > backend.labels.index("baseline")
            checks.append(
                {
                    "case": case,
                    "state": record["state"],
                    "executed": backend.executed,
                    "cancelled": result.get("cancelled", False),
                    "passed": True,
                }
            )
    with (HERE / "mock-checks.json").open("x") as stream:
        json.dump(
            {
                "state": "independent-owned-fake-capture-controls-passed",
                "cases": checks,
                "newDockerGoNodeUpstreamNetworkProviderActions": 0,
            },
            stream,
            indent=2,
            sort_keys=True,
        )
        stream.write("\n")
    print(json.dumps({"passed": len(checks), "actualContainerCalls": 0}))


if __name__ == "__main__":
    main()
