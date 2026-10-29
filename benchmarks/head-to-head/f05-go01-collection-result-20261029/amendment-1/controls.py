"""Local result mutations, never a live collection or daemon invocation."""

import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("third_result_verifier", HERE / "verify.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def write(root, name, value):
    (root / name).write_text(json.dumps(value, indent=2) + "\n")


def outcome(root, **changes):
    result = v.read(root, "evidence/result.json")
    result.update(changes)
    write(root, "evidence/result.json", result)
    write(root, "outer/driver.log", result)


def package_bytes(root, raw):
    (root / "evidence/packages.jsonstream").write_bytes(raw)
    (root / "evidence/logs/go-list/stdout.bin").write_bytes(raw)
    trace = v.read(root, "evidence/trace.json")
    receipt = trace["receipts"]["logs/go-list/receipt.json"]
    receipt["stdoutSha256"] = v.digest(root / "evidence/packages.jsonstream")
    write(root, "evidence/logs/go-list/receipt.json", receipt)
    write(root, "evidence/trace.json", trace)


def main():
    plan, auth = v.closure(HERE)
    cases = [
        ("valid-incomplete-result", lambda _: None, True),
        ("fabricated-collection-success", lambda p: outcome(p, collectionObserved=True), False),
        ("missing-cleanup-absence", lambda p: outcome(p, containerAbsent=False), False),
        ("empty-raw-package-stream-consistent-hash", lambda p: package_bytes(p, b""), False),
        (
            "truncated-raw-package-stream-consistent-hash",
            lambda p: package_bytes(p, b'{"ImportPath":'),
            False,
        ),
        (
            "false-accepted-package-inventory",
            lambda p: write(p, "evidence/package-inventory.json", {}),
            False,
        ),
        (
            "invented-later-collection",
            lambda p: (p / "evidence/collection-events.jsonl").write_text("{}\n"),
            False,
        ),
        (
            "raw-package-copy-mismatch",
            lambda p: (p / "evidence/packages.jsonstream").write_bytes(b"{}"),
            False,
        ),
    ]
    results = []
    with tempfile.TemporaryDirectory(prefix="dotrepo-go01-third-result-controls-") as directory:
        for i, (name, mutate, expected) in enumerate(cases):
            root = Path(directory) / str(i)
            shutil.copytree(HERE, root, ignore=shutil.ignore_patterns("__pycache__", ".ruff_cache"))
            mutate(root)
            error = None
            try:
                v.observations(root, plan, auth)
                accepted = True
            except (ValueError, KeyError) as exc:
                accepted, error = False, str(exc)
            v.require(accepted == expected, f"unexpected control: {name}")
            results.append(
                {"case": name, "accepted": accepted, "expectedAccepted": expected, "error": error}
            )
    print(json.dumps({"synthetic": True, "liveCalls": 0, "cases": results}, indent=2))


if __name__ == "__main__":
    main()
