"""Read-only source/hash verification; never instantiate a Docker backend."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    freeze = json.loads((HERE / "FREEZE.json").read_bytes())
    for name, b in freeze["artifacts"].items():
        p = HERE / name
        assert p.is_file() and not p.is_symlink(), name
        assert (
            p.stat().st_size == b["bytes"]
            and hashlib.sha256(p.read_bytes()).hexdigest() == b["sha256"]
        ), name
    plan = json.loads((HERE / "plan.json").read_bytes())
    parent = Path("/tmp/dotrepo-f05-python01-environment-plan-20261029")
    assert (
        hashlib.sha256((parent / "FREEZE.json").read_bytes()).hexdigest()
        == plan["parentFreezeSha256"]
    )
    assert (
        hashlib.sha256((parent / "plan.json").read_bytes()).hexdigest() == plan["parentPlanSha256"]
    )
    for path, digest in plan["reusedSources"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, path
    provenance = plan["transportProvenance"]
    assert (
        hashlib.sha256(Path(provenance["original"]).read_bytes()).hexdigest()
        == provenance["sha256"]
    )
    assert (
        hashlib.sha256(Path(provenance["priorReviewFreeze"]).read_bytes()).hexdigest()
        == provenance["priorReviewFreezeSha256"]
    )
    controls = json.loads((HERE / "controls.json").read_bytes())
    assert (
        controls["count"] == 26
        and not controls["probeExecuted"]
        and controls["actualDaemonCalls"] == 0
    )
    assert not freeze["executionAuthorized"] and not plan["executionAuthorized"]
    print(
        f"{len(freeze['artifacts'])} driver artifacts and immutable parent/reused helper bindings match"
    )


if __name__ == "__main__":
    main()
