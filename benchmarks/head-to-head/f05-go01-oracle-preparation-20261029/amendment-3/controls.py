"""Owned mocked capture→post-run controls. No process/daemon/upstream calls."""

import argparse
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
from types import SimpleNamespace

import adapter

sys.dont_write_bytecode = True
sys.path.insert(0, str(adapter.ROOT / "benchmarks/head-to-head"))
from bench import agent_runtime as runtime  # noqa: E402
from bench import event_capture as helper  # noqa: E402

ORACLE, _ = adapter.owners()
sys.modules["oracle"] = ORACLE
FIXTURES = adapter.module(
    "am2_fixture",
    adapter.AM2 / "controls.py",
    "921f59eda2fbceb3c633dc69c89179ac2e39317cf2caa9b0e03e5d496378d4a5",
)


def raw_events(rows):
    return "".join(json.dumps(row) + "\n" for row in rows).encode()


def fixture(root, data=None):
    """Real reviewed host capture code, with every transport invocation mocked."""
    data = deepcopy(FIXTURES.fixture()) if data is None else deepcopy(data)
    payload = raw_events(data[0])
    source = (
        adapter.ROOT
        / "benchmarks/head-to-head/f05-go01-requalification-proposal-20261029/sources/Herebyfile.mjs"
    )
    bundle = SimpleNamespace(files={"Herebyfile.mjs": source.read_bytes()})
    tool = "/workspace/repository/tools/gotestsum"
    spec = {
        "helperSha256": adapter.HELPER_SHA,
        "path": "/workspace/go-test-events.jsonl",
        "sourceFiles": ["Herebyfile.mjs"],
        "toolPaths": {tool: None},
        "maxEventBytes": 16 * 1024**2,
        "maxMetadataBytes": 2 * 1024**2,
        "maxCaptureBytes": 32 * 1024**2,
        "maxRequests": 8,
    }
    resources = {
        "cpus": 3,
        "memoryBytes": 4294967296,
        "pidsLimit": 256,
        "workspaceBytes": 8589934592,
        "tmpBytes": 536870912,
    }
    config = {
        "runnerSha256": adapter.RUNTIME_SHA,
        "environment": {"HOME": "/workspace/.home"},
        "resources": resources,
        "containerUser": "1000:1000",
        "maxToolOutputBytes": 2097152,
        "eventCaptures": {"github.com/microsoft/typescript": spec},
    }
    request = {
        "sessionId": "owned-synthetic-session",
        "task": {"repository": "github.com/microsoft/typescript", "revision": ORACLE.REVISION},
        "environment": {
            "imageDigest": "sha256:b47cd4a5061d271780bab25aa2637c2623dc675bd43380fc80cb65ec44e50092"
        },
        "artifacts": {"runtime": {"sha256": adapter.sha(adapter.encode(config))}},
        "cacheState": "warm",
        "budgets": {"wallTimeSeconds": 60},
    }
    request_raw, config_raw = adapter.encode(request), adapter.encode(config)
    context = {
        "sessionId": request["sessionId"],
        "requestSha256": adapter.sha(request_raw),
        "repository": request["task"]["repository"],
        "revision": ORACLE.REVISION,
        "imageDigest": request["environment"]["imageDigest"],
        "sourceArchiveSha256": ORACLE.SOURCE,
        "sourceInventorySha256": "7" * 64,
        "sourceProvenanceSha256": "8" * 64,
        "runtimeArtifactSha256": request["artifacts"]["runtime"]["sha256"],
        "runtimeConfigurationSha256": adapter.sha(config_raw),
        "runnerSha256": adapter.RUNTIME_SHA,
        "environment": config["environment"],
        "resources": resources,
        "containerUser": config["containerUser"],
        "cacheState": "warm",
        "cachePreparationSha256": "9" * 64,
        "cacheArchiveSha256": "a" * 64,
    }
    host = {
        "ReadonlyRootfs": True,
        "NetworkMode": "none",
        "Memory": resources["memoryBytes"],
        "MemorySwap": resources["memoryBytes"],
        "NanoCpus": 3000000000,
        "PidsLimit": 256,
        "CapDrop": ["ALL"],
        "SecurityOpt": ["no-new-privileges"],
        "IpcMode": "private",
        "PidMode": "",
        "CgroupnsMode": "private",
        "Tmpfs": {
            path: f"rw,exec,nosuid,nodev,size={size},uid=1000,gid=1000,mode=0700"
            for path, size in [
                ("/workspace", resources["workspaceBytes"]),
                ("/tmp", resources["tmpBytes"]),
            ]
        },
    }
    state = {"process": False}

    def invoke(argv, *, data=b"", timeout, output_limit, raw=False):
        assert raw is True and timeout > 0
        args = argv[1:]
        if args[0] == "inspect":
            out = json.dumps(
                [
                    {
                        "Id": "b" * 64,
                        "Name": "/" + backend.name,
                        "Image": context["imageDigest"],
                        "Mounts": [],
                        "HostConfig": host,
                        "Config": {"User": "1000:1000", "Env": ["HOME=/workspace/.home"]},
                        "NetworkSettings": {},
                        "State": {"Running": True},
                    }
                ]
            ).encode()
        elif "xargs" in args:
            values = []
            for path in data.decode().split("\0")[:-1]:
                checksum = (
                    adapter.sha(b"owned source-generated tool")
                    if path == tool
                    else adapter.sha(bundle.files[path.removeprefix("/workspace/repository/")])
                )
                values += [b"file", (checksum + "  " + path).encode()]
            out = b"\0".join(values) + b"\0"
        elif "--workdir=/workspace/repository" in args:
            state["process"] = True
            return {
                "stdout": b"owned wrapper stdout\n",
                "stderr": b"",
                "exitCode": data_case[3]["exitCode"],
                "error": None,
            }
        elif "tar" in args:
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive:
                member = tarfile.TarInfo("go-test-events.jsonl")
                member.size, member.mode = len(payload), 0o644
                archive.addfile(member, io.BytesIO(payload))
            out = stream.getvalue()
        elif "printf 'present" in args[-1]:
            out = b"absent\n"
        else:
            out = (
                f"regular|{len(payload)}|1|123|1|1|644\n{adapter.sha(payload)}  {spec['path']}".encode()
                + b"\0"
            )
        assert len(out) <= output_limit
        return {"stdout": out, "stderr": b"", "exitCode": 0, "error": None}

    data_case = data
    backend = runtime.DockerBackend(invoke=invoke)
    backend.event_capture = (spec, bundle, root, context)
    backend.capture_number = 0
    result, descriptor = backend.shell_with_capture(ORACLE.COMMAND, 60, 2097152, "owned-call")
    assert state["process"] and descriptor["state"] == "captured-unqualified-event-association"
    trace = {
        "sessionId": request["sessionId"],
        "requestSha256": adapter.sha(request_raw),
        "events": [
            {
                "index": 1,
                "kind": "tool-request",
                "name": "shell",
                "arguments": {"command": ORACLE.COMMAND},
                "id": "owned-call",
            },
            {"index": 2, "kind": "event-capture", "descriptor": descriptor},
            {"index": 3, "kind": "tool-response", "id": "owned-call", "result": result},
        ],
    }
    return {
        "root": root,
        "relative": "event-captures/0001/descriptor.json",
        "request": request_raw,
        "config": config_raw,
        "trace": adapter.encode(trace),
        "data": data_case,
    }


