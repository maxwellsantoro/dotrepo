"""Build the owned probe command manifest; no external actions."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = Path("/Users/maxwell/projects/agent/dotrepo/benchmarks/head-to-head")
PARENT = Path("/tmp/dotrepo-f05-python01-environment-plan-20261029")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parent = json.loads((PARENT / "plan.json").read_bytes())
    image = (
        BASE / "f05-dependency-preparation-20261029/image-attempt-3/logs/image-inspect/stdout.txt"
    )
    reused = [
        BASE / "f05-go01-dependency-preparation-20261029/prepare.py",
        BASE / "f05-go01-offline-setup-plan-20261029/amendment-1/setup.py",
        BASE / "f05-go01-collection-driver-20261029/amendment-3/collection.py",
    ]
    p = {
        "identity": "python01-source-free-probe-driver-v1",
        "parentFreezeSha256": sha(PARENT / "FREEZE.json"),
        "parentPlanSha256": sha(PARENT / "plan.json"),
        "environmentPlanReview": {
            "path": "/tmp/dotrepo-f05-python01-environment-plan-review-20261029/FREEZE.json",
            "sha256": sha(
                Path("/tmp/dotrepo-f05-python01-environment-plan-review-20261029/FREEZE.json")
            ),
        },
        "probe": parent["probe"],
        "imageId": parent["image"]["id"],
        "imageEnvironment": json.loads(image.read_bytes())[0]["Config"]["Env"],
        "retainedImageInspect": {"path": str(image), "sha256": sha(image)},
        "limits": {
            "workSeconds": 900,
            "cleanupSeconds": 60,
            "probeSeconds": 60,
            "combinedStdoutStderrBytes": 2097152,
            "probeMetadataBytes": 16384,
            "cpus": 3,
            "memoryBytes": 4294967296,
            "pids": 256,
        },
        "scripts": {
            n: sha(HERE / n)
            for n in ["driver.py", "controls.py", "make_plan.py", "process_io.py", "boundaries.py"]
        },
        "reusedSources": {str(n): sha(n) for n in reused},
        "transportProvenance": {
            "original": str(BASE / "f05-go01-source-registry-runtime-20261029/process_io.py"),
            "sha256": sha(HERE / "process_io.py"),
            "unchanged": True,
            "priorReviewFreeze": str(
                BASE / "f05-go01-source-registry-runtime-review-20261029/FREEZE.json"
            ),
            "priorReviewFreezeSha256": sha(
                BASE / "f05-go01-source-registry-runtime-review-20261029/FREEZE.json"
            ),
        },
        "executionAuthorized": False,
        "dependencySetupAuthorized": False,
        "actualAdmission": False,
        "oracleQualified": False,
        "campaignAdmitted": False,
        "costUsd": None,
    }
    assert sha(HERE / "process_io.py") == sha(
        BASE / "f05-go01-source-registry-runtime-20261029/process_io.py"
    )
    assert sha(HERE / "boundaries.py") == sha(
        BASE / "f05-go01-dependency-preparation-20261029/boundaries.py"
    )
    (HERE / "plan.json").write_text(json.dumps(p, indent=2) + "\n")
    print("manifest assembled; execution unauthorized")


if __name__ == "__main__":
    main()
