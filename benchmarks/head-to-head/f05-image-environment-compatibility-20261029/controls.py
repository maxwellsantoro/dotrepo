"""Replay exact retained image metadata through owned mock transport only."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
from bench import agent_runtime  # noqa: E402


def load_before():
    path = HERE / "before/agent_runtime.py"
    name = "bench.image_environment_before"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def observe(module, raw):
    image = json.loads(raw)[0]
    config = {
        "qualifications": dict.fromkeys(module.QUALIFICATIONS, True),
        "containerUser": "1000:1000",
        "environment": {"HOME": "/workspace/.home"},
        "resources": {
            "memoryBytes": 4294967296,
            "cpus": 3,
            "pidsLimit": 256,
            "workspaceBytes": 8589934592,
            "tmpBytes": 536870912,
        },
    }
    request = {
        "environment": {"imageDigest": image["Id"]},
        "workspaceKey": "owned-fixture/image-environment/replay",
    }
    commands = []

    def fake(argv, **kwargs):
        commands.append(argv)
        return {
            "stdout": raw.decode() if argv[1:3] == ["image", "inspect"] else "owned-mock-id",
            "stderr": "",
            "exitCode": 0,
            "error": None,
        }

    backend = module.DockerBackend(fake)
    error = None
    try:
        result = backend.provision(request, config, 10)
    except ValueError as exc:
        error, result = str(exc), None
    created = backend.created
    cleanup = backend.cleanup()
    return {
        "runtimeSha256": hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
        "error": error,
        "result": result,
        "mockCommands": commands,
        "createdFlagAfterProvision": created,
        "cleanupMockExitCode": cleanup["exitCode"],
        "actualDaemonCalls": 0,
        "actualAdmission": False,
        "qualificationsNote": "Synthetic qualification flags only unlock owned mock preflight.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), "use a fresh output path"
    source = ROOT / (
        "benchmarks/head-to-head/f05-dependency-preparation-20261029/"
        "image-attempt-3/logs/image-inspect/stdout.txt"
    )
    raw = source.read_bytes()
    before, after = observe(load_before(), raw), observe(agent_runtime, raw)
    assert before["error"] == "image contains nonallowlisted environment"
    assert [a[1] for a in before["mockCommands"]] == ["image"]
    assert after["error"] is None
    assert [a[1] for a in after["mockCommands"]] == ["image", "create", "start", "rm"]
    created = after["mockCommands"][1]
    assert not any(a.startswith(("GOENV=", "GOTOOLCHAIN=")) for a in created)
    assert {"--network=none", "--read-only", "--cap-drop=ALL", "--pull=never"} <= set(created)
    report = {
        "scope": "Offline owned mock replay; no daemon/provider/upstream code execution",
        "imageMetadataSha256": hashlib.sha256(raw).hexdigest(),
        "before": before,
        "after": after,
        "actualAdmission": False,
        "executionAuthorized": False,
        "taskOutcomeObserved": False,
        "oracleQualified": False,
        "campaignAdmitted": False,
        "costUsd": None,
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("before rejected; after mocked image/create/start/cleanup; no injected Go defaults")


if __name__ == "__main__":
    main()
