"""First-party controller inside the bounded execution container; invoke via uv."""

from __future__ import annotations

import hashlib
import importlib.metadata as metadata
import json
import os
import platform
import resource
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path

WORK = Path("/work")
CHECKOUT = WORK / "checkout"
COMMANDS = {
    "setup": ["uv", "sync", "--locked", "--python", "/usr/local/bin/python3.12", "--group", "dev"],
    "test": [
        "uv",
        "run",
        "--offline",
        "--no-sync",
        "--python",
        "/usr/local/bin/python3.12",
        "pytest",
        "testing",
        "--color=no",
        "--junitxml=/work/results.xml",
    ],
}


def network_bytes():
    total = 0
    for line in Path("/proc/net/dev").read_text().splitlines()[2:]:
        name, counters = line.split(":", 1)
        if name.strip() != "lo":
            values = counters.split()
            total += int(values[0]) + int(values[8])
    return total


def execute(stage):
    seconds = 180 if stage == "setup" else 60
    started, initial_network = time.monotonic(), network_bytes()
    usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    process = subprocess.Popen(
        COMMANDS[stage],
        cwd=CHECKOUT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    stop, observed = None, 0
    with (WORK / (stage + ".log")).open("wb") as log:
        while selector.get_map():
            if time.monotonic() - started >= seconds:
                stop = "wall-budget"
            if network_bytes() - initial_network > 64 * 1024 * 1024:
                stop = "network-budget"
            if stop:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            for key, _ in selector.select(timeout=0.1):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                remaining = (1 << 20) - observed
                log.write(chunk[: max(0, remaining)])
                observed += len(chunk)
                if observed > 1 << 20:
                    stop = "output-budget"
                    break
    selector.close()
    process.wait(timeout=5)
    usage_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = {
        "stage": stage,
        "command": COMMANDS[stage],
        "exitCode": process.returncode,
        "stopReason": stop,
        "wallSeconds": time.monotonic() - started,
        "networkInterfaceBytes": network_bytes() - initial_network,
        "observedOutputBytes": observed,
        "childCpuSeconds": usage_after.ru_utime
        + usage_after.ru_stime
        - usage_before.ru_utime
        - usage_before.ru_stime,
        "childMaxRssKiB": usage_after.ru_maxrss,
    }
    (WORK / (stage + ".json")).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)
    return 0 if process.returncode == 0 and stop is None else 1


def probe():
    import iniconfig

    expected = json.loads((WORK / "source-manifest.json").read_text())
    observed = {
        name: hashlib.sha256((CHECKOUT / name).read_bytes()).hexdigest() for name in expected
    }

    def git(*args):
        return subprocess.check_output(
            ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", *args],
            cwd=CHECKOUT,
            text=True,
        ).strip()

    module = Path(iniconfig.__file__).resolve()
    distribution = metadata.distribution("iniconfig")
    direct_url = distribution.read_text("direct_url.json")
    result = {
        "system": platform.system(),
        "architecture": platform.machine(),
        "pythonVersion": list(sys.version_info[:3]),
        "pythonExecutable": sys.executable,
        "pythonBinarySha256": hashlib.sha256(
            Path(sys.executable).resolve().read_bytes()
        ).hexdigest(),
        "prefix": sys.prefix,
        "packagePath": str(module),
        "packageSha256": hashlib.sha256(module.read_bytes()).hexdigest(),
        "packageVersion": distribution.version,
        "directUrl": json.loads(direct_url) if direct_url else None,
        "installedPackages": sorted(
            {(d.metadata["Name"], d.version) for d in metadata.distributions()}
        ),
        "trackedSha256": observed,
        "trackedBytesUnchanged": observed == expected,
        "gitHead": git("rev-parse", "HEAD"),
        "gitTree": git("rev-parse", "HEAD^{tree}"),
        "gitDescribe": git("describe", "--tags", "--always", "--dirty"),
        "gitTrackedStatus": git("status", "--porcelain", "--untracked-files=no"),
        "networkDevices": [
            line.split(":", 1)[0].strip()
            for line in Path("/proc/net/dev").read_text().splitlines()[2:]
        ],
    }
    print(json.dumps(result, indent=2))


def network():
    # Separate first-party action: no upstream import precedes this observation.
    result = {}
    for name, arguments in (
        ("links", ["-details", "link", "show"]),
        ("routes4", ["-4", "route", "show", "table", "all"]),
        ("routes6", ["-6", "route", "show", "table", "all"]),
    ):
        result[name] = json.loads(subprocess.check_output(["ip", "-json", *arguments]))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    action = sys.argv[1]
    if action in COMMANDS:
        raise SystemExit(execute(action))
    if action == "probe":
        probe()
    elif action == "network":
        network()
    else:
        raise ValueError("unknown controller action")
