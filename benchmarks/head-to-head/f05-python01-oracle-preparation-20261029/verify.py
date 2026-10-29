"""Read-only hashes/reconstruction; no source imports or workload execution."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path("/Users/maxwell/projects/agent/dotrepo")


def verify():
    inputs = json.loads((HERE / "source-bindings.json").read_bytes())
    for row in inputs["files"]:
        path = Path(row["path"])
        path = path if path.is_absolute() else ROOT / path
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row["sha256"] and len(raw) == row["bytes"], row[
            "path"
        ]
    freeze = json.loads((HERE / "FREEZE.json").read_bytes())
    for name, row in freeze["artifacts"].items():
        raw = (HERE / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row["sha256"] and len(raw) == row["bytes"], name
    print(
        json.dumps(
            {
                "allPassed": True,
                "boundInputs": len(inputs["files"]),
                "artifacts": len(freeze["artifacts"]),
                "actualAdmission": False,
            }
        )
    )


if __name__ == "__main__":
    verify()
