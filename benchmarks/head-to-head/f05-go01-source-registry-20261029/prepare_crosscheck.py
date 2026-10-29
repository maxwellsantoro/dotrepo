"""Retain partial native listing observations, never turn them into full gold."""

import json
from pathlib import Path

import build_input as builder

HERE = Path(__file__).resolve().parent


def main():
    path = builder.RESULT / "evidence/logs/go-test-list/stdout.bin"
    raw = path.read_bytes()
    builder.require(
        builder.sha(raw) == "3e35220c5d834daec10a374f21b7855e57da27d7788f1b83af123f6e5e55f202",
        "partial raw events hash",
    )
    inventory_path = builder.RESULT / "evidence/package-inventory.json"
    inventory = builder.load(inventory_path.read_bytes())
    builder.require(
        builder.sha(inventory_path.read_bytes()) == builder.PACKAGE_INVENTORY_SHA,
        "native inventory binding",
    )
    outputs, terminals = {name: "" for name in inventory}, {}
    for line in raw.splitlines():
        row = builder.load(line)
        builder.require(not row.get("Test"), "unexpected test-body event in listing fixture")
        if row["Action"] == "output":
            outputs[row["Package"]] += row.get("Output", "")
        if row["Action"] in ["pass", "fail", "skip"]:
            builder.require(row["Package"] not in terminals, "duplicate native terminal")
            terminals[row["Package"]] = row["Action"]
    builder.require(set(terminals) == set(inventory), "native terminal package set")
    observations = {}
    for name, status in sorted(terminals.items()):
        lines = [
            line
            for line in outputs[name].splitlines()
            if line.startswith(("Test", "Benchmark", "Fuzz", "Example"))
        ]
        observations[name] = {
            "nativeListingTerminal": status,
            "observedNameLines": lines,
            "noTestFilesDiagnostic": "[no test files]" in outputs[name],
            "selectedTestSourceFiles": len(inventory[name].get("TestGoFiles", []))
            + len(inventory[name].get("XTestGoFiles", [])),
            "comparisonRole": "positive-partial-listing"
            if status == "pass"
            else "empty-no-test-diagnostic"
            if status == "skip"
            else "source-only-not-validated-live",
        }
    counts = {
        status: sum(row["nativeListingTerminal"] == status for row in observations.values())
        for status in ["pass", "skip", "fail"]
    }
    builder.require(counts == {"pass": 25, "skip": 18, "fail": 61}, "partial fixture counts")
    value = {
        "state": "retained-partial-observations-only-source-helper-unrun",
        "rawEventsPath": str(path),
        "rawEventsSha256": builder.sha(raw),
        "packageInventorySha256": builder.PACKAGE_INVENTORY_SHA,
        "resultFreezeSha256": builder.RESULT_FREEZE_SHA,
        "counts": counts,
        "packages": observations,
        "nativeFullCollectionExists": False,
        "testBodiesExecutedByThisPreparation": False,
        "warning": "These are exact observed name lines, not newly established source registry/expected cases.61 failed packages remain unvalidated live. Printed names alone are not observer authentication.",
    }
    with (HERE / "partial-listing-observations.json").open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"counts": counts, "sourceHelperRun": False}))


if __name__ == "__main__":
    main()
