#!/usr/bin/env -S uv run python
"""Exercise the real Docker backend with an owned ELF-copy control, no provider."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import tarfile
import time

BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH))
from bench import agent_runtime as current_runtime  # noqa: E402


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--runtime-source", type=Path)
    parser.add_argument("--expect-exec", choices=("allowed", "denied"), required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", args.image):
        parser.error("image must be an exact locally qualified image ID")
    args.out.mkdir(parents=True, exist_ok=False)
    runtime = current_runtime
    source = Path(runtime.__file__)
    if args.runtime_source:
        source = args.runtime_source
        loader = importlib.machinery.SourceFileLoader("bench.backend_control_baseline", str(source))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        runtime = importlib.util.module_from_spec(spec)
        sys.modules[loader.name] = runtime
        loader.exec_module(runtime)

    raw = b"Owned backend control; no repository task, profile or answer.\n"
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        member = tarfile.TarInfo("README.md")
        member.size, member.mode = len(raw), 0o644
        archive.addfile(member, io.BytesIO(raw))
    bundle = runtime.SourceBundle(buffer.getvalue(), {"README.md": raw}, {}, "control")
    request = {"environment": {"imageDigest": args.image}, "workspaceKey": "backend-control"}
    config = {
        # Synthetic admission values exercise only the backend. They do not
        # qualify a provider, task environment, cache, or campaign launch.
        "qualifications": dict.fromkeys(runtime.QUALIFICATIONS, True),
        "containerUser": "1000:1000",
        "resources": {
            "memoryBytes": 268435456,
            "cpus": 1,
            "pidsLimit": 32,
            "workspaceBytes": 8388608,
            "tmpBytes": 8388608,
        },
        "environment": {"HOME": "/workspace/.home", "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
    }
    result = {
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "runtimeSha256": sha(source.read_bytes()),
        "driverSha256": sha(Path(__file__).read_bytes()),
        "imageId": args.image,
        "expectedExecution": args.expect_exec,
        "controlSourceSha256": sha(bundle.archive),
        "configuration": config,
        "qualificationScope": "backend-only synthetic controls; no provider or task qualification",
        "providerCalls": 0,
        "providerCostUsd": None,
        "checks": {},
        "status": "failed",
    }
    backend, started = runtime.DockerBackend(), time.monotonic()
    try:
        result["provision"] = backend.provision(request, config, 30)
        checkout = backend.checkout(bundle, 10)
        assert checkout["exitCode"] == 0, checkout
        observed = {}
        for name, command in (
            (
                "workspace-execution",
                "cp /bin/true ./control-elf && chmod 700 ./control-elf && ./control-elf",
            ),
            (
                "tmp-execution",
                "cp /bin/true /tmp/control-elf && chmod 700 /tmp/control-elf && /tmp/control-elf",
            ),
            ("nonroot", "id -u"),
            ("readonly-root", "printf forbidden > /usr/control-forbidden"),
        ):
            observed[name] = backend.shell(command, 10, 4096)
        allowed = args.expect_exec == "allowed"
        for name in ("workspace-execution", "tmp-execution"):
            result["checks"][name] = (observed[name]["exitCode"] == 0) == allowed
        result["checks"]["nonroot"] = observed["nonroot"]["stdout"].strip() == "1000"
        result["checks"]["readonly-root"] = observed["readonly-root"]["exitCode"] != 0
        inspect = backend._call(["inspect", backend.name], 10, limit=131072)
        metadata = json.loads(inspect["stdout"])[0]
        host = metadata["HostConfig"]
        result["checks"]["network-none"] = host["NetworkMode"] == "none"
        result["checks"]["no-host-mounts"] = all(
            mount["Type"] == "tmpfs" for mount in metadata["Mounts"]
        )
        result["checks"]["bounded-readonly"] = (
            host["ReadonlyRootfs"] and host["Memory"] == config["resources"]["memoryBytes"]
        )
        flood = backend.shell("yes control", 5, 1024)
        result["checks"]["bounded-output"] = (
            flood["error"] == "output-limit"
            and len((flood["stdout"] + flood["stderr"]).encode()) <= 1024
        )
        timeout = backend.shell("sleep 5", 0.2, 1024)
        result["checks"]["bounded-time"] = timeout["error"] == "timeout"
        result["observations"] = observed
        assert all(result["checks"].values()), result["checks"]
        result["status"] = "passed"
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
    finally:
        cleanup = backend.cleanup()
        result["cleanup"] = cleanup
        result["checks"]["cleanup"] = cleanup["exitCode"] == 0
        if not result["checks"]["cleanup"]:
            result["status"] = "failed"
        result["elapsedSeconds"] = time.monotonic() - started
        result["operations"] = backend.operations
        (args.out / "receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "checks": result["checks"]}))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
