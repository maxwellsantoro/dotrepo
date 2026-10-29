"""Data-only immutable packet and current owning source checks."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def check(path, expected):
    assert path.is_file() and not path.is_symlink(), str(path)
    raw = path.read_bytes()
    assert len(raw) == expected["bytes"], str(path)
    assert hashlib.sha256(raw).hexdigest() == expected["sha256"], str(path)


def main():
    freeze = json.loads((HERE / "FREEZE.json").read_bytes())
    for relative, expected in freeze["artifacts"].items():
        check(HERE / relative, expected)
    bindings = json.loads((HERE / "source-bindings.json").read_bytes())
    for relative, expected in bindings["sources"].items():
        check(ROOT / relative, expected)
    print(f"{len(freeze['artifacts'])} packet artifacts and 3 current source bindings match")


if __name__ == "__main__":
    main()
