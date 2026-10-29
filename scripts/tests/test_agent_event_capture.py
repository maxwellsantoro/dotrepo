"""Mocked optional same-tool-call capture; no daemon/upstream/provider calls."""

from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import tarfile

import pytest

BENCH = Path(__file__).resolve().parents[2] / "benchmarks/head-to-head"
sys.path.insert(0, str(BENCH))
from bench import event_capture as capture  # noqa: E402
from bench import agent_runtime as runtime  # noqa: E402
from test_agent_runtime import session as session_fixture  # noqa: E402


@pytest.fixture
def session(tmp_path):
    return session_fixture.__wrapped__(tmp_path)


PAYLOAD = b'{"owned":"raw bytes"}\n\xff\x80'
TOOL = "/usr/bin/owned-tool"


def spec(bundle):
    return {
        "helperSha256": capture.digest(Path(capture.__file__).read_bytes()),
        "path": "/workspace/go-test-events.jsonl",
        "sourceFiles": sorted(bundle.files),
        "toolPaths": {TOOL: capture.digest(b"owned tool")},
        "maxEventBytes": 4096,
        "maxMetadataBytes": 8192,
        "maxCaptureBytes": 65536,
        "maxRequests": 8,
    }


def tar_payload(value, *, kind=None, name="go-test-events.jsonl"):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w", format=tarfile.USTAR_FORMAT) as stream:
        row = tarfile.TarInfo(name)
        row.mode = 0o644
        if kind is not None:
            row.type, row.linkname = kind, "target"
        else:
            row.size = len(value)
        stream.addfile(row, io.BytesIO(value) if kind is None else None)
    return out.getvalue()


class Boundary:
    def __init__(self, spec, bundle, context, *, failure=None, clock=None):
        self.spec, self.bundle, self.context = spec, bundle, context
        self.failure, self.labels, self.executed, self.clock = failure, [], False, clock
        self.metadata_count = self.inspect_count = 0

    def call(self, argv, timeout, *, data=b"", limit, raw):
        assert raw is True and timeout > 0
        error, out, err = None, b"", b""
        if argv[0] == "inspect":
            self.inspect_count += 1
            row = {
                "Id": "a" * 64,
                "Name": "/owned-container",
                "Image": self.context["imageDigest"],
                "Config": {"User": "1000:1000", "Env": ["HOME=/workspace/.home"]},
                "HostConfig": {"ReadonlyRootfs": True, "NetworkMode": "none"},
                "Mounts": [],
                "NetworkSettings": {},
                "State": {"Running": True, "counter": self.inspect_count},
            }
            if self.failure == "context-after" and self.executed:
                row["HostConfig"]["NetworkMode"] = "bridge"
            out = json.dumps([row]).encode()
            label = "inspect-after" if self.executed else "inspect-before"
        elif argv[0] == "exec" and "xargs" in argv:
            if self.failure == "unknown-transport" and not self.executed:
                raise OSError("owned fake transport failed without raw receipt")
            values = []
            for path in data.decode().split("\x00")[:-1]:
                if path == TOOL:
                    if self.failure == "tool-generated" and not self.executed:
                        values.extend([b"absent", path.encode()])
                        continue
                    checksum = capture.digest(b"owned tool")
                    if self.failure == "tool-after" and self.executed:
                        checksum = "0" * 64
                else:
                    relative = path.removeprefix("/workspace/repository/")
                    checksum = capture.digest(self.bundle.files[relative])
                if self.failure == "source-after" and self.executed and path != TOOL:
                    checksum = "0" * 64
                values.extend([b"file", (checksum + "  " + path).encode()])
            out = b"\x00".join(values) + b"\x00"
            label = "witness-after" if self.executed else "witness-before"
        elif argv[0] == "exec" and "tar" in argv:
            out = tar_payload(PAYLOAD)
            if self.failure == "export-link":
                out = tar_payload(b"", kind=tarfile.SYMTYPE)
            if self.failure == "export-hardlink":
                out = tar_payload(b"", kind=tarfile.LNKTYPE)
            if self.failure == "export-path":
                out = tar_payload(PAYLOAD, name="../elsewhere")
            if self.failure == "cap":
                out = b"x" * (limit + 1)
            label = "export"
        else:
            script = argv[-1]
            if "printf 'present" in script:
                out = b"present\n" if self.failure == "stale" else b"absent\n"
                label = "baseline"
            else:
                self.metadata_count += 1
                checksum = capture.digest(PAYLOAD)
                if self.failure == "changed-event" and self.metadata_count == 2:
                    checksum = "0" * 64
                out = (
                    f"regular|{len(PAYLOAD)}|1|123|1|1|644\n{checksum}  {self.spec['path']}"
                ).encode() + b"\0"
                if self.failure in {"absent", "special", "symlink", "oversize"}:
                    out = (self.failure + "\n").encode()
                if self.failure == "hardlinked":
                    out = out.replace(b"|1|123|", b"|2|123|")
                label = "event-metadata"
        self.labels.append(label)
        if self.failure == "pre-deadline" and label == "baseline":
            self.clock[0] = 11
        result = {"stdout": out, "stderr": err, "exitCode": 0, "error": error}
        if self.failure == "cancelled-export" and label == "export":
            result.update(error="KeyboardInterrupt", cancelled=True)
        return result

    def execute(self, timeout):
        assert timeout > 0
        self.executed = True
        self.labels.append("chosen-command")
        if self.failure == "main-deadline":
            self.clock[0] = 11
        return {
            "stdout": "chosen output",
            "stderr": "",
            "exitCode": 1 if self.failure == "assertion-exit" else 0,
            "error": "timeout" if self.failure == "main-deadline" else None,
            "cancelled": self.failure == "cancelled",
        }


