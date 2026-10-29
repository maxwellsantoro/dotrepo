"""Post-run Go01 capture consistency adapter. No launcher or actual admission.

Actual evaluation stays closed: this descriptor has no normal setup, source-owned
producer-build or effective child Go-selection observations. Synthetic evaluation
reuses the unchanged amendment-2 scorer after validating the real capture shape.
"""

from datetime import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import tarfile
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
AM2 = HERE.parent / "amendment-2"
RUNTIME_SHA = "dc585e08f24e1a20da9d9ccdafac4af3f4e10cb8451de7ca3a74c05ecc985fa0"
HELPER_SHA = "ffe5b5e27aaca28bceae83aac15bfeb5e83963eef63a3b2f41c97833787b4a12"
MAP_SHA = "768482aa2dcec46151e529a1126a8d74fbaba56f168d86c915002aa70d869e4a"
GAPS = [
    "normal-npm-setup-process-and-package/hook-observations-not-joined",
    "source-owned-gotestsum-build-or-validated-cache-provenance-not-joined",
    "effective-child-Go-selection-context-not-observed-by-capture",
]


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def constant(value):
    raise ValueError("nonfinite JSON: " + value)


def load(raw, maximum=2 * 1024**2):
    require(isinstance(raw, bytes) and len(raw) <= maximum, "JSON input cap/type")
    return json.loads(
        raw.decode("utf-8", errors="strict"), object_pairs_hook=unique, parse_constant=constant
    )


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def count(value, expected):
    return type(value) is int and value == expected


def stamp(value):
    require(isinstance(value, str), "timestamp type")
    parsed = datetime.fromisoformat(value)
    require(parsed.tzinfo is not None, "timestamp timezone")
    return parsed


def read(root, relative, maximum):
    """Read only fixed regular host artifacts; no extraction or followed links."""
    require(
        isinstance(relative, str) and re.fullmatch(r"[A-Za-z0-9_./-]+", relative), "artifact path"
    )
    parts = relative.split("/")
    require(all(part not in ("", ".", "..") for part in parts), "artifact traversal")
    path = Path(root)
    require(path.is_dir() and not path.is_symlink(), "artifact root")
    for part in parts[:-1]:
        path /= part
        require(path.is_dir() and not path.is_symlink(), "artifact ancestor")
    fd = os.open(path / parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_size <= maximum, "artifact regular/size")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(maximum + 1)
        require(len(raw) == info.st_size and len(raw) <= maximum, "artifact changed/capped")
        after = os.fstat(fd)
        require(
            all(
                getattr(after, k) == getattr(info, k)
                for k in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
            ),
            "artifact changed during read",
        )
        return raw
    finally:
        os.close(fd)


def module(name, path, expected):
    require(sha(path.read_bytes()) == expected, "changed adapter dependency: " + path.name)
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def owners():
    derive = module(
        "derive",
        AM2 / "derive.py",
        "9b58061af3b1205637becea668544cc6f7b4dbb0d68a51cf1fc05601370dcde2",
    )
    oracle = module(
        "go01_am2_oracle",
        AM2 / "oracle.py",
        "d969170818e80124a0eb99947aa584b82ae9c9f50e8b32ba6dc62fe17fd3b1c9",
    )
    helper = module(
        "go01_reviewed_capture_helper",
        ROOT / "benchmarks/head-to-head/bench/event_capture.py",
        HELPER_SHA,
    )
    require(
        sha((ROOT / "benchmarks/head-to-head/bench/agent_runtime.py").read_bytes()) == RUNTIME_SHA,
        "runtime subject changed",
    )
    require(derive.MAP_SHA == MAP_SHA, "source map changed")
    return oracle, helper


