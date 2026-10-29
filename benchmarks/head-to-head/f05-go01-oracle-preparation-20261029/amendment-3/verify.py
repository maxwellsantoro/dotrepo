"""Read-only exact packet/dependency hashes, not execution qualification."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def verify():
    bindings = json.loads((HERE / "source-bindings.json").read_bytes())
    for row in bindings["files"]:
        raw = (ROOT / row["path"]).read_bytes()
        assert len(raw) == row["bytes"] and hashlib.sha256(raw).hexdigest() == row["sha256"], row[
            "path"
        ]
    freeze = json.loads((HERE / "FREEZE.json").read_bytes())
    for path, row in freeze["artifacts"].items():
        raw = (HERE / path).read_bytes()
        assert len(raw) == row["bytes"] and hashlib.sha256(raw).hexdigest() == row["sha256"], path
    print(
        json.dumps(
            {
                "boundInputs": len(bindings["files"]),
                "artifacts": len(freeze["artifacts"]),
                "allPassed": True,
                "executionAuthorized": False,
            }
        )
    )


if __name__ == "__main__":
    verify()
