"""Read-only integrity verification for this source-only receiver amendment."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    parent = json.loads((PARENT / "FREEZE.json").read_text())
    assert sha(PARENT / "FREEZE.json") == (
        "b2fd2550fd9ca1b5dc20774badfb77863e28236cc0535f11c6012a5aa6a0ab8d"
    )
    for name, digest in parent["artifactSha256"].items():
        assert sha(PARENT / name) == digest, name
    local = parent["localDerivedInput"]
    assert sha(Path(local["path"])) == local["sha256"]
    assert Path(local["path"]).stat().st_size == local["bytes"]
    review_path = ROOT / "benchmarks/head-to-head/f05-go01-source-registry-review-20261029"
    assert sha(review_path / "FREEZE.json") == (
        "df6d752afd787928917416664c879a5422edf632750ba3e2d52cb37f2edce074"
    )
    review = json.loads((review_path / "FREEZE.json").read_text())
    # Reviewer freezes use the same relative artifact map as the source proposal.
    for name, digest in review["artifacts"].items():
        assert sha(review_path / name) == digest["sha256"], name
        assert (review_path / name).stat().st_size == digest["bytes"], name
    plan = json.loads((HERE / "plan.json").read_text())
    original_plan = json.loads((PARENT / "plan.json").read_text())
    for key in ["helperBuildContextProspective", "sourceContext", "input", "inputBounds"]:
        assert plan[key] == original_plan[key], key
    subject = json.loads((HERE / "subject.json").read_text())
    assert subject["planSha256"] == sha(HERE / "plan.json")
    for name, digest in subject["pythonSha256"].items():
        assert sha(HERE / name) == digest, name
    for name, binding in subject["helperSourceBindings"].items():
        assert sha(ROOT / binding["path"]) == binding["sha256"], name
    assert (HERE / "constructor_controls.py").read_bytes() == (
        PARENT / "constructor_controls.py"
    ).read_bytes()
    assert (HERE / "receiver_controls.py").read_bytes() == (
        PARENT / "receiver_controls.py"
    ).read_bytes()
    return {
        "state": "verified-source-only-amendment-integrity",
        "parentArtifactsUnchanged": len(parent["artifactSha256"]),
        "beforeReviewArtifactsUnchanged": len(review["artifacts"]),
        "inputBytesUnchanged": local["bytes"],
        "inputSha256": local["sha256"],
        "helperSourcesUnchanged": 3,
        "helperEnvironmentAndPathsUnchanged": True,
        "GoCompiledOrRun": False,
        "nativeCollectionOccurred": False,
        "collectionGateChanged": False,
        "oracleQualified": False,
        "executionAuthorized": False,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, sort_keys=True))