def run_capture(session, tmp_path, failure=None, *, changes=None):
    request, _, bundle = session
    config = spec(bundle)
    if changes:
        config.update(changes)
    context = {"imageDigest": request["environment"]["imageDigest"], "containerUser": "1000:1000"}
    clock = [0]
    backend = Boundary(config, bundle, context, failure=failure, clock=clock)
    observer = capture.Capture(
        config, bundle, context, tmp_path / "capture", backend.call, clock=lambda: clock[0]
    )

    def execute(timeout):
        result = backend.execute(timeout)
        observer.record["processTransportBytesComplete"] = True
        observer.record["processReceipt"] = {
            "argv": [
                "docker",
                "exec",
                "--workdir=/workspace/repository",
                "owned-container",
                "/bin/sh",
                "-c",
                "arbitrary chosen command",
            ],
            "exitCode": result["exitCode"],
            "error": result["error"],
        }
        return result

    result, record = observer.run("owned-container", "arbitrary chosen command", 10, execute)
    return result, record, backend


def test_byte_exact_export_and_same_call_order(session, tmp_path):
    result, record, backend = run_capture(session, tmp_path)
    assert result["exitCode"] == 0 and record["state"] == "captured-unqualified-event-association"
    assert (tmp_path / "capture/events.bin").read_bytes() == PAYLOAD
    assert record["event-file"]["sha256"] == capture.digest(PAYLOAD)
    assert record["requests"] == 8 and record["transportBytes"] > len(PAYLOAD)
    assert backend.labels.index("chosen-command") > backend.labels.index("baseline")
    assert backend.labels[-2:] == ["export", "event-metadata"]
    assert record["oracleQualified"] is False and record["taskOutcomeObserved"] is False
    assert record["wholeSourceTreeIntegrityEstablished"] is False
    assert (
        json.loads((tmp_path / "capture/descriptor.json").read_bytes())["event-file"]
        == record["event-file"]
    )


