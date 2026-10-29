"""Synthetic mutations of immutable receipts; no process/daemon or native execution."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import zlib

sys.dont_write_bytecode = True
import verify as v  # noqa: E402


def write(root, name, value):
    (root / name).write_text(json.dumps(value, indent=2) + "\n")


def mutate_json(root, name, key, value):
    data = v.load(root, name)
    data[key] = value
    write(root, name, data)


def result_flag(root):
    for name in ["evidence/result.json", "outer/driver.log"]:
        mutate_json(root, name, "nativeCollectionOccurred", True)


def output_edit(root, label, content):
    path = root / f"evidence/logs/{label}/stdout.bin"
    path.write_bytes(content)
    receipt_path = f"evidence/logs/{label}/receipt.json"
    receipt = v.load(root, receipt_path)
    receipt["stdoutBytes"] = len(content)
    receipt["stdoutSha256"] = hashlib.sha256(content).hexdigest()
    write(root, receipt_path, receipt)
    trace = v.load(root, "evidence/trace.json")
    trace["receipts"][f"logs/{label}/receipt.json"] = receipt
    write(root, "evidence/trace.json", trace)


def missing_unit(root):
    path = root / "evidence/logs/owned-tests/stdout.bin"
    rows = [json.loads(line) for line in path.read_bytes().splitlines()]
    child = next(row["Test"] for row in rows if "/" in row.get("Test", ""))
    output_edit(
        root,
        "owned-tests",
        b"\n".join(json.dumps(row).encode() for row in rows if row.get("Test") != child) + b"\n",
    )


def gzip_crc(root):
    path = root / "evidence/registry.gz"
    data = bytearray(path.read_bytes())
    data[-8] ^= 1
    path.write_bytes(data)
    receipt_path = "evidence/logs/owned-cli/receipt.json"
    receipt = v.load(root, receipt_path)
    receipt["binarySha256"] = hashlib.sha256(data).hexdigest()
    write(root, receipt_path, receipt)
    trace = v.load(root, "evidence/trace.json")
    trace["receipts"]["logs/owned-cli/receipt.json"] = receipt
    write(root, "evidence/trace.json", trace)


def partial_loss(root):
    data = v.load(root, "bindings/partial-listing-observations.json")
    name = next(
        name for name, row in data["packages"].items() if row["nativeListingTerminal"] == "fail"
    )
    del data["packages"][name]
    write(root, "bindings/partial-listing-observations.json", data)


def diagnostics_loss(root):
    data = v.load(root, "full-diagnostics.json")
    data["packages"].pop()
    write(root, "full-diagnostics.json", data)


def changed_env(root):
    path = root / "evidence/logs/inspect-before/stdout.bin"
    data = json.loads(path.read_bytes())
    data[0]["HostConfig"]["NetworkMode"] = "bridge"
    output_edit(root, "inspect-before", json.dumps(data).encode())


def main():
    plan, auth = v.closure(v.HERE)
    controls = [
        ("original-actual-observation", lambda root: None, True),
        ("fabricated-native-collection", result_flag, False),
        ("missing-owned-child-unit", missing_unit, False),
        ("gzip-crc-changed-with-receipt-hash", gzip_crc, False),
        ("lost-failed-native-package", partial_loss, False),
        ("lost-full-diagnostics-package", diagnostics_loss, False),
        (
            "report-target-compile-overclaim",
            lambda root: mutate_json(root, "report.json", "targetCompileValidityEstablished", True),
            False,
        ),
        ("bridge-network-with-receipt-hash", changed_env, False),
        (
            "independent-absence-overclaim",
            lambda root: mutate_json(
                root, "report.json", "cleanup", {"independentAbsenceObservation": True}
            ),
            False,
        ),
    ]
    results = []
    with tempfile.TemporaryDirectory(
        prefix="dotrepo-owned-registry-result-controls-", dir="/tmp"
    ) as temp:
        for name, mutation, expected in controls:
            root = Path(temp) / name
            shutil.copytree(v.HERE, root)
            mutation(root)
            try:
                v.observations(root, deepcopy(plan), deepcopy(auth))
                accepted, error = True, None
            except (ValueError, KeyError, AssertionError, UnicodeError, zlib.error) as exc:
                accepted, error = False, str(exc)
            if accepted != expected:
                raise AssertionError(
                    f"{name}: accepted={accepted}, expected={expected}, error={error}"
                )
            results.append(
                {"case": name, "accepted": accepted, "expectedAccepted": expected, "error": error}
            )
    print(json.dumps({"synthetic": True, "nativeActions": False, "cases": results}, indent=2))


if __name__ == "__main__":
    main()
