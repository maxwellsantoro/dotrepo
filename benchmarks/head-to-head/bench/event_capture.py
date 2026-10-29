"""Optional host-owned same-shell-call event capture; no scorer or process launcher.

This module observes a frozen source/tool subset and exports a regular event file
before the shell operation returns. It does not establish whole-tree integrity,
source-owned tool-build provenance, command scope, or a completed task. Those are
post-run checks. The normal producer may write the event file; active same-UID
adversarial writer authentication is outside this operator-consistency boundary.
"""

from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import shlex
import tarfile
import time

HEX = re.compile(r"[0-9a-f]{64}")
MAX_EVENT = 256 * 1024**2
MAX_METADATA = 2 * 1024**2
MAX_TOTAL = 512 * 1024**2
KEYS = {
    "helperSha256",
    "path",
    "sourceFiles",
    "toolPaths",
    "maxEventBytes",
    "maxMetadataBytes",
    "maxCaptureBytes",
    "maxRequests",
}


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()


def reject_constant(value):
    raise ValueError("nonfinite inspect JSON")


def literal_path(value):
    return (
        isinstance(value, str)
        and 0 < len(value) <= 1024
        and not any(ord(c) < 32 or ord(c) == 127 for c in value)
        and "\\" not in value
        and "\x00" not in value
        and all(part not in ("", ".", "..") for part in value.lstrip("/").split("/"))
    )


def validate(spec):
    require(isinstance(spec, dict) and set(spec) == KEYS, "event capture config keys")
    require(
        spec["helperSha256"] == digest(Path(__file__).read_bytes()), "event capture helper changed"
    )
    path = spec["path"]
    require(
        isinstance(path, str)
        and re.fullmatch(r"/workspace/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", path)
        and path != "/workspace/repository",
        "event path must be a fixed workspace child",
    )
    sources = spec["sourceFiles"]
    require(
        isinstance(sources, list)
        and 0 < len(sources) <= 10000
        and all(literal_path(p) and not p.startswith("/") for p in sources)
        and sources == sorted(set(sources)),
        "event capture source subset",
    )
    tools = spec["toolPaths"]
    require(
        isinstance(tools, dict)
        and 0 < len(tools) <= 32
        and all(literal_path(p) and p.startswith("/") and p != path for p in tools)
        and all(h is None or isinstance(h, str) and HEX.fullmatch(h) for h in tools.values()),
        "event capture tool observations",
    )
    for key, maximum in [
        ("maxEventBytes", MAX_EVENT),
        ("maxMetadataBytes", MAX_METADATA),
        ("maxCaptureBytes", MAX_TOTAL),
        ("maxRequests", 16),
    ]:
        require(type(spec[key]) is int and 0 < spec[key] <= maximum, "event capture bound: " + key)


def witnesses(raw, paths):
    parts = raw.split(b"\0")
    require(parts[-1] == b"" and len(parts) == len(paths) * 2 + 1, "witness framing/count")
    result = {}
    for i in range(0, len(parts) - 1, 2):
        kind = parts[i].decode("ascii")
        value = parts[i + 1].decode("utf-8", errors="strict")
        require(kind in {"file", "link", "absent", "special"}, "witness kind")
        if kind in {"file", "link"}:
            checksum, name = value.split("  ", 1)
            require(HEX.fullmatch(checksum), "witness checksum")
        else:
            checksum, name = None, value
        require(name in paths and name not in result, "witness path")
        result[name] = {"kind": kind, "sha256": checksum}
    require(set(result) == set(paths), "missing witness")
    return result


WITNESS = """for p do
if test -f "$p"; then
  if test -L "$p"; then printf 'link\\0'; else printf 'file\\0'; fi
  sha256sum --zero -- "$p" || exit
elif test -L "$p" || test -e "$p"; then printf 'special\\0%s\\0' "$p"
else printf 'absent\\0%s\\0' "$p"; fi
done"""


def event_metadata(command_path, maximum):
    p = shlex.quote(command_path)
    return (
        f"if test -L {p}; then printf 'symlink\\n'; "
        f"elif test ! -e {p}; then printf 'absent\\n'; "
        f"elif test ! -f {p}; then printf 'special\\n'; "
        f"elif test \"$(stat -c %s -- {p})\" -gt {maximum}; then printf 'oversize\\n'; "
        f"else stat -c 'regular|%s|%h|%i|%Y|%Z|%a' -- {p}; sha256sum --zero -- {p}; fi"
    )


