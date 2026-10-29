"""Exercise the copied bounded transport with fake processes and byte streams."""

import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

import runtime as r


class Stream:
    def __init__(self, number, chunks):
        self.number, self.chunks, self.closed = number, chunks, False

    def fileno(self):
        return self.number

    def close(self):
        self.closed = True


class Process:
    def __init__(self, stdout, stderr):
        self.stdout = Stream(
            900001, [stdout[i : i + 65536] for i in range(0, len(stdout), 65536)] + [b""]
        )
        self.stderr = Stream(900002, [stderr, b""])
        self.stdin, self.returncode, self.killed = None, None, False

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed, self.returncode = True, -9

    def wait(self, **kwargs):
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


def main():
    plan = r.load_plan()
    _, _, transport = r.dependencies(plan)
    originals = (
        transport.subprocess.Popen,
        transport.selectors.DefaultSelector,
        transport.os.set_blocking,
        transport.os.read,
        transport.time.monotonic,
    )
    results = []
    try:
        with tempfile.TemporaryDirectory(
            prefix="dotrepo-owned-registry-byte-transport-"
        ) as directory:
            for name, stdout, stderr in [
                ("binary-lossless", b"\x1f\x8b\x00\xff\x80", b""),
                ("combined-cap", b"x" * r.TEXT_LIMIT, b"e"),
                ("binary-cap", b"x" * (r.TEXT_LIMIT + 1), b""),
                ("cancel", b"", b""),
                ("deadline", b"", b""),
            ]:
                process, clock = Process(stdout, stderr), [0]

                class Selector:
                    def __init__(self):
                        self.values = {}

                    def register(self, stream, events, role):
                        self.values[stream.fileno()] = SimpleNamespace(
                            fileobj=stream, fd=stream.fileno(), data=role
                        )

                    def unregister(self, stream):
                        del self.values[stream.fileno()]

                    def get_map(self):
                        return self.values

                    def select(self, *args):
                        if name == "cancel":
                            raise KeyboardInterrupt("synthetic cancellation")
                        if name == "deadline":
                            clock[0] = 11
                            return []
                        return [(item, None) for item in list(self.values.values())]

                    def close(self):
                        pass

                transport.subprocess.Popen = lambda *args, **kwargs: process
                transport.selectors.DefaultSelector = Selector
                transport.os.set_blocking = lambda *args: None
                transport.os.read = lambda fd, length: (
                    process.stdout if fd == process.stdout.fileno() else process.stderr
                ).chunks.pop(0)
                transport.time.monotonic = lambda: clock[0]
                binary = Path(directory) / f"{name}.bin"
                result = transport.DockerBackend().command(
                    Path(directory), name, ["NEVER_EXECUTED"], deadline=10, binary_path=binary
                )
                raw_error = (Path(directory) / "logs" / name / "stderr.bin").read_bytes()
                r.require(
                    binary.stat().st_size + len(raw_error) <= r.TEXT_LIMIT,
                    "combined bound exceeded",
                )
                if name == "binary-lossless":
                    r.require(
                        binary.read_bytes() == stdout
                        and result["error"] is None
                        and result["binarySha256"] == hashlib.sha256(stdout).hexdigest(),
                        "binary bytes decoded/changed",
                    )
                    r.require(
                        (Path(directory) / "logs" / name / "stdout.bin").read_bytes() == b"",
                        "binary duplicated as text",
                    )
                else:
                    r.require(
                        result["error"] and process.killed and result["exitCode"] == -9,
                        "fake failure did not terminate",
                    )
                r.require(result["cancelled"] == (name == "cancel"), "cancellation receipt")
                results.append(
                    {
                        "case": name,
                        "passed": True,
                        "binaryBytes": result["binaryBytes"],
                        "error": result["error"],
                        "cancelled": result["cancelled"],
                    }
                )
    finally:
        (
            transport.subprocess.Popen,
            transport.selectors.DefaultSelector,
            transport.os.set_blocking,
            transport.os.read,
            transport.time.monotonic,
        ) = originals
    print(json.dumps({"synthetic": True, "realProcessSocketCalls": 0, "cases": results}, indent=2))


if __name__ == "__main__":
    main()
