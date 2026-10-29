"""Owned mocked final-wait cancellation; does not start any process."""

import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "benchmarks/head-to-head"))
from bench import agent_runtime as runtime  # noqa: E402


def main():
    assert hashlib.sha256(Path(runtime.__file__).read_bytes()).hexdigest() == (
        "dc585e08f24e1a20da9d9ccdafac4af3f4e10cb8451de7ca3a74c05ecc985fa0"
    )

    class Pipe:
        closed = False

        def fileno(self):
            return 123

        def close(self):
            self.closed = True

    class Selector:
        closed = False

        def register(self, *_):
            pass

        def get_map(self):
            return {}

        def close(self):
            self.closed = True

    class Process:
        stdout, stderr = Pipe(), Pipe()
        returncode = None
        waits = 0
        kills = 0

        def kill(self):
            self.kills += 1

        def wait(self, timeout=None):
            self.waits += 1
            if self.waits == 1:
                assert timeout is not None and 0 <= timeout <= 10
                raise KeyboardInterrupt("owned mocked cancellation during final wait")
            assert self.kills == 1
            self.returncode = -9
            return self.returncode

    process, selector = Process(), Selector()
    with (
        patch.object(runtime.subprocess, "Popen", return_value=process),
        patch.object(runtime.selectors, "DefaultSelector", return_value=selector),
        patch.object(runtime.os, "set_blocking"),
    ):
        result = runtime.limited_process(
            ["owned-no-process"], timeout=10, output_limit=128, raw=True
        )
    assert result["error"] == "KeyboardInterrupt" and result["cancelled"] is True
    assert result["exitCode"] == -9 and result["stdout"] == result["stderr"] == b""
    assert process.waits == 2 and process.kills == 1
    assert process.stdout.closed and process.stderr.closed and selector.closed
    report = {
        "case": "final wait cancellation kills/reaps and closes resources",
        "passed": True,
        "waitCalls": process.waits,
        "killCalls": process.kills,
        "cancelled": result["cancelled"],
        "error": result["error"],
        "newRealProcesses": 0,
        "newDockerGoNodeUpstreamNetworkProviderActions": 0,
    }
    with (HERE / "wait-cancel-check.json").open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
