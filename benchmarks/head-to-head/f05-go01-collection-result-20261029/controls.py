"""Synthetic mutations of retained results; no daemon, driver or upstream calls."""

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("retained_collection_verifier", HERE / "verify.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def write(root, name, value):
    (root / name).write_text(json.dumps(value, indent=2) + "\n")


def result(root, **values):
    value = verifier.read(root, "attempt-2/result.json")
    value.update(values)
    write(root, "attempt-2/result.json", value)
    write(root, "outer/driver-2.log", value)


def command_exit(root):
    trace = verifier.read(root, "attempt-2/trace.json")
    path = "logs/go-env/receipt.json"
    trace["receipts"][path]["exitCode"] = 1
    write(root, f"attempt-2/{path}", trace["receipts"][path])
    write(root, "attempt-2/trace.json", trace)


def effective_env(root):
    path = "attempt-2/logs/container-inspect/stdout.bin"
    value = verifier.read(root, path)
    value[0]["Config"]["Env"].remove("GOENV=off")
    write(root, path, value)
    update_raw_hash(root, "container-inspect")


def update_raw_hash(root, label):
    trace = verifier.read(root, "attempt-2/trace.json")
    name = f"logs/{label}/receipt.json"
    trace["receipts"][name]["stdoutSha256"] = verifier.digest(
        root / f"attempt-2/logs/{label}/stdout.bin"
    )
    write(root, f"attempt-2/{name}", trace["receipts"][name])
    write(root, "attempt-2/trace.json", trace)


def unrelated_env_failure(root):
    path = "attempt-2/logs/go-env/stdout.bin"
    value = verifier.read(root, path)
    value["CC"] = "/some/other/compiler"
    write(root, path, value)
    write(root, "attempt-2/go-environment.json", value)
    update_raw_hash(root, "go-env")


def unexpected_collection(root):
    (root / "attempt-2/collection-events.jsonl").write_text("{}\n")


def main():
    plan, auth = verifier.closure(HERE)
    cases = [
        ("valid-retained-observations", lambda _: None, True, "observations"),
        (
            "raw-stream-corruption",
            lambda p: (p / "attempt-2/logs/go-env/stdout.bin").write_bytes(b"{}"),
            False,
            "observations",
        ),
        (
            "invented-completion",
            lambda p: result(p, nativeCollectionOccurred=True),
            False,
            "observations",
        ),
        (
            "lost-cleanup-evidence",
            lambda p: result(p, containerAbsent=False),
            False,
            "observations",
        ),
        ("go-env-exit-mismatch", command_exit, False, "observations"),
        (
            "different-env-mismatch-with-consistent-hashes",
            unrelated_env_failure,
            False,
            "observations",
        ),
        ("effective-env-change-with-consistent-hashes", effective_env, False, "observations"),
        ("unexpected-later-collection-artifact", unexpected_collection, False, "observations"),
        (
            "acceptance-original-byte-change",
            lambda p: write(p, "authorization/acceptance.json", {}),
            False,
            "closure",
        ),
    ]
    outcomes = []
    with tempfile.TemporaryDirectory(
        prefix="dotrepo-go01-collection-result-controls-"
    ) as directory:
        for i, (name, mutate, accepted, phase) in enumerate(cases):
            root = Path(directory) / str(i)
            shutil.copytree(HERE, root, ignore=shutil.ignore_patterns("__pycache__", ".ruff_cache"))
            mutate(root)
            error = None
            try:
                if phase == "closure":
                    verifier.closure(root)
                else:
                    verifier.observations(root, copy.deepcopy(plan), copy.deepcopy(auth))
                observed = True
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                observed = False
                error = str(exc)
            verifier.require(observed == accepted, f"unexpected control result: {name}")
            outcomes.append(
                {"case": name, "accepted": observed, "expectedAccepted": accepted, "error": error}
            )
    print(json.dumps({"synthetic": True, "liveCalls": 0, "cases": outcomes}, indent=2))


if __name__ == "__main__":
    main()
