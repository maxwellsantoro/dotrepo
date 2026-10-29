"""Synthetic result-only counterexamples, never a daemon or upstream command."""

import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("fourth_result_verifier", HERE / "verify.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def write(root, name, value):
    (root / name).write_text(json.dumps(value, indent=2) + "\n")


def outcome(root, **changes):
    result = v.read(root, "evidence/result.json")
    result.update(changes)
    write(root, "evidence/result.json", result)
    write(root, "outer/driver.log", result)


def lost_package(root):
    inventory = v.read(root, "evidence/package-inventory.json")
    inventory.pop(next(iter(inventory)))
    write(root, "evidence/package-inventory.json", inventory)


def cause_claim(root):
    report = v.read(root, "report.json")
    report.update(terminationCause="OOM", oomProven=True)
    write(root, "report.json", report)


def terminal_scope(root):
    path = root / "evidence/logs/go-test-list/stdout.bin"
    events = [json.loads(line) for line in path.read_bytes().splitlines()]
    next(e for e in events if e["Action"] == "pass")["Package"] = (
        "github.com/microsoft/TypeScript/tsc/unrelated"
    )
    path.write_bytes(b"".join((json.dumps(e) + "\n").encode() for e in events))
    trace = v.read(root, "evidence/trace.json")
    name = "logs/go-test-list/receipt.json"
    trace["receipts"][name]["stdoutSha256"] = v.digest(path)
    write(root, f"evidence/{name}", trace["receipts"][name])
    write(root, "evidence/trace.json", trace)


def main():
    plan, auth = v.closure(HERE)
    cases = [
        ("valid-incomplete-attempt", lambda _: None, True),
        ("fabricated-full-collection", lambda p: outcome(p, nativeCollectionOccurred=True), False),
        ("lost-attempted-flag", lambda p: outcome(p, nativeCollectionAttempted=False), False),
        ("unproven-oom-cause", cause_claim, False),
        ("lost-package-inventory", lost_package, False),
        (
            "fabricated-full-manifest",
            lambda p: write(p, "evidence/collection-manifest.json", {}),
            False,
        ),
        ("different-terminal-scope-consistent-hash", terminal_scope, False),
        ("lost-cleanup-absence", lambda p: outcome(p, containerAbsent=False), False),
        ("fabricated-timeout", lambda p: outcome(p, workBudgetExceeded=True), False),
    ]
    results = []
    with tempfile.TemporaryDirectory(prefix="dotrepo-go01-fourth-result-controls-") as directory:
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
