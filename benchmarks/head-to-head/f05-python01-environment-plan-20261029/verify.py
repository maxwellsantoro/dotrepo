"""Read-only plan/source binding verification. No probe or upstream execution."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    freeze = json.loads((HERE / "FREEZE.json").read_bytes())
    for name, binding in freeze["artifacts"].items():
        path = HERE / name
        assert path.is_file() and not path.is_symlink(), name
        raw = path.read_bytes()
        assert len(raw) == binding["bytes"], name
        assert hashlib.sha256(raw).hexdigest() == binding["sha256"], name
    plan = json.loads((HERE / "plan.json").read_bytes())
    for name, digest in plan["inputBindings"].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest, name
    archive = Path(plan["source"]["archive"])
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == plan["source"]["sha256"]
    assert plan["executionAuthorized"] is False and plan["probeExecuted"] is False
    print(
        f"{len(freeze['artifacts'])} plan artifacts, {len(plan['inputBindings'])} retained input bindings and archive match"
    )


if __name__ == "__main__":
    main()
