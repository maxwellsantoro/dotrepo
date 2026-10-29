"""Future partial observational comparison, never native/full-suite qualification."""

import argparse
import json
from pathlib import Path

import build_input as builder
import read_registry as receiver

HERE = Path(__file__).resolve().parent


def compare(registry, observations):
    source = {row["importPath"]: row for row in registry["packages"]}
    differences, passed, empty, source_only = [], [], [], []
    for name, observation in observations["packages"].items():
        row = source[name]
        names = [entry["name"] for field in receiver.FIELDS[:-1] for entry in row[field]]
        status = observation["nativeListingTerminal"]
        if status == "fail":
            source_only.append(name)
            continue
        if row["diagnostics"]:
            differences.append(
                {"package": name, "reason": "source diagnostics", "diagnostics": row["diagnostics"]}
            )
        elif status == "pass" and names == observation["observedNameLines"]:
            passed.append(name)
        elif (
            status == "skip"
            and not names
            and observation["noTestFilesDiagnostic"]
            and observation["selectedTestSourceFiles"] == 0
        ):
            empty.append(name)
        else:
            differences.append(
                {
                    "package": name,
                    "reason": "source/partial-listing mismatch",
                    "sourceNames": names,
                    "observedNameLines": observation["observedNameLines"],
                }
            )
    positive_names = {
        name
        for name, row in observations["packages"].items()
        if row["nativeListingTerminal"] == "pass"
    }
    builder.require(
        len(passed) + sum(row["package"] in positive_names for row in differences) == 25,
        "positive comparison extent",
    )
    builder.require(len(source_only) == 61, "failed package comparison scope")
    return {
        "state": "partial-observational-crosscheck-consistent-unqualified"
        if not differences
        else "partial-observational-crosscheck-mismatch",
        "matchedPassPackages": passed,
        "matchedNoTestPackages": empty,
        "unvalidatedFailedPackages": source_only,
        "differences": differences,
        "sourceRegistryDiagnosticsPackages": [
            row["importPath"] for row in registry["packages"] if row["diagnostics"]
        ],
        "nativeFullCollectionExists": False,
        "compileValidityUnestablished": True,
        "taskOutcomeObserved": False,
        "collectionGateChanged": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gzip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    builder.require(args.gzip.stat().st_size <= receiver.MAX_COMPRESSED, "wire file size")
    raw = receiver.inflate(args.gzip.read_bytes())
    registry = builder.load(raw)
    provenance = builder.load((HERE / "input-provenance.json").read_bytes())
    package_raw = Path(provenance["packageInventoryPath"]).read_bytes()
    builder.require(
        builder.sha(package_raw) == builder.PACKAGE_INVENTORY_SHA,
        "native package inventory binding",
    )
    receiver.validate(registry, provenance, builder.load(package_raw))
    observations = builder.load((HERE / "partial-listing-observations.json").read_bytes())
    result = compare(registry, observations)
    result.update(
        registryJsonSha256=builder.sha(raw),
        partialObservationsSha256=builder.file_sha(HERE / "partial-listing-observations.json"),
    )
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(
        json.dumps(
            {
                key: len(value) if isinstance(value, list) else value
                for key, value in result.items()
            },
            indent=2,
        )
    )
    if result["differences"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
