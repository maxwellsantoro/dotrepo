"""Owned local POSIX child only: stream EOF before process deadline handling."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "benchmarks/head-to-head"))
from bench import agent_runtime as runtime  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--prefix", action="store_true")
    args = parser.parse_args()
    scratch = Path(tempfile.mkdtemp(prefix="dotrepo-event-capture-review-", dir="/tmp"))
    pidfile = scratch / "pid"
    prefix = "printf '\\377\\200owned\\n'; " if args.prefix else ""
    argv = [
        "/bin/sh",
        "-c",
        'printf "%s" "$$" > "$1"; ' + prefix + "exec 1>&- 2>&-; exec sleep 8",
        "owned-review",
        str(pidfile),
    ]
    started = time.monotonic()
    value = error = None
    try:
        value = runtime.limited_process(argv, timeout=0.05, output_limit=128, raw=True)
    except BaseException as exc:
        error = {"type": type(exc).__name__, "text": str(exc)}
    elapsed = time.monotonic() - started
    pid = int(pidfile.read_text())
    # Never signal a reused unrelated PID: waitpid first establishes that the
    # leaked process is still this review process's own unreaped live child.
    live_owned = False
    cleanup = None
    try:
        child, status = os.waitpid(pid, os.WNOHANG)
        if child == 0:
            live_owned = True
            os.kill(pid, signal.SIGKILL)
            cleanup = os.waitpid(pid, 0)
        else:
            cleanup = [child, status]
    except ChildProcessError:
        cleanup = "already reaped by transport"
    if value is not None:
        value = {
            **value,
            **{
                role: {"bytes": len(value[role]), "hex": value[role].hex()}
                for role in ["stdout", "stderr"]
            },
        }
    report = {
        "case": "owned child closes stdout/stderr before sleeping past deadline",
        "argv": argv,
        "timeoutSeconds": 0.05,
        "elapsedSeconds": elapsed,
        "returnValue": value,
        "exception": error,
        "ownedChildPid": pid,
        "ownedChildStillAliveAfterFunction": live_owned,
        "reviewerCleanupOfOwnedChild": cleanup,
        "runtimeSha256": hashlib.sha256(Path(runtime.__file__).read_bytes()).hexdigest(),
        "newDockerGoNodeProviderNetworkCalls": 0,
    }
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
