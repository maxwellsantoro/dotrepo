"""Bind actual retained cache bytes to draft runtime dependency-cache specs.

No audit flag is upgraded here; independent review and offline qualification are
mandatory. Only local data is read. Full archive bytes stay outside Git in /tmp.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile

HERE = Path(__file__).resolve().parent
SCRATCH = Path("/tmp/dotrepo-f05-dependency-preparation-20261029")


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024**2):
            digest.update(chunk)
    return digest.hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def artifact(path, label=None):
    return {"path": label or path.name, "sha256": sha(path)}


def main():
    common = json.loads((HERE / "common-image.json").read_text())
    plan = json.loads((HERE / "plan.v3.json").read_text())
    native = (HERE / "image-attempt-3/logs/tools/stdout.txt").read_text()
    tasks = []
    for task_id, spec in plan["tasks"].items():
        producer_script, producer_plan = "prepare.v3.py", "plan.v3.json"
        leaf = task_id
        if task_id == "rust-02":
            leaf = "rust-02-attempt-2"
            producer_script, producer_plan = "prepare.v4.py", "plan.v4.json"
            spec = json.loads((HERE / producer_plan).read_text())["tasks"][task_id]
        folder, scratch = HERE / leaf, SCRATCH / leaf
        result = json.loads((folder / "result.json").read_text())
        if result["state"] != "download-cache-retained-unqualified":
            tasks.append(result)
            continue
        cache = Path(result["archivePath"])
        inventory = json.loads((folder / "inventory.json").read_text())
        actual, expanded = {}, 0
        with tarfile.open(cache, mode="r:") as archive:
            for member in archive:
                name = member.name
                assert member.isfile() and name not in actual
                assert (
                    not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts
                )
                assert any(name.startswith(root + "/") for root in spec["roots"])
                raw = archive.extractfile(member).read()
                actual[name] = hashlib.sha256(raw).hexdigest()
                expanded += len(raw)
        assert actual == inventory["files"] and sha(cache) == result["archiveSha256"]
        assert expanded == result["cacheExpandedBytes"] <= 1024**3
        receipts = {}
        for receipt in sorted((folder / "logs").glob("*/receipt.json")):
            value = json.loads(receipt.read_text())
            for role in ("stdout", "stderr"):
                assert sha(receipt.parent / f"{role}.txt") == value[f"{role}Sha256"]
            receipts[str(receipt.relative_to(folder))] = value
        trace = {
            "identity": "download-only-native-trace-v1",
            "receipts": receipts,
            "exportReceipt": json.loads((folder / "cache-export-receipt.json").read_text()),
            "result": result,
            "frozenPlan": artifact(HERE / producer_plan),
        }
        write(folder / "trace.json", trace)
        prep = {
            "imageDigest": common["imageId"],
            "revision": spec["revision"],
            "sourceArchiveSha256": spec["sourceArchiveSha256"],
            "cacheArchiveSha256": result["archiveSha256"],
            "scriptSha256": sha(HERE / producer_script),
            "scriptClosure": json.loads((HERE / producer_plan).read_text())["scripts"],
            "planSha256": sha(HERE / producer_plan),
            "traceSha256": sha(folder / "trace.json"),
            "downloadOnly": True,
            "buildOutputsExcluded": False,
            "taskSourceExcluded": False,
            "credentialsExcluded": False,
            "auditState": "draft-unqualified; false audit flags mean independent content/member review is pending, not a detected inclusion",
            "preparationCostUsd": None,
            "toolVersions": {
                "commonImageNativeProbe": native,
                "taskNativeProbe": (folder / "logs/tools-after-download/stdout.txt").read_text(),
            },
            "limitations": [
                "These draft flags intentionally fail runtime cache admission until independent audit; do not replace false with true mechanically.",
                "Root prefix/regular-file/size/hash checks passed, but content classification, protected evaluation aliases and absence of credentials have not been independently audited.",
                "No source tests/build scripts executed. Common-image tool availability does not prove task/environment equivalence or offline cache completeness.",
                "npm temporary tooling installation and checkout node_modules are not exported. A future session needs a frozen offline setup policy for npm11.12.1 installation from retained content.",
                "Costs are unavailable, not zero; native transfer counters and elapsed preparation are separately retained.",
            ],
        }
        write(folder / "preparation.json", prep)
        cache_spec = {
            "bundle": {
                "revision": spec["revision"],
                "archive": artifact(cache),
                "inventory": artifact(folder / "inventory.json"),
                "provenance": artifact(folder / "provenance.json"),
            },
            "preparation": artifact(folder / "preparation.json"),
            "script": artifact(HERE / producer_script),
            "trace": artifact(folder / "trace.json"),
        }
        write(folder / "dependency-cache-spec.json", cache_spec)
        for source in [
            folder / "inventory.json",
            folder / "provenance.json",
            folder / "preparation.json",
            folder / "trace.json",
            folder / "dependency-cache-spec.json",
            HERE / producer_script,
            HERE / producer_plan,
            HERE / "control.py",
            HERE / "capture.py",
        ]:
            shutil.copyfile(source, scratch / source.name)
        tasks.append(
            {
                **result,
                "scratchArtifactRoot": str(scratch),
                "draftRuntimeSpec": str((folder / "dependency-cache-spec.json").relative_to(HERE)),
                "preparationSha256": sha(folder / "preparation.json"),
                "inventorySha256": sha(folder / "inventory.json"),
                "traceSha256": sha(folder / "trace.json"),
                "nativeReceiptsVerified": len(receipts),
            }
        )
    write(
        HERE / "report.json",
        {
            "identity": "f05-source-free-common-image-download-caches-v1",
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "commonImage": common,
            "tasks": tasks,
            "state": "candidate tools plus draft download caches; independent audit and actual offline task requalification pending",
            "all12EnvironmentQualified": False,
            "modelCalls": 0,
            "upstreamTaskExecution": False,
            "indexConsulted": False,
            "vmChanged": False,
            "costUsd": None,
            "costExclusions": ["No metered Docker/host/download charge source."],
        },
    )


if __name__ == "__main__":
    main()
