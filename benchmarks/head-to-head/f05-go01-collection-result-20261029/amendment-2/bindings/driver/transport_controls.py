"""Exercise client cancellation/deadline receipts with entirely fake processes."""

import json
from pathlib import Path
import socket
import subprocess
import tempfile

import collection

HERE = Path(__file__).resolve().parent


def denied(*args, **kwargs):
    raise AssertionError("Real process/socket prohibited")


subprocess.Popen = denied
socket.socket = denied
socket.create_connection = denied


class Stream:
    closed = False

    def fileno(self):
        return 999999

    def close(self):
        self.closed = True


class Process:
    def __init__(self):
        self.stdout, self.stderr, self.stdin = Stream(), Stream(), None
        self.returncode, self.killed = None, False

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed, self.returncode = True, -9

    def wait(self, **kwargs):
        return self.returncode


def main():
    collection.load_plan()
    transport = collection.module(HERE / "process_io.py", "synthetic_transport")
    checks = []
    with tempfile.TemporaryDirectory(prefix="dotrepo-go01-collection-transport-") as temporary:
        for failure in ["cancellation", "deadline"]:
            clock, process = [0], Process()

            class Selector:
                def register(self, *args):
                    pass

                def get_map(self):
                    return {"owned": True}

                def select(self, *args):
                    if failure == "cancellation":
                        raise KeyboardInterrupt("owned client cancellation")
                    clock[0] = 11
                    return []

                def close(self):
                    pass

            transport.subprocess.Popen = lambda *args, **kwargs: process
            transport.selectors.DefaultSelector = Selector
            transport.os.set_blocking = lambda *args: None
            transport.time.monotonic = lambda: clock[0]
            result = transport.DockerBackend().command(
                Path(temporary), failure, ["NEVER_EXECUTED"], deadline=10
            )
            assert process.killed and result["exitCode"] == -9 and result["error"]
            assert result["cancelled"] == (failure == "cancellation") and result["costUsd"] is None
            checks.append(
                {"case": failure, "passed": True, "fakeClientKilled": True, "receipt": result}
            )
    subprocess.Popen = denied
    collection.write(
        HERE / "transport-controls.json",
        {"passed": len(checks), "controls": checks, "realProcessSocketCalls": 0},
    )
    print(json.dumps({"passed": len(checks), "realProcessSocketCalls": 0}))


if __name__ == "__main__":
    main()