def score(case, *, synthetic=True):
    return adapter.evaluate(
        case["root"],
        case["relative"],
        case["request"],
        case["config"],
        case["trace"],
        *case["data"][1:],
        synthetic=synthetic,
    )


def mutate_descriptor(case, mutate):
    path = case["root"] / case["relative"]
    value = adapter.load(path.read_bytes())
    mutate(value)
    path.write_bytes(helper.encode(value))
    trace = adapter.load(case["trace"], 64 * 1024**2)
    trace["events"][1]["descriptor"] = {
        **value,
        "descriptorPath": case["relative"],
        "descriptorSha256": adapter.sha(path.read_bytes()),
    }
    case["trace"] = adapter.encode(trace)


def empty_events():
    data = FIXTURES.fixture()
    data[0][:] = [{"Package": next(iter(data[1]["packages"])), "Action": "start"}]
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = []

    def check(name, mutation=None, *, data=None, actual=False, complete=False, association=False):
        with tempfile.TemporaryDirectory(prefix="dotrepo-go01-am3-control-") as directory:
            case = fixture(Path(directory), data)
            if mutation:
                mutation(case)
            result = score(case, synthetic=not actual)
            assert result["candidateOutcomeObserved"] is complete, (name, result)
            if association:
                assert result["captureAssociationValidated"], (name, result)
            elif not complete:
                assert not result["captureAssociationValidated"], (name, result)
            assert not any(
                result[key]
                for key in [
                    "taskOutcomeObserved",
                    "oracleQualified",
                    "campaignAdmitted",
                    "nativeCollectionOccurred",
                ]
            ), (name, result)
            results.append({"name": name, "result": result})

    check("full5972synthetic-pass", complete=True, association=True)
    failed = FIXTURES.fixture()
    FIXTURES.assertion(failed)
    check("full-terminal-assertion-failure", data=failed, complete=True, association=True)
    check("actual-mode-refuses-even-complete-consistent-capture", actual=True, association=True)
    check(
        "caller-true-flags-cannot-close-actual-gaps",
        lambda c: c["data"][3].update(
            setupComplete=True, toolBuildComplete=True, effectiveChildSelection=True
        ),
        actual=True,
        association=True,
    )
    for name, change in [
        ("zeroed-unmetered-cost", lambda d: d.update(costUsd=0)),
        ("boolean-byte-count", lambda d: d["processReceipt"]["stderr"].update(bytes=False)),
        ("wrong-command", lambda d: d.update(command="go test ./...")),
        ("stale-baseline", lambda d: d.update(**{"event-baseline": "present\n"})),
        ("missing-operation", lambda d: d["operations"].pop()),
        ("changed-operation-command", lambda d: d["operations"][6]["argv"].append("elsewhere")),
        ("request-accounting", lambda d: d.update(requests=7)),
        ("unknown-byte-accounting", lambda d: d.update(transportBytesComplete=False)),
        ("process-byte-accounting", lambda d: d.update(processTransportBytes=0)),
        ("export-after-deadline", lambda d: d["operations"][-1].update(remainingSeconds=0)),
        (
            "export-time-before-process",
            lambda d: d["operations"][-1].update(startedAt=d["startedAt"]),
        ),
        ("timeout", lambda d: d["processReceipt"].update(error="timeout")),
        ("signal-kill", lambda d: d["processReceipt"].update(exitCode=137)),
        ("raw-receipt-missing", lambda d: d.pop("processReceipt")),
        (
            "source-subset-lie",
            lambda d: d["observedSourceSubset"].update(
                {"/workspace/repository/Herebyfile.mjs": "0" * 64}
            ),
        ),
        ("toolcall-mismatch", lambda d: d["context"].update(toolCallId="other-call")),
        (
            "base-env-not-child-context",
            lambda d: d["context"].update(environment={"GOOS": "linux"}),
        ),
        ("metadata-mismatch", lambda d: d["event-after-export"].update(sha256="0" * 64)),
        ("cancelled-process", lambda d: d["processResult"].update(cancelled=True)),
        (
            "source-whole-tree-overclaim",
            lambda d: d.update(wholeSourceTreeIntegrityEstablished=True),
        ),
        ("unknown-revision", lambda d: d["context"].update(revision=None)),
        ("too-much-time", lambda d: d.update(elapsedSeconds=61)),
    ]:
        check(name, lambda c, change=change: mutate_descriptor(c, change))
    check(
        "raw-event-file-edited",
        lambda c: (c["root"] / "event-captures/0001/events.bin").write_bytes(b"{}\n"),
    )
    check(
        "raw-process-file-edited",
        lambda c: (c["root"] / "event-captures/0001/process-stdout.bin").write_bytes(b"edited"),
    )
    check(
        "raw-export-file-edited",
        lambda c: (c["root"] / "event-captures/0001/export/stdout.bin").write_bytes(b"not tar"),
    )
    check(
        "symlink-host-event",
        lambda c: (
            (c["root"] / "event-captures/0001/events.bin").unlink(),
            (c["root"] / "event-captures/0001/events.bin").symlink_to("process-stdout.bin"),
        ),
    )
    check("traversal-path", lambda c: c.update(relative="../descriptor.json"))
    check(
        "trace-missing",
        lambda c: c.update(
            trace=adapter.encode(
                {
                    "sessionId": "owned-synthetic-session",
                    "requestSha256": adapter.sha(c["request"]),
                    "events": [],
                }
            )
        ),
    )
    check(
        "config-artifact-reserialization-refused",
        lambda c: c.update(config=c["config"] + b" "),
    )
    check(
        "semantic-config-mutation",
        lambda c: c.update(config=c["config"].replace(b"2097152", b"2097153")),
    )
    check(
        "metadata-special-file",
        lambda c: mutate_descriptor(c, lambda d: d["event-before-export"].update(kind="special")),
    )
    check(
        "cap-not-observed-complete",
        lambda c: mutate_descriptor(c, lambda d: d["operations"][6].update(error="output-limit")),
    )
    check(
        "capture-errors-after-failed-shell",
        lambda c: mutate_descriptor(
            c, lambda d: d["errors"].append({"stage": "export-association", "reason": "absent"})
        ),
    )
    check("empty-native-style-events-do-not-satisfy-map", data=empty_events(), association=True)
    for raw in (b'{"x":NaN}', b'{"x":1,"x":2}'):
        try:
            adapter.load(raw)
        except ValueError:
            results.append({"name": "strict-json-refusal", "refused": True})
        else:
            raise AssertionError("malformed JSON accepted")
    report = {
        "state": "owned-synthetic-controls-passed",
        "controls": results,
        "count": len(results),
        "nativeActions": 0,
        "providerCalls": 0,
        "actualAdmission": False,
    }
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"count": len(results), "allPassed": True}))


if __name__ == "__main__":
    main()