def association(session, relative, request_raw, config_raw, trace_raw):
    """Validate retained host artifacts within reviewed operator-consistency scope.

    Hash consistency does not authenticate arbitrary submitted directories. The
    caller must retain this host runtime output as such; no agent file/true flag
    can substitute for the exact trace, raw observations and process association.
    """
    oracle, helper = owners()
    request, config, trace = (
        load(request_raw),
        load(config_raw, 16 * 1024**2),
        load(trace_raw, 64 * 1024**2),
    )
    require(re.fullmatch(r"event-captures/[0-9]{4}/descriptor.json", relative), "descriptor path")
    raw = read(session, relative, 2 * 1024**2)
    descriptor = load(raw)
    folder = str(Path(relative).parent)
    context = descriptor["context"]
    require(trace["sessionId"] == request["sessionId"] == context["sessionId"], "session mismatch")
    require(
        trace["requestSha256"] == sha(request_raw) == context["requestSha256"], "request mismatch"
    )
    require(
        context["repository"] == request["task"]["repository"] == "github.com/microsoft/typescript",
        "repository mismatch",
    )
    require(
        context["revision"] == request["task"]["revision"] == oracle.REVISION, "revision mismatch"
    )
    require(context["sourceArchiveSha256"] == oracle.SOURCE, "source archive mismatch")
    require(
        context["imageDigest"]
        == request["environment"]["imageDigest"]
        == "sha256:b47cd4a5061d271780bab25aa2637c2623dc675bd43380fc80cb65ec44e50092",
        "image mismatch",
    )
    require(
        context["runtimeArtifactSha256"]
        == request["artifacts"]["runtime"]["sha256"]
        == sha(config_raw),
        "runtime artifact mismatch",
    )
    require(context["runtimeConfigurationSha256"] == sha(encode(config)), "configuration mismatch")
    require(context["runnerSha256"] == config["runnerSha256"] == RUNTIME_SHA, "runner mismatch")
    for key in ("environment", "resources", "containerUser"):
        require(context[key] == config[key], "configured context mismatch: " + key)
    require(context["cacheState"] == request["cacheState"], "cache-state mismatch")
    spec = config["eventCaptures"][context["repository"]]
    helper.validate(spec)
    require(spec["path"] == "/workspace/go-test-events.jsonl", "event path mismatch")
    require(
        descriptor["configuration"] == spec
        and descriptor["configurationSha256"] == sha(helper.encode(spec)),
        "capture configuration mismatch",
    )
    require(
        descriptor["state"] == "captured-unqualified-event-association"
        and descriptor["errors"] == [],
        "capture incomplete/errors",
    )
    require(
        descriptor["taskOutcomeObserved"] is False
        and descriptor["oracleQualified"] is False
        and descriptor["wholeSourceTreeIntegrityEstablished"] is False,
        "capture overclaim",
    )
    require(descriptor["costUsd"] is None, "unmetered capture cost must remain null")
    require(
        descriptor["command"] == oracle.COMMAND
        and descriptor["commandSha256"] == sha(oracle.COMMAND.encode()),
        "wrong full default command",
    )
    events = trace["events"]
    require(isinstance(events, list) and len(events) <= 100000, "trace event bound")
    require([row["index"] for row in events] == list(range(1, len(events) + 1)), "trace sequence")
    hits = [
        i
        for i, row in enumerate(events)
        if row["kind"] == "event-capture" and row["descriptor"].get("descriptorPath") == relative
    ]
    require(len(hits) == 1 and 0 < hits[0] < len(events) - 1, "capture trace missing/duplicate")
    i = hits[0]
    traced = {**descriptor, "descriptorPath": relative, "descriptorSha256": sha(raw)}
    require(events[i]["descriptor"] == traced, "trace/descriptor disagreement")
    call, response = events[i - 1], events[i + 1]
    require(
        call["kind"] == "tool-request"
        and call["name"] == "shell"
        and call["arguments"] == {"command": oracle.COMMAND},
        "chosen shell association",
    )
    require(
        call["id"] == context["toolCallId"] == response["id"]
        and response["kind"] == "tool-response",
        "tool-call association",
    )
    require(
        sum(row["kind"] == "tool-request" and row.get("id") == call["id"] for row in events) == 1,
        "duplicate tool-call ID",
    )
    ordinal = sum(row["kind"] == "event-capture" for row in events[: i + 1])
    require(
        type(context["toolCallOrdinal"]) is int
        and context["toolCallOrdinal"] == ordinal
        and relative == f"event-captures/{ordinal:04d}/descriptor.json",
        "capture ordinal",
    )
    process = descriptor["processReceipt"]
    container = descriptor["containerName"]
    require(
        process["argv"]
        == [
            "docker",
            "exec",
            "--workdir=/workspace/repository",
            container,
            "/bin/sh",
            "-c",
            oracle.COMMAND,
        ],
        "process command/container",
    )
    require(
        type(process["exitCode"]) is int
        and process["exitCode"] in (0, 1)
        and process["error"] is None,
        "process transport/failure",
    )
    result = descriptor["processResult"]
    require(
        result["exitCode"] == process["exitCode"]
        and result.get("error") is None
        and not result.get("cancelled"),
        "process result mismatch",
    )
    require(response["result"] == result, "tool response mismatch")
    process_total = 0
    for role in ("stdout", "stderr"):
        item = process[role]
        require(item["path"] == f"process-{role}.bin", "raw process path")
        value = read(session, folder + "/" + item["path"], config["maxToolOutputBytes"])
        require(
            count(item["bytes"], len(value)) and item["sha256"] == sha(value),
            "raw process bytes/hash",
        )
        require(result[role] == value.decode(errors="replace"), "process display association")
        process_total += len(value)
    require(process_total <= config["maxToolOutputBytes"], "combined process output cap")
    require(
        descriptor["processTransportBytesComplete"] is True
        and count(descriptor["processTransportBytes"], process_total),
        "process byte accounting",
    )
    begin, finish = stamp(descriptor["startedAt"]), stamp(descriptor["completedAt"])
    ps, pe = stamp(process["startedAt"]), stamp(process["completedAt"])
    require(begin <= ps <= pe <= finish, "capture/process time order")
    elapsed = descriptor["elapsedSeconds"]
    require(
        number(elapsed)
        and number(process["elapsedSeconds"])
        and process["elapsedSeconds"] <= elapsed <= request["budgets"]["wallTimeSeconds"],
        "shared elapsed/wall budget",
    )
    inventory_path = (
        ROOT / "benchmarks/head-to-head/f05-qualification-20261029/go-01-full/inventory.json"
    )
    inventory_raw = inventory_path.read_bytes()
    require(
        sha(inventory_raw) == "96c935c31228fa8e05bb836a93257beeb87ac524e5eb30cdde3c546a1ea4be0e",
        "frozen source inventory",
    )
    inventory = load(inventory_raw, 16 * 1024**2)["files"]
    subset = {"/workspace/repository/" + p: inventory[p] for p in spec["sourceFiles"]}
    require(descriptor["observedSourceSubset"] == subset, "source subset not frozen bytes")
    paths = sorted([*subset, *spec["toolPaths"]])
    witness_stdin = b"".join(p.encode() + b"\0" for p in paths)
    expected_args = [
        ["inspect", container],
        [
            "exec",
            "-i",
            container,
            "xargs",
            "-0",
            "/bin/sh",
            "-c",
            helper.WITNESS,
            "capture-witness",
        ],
        [
            "exec",
            container,
            "/bin/sh",
            "-c",
            f"if test -e {spec['path']} || test -L {spec['path']}; then printf 'present\\n'; else printf 'absent\\n'; fi",
        ],
        ["inspect", container],
        [
            "exec",
            "-i",
            container,
            "xargs",
            "-0",
            "/bin/sh",
            "-c",
            helper.WITNESS,
            "capture-witness",
        ],
        [
            "exec",
            container,
            "/bin/sh",
            "-c",
            helper.event_metadata(spec["path"], spec["maxEventBytes"]),
        ],
        [
            "exec",
            container,
            "tar",
            "--create",
            "--format=ustar",
            "--no-recursion",
            "-C",
            "/workspace",
            "--",
            "go-test-events.jsonl",
        ],
        [
            "exec",
            container,
            "/bin/sh",
            "-c",
            helper.event_metadata(spec["path"], spec["maxEventBytes"]),
        ],
    ]
    labels = [
        "inspect-before",
        "witness-before",
        "event-baseline",
        "inspect-after",
        "witness-after",
        "event-before-export",
        "export",
        "event-after-export",
    ]
    operations = descriptor["operations"]
    require(
        [r["label"] for r in operations] == labels
        and descriptor["requests"] == len(labels) <= spec["maxRequests"],
        "operation sequence/count",
    )
    output, transferred, last_end, remaining = {}, 0, begin, request["budgets"]["wallTimeSeconds"]
    for n, row in enumerate(operations):
        label = labels[n]
        require(
            row["argv"] == expected_args[n]
            and row["exitCode"] == 0
            and type(row["exitCode"]) is int
            and row.get("error") is None
            and not row.get("cancelled"),
            "instrumentation operation failed/changed",
        )
        start, end = stamp(row["startedAt"]), stamp(row["completedAt"])
        require(last_end <= start <= end <= finish, "operation time order")
        require(end <= ps if n <= 2 else start >= pe, "same-call process/export ordering")
        last_end = end
        require(
            number(row["remainingSeconds"]) and 0 < row["remainingSeconds"] <= remaining,
            "shared deadline observation",
        )
        remaining = row["remainingSeconds"]
        data = witness_stdin if n in (1, 4) else b""
        require(
            count(row["stdinBytes"], len(data)) and row["stdinSha256"] == sha(data),
            "instrumentation input association",
        )
        maximum = spec["maxEventBytes"] + 10240 if label == "export" else spec["maxMetadataBytes"]
        values = {}
        for role in ("stdout", "stderr"):
            value = read(session, folder + "/" + label + "/" + role + ".bin", maximum)
            require(
                count(row[role + "Bytes"], len(value)) and row[role + "Sha256"] == sha(value),
                "instrumentation raw bytes/hash",
            )
            values[role] = value
        require(
            not values["stderr"] and len(values["stdout"]) <= maximum,
            "instrumentation output/stderr",
        )
        byte_count = len(data) + len(values["stdout"])
        require(
            type(row["observedTransportBytes"]) is int
            and row["observedTransportBytes"] == byte_count,
            "operation transport accounting",
        )
        transferred += byte_count
        output[label] = values["stdout"]
    require(
        descriptor["transportBytesComplete"] is True
        and count(descriptor["transportBytes"], transferred)
        and transferred <= spec["maxCaptureBytes"],
        "capture aggregate accounting",
    )
    require(
        output["event-baseline"] == b"absent\n" and descriptor["event-baseline"] == "absent\n",
        "event path not fresh",
    )
    for label in ("inspect-before", "inspect-after"):
        rows = load(output[label])
        require(
            isinstance(rows, list) and len(rows) == 1 and rows[0] == descriptor[label],
            "inspect raw association",
        )
        row = rows[0]
        require(
            row["Name"] == "/" + container
            and row["Image"] == context["imageDigest"]
            and re.fullmatch(r"[0-9a-f]{64}", row["Id"]),
            "container identity",
        )
        require(
            row["Mounts"] == []
            and row["HostConfig"]["ReadonlyRootfs"] is True
            and row["HostConfig"]["NetworkMode"] == "none"
            and row["Config"]["User"] == context["containerUser"],
            "isolation mismatch",
        )
        resources = config["resources"]
        require(
            resources
            == {
                "cpus": 3,
                "memoryBytes": 4294967296,
                "pidsLimit": 256,
                "workspaceBytes": 8589934592,
                "tmpBytes": 536870912,
            },
            "fixed resource conditions changed",
        )
        host = row["HostConfig"]
        require(
            host["Memory"] == host["MemorySwap"] == resources["memoryBytes"]
            and host["NanoCpus"] == 3000000000
            and host["PidsLimit"] == 256,
            "observed resource mismatch",
        )
        require(
            host["CapDrop"] == ["ALL"]
            and host["SecurityOpt"] == ["no-new-privileges"]
            and host["IpcMode"] == "private"
            and host["PidMode"] in ("", "private")
            and host["CgroupnsMode"] == "private",
            "observed isolation options",
        )
        uid, gid = config["containerUser"].split(":")
        require(
            host["Tmpfs"]
            == {
                path: f"rw,exec,nosuid,nodev,size={size},uid={uid},gid={gid},mode=0700"
                for path, size in [
                    ("/workspace", resources["workspaceBytes"]),
                    ("/tmp", resources["tmpBytes"]),
                ]
            },
            "observed workspace/tmp limits",
        )
        env = row["Config"]["Env"]
        require(
            isinstance(env, list) and all(isinstance(v, str) and "=" in v for v in env),
            "base environment shape",
        )
        env_pairs = [item.split("=", 1) for item in env]
        require(len({key for key, _ in env_pairs}) == len(env_pairs), "duplicate base environment")
        require(
            all(dict(env_pairs).get(k) == v for k, v in config["environment"].items()),
            "base environment mismatch",
        )
    for key in ("Id", "Image", "Config", "HostConfig", "Mounts", "NetworkSettings"):
        require(
            descriptor["inspect-before"].get(key) == descriptor["inspect-after"].get(key),
            "container before/after changed",
        )
    for label in ("witness-before", "witness-after"):
        observed = helper.witnesses(output[label], paths)
        require(observed == descriptor[label], "witness raw association")
        require(
            all(observed[p] == {"kind": "file", "sha256": h} for p, h in subset.items()),
            "source subset changed",
        )
        require(
            all(
                h is None or observed[p]["kind"] in ("file", "link") and observed[p]["sha256"] == h
                for p, h in spec["toolPaths"].items()
            ),
            "pinned tool changed",
        )
    metadata = []
    for label in ("event-before-export", "event-after-export"):
        item = helper.parse_event_metadata(output[label], spec["path"], spec["maxEventBytes"])
        require(
            item == descriptor[label] and item["kind"] == "regular", "event metadata association"
        )
        metadata.append(item)
    require(metadata[0] == metadata[1], "event changed during export")
    events_raw = helper.event_bytes(output["export"], spec["path"], spec["maxEventBytes"])
    item = descriptor["event-file"]
    require(
        item == {"path": "events.bin", "bytes": len(events_raw), "sha256": sha(events_raw)}
        and item["sha256"] == metadata[0]["sha256"]
        and item["bytes"] == metadata[0]["bytes"],
        "event export binding",
    )
    require(
        read(session, folder + "/events.bin", spec["maxEventBytes"]) == events_raw,
        "host event bytes differ",
    )
    events_raw.decode("utf-8", errors="strict")
    return descriptor, events_raw


