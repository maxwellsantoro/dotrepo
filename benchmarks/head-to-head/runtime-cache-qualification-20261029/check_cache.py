#!/usr/bin/env -S uv run python
"""Real Docker copy isolation with owned cache bytes, no upstream or provider."""

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile

BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH))
from bench import agent_runtime as runtime  # noqa: E402


def bundle(path, raw):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        member = tarfile.TarInfo(path)
        member.size, member.mode = len(raw), 0o600
        archive.addfile(member, io.BytesIO(raw))
    return runtime.SourceBundle(stream.getvalue(), {path: raw}, {}, "owned-control")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False, parents=True)
    cache = bundle("cargo/registry/cache/owned-control", b"initial-owned-cache\n")
    source = bundle("README.md", b"owned source; no task answers\n")
    config = {
        "qualifications": dict.fromkeys(runtime.QUALIFICATIONS, True),
        "containerUser": "1000:1000",
        "resources": {
            "memoryBytes": 268435456,
            "cpus": 1,
            "pidsLimit": 32,
            "workspaceBytes": 8388608,
            "tmpBytes": 8388608,
        },
        "environment": {"HOME": "/workspace/.home", "PATH": "/usr/bin:/bin"},
    }
    receipt = {
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "scope": "Synthetic backend copy controls only; no dependency/task/provider qualification",
        "driverSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "runtimeSha256": hashlib.sha256(Path(runtime.__file__).read_bytes()).hexdigest(),
        "cacheArchiveSha256": hashlib.sha256(cache.archive).hexdigest(),
        "imageId": args.image,
        "providerCalls": 0,
        "preparationCostUsd": None,
        "status": "failed",
        "sessions": [],
    }
    try:
        for index in range(2):
            backend = runtime.DockerBackend()
            session = {"container": backend.name, "checks": {}}
            receipt["sessions"].append(session)
            try:
                request = {
                    "environment": {"imageDigest": args.image},
                    "workspaceKey": f"cache-control/{index}",
                }
                backend.provision(request, config, 30)
                seeded = backend.seed_dependencies(cache, 10)
                assert seeded["exitCode"] == 0 and not seeded["error"]
                # Pre-clone state stays empty of task source after cache seeding.
                absent = backend._call(
                    ["exec", backend.name, "/bin/sh", "-c", "test ! -e /workspace/repository"], 10
                )
                session["checks"]["preclone-source-absent"] = absent["exitCode"] == 0
                assert backend.checkout(source, 10)["exitCode"] == 0
                original = backend.shell(
                    "cat /workspace/dependency-cache/cargo/registry/cache/owned-control", 10, 1024
                )
                session["checks"]["fresh-cache-bytes"] = (
                    original["stdout"] == "initial-owned-cache\n"
                )
                result = backend.shell(
                    "printf session-mutation > /workspace/dependency-cache/cargo/registry/cache/owned-control",
                    10,
                    1024,
                )
                session["checks"]["private-copy-writable"] = result["exitCode"] == 0
                assert all(session["checks"].values()), session
            finally:
                session["cleanup"] = backend.cleanup()
                session["operations"] = backend.operations
                absent = backend._call(["container", "inspect", backend.name], 10)
                session["absence"] = absent
                assert session["cleanup"]["exitCode"] == 0
                assert absent["exitCode"] == 1 and "No such container" in absent["stderr"]
        receipt["status"] = "passed"
    except Exception as error:
        receipt["error"] = f"{type(error).__name__}: {error}"
    finally:
        (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "sessions": len(receipt["sessions"])}))
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
