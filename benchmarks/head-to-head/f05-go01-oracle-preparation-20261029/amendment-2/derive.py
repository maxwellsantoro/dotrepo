"""Derive exact source expectations using retained data and hash-bound pure checks."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASE = ROOT / "benchmarks/head-to-head"
RESULT = BASE / "f05-go01-source-registry-result-20261029"
BINDINGS_SHA = "25ad36a65f53431ded8afd7f171c539805f1de9619b95c3ed1e67654b0ced795"
MAP_SHA = "768482aa2dcec46151e529a1126a8d74fbaba56f168d86c915002aa70d869e4a"
SOURCE_CONTEXT_SHA = "658d568de13e3bf12b414b4a805a69d7bfe327e79bc2c72c754225647996f022"
REQUIRED_FIELDS = ("tests", "examples", "fuzzTargets")


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def bound_sources():
    raw = (HERE / "source-bindings.json").read_bytes()
    require(sha(raw) == BINDINGS_SHA, "changed source bindings")
    bindings = json.loads(raw)
    for row in bindings["files"]:
        path = ROOT / row["path"]
        require(path.resolve().is_relative_to(ROOT.resolve()), "source binding path")
        data = path.read_bytes()
        require(
            len(data) == row["bytes"] and sha(data) == row["sha256"],
            "changed bound source: " + row["path"],
        )
    return bindings


def names_from_registry(registry, inventory):
    require(registry["state"] == "source-derived-uncompiled", "unresolved discovery")
    require(registry["universalCompileValidityUnestablished"] is True, "false compile validity")
    require(
        sha(canonical(registry["sourceContext"])) == SOURCE_CONTEXT_SHA,
        "changed target selection context",
    )
    packages = registry["packages"]
    require(
        len(packages) == 104 and {p["importPath"] for p in packages} == set(inventory),
        "incomplete package selection",
    )
    names = {}
    for row in packages:
        require(
            row["importPath"] not in names
            and row["diagnostics"] == []
            and row["state"] == "source-derived-uncompiled"
            and row["compileValidityUnestablished"] is True,
            "unresolved or duplicate package",
        )
        selected = sorted(item["name"] for field in REQUIRED_FIELDS for item in row[field])
        require(len(selected) == len(set(selected)), "duplicate runtime name")
        names[row["importPath"]] = selected
    require(
        sha(canonical(names)) == MAP_SHA and sum(map(len, names.values())) == 5972,
        "changed expected identity map",
    )
    return names


def derive():
    bindings = bound_sources()
    # The frozen result verifier performs local hash/JSON/archive operations only.
    spec = importlib.util.spec_from_file_location(
        "source_expectation_retained_result_verifier", RESULT / "verify.py"
    )
    observed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(observed)
    plan, auth = observed.closure(RESULT)
    checked, _, registry = observed.observations(RESULT, plan, auth)
    inventory = json.loads((RESULT / "bindings/native/package-inventory.json").read_bytes())
    names = names_from_registry(registry, inventory)
    metadata = {
        "state": "source-derived-uncompiled-expectation",
        "sourceSubject": {
            "sourceBindingsSha256": BINDINGS_SHA,
            "resultFreezeSha256": sha((RESULT / "FREEZE.json").read_bytes()),
            "independentResultReviewFreezeSha256": sha(
                (BASE / "f05-go01-source-registry-result-review-20261029/FREEZE.json").read_bytes()
            ),
            "registryGzipSha256": checked["wireSha256"],
            "registryExpandedSha256": checked["expandedSha256"],
            "inputSha256": registry["inputSha256"],
            "sourceContext": registry["sourceContext"],
        },
        "expectedMapSha256": MAP_SHA,
        "expectedMapBytes": len(canonical(names)),
        "packageCount": 104,
        "requiredTopLevelCount": 5972,
        "emptyNamePackages": 40,
        "noSelectedTestSourcePackages": sorted(
            name
            for name, row in inventory.items()
            if not row.get("TestGoFiles", []) and not row.get("XTestGoFiles", [])
        ),
        "requiredKinds": list(REQUIRED_FIELDS),
        "benchmarksNotRequired": 48,
        "testMainWrappersNotCaseIds": 11,
        "nativeCollection": False,
        "captureJoinState": "open-reviewed-full-task-capture-join-required",
        "oracleQualified": False,
        "campaignAdmitted": False,
    }
    require(sum(not v for v in names.values()) == metadata["emptyNamePackages"], "empty name scope")
    return metadata, names, bindings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Fresh directory; no existing outputs overwritten",
    )
    args = parser.parse_args()
    metadata, names, _ = derive()
    args.output.mkdir(exist_ok=False)
    (args.output / "expected-map.json").write_bytes(canonical(names))
    (args.output / "expectation.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(
        json.dumps(
            {
                "packages": 104,
                "requiredTopLevelNames": 5972,
                "nativeCollection": False,
                "oracleQualified": False,
            }
        )
    )


if __name__ == "__main__":
    main()
