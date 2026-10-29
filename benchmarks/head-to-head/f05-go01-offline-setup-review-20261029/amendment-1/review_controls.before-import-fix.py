"""Synthetic amendment review; real processes and sockets are prohibited."""

import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import runpy
import socket
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = Path("/Users/maxwell/projects/agent/dotrepo")
AUTHOR = ROOT / "benchmarks/head-to-head/f05-go01-offline-setup-plan-20261029"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def denied(*args, **kwargs):
    raise AssertionError("Real process/network action prohibited in review")


subprocess.Popen = denied
socket.socket = denied
socket.create_connection = denied


def main():
    source = AUTHOR / "amendment-1"
    assert sha(source / "freeze.json") == (
        "eff3d9798e00f55009fe1ae754b04a20ee9bd1d75f1ed5264c99d797df54e032"
    )
    frozen = json.loads((source / "freeze.json").read_text())
    for name, digest in frozen["artifactSha256"].items():
        assert sha(source / name) == digest, name
    original = json.loads((AUTHOR / "freeze.json").read_text())
    assert all(sha(AUTHOR / name) == digest for name, digest in original["artifactSha256"].items())
    before = json.loads((HERE.parent / "FREEZE.json").read_text())
    assert all(
        sha(HERE.parent / name) == digest for name, digest in before["artifactSha256"].items()
    )
    copied = HERE / "isolated-copy"
    copied.mkdir()
    (copied / "plan.json").write_bytes((AUTHOR / "plan.json").read_bytes())
    nested = copied / "amendment-1"
    nested.mkdir()
    for name, digest in frozen["artifactSha256"].items():
        if name == "controls.json":
            continue
        (nested / name).write_bytes((source / name).read_bytes())
        assert sha(nested / name) == digest
    sys.path.insert(0, str(nested))
    runpy.run_path(str(nested / "controls.py"), run_name="__main__")
    import controls
    import setup

    plan = setup.load_plan()
    base = controls.metadata(plan)
    env = dict(value.split("=", 1) for value in base["Config"]["Env"])
    results = []
    for name, key, value in [
        ("original-shared-pid", "PidMode", "container:another"),
        ("original-added-cap", "CapAdd", ["SYS_ADMIN"]),
        ("original-host-ipc", "IpcMode", "host"),
        ("unknown-pid", "PidMode", "unknown"),
        ("unknown-cgroup", "CgroupnsMode", "unknown"),
        (
            "security-disabled-plus-safe",
            "SecurityOpt",
            ["no-new-privileges", "no-new-privileges=false"],
        ),
        ("security-unknown", "SecurityOpt", ["unknown"]),
        ("init-integer", "Init", 1),
        ("capadd-scalar", "CapAdd", ""),
        ("published-port", "PortBindings", {"123/tcp": [{}]}),
        ("shared-userns", "UsernsMode", "container:another"),
        ("bridge-network", "NetworkMode", "bridge"),
    ]:
        row = deepcopy(base)
        row["HostConfig"][key] = value
        try:
            setup.inspect(row, env)
        except (ValueError, KeyError, TypeError):
            rejected = True
        else:
            rejected = False
        assert rejected, name
        results.append({"case": name, "rejected": True})
    for caps in [None, []]:
        row = deepcopy(base)
        row["HostConfig"]["CapAdd"] = caps
        setup.inspect(row, env)
        results.append({"case": "exact-positive-capadd-" + repr(caps), "accepted": True})
    for key in ["Init", "DeviceRequests", "UsernsMode", "UTSMode", "PortBindings"]:
        row = deepcopy(base)
        del row["HostConfig"][key]
        try:
            setup.inspect(row, env)
        except (ValueError, KeyError, TypeError):
            pass
        else:
            raise AssertionError("Missing required field accepted: " + key)
        results.append({"case": "missing-" + key, "rejected": True})

    def functions(path):
        return {
            node.name: ast.dump(node, include_attributes=False)
            for node in ast.parse(path.read_text()).body
            if isinstance(node, ast.FunctionDef)
        }

    old_functions, new_functions = functions(AUTHOR / "setup.py"), functions(source / "setup.py")
    unchanged = [name for name in old_functions if old_functions[name] == new_functions[name]]
    assert set(old_functions) - set(unchanged) == {"inspect"}
    results.append({"case": "only-inspect-function-changed", "unchangedFunctions": unchanged})
    prior_path = ROOT / (
        "benchmarks/head-to-head/f05-offline-results-20261029/typescript-02/"
        "raw/logs/container-inspect/stdout.txt"
    )
    assert sha(prior_path) == "603bdf52c550ae67d8a5a2335d41bcf8ab8f7a7d35ed1f2edb83d159366e4ada"
    prior_host = json.loads(prior_path.read_text())[0]["HostConfig"]
    policy = json.loads((source / "inspect-policy.json").read_text())
    assert all(prior_host[key] == value for key, value in policy["required"].items())
    assert prior_host["CapAdd"] is None
    results.append(
        {
            "case": "required-policy-matches-historical-inspect",
            "historicalSourceSha256": sha(prior_path),
        }
    )
    setup.write(
        HERE / "independent-controls.json",
        {
            "authorFreezeSha256": sha(source / "freeze.json"),
            "authorControlsPassed": 64,
            "independentCases": results,
            "actualSetupOccurred": False,
            "realProcessNetworkPackageNativeProviderCalls": 0,
            "originalArtifactsUnchanged": 18,
            "beforeReviewArtifactsUnchanged": 16,
        },
    )
    print(json.dumps({"independentCasesPassed": len(results), "actualSetupOccurred": False}))


if __name__ == "__main__":
    main()