@pytest.mark.parametrize(
    "failure",
    [
        "stale",
        "absent",
        "special",
        "symlink",
        "oversize",
        "hardlinked",
        "export-link",
        "export-hardlink",
        "export-path",
        "source-after",
        "tool-after",
        "unknown-transport",
        "context-after",
        "changed-event",
        "cap",
        "cancelled",
    ],
)
def test_unsafe_missing_changed_or_failed_capture_never_blocks_command(session, tmp_path, failure):
    result, record, backend = run_capture(session, tmp_path, failure)
    assert backend.executed and result["stdout"] == "chosen output"
    assert record["state"] == "incomplete-unqualified-event-capture" and record["errors"]
    assert record["taskOutcomeObserved"] is False


def test_complete_capture_after_nonzero_exit_is_not_task_success(session, tmp_path):
    result, record, _ = run_capture(session, tmp_path, "assertion-exit")
    assert result["exitCode"] == 1 and record["state"] == "captured-unqualified-event-association"
    assert record["taskOutcomeObserved"] is False


@pytest.mark.parametrize("failure", ["pre-deadline", "main-deadline"])
def test_one_shared_deadline_no_fresh_export_budget(session, tmp_path, failure):
    result, record, backend = run_capture(session, tmp_path, failure)
    assert record["state"] == "incomplete-unqualified-event-capture"
    assert backend.executed is (failure == "main-deadline")
    assert "export" not in backend.labels
    if failure == "pre-deadline":
        assert result["error"] == "timeout"


@pytest.mark.parametrize("changes", [{"maxRequests": 1}, {"maxCaptureBytes": 16}])
def test_capture_instrumentation_budget_does_not_deny_chosen_command(session, tmp_path, changes):
    result, record, backend = run_capture(session, tmp_path, changes=changes)
    assert backend.executed and result["exitCode"] == 0
    assert record["state"] == "incomplete-unqualified-event-capture"
    assert record["requests"] <= changes.get("maxRequests", 8)


@pytest.mark.parametrize(
    "key,value",
    [
        ("path", "/workspace/repository/answer"),
        ("path", "/tmp/events"),
        ("sourceFiles", ["../answer"]),
        ("maxEventBytes", True),
        ("maxRequests", 17),
        ("helperSha256", "0" * 64),
    ],
)
def test_capture_frozen_config_rejects_unsafe_or_unbound_values(session, key, value):
    config = spec(session[2])
    config[key] = value
    with pytest.raises(ValueError):
        capture.validate(config)


def test_capture_config_does_not_read_gold_and_is_arm_independent(session):
    request, config, bundle = session
    config["eventCaptures"] = {request["task"]["repository"]: spec(bundle)}
    runtime.validate_runtime(config, request)
    other = deepcopy(request)
    other["arm"] = "dotrepo-access"
    runtime.validate_runtime(config, other)
    config["eventCaptures"]["unknown/repo"] = spec(bundle)
    with pytest.raises(ValueError, match="frozen repositories"):
        runtime.validate_runtime(config, request)