def evaluate(
    session,
    relative,
    request_raw,
    config_raw,
    trace_raw,
    expectation,
    policy,
    execution,
    *,
    synthetic=False,
):
    result = {
        "taskId": "go-01",
        "synthetic": synthetic,
        "captureAssociationValidated": False,
        "candidateOutcomeObserved": False,
        "taskOutcomeObserved": False,
        "oracleQualified": False,
        "campaignAdmitted": False,
        "nativeCollectionOccurred": False,
        "reason": "unresolved",
        "remainingJoins": list(GAPS),
    }
    try:
        require(type(synthetic) is bool, "synthetic type")
        descriptor, events_raw = association(session, relative, request_raw, config_raw, trace_raw)
        result["captureAssociationValidated"] = True
        result["rawEventsSha256"] = sha(events_raw)
        require(synthetic, "actual-full-task-setup-tool-effective-context-join-unavailable")
        oracle, _ = owners()
        # These are explicit synthetic scorer fixtures, never promoted to actual witnesses.
        execution = dict(execution)
        receipt = descriptor["processReceipt"]
        execution.update(
            startedAt=receipt["startedAt"],
            exitCode=receipt["exitCode"],
            error=receipt["error"],
            rawEventsSha256=sha(events_raw),
            stderr=read(
                session,
                str(Path(relative).parent) + "/process-stderr.bin",
                load(config_raw)["maxToolOutputBytes"],
            ).decode("utf-8", errors="strict"),
        )
        execution["expectationSha256"] = oracle.digest(expectation)
        execution["policySha256"] = oracle.digest(policy)
        metadata, _ = oracle.load_expectation()
        execution["syntheticCapture"] = {
            "state": "synthetic-full-task-capture-fixture",
            "synthetic": True,
            "command": oracle.COMMAND,
            "rawEventsSha256": sha(events_raw),
            "sourceSubjectSha256": oracle.digest(metadata["sourceSubject"]),
            "setupRole": "full-normal-setup",
            "eventOrigin": "owned-synthetic-fixture-not-arbitrary-agent-file",
        }
        scored = oracle.evaluate(
            events_raw.decode("utf-8", errors="strict"),
            expectation,
            policy,
            execution,
            synthetic=True,
        )
        result.update(scored, captureAssociationValidated=True, remainingJoins=list(GAPS))
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        OSError,
        UnicodeError,
        tarfile.TarError,
    ) as error:
        result["reason"] = str(error)
    return result
