"""Read-only local verification of this bounded preparation evidence.

Requires retained scratch source/cache archives. No daemon, network, runtime
module, provider or project code is invoked. Costs/audits remain unavailable.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

HERE = Path(__file__).resolve().parent
FIRST = HERE.parent / "f05-qualification-20261029"
SCRATCH = Path("/tmp/dotrepo-f05-dependency-preparation-20261029")


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while raw := stream.read(1024**2):
            digest.update(raw)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    old = json.loads((FIRST / "artifact-hashes.json").read_text())["files"]
    for path, digest in old.items():
        assert sha(FIRST / path) == digest, path
    for name in ["plan.json", "plan.v2.json", "plan.v3.json", "plan.v4.json"]:
        plan = json.loads((HERE / name).read_text())
        for path, digest in plan["scripts"].items():
            assert sha(HERE / path) == digest
    common = json.loads((HERE / "common-image.json").read_text())
    image = json.loads((HERE / "image-attempt-3/logs/image-inspect/stdout.txt").read_text())[0]
    assert common["imageId"] == image["Id"]
    assert common["recipeSha256"] == sha(HERE / "Dockerfile.v3")
    assert not image["Config"].get("Volumes") and not image["Config"].get("OnBuild")
    assert {row.split("=", 1)[0] for row in image["Config"]["Env"]} == {
        "PATH",
        "RUSTUP_HOME",
        "CARGO_HOME",
        "GOTOOLCHAIN",
        "GOENV",
    }
    plan = json.loads((HERE / "plan.v3.json").read_text())
    tasks = []
    for task_id, spec in plan["tasks"].items():
        leaf = "rust-02-attempt-2" if task_id == "rust-02" else task_id
        folder, scratch = HERE / leaf, SCRATCH / leaf
        result = json.loads((folder / "result.json").read_text())
        cache_spec = json.loads((folder / "dependency-cache-spec.json").read_text())
        for role in ["preparation", "script", "trace"]:
            artifact = cache_spec[role]
            assert sha(scratch / artifact["path"]) == artifact["sha256"]
        bundle = cache_spec["bundle"]
        for role in ["archive", "inventory", "provenance"]:
            artifact = bundle[role]
            assert sha(scratch / artifact["path"]) == artifact["sha256"]
        inventory = json.loads((folder / "inventory.json").read_text())
        provenance = json.loads((folder / "provenance.json").read_text())
        prep = json.loads((folder / "preparation.json").read_text())
        assert prep["imageDigest"] == common["imageId"] == result["imageId"]
        assert prep["sourceArchiveSha256"] == spec["sourceArchiveSha256"]
        assert prep["revision"] == spec["revision"] == bundle["revision"]
        assert (
            prep["cacheArchiveSha256"] == bundle["archive"]["sha256"] == provenance["archiveSha256"]
        )
        assert prep["downloadOnly"] is True and all(
            prep[key] is False
            for key in ["buildOutputsExcluded", "taskSourceExcluded", "credentialsExcluded"]
        )
        assert prep["preparationCostUsd"] is None and result["cacheAuditQualified"] is False
        files, expanded = {}, 0
        with tarfile.open(scratch / bundle["archive"]["path"], mode="r:") as archive:
            for member in archive:
                name = member.name
                path = PurePosixPath(name)
                assert member.isfile() and name not in files
                assert not path.is_absolute() and ".." not in path.parts
                assert any(name.startswith(root + "/") for root in spec["roots"])
                assert member.uid == member.gid == member.mtime == 0 and member.mode in [
                    0o644,
                    0o755,
                ]
                raw = archive.extractfile(member).read()
                files[name] = hashlib.sha256(raw).hexdigest()
                expanded += len(raw)
        source = json.loads((FIRST / spec["sourceFolder"] / "acquisition.json").read_text())
        assert sha(Path(source["runtimeArchivePath"])) == spec["sourceArchiveSha256"]
        assert sha(FIRST / spec["sourceFolder"] / "inventory.json") == spec["sourceInventorySha256"]
        assert expanded <= 1024**3 and expanded + source["sourceBytes"] <= 2 * 1024**3
        assert Path(result["archivePath"]).stat().st_size <= 512 * 1024**2
        assert (
            inventory["files"] == files
            and inventory["missingSubmodules"] == inventory["missingLfsObjects"] == []
        )
        assert result["setupSeconds"] <= 900
        offline = json.loads((folder / "logs/offline-inspect/stdout.txt").read_text())[0]
        assert not offline["Mounts"] and not offline["NetworkSettings"]["Networks"]
        assert offline["HostConfig"]["ReadonlyRootfs"] and offline["HostConfig"]["CapDrop"] == [
            "ALL"
        ]
        tasks.append(
            {
                "taskId": task_id,
                "cacheFiles": len(files),
                "expandedBytes": expanded,
                "archiveBytes": Path(result["archivePath"]).stat().st_size,
                "archiveSha256": result["archiveSha256"],
                "draftAdmissionRefused": True,
            }
        )
    receipts = list(HERE.glob("**/logs/*/receipt.json"))
    for path in receipts:
        row = json.loads(path.read_text())
        for role in ["stdout", "stderr"]:
            assert sha(path.parent / f"{role}.txt") == row[f"{role}Sha256"]
        assert row["costUsd"] is None
    report = {
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "status": "passed",
        "priorFrozenArtifactsVerified": len(old),
        "commandReceiptsVerified": len(receipts),
        "tasks": tasks,
        "limitations": [
            "Internal byte/contract consistency only, not provenance authenticity.",
            "Audit flags intentionally refuse live runtime admission. Independent content/protected-alias audit and offline full task requalification remain necessary.",
            "No daemon, source execution, provider/model or index/profile access.",
        ],
    }
    if args.output:
        with args.output.open("x") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
    else:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
