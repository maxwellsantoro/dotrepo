#!/usr/bin/env -S uv run python
"""Admit frozen tar data, then exercise only owned links in fresh Docker sandboxes."""

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH))
from bench import agent_experiment as experiment  # noqa: E402
from bench import agent_runtime as runtime  # noqa: E402

IMAGE = "sha256:8032a060e0198814ffe1868893bf89bdb02fa79f4de617873f23eb8dd3915af4"
PACKET = Path(__file__).resolve().parent


def save(path, value):
    raw = experiment.encode(value)
    path.write_bytes(raw)
    return {"path": path.name, "sha256": experiment.digest(raw)}


def link_entry(target):
    raw = target.encode()
    return {
        "target": target,
        "sha256": experiment.digest(raw),
        "gitBlobSha": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(),
        "mode": "120000",
    }


def full_admission(scratch):
    results = []
    for task in ("python-02", "typescript-01"):
        original = PACKET.parent / task
        acquisition = json.loads((original / "acquisition.json").read_text())
        details = json.loads((original / "file-details.json").read_text())
        inventory = json.loads((original / "inventory.json").read_text())
        inventory["symlinks"] = {
            name: {**entry, "mode": "120000"} for name, entry in details["symlinks"].items()
        }
        # Copy retained regular archive bytes into our private staging root;
        # no tar extraction, host link creation, acquisition or upstream code.
        stage = scratch / task
        stage.mkdir()
        archive = Path(acquisition["archivePath"])
        assert not archive.is_symlink()
        shutil.copyfile(archive, stage / "source.tar")
        spec = {
            "revision": inventory["revision"],
            "archive": {"path": "source.tar", "sha256": acquisition["archiveSha256"]},
            "inventory": save(stage / "inventory.json", inventory),
            "provenance": save(
                stage / "provenance.json", json.loads((original / "provenance.json").read_text())
            ),
        }
        bundle = runtime.source_bundle(stage, spec, inventory["revision"], set(), 1024**3)
        assert bundle.archive == archive.read_bytes()
        assert bundle.symlinks == inventory["symlinks"]
        bound = []
        for name, entry in bundle.symlinks.items():
            raw = json.loads(runtime.source_read(bundle, name))
            assert raw["target"] == entry["target"] and raw["mode"] == "120000"
            bound.append({"path": name, **entry, "resolved": bundle.resolved_links[name]})
        derived = PACKET / f"{task}-link-inventory.json"
        derived.write_bytes(experiment.encode(inventory))
        results.append(
            {
                "task": task,
                "sourceRevision": inventory["revision"],
                "originalArchiveSha256": experiment.digest(bundle.archive),
                "originalInventorySha256": experiment.digest(
                    (original / "inventory.json").read_bytes()
                ),
                "originalDetailsSha256": experiment.digest(
                    (original / "file-details.json").read_bytes()
                ),
                "originalProvenanceSha256": experiment.digest(
                    (original / "provenance.json").read_bytes()
                ),
                "newInventorySha256": experiment.digest(derived.read_bytes()),
                "regularFiles": len(bundle.files),
                "links": bound,
                "hiddenHashes": "Empty for source data admission control; not a campaign arm/gold qualification.",
                "upstreamCodeExecuted": False,
            }
        )
        del bundle
    return results


def fixture(scratch):
    files = {"data/message": b"owned control original\n", "data/run.sh": b"#!/bin/sh\nexit 0\n"}
    links = {"docs": link_entry("data/"), "README": link_entry("docs/message")}
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as stream:
        # Deliberately links first: admission is order independent; transport
        # must still place actual links after every regular member.
        for name, entry in links.items():
            member = tarfile.TarInfo(name)
            member.type, member.linkname, member.mode = tarfile.SYMTYPE, entry["target"], 0o777
            stream.addfile(member)
        for name, raw in files.items():
            member = tarfile.TarInfo(name)
            member.size, member.mode = len(raw), 0o755 if name.endswith(".sh") else 0o644
            stream.addfile(member, io.BytesIO(raw))
    raw = buffer.getvalue()
    (scratch / "source.tar").write_bytes(raw)
    revision = "a" * 40
    spec = {
        "revision": revision,
        "archive": {"path": "source.tar", "sha256": experiment.digest(raw)},
        "inventory": save(
            scratch / "inventory.json",
            {
                "revision": revision,
                "files": {name: experiment.digest(data) for name, data in files.items()},
                "symlinks": links,
                "missingSubmodules": [],
                "missingLfsObjects": [],
                "limitations": ["Owned synthetic control"],
            },
        ),
        "provenance": save(
            scratch / "provenance.json",
            {
                "revision": revision,
                "archiveSha256": experiment.digest(raw),
                "url": "https://example.test/owned-control",
                "checkedAt": "2026-10-29T00:00:00Z",
            },
        ),
    }
    return runtime.source_bundle(scratch, spec, revision, set(), 1000000)