def parse_event_metadata(raw, path, maximum):
    if raw in (b"absent\n", b"special\n", b"symlink\n", b"oversize\n"):
        return {"kind": raw.decode().strip()}
    first, rest = raw.split(b"\n", 1)
    values = first.decode("ascii").split("|")
    require(len(values) == 7 and values[0] == "regular", "event stat framing")
    size, links, inode, mtime, ctime = [int(v) for v in values[1:6]]
    mode = int(values[6], 8)
    require(0 <= size <= maximum and links == 1 and mode & ~0o777 == 0, "unsafe event stat")
    checksum, name = rest.removesuffix(b"\0").decode("utf-8", errors="strict").split("  ", 1)
    require(rest.endswith(b"\0") and name == path and HEX.fullmatch(checksum), "event stat hash")
    return {
        "kind": "regular",
        "bytes": size,
        "links": links,
        "inode": inode,
        "mtime": mtime,
        "ctime": ctime,
        "mode": mode,
        "sha256": checksum,
    }


def event_bytes(raw, path, maximum):
    require(len(raw) <= maximum + 10240, "event archive cap")
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        item = archive.next()
        require(item is not None, "event archive member count")
        require(
            item.name == path.removeprefix("/workspace/")
            and item.type in {tarfile.REGTYPE, tarfile.AREGTYPE}
            and not item.sparse
            and item.mode & ~0o777 == 0
            and item.size <= maximum
            and item.offset == 0
            and item.offset_data == 512
            and not item.pax_headers,
            "unsafe event archive member",
        )
        value = archive.extractfile(item).read(maximum + 1)
        require(len(value) == item.size, "short event file")
        require(archive.next() is None, "event archive member count")
        end = 512 + ((item.size + 511) // 512) * 512
        require(
            len(raw) >= end + 1024 and not raw[end:].strip(b"\0"), "event archive trailing data"
        )
        return value


class Capture:
    def __init__(self, spec, bundle, context, folder, call, *, clock=time.monotonic):
        validate(spec)
        require(all(p in bundle.files for p in spec["sourceFiles"]), "capture source not retained")
        self.spec, self.folder, self.call, self.clock = spec, Path(folder), call, clock
        self.folder.mkdir(parents=True, exist_ok=False)
        self.sources = {
            "/workspace/repository/" + p: digest(bundle.files[p]) for p in spec["sourceFiles"]
        }
        require(not self.sources.keys() & spec["toolPaths"].keys(), "source/tool witness overlap")
        self.paths = sorted([*self.sources, *spec["toolPaths"]])
        self.record = {
            "state": "incomplete-unqualified-event-capture",
            "context": context,
            "configuration": spec,
            "configurationSha256": digest(encode(spec)),
            "observedSourceSubset": self.sources,
            "operations": [],
            "errors": [],
            "transportBytes": 0,
            "transportBytesComplete": True,
            "processTransportBytes": 0,
            "processTransportBytesComplete": True,
            "requests": 0,
            "taskOutcomeObserved": False,
            "oracleQualified": False,
            "wholeSourceTreeIntegrityEstablished": False,
            "costUsd": None,
            "costExclusions": [
                "Host/container instrumentation cost has no metered dollar receipt."
            ],
            "limitation": "Observed source/tool subset and operator process/export association only; post-run scope/context/tool-provenance checks remain required.",
        }

    def raw(self, label, args, *, maximum, data=b""):
        require(self.record["transportBytesComplete"], "capture transport accounting unknown")
        require(self.clock() < self.deadline, "capture shared deadline exhausted")
        require(self.record["requests"] < self.spec["maxRequests"], "capture request bound")
        available = self.spec["maxCaptureBytes"] - self.record["transportBytes"] - len(data)
        require(available > 0, "capture transport budget exhausted")
        limit = min(maximum, available)
        self.record["requests"] += 1
        stamp = datetime.now(timezone.utc).isoformat()
        try:
            result = self.call(args, self.deadline - self.clock(), data=data, limit=limit, raw=True)
        except BaseException as exc:
            self.record["transportBytesComplete"] = False
            self.record["operations"].append(
                {
                    "label": label,
                    "argv": args,
                    "stdinBytesPrepared": len(data),
                    "stdinSha256": digest(data),
                    "errorType": type(exc).__name__,
                    "transportBytes": None,
                    "startedAt": stamp,
                    "completedAt": datetime.now(timezone.utc).isoformat(),
                }
            )
            raise
        out, err = result["stdout"], result["stderr"]
        if not isinstance(out, bytes) or not isinstance(err, bytes):
            self.record["transportBytesComplete"] = False
        require(isinstance(out, bytes) and isinstance(err, bytes), "capture transport must be raw")
        self.record["transportBytes"] += len(data) + len(out) + len(err)
        leaf = self.folder / label
        leaf.mkdir()
        stored_out, stored_err = out[:limit], err[: max(0, limit - len(out))]
        (leaf / "stdout.bin").write_bytes(stored_out)
        (leaf / "stderr.bin").write_bytes(stored_err)
        receipt = {k: v for k, v in result.items() if k not in {"stdout", "stderr"}}
        receipt.update(
            label=label,
            argv=args,
            stdinBytes=len(data),
            stdinSha256=digest(data),
            stdoutBytes=len(stored_out),
            stdoutSha256=digest(stored_out),
            stderrBytes=len(stored_err),
            stderrSha256=digest(stored_err),
            observedTransportBytes=len(data) + len(out) + len(err),
            remainingSeconds=self.deadline - self.clock(),
            startedAt=stamp,
            completedAt=datetime.now(timezone.utc).isoformat(),
        )
        self.record["operations"].append(receipt)
        if result.get("cancelled"):
            raise KeyboardInterrupt("capture transport cancelled")
        require(len(out) + len(err) <= limit, "capture raw output cap")
        require(not result.get("error") and result["exitCode"] == 0, label + " failed")
        require(self.clock() < self.deadline, "capture shared deadline exhausted")
        return out

    def probe(self, label):
        raw = self.raw(
            label,
            [
                "exec",
                "-i",
                self.container,
                "xargs",
                "-0",
                "/bin/sh",
                "-c",
                WITNESS,
                "capture-witness",
            ],
            maximum=self.spec["maxMetadataBytes"],
            data=b"".join(p.encode() + b"\0" for p in self.paths),
        )
        value = witnesses(raw, self.paths)
        require(
            all(value[p] == {"kind": "file", "sha256": h} for p, h in self.sources.items()),
            "observed source subset changed",
        )
        for path, expected in self.spec["toolPaths"].items():
            if expected is not None:
                require(
                    value[path]["kind"] in {"file", "link"} and value[path]["sha256"] == expected,
                    "observed tool changed",
                )
        return value

    def inspect(self, label):
        raw = self.raw(label, ["inspect", self.container], maximum=self.spec["maxMetadataBytes"])
        rows = json.loads(raw, parse_constant=reject_constant)
        require(
            isinstance(rows, list) and len(rows) == 1 and isinstance(rows[0], dict),
            "capture inspect shape",
        )
        row = rows[0]
        require(isinstance(row.get("Id"), str) and HEX.fullmatch(row["Id"]), "capture container ID")
        require(row["Name"] == "/" + self.container, "capture container association")
        context = self.record["context"]
        require(row["Image"] == context["imageDigest"], "capture image association")
        require(
            not row["Mounts"]
            and row["HostConfig"]["ReadonlyRootfs"] is True
            and row["HostConfig"]["NetworkMode"] == "none"
            and row["Config"]["User"] == context["containerUser"],
            "capture isolation observation",
        )
        return row

    def observe(self, label, operation, *, retain=True):
        try:
            value = operation()
            if retain:
                self.record[label] = value
            return value
        except (ValueError, KeyError, TypeError, OSError, tarfile.TarError, UnicodeError) as exc:
            self.record["errors"].append(
                {"stage": label, "type": type(exc).__name__, "reason": str(exc)}
            )
            return None

    def run(self, container, command, timeout, execute, *, deadline=None, started=None):
        started = self.clock() if started is None else started
        self.container = container
        self.deadline = started + timeout if deadline is None else deadline
        self.record.update(
            command=command, commandSha256=digest(command.encode()), containerName=container
        )
        self.record.setdefault("startedAt", datetime.now(timezone.utc).isoformat())
        result = None
        try:
            self.observe("inspect-before", lambda: self.inspect("inspect-before"))
            self.observe("witness-before", lambda: self.probe("witness-before"))
            baseline = self.observe(
                "event-baseline",
                lambda: self.raw(
                    "event-baseline",
                    [
                        "exec",
                        container,
                        "/bin/sh",
                        "-c",
                        f"if test -e {shlex.quote(self.spec['path'])} || test -L {shlex.quote(self.spec['path'])}; then printf 'present\\n'; else printf 'absent\\n'; fi",
                    ],
                    maximum=self.spec["maxMetadataBytes"],
                ).decode("ascii"),
            )
            if baseline != "absent\n":
                self.record["errors"].append(
                    {"stage": "event-baseline", "reason": "event path not witnessed fresh"}
                )
            require(self.clock() < self.deadline, "shared deadline exhausted before chosen command")
            # No command matching, scorer or gold consultation; baseline errors never deny a command.
            self.record["processTransportBytesComplete"] = False
            result = execute(self.deadline - self.clock())
            self.record["processResult"] = result
            receipt = self.record.get("processReceipt", {})
            if not (
                self.record["processTransportBytesComplete"]
                and receipt.get("argv")
                == [
                    "docker",
                    "exec",
                    "--workdir=/workspace/repository",
                    container,
                    "/bin/sh",
                    "-c",
                    command,
                ]
                and receipt.get("exitCode") == result.get("exitCode")
                and receipt.get("error") == result.get("error")
            ):
                self.record["errors"].append(
                    {
                        "stage": "chosen-process",
                        "reason": "raw process receipt unavailable/inconsistent",
                    }
                )
            if result.get("error") or result.get("cancelled"):
                self.record["errors"].append(
                    {"stage": "chosen-process", "reason": "process failed/cancelled transport"}
                )
            if result.get("cancelled"):
                return result, self.record
            self.observe("inspect-after", lambda: self.inspect("inspect-after"))
            self.observe("witness-after", lambda: self.probe("witness-after"))
            path, maximum = self.spec["path"], self.spec["maxEventBytes"]

            def metadata(label):
                raw = self.raw(
                    label,
                    ["exec", container, "/bin/sh", "-c", event_metadata(path, maximum)],
                    maximum=self.spec["maxMetadataBytes"],
                )
                return parse_event_metadata(raw, path, maximum)

            before = self.observe("event-before-export", lambda: metadata("event-before-export"))
            if before is not None and before["kind"] == "regular":
                raw_tar = self.observe(
                    "export",
                    lambda: self.raw(
                        "export",
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
                            path.removeprefix("/workspace/"),
                        ],
                        maximum=maximum + 10240,
                    ),
                    retain=False,
                )
                if raw_tar is not None:
                    # Store raw tar as an artifact, not inside JSON/provider messages.
                    exported = self.observe(
                        "event-file",
                        lambda: event_bytes(raw_tar, path, maximum),
                        retain=False,
                    )
                    if exported is not None:
                        (self.folder / "events.bin").write_bytes(exported)
                        self.record["event-file"] = {
                            "path": "events.bin",
                            "bytes": len(exported),
                            "sha256": digest(exported),
                        }
                after = self.observe("event-after-export", lambda: metadata("event-after-export"))
                exported = self.record.get("event-file")
                if not (
                    before == after
                    and isinstance(exported, dict)
                    and exported["sha256"] == before["sha256"]
                    and exported["bytes"] == before["bytes"]
                ):
                    self.record["errors"].append(
                        {
                            "stage": "export-association",
                            "reason": "event stat/hash changed or export incomplete",
                        }
                    )
            else:
                self.record["errors"].append(
                    {"stage": "export-association", "reason": "event file absent/unsafe/oversize"}
                )
            if self.record.get("inspect-before") != self.record.get("inspect-after"):
                # Volatile Docker State fields differ normally; compare stable source/tool context only below.
                before_context = self.record.get("inspect-before", {})
                after_context = self.record.get("inspect-after", {})
                for key in ["Id", "Image", "Config", "HostConfig", "Mounts", "NetworkSettings"]:
                    if before_context.get(key) != after_context.get(key):
                        self.record["errors"].append(
                            {
                                "stage": "container-context",
                                "reason": "container context changed: " + key,
                            }
                        )
            require(self.clock() < self.deadline, "capture shared deadline exhausted")
            if not self.record["errors"]:
                self.record["state"] = "captured-unqualified-event-association"
        except BaseException as exc:
            self.record["errors"].append(
                {"stage": "capture", "type": type(exc).__name__, "reason": str(exc)}
            )
            if result is None:
                result = {
                    "stdout": "",
                    "stderr": "",
                    "exitCode": None,
                    "error": "timeout"
                    if isinstance(exc, TimeoutError) or self.clock() >= self.deadline
                    else type(exc).__name__,
                    "cancelled": isinstance(exc, (KeyboardInterrupt, SystemExit)),
                }
            elif isinstance(exc, (KeyboardInterrupt, SystemExit)):
                result = {**result, "error": type(exc).__name__, "cancelled": True}
            elif self.clock() >= self.deadline:
                result = {**result, "error": "timeout"}
        finally:
            self.record["elapsedSeconds"] = self.clock() - started
            self.record["completedAt"] = datetime.now(timezone.utc).isoformat()
            (self.folder / "descriptor.json").write_bytes(encode(self.record))
        return result, self.record