@pytest.mark.parametrize("failure", [None, "stale", "unknown-transport", "cancelled-export"])
def test_session_host_only_capture_receipt_accounting_and_cleanup(session, tmp_path, failure):
    from test_agent_runtime import FakeProvider, response

    request, config, bundle = session
    config["eventCaptures"] = {request["task"]["repository"]: spec(bundle)}

    class Docker(runtime.DockerBackend):
        simulation = True

        def __init__(self):
            super().__init__(self.invoke_fixture)
            self.cleaned = False

        def provision(self, request, config, timeout):
            context = {
                "imageDigest": request["environment"]["imageDigest"],
                "containerUser": "1000:1000",
            }
            self.boundary = Boundary(spec(bundle), bundle, context, failure=failure)
            self.boundary_container = self.name
            return {"fixture": "no daemon"}

        def checkout(self, bundle, timeout):
            return {"exitCode": 0, "error": None}

        def cleanup(self):
            self.cleaned = True
            return {"exitCode": 0, "error": None}

        def invoke_fixture(self, argv, *, data, timeout, output_limit, raw=False):
            assert raw and argv[0] == "docker"
            if "--workdir=/workspace/repository" in argv:
                self.boundary.executed = True
                return {"stdout": b"\xffchosen raw", "stderr": b"", "exitCode": 0, "error": None}
            actual_name = self.name
            argv = ["owned-container" if part == actual_name else part for part in argv[1:]]
            result = self.boundary.call(argv, timeout, data=data, limit=output_limit, raw=True)
            if argv[0] == "inspect":
                result["stdout"] = result["stdout"].replace(
                    b"/owned-container", ("/" + actual_name).encode()
                )
            return result

    backend = Docker()
    provider = FakeProvider(
        response(("checkout_source", {})),
        response(("shell", {"command": "arbitrary-not-gold-command"})),
        response(text="done"),
    )
    result = runtime.run_session(
        request, config, bundle, "system", "task", None, provider, backend, tmp_path / "run"
    )
    assert backend.cleaned
    assert result["status"] == (
        "budget-exhausted" if failure == "cancelled-export" else "agent-finished"
    )
    accounting = result["eventCaptureAccounting"]
    if failure == "unknown-transport":
        assert accounting["requests"] == 2 and accounting["transportBytes"] is None
        assert result["effort"]["decodedBytes"] is None
    else:
        assert accounting["requests"] == (7 if failure == "cancelled-export" else 8)
        assert accounting["transportBytes"] > len(PAYLOAD)
        assert result["effort"]["decodedBytes"] >= accounting["transportBytes"] + len(
            b"\xffchosen raw"
        )
    trace = json.loads((tmp_path / "run/trace.json").read_bytes())
    descriptor = next(
        event["descriptor"] for event in trace["events"] if event["kind"] == "event-capture"
    )
    assert descriptor["command"] == "arbitrary-not-gold-command"
    assert descriptor["context"]["requestSha256"] == trace["requestSha256"]
    assert descriptor["state"] == (
        "incomplete-unqualified-event-capture"
        if failure is not None
        else "captured-unqualified-event-association"
    )
    process = tmp_path / "run/event-captures/0001/process-stdout.bin"
    assert process.read_bytes() == b"\xffchosen raw"
    assert descriptor["processReceipt"]["stdout"]["sha256"] == capture.digest(process.read_bytes())
    assert descriptor["processReceipt"]["argv"][-1] == descriptor["command"]
    response_row = next(
        event
        for event in trace["events"]
        if event["kind"] == "tool-response" and event["result"].get("stdout")
    )
    assert "descriptorPath" not in json.dumps(response_row["result"])
    assert "event-file" not in json.dumps(response_row["result"])
    assert response_row["result"]["stdout"] == "\ufffdchosen raw"
    assert result["correctCompletion"] is None and result["scoringPerformed"] is False


@pytest.mark.parametrize(
    "wire", [tar_payload(PAYLOAD) + b"trailing", tar_payload(PAYLOAD) + tar_payload(PAYLOAD)]
)
def test_ambiguous_event_archive_rejected(wire):
    with pytest.raises(ValueError):
        capture.event_bytes(wire, "/workspace/go-test-events.jsonl", 4096)


def test_source_owned_generated_tool_is_observed_not_implicitly_qualified(session, tmp_path):
    result, record, _ = run_capture(
        session, tmp_path, "tool-generated", changes={"toolPaths": {TOOL: None}}
    )
    assert result["exitCode"] == 0 and record["state"] == "captured-unqualified-event-association"
    assert record["witness-before"][TOOL] == {"kind": "absent", "sha256": None}
    assert record["witness-after"][TOOL]["sha256"] == capture.digest(b"owned tool")
    assert record["oracleQualified"] is False and record["taskOutcomeObserved"] is False