def docker_control(bundle):
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
        "environment": {"HOME": "/workspace/.home", "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
    }
    request = {"environment": {"imageDigest": IMAGE}, "workspaceKey": "owned-source-link-control"}
    receipts = []
    for number in (1, 2):
        backend = runtime.DockerBackend()
        receipt = {"sequence": number, "container": backend.name, "checks": {}, "status": "failed"}
        try:
            receipt["provision"] = backend.provision(request, config, 30)
            receipt["checkout"] = backend.checkout(bundle, 10)
            assert receipt["checkout"]["exitCode"] == 0, receipt["checkout"]
            read = backend.shell(
                "readlink docs; readlink README; cat README; stat -c '%a' data/run.sh; id -u",
                10,
                4096,
            )
            receipt["read"] = read
            receipt["checks"]["links-byte-faithful-modes-nonroot-fresh"] = (
                read["stdout"] == "data/\ndocs/message\nowned control original\n755\n1000\n"
            )
            metadata = backend._call(["inspect", backend.name], 10, limit=131072)
            host = json.loads(metadata["stdout"])[0]
            receipt["checks"]["mount-free-network-none-readonly"] = (
                host["HostConfig"]["NetworkMode"] == "none"
                and host["HostConfig"]["ReadonlyRootfs"]
                and all(m["Type"] == "tmpfs" for m in host["Mounts"])
            )
            if number == 1:
                changed = backend.shell(
                    "printf 'owned changed\n' > docs/message; cat data/message", 10, 4096
                )
                receipt["changed"] = changed
                receipt["checks"]["actual-directory-alias"] = changed["stdout"] == "owned changed\n"
            second = backend.checkout(bundle, 10)
            receipt["secondCheckout"] = second
            receipt["checks"]["fresh-directory-refuses-merge"] = (
                second["exitCode"] != 0 and second["sourceCopy"]["stdinBytes"] == 0
            )
            copy = receipt["checkout"]["sourceCopy"]
            receipt["checks"]["copy-byte-accounting"] = (
                copy["stdinBytes"] > len(bundle.archive) and len(copy["archives"]) == 2
            )
            assert all(receipt["checks"].values()), receipt["checks"]
            receipt["status"] = "passed"
        except Exception as exc:
            receipt["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            receipt["cleanup"] = backend.cleanup()
            absent = backend._call(["inspect", backend.name], 10, limit=4096)
            receipt["absentAfterCleanup"] = absent
            receipt["checks"]["cleanup-independently-confirmed"] = (
                receipt["cleanup"]["exitCode"] == 0 and absent["exitCode"] != 0
            )
            receipt["operations"] = backend.operations
            if not receipt["checks"]["cleanup-independently-confirmed"]:
                receipt["status"] = "failed"
            receipts.append(receipt)
    return receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", action="store_true")
    args = parser.parse_args()
    scratch = Path(tempfile.mkdtemp(prefix="dotrepo-source-links-", dir="/tmp"))
    result = {
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "runtimeSha256": experiment.digest(Path(runtime.__file__).read_bytes()),
        "driverSha256": experiment.digest(Path(__file__).read_bytes()),
        "image": IMAGE,
        "providerCalls": 0,
        "upstreamExecution": False,
        "scratch": str(scratch),
        "status": "failed",
    }
    try:
        result["actualSourceAdmission"] = full_admission(scratch)
        owned = scratch / "owned"
        owned.mkdir()
        bundle = fixture(owned)
        result["ownedFixtureArchiveSha256"] = experiment.digest(bundle.archive)
        if args.docker:
            result["docker"] = docker_control(bundle)
            assert all(r["status"] == "passed" for r in result["docker"])
        result["status"] = "passed"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    (PACKET / "qualification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {"status": result["status"], "error": result.get("error"), "scratch": str(scratch)}
        )
    )
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
