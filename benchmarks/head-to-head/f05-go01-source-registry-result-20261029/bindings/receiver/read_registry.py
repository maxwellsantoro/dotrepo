"""Bounded receiver for a future owned-helper gzip output, not an outcome oracle."""

import argparse
import json
from pathlib import Path
import zlib

import build_input as builder

MAX_COMPRESSED = 2 << 20
MAX_EXPANDED = 8 << 20
FIELDS = ["tests", "benchmarks", "fuzzTargets", "examples", "testMains"]
KINDS = ["test", "benchmark", "fuzz", "example", "testMain"]


def inflate(raw):
    builder.require(18 <= len(raw) <= MAX_COMPRESSED, "compressed byte bound")
    builder.require(
        raw[:10] == bytes.fromhex("1f8b08000000000002ff"), "deterministic single gzip header"
    )
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    expanded = decoder.decompress(raw, MAX_EXPANDED + 1)
    builder.require(len(expanded) <= MAX_EXPANDED, "expanded byte bound")
    builder.require(
        decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
        "truncated/multiple/trailing gzip data",
    )
    return expanded


def validate(value, provenance, packages):
    builder.require(isinstance(value, dict), "output object")
    builder.require(
        set(value)
        == {
            "schema",
            "state",
            "sourceContext",
            "helperGoVersion",
            "helperGOOS",
            "helperGOARCH",
            "inputSha256",
            "packages",
            "universalCompileValidityUnestablished",
            "nativeCollectionOccurred",
            "taskOutcomeObserved",
        },
        "output schema keys",
    )
    builder.require(
        value["schema"] == "go01-source-registry-output-v1"
        and value["state"] in ["source-derived-uncompiled", "unresolved-source-discovery"]
        and value["sourceContext"] == provenance["sourceContext"]
        and value["inputSha256"] == provenance["inputSha256"]
        and value["helperGoVersion"] == "go1.27.3"
        and value["helperGOOS"] == "linux"
        and value["helperGOARCH"] == "arm64"
        and value["universalCompileValidityUnestablished"] is True
        and value["nativeCollectionOccurred"] is False
        and value["taskOutcomeObserved"] is False,
        "output source/helper context or qualification flags",
    )
    rows = value["packages"]
    builder.require(
        isinstance(rows, list)
        and all(isinstance(row, dict) for row in rows)
        and [row.get("importPath") for row in rows] == sorted(packages),
        "complete exact package order/set",
    )
    seen_ids, count, unresolved = set(), 0, False
    for row in rows:
        builder.require(
            set(row)
            == {"importPath", *FIELDS, "diagnostics", "state", "compileValidityUnestablished"},
            "package output keys",
        )
        builder.require(
            row["compileValidityUnestablished"] is True and isinstance(row["diagnostics"], list),
            "package validity/diagnostics",
        )
        for diagnostic in row["diagnostics"]:
            builder.require(isinstance(diagnostic, dict), "diagnostic object")
            builder.require(
                {"code", "message"} <= set(diagnostic) <= {"code", "message", "sourcePath"},
                "diagnostic keys",
            )
            builder.require(
                isinstance(diagnostic["code"], str)
                and bool(diagnostic["code"])
                and isinstance(diagnostic["message"], str)
                and bool(diagnostic["message"]),
                "diagnostic string fields",
            )
            if "sourcePath" in diagnostic:
                diagnostic_path = diagnostic["sourcePath"]
                native = packages[row["importPath"]]
                builder.require(
                    isinstance(diagnostic_path, str)
                    and diagnostic_path in provenance["selectedFiles"]
                    and diagnostic_path
                    == native["Dir"].removeprefix("/workspace/repository/")
                    + "/"
                    + diagnostic_path.rsplit("/", 1)[-1]
                    and diagnostic_path.rsplit("/", 1)[-1]
                    in native.get("TestGoFiles", []) + native.get("XTestGoFiles", []),
                    "diagnostic source package membership",
                )
        builder.require(
            row["state"]
            == (
                "unresolved-source-discovery" if row["diagnostics"] else "source-derived-uncompiled"
            ),
            "package state disagrees with diagnostics",
        )
        unresolved |= bool(row["diagnostics"])
        for field, kind in zip(FIELDS, KINDS):
            builder.require(isinstance(row[field], list), "declaration list")
            for declaration in row[field]:
                builder.require(isinstance(declaration, dict), "declaration object")
                count += 1
                builder.require(count <= 10000, "declaration count bound")
                required = {
                    "id",
                    "kind",
                    "name",
                    "sourcePath",
                    "sourceSha256",
                    "packageRole",
                    "line",
                    "column",
                    "offset",
                    "endOffset",
                }
                builder.require(
                    required
                    <= set(declaration)
                    <= required | {"output", "emptyOutput", "unordered"},
                    "declaration keys",
                )
                for key, expected_type in [
                    ("output", str),
                    ("emptyOutput", bool),
                    ("unordered", bool),
                ]:
                    if key in declaration:
                        builder.require(
                            type(declaration[key]) is expected_type, "optional declaration type"
                        )
                source_path = declaration["sourcePath"]
                builder.require(isinstance(source_path, str), "source path string")
                item = provenance["selectedFiles"].get(source_path)
                builder.require(
                    item is not None and declaration["sourceSha256"] == item["sha256"],
                    "declaration source binding",
                )
                role = declaration["packageRole"]
                source_field = "TestGoFiles" if role == "internal" else "XTestGoFiles"
                native = packages[row["importPath"]]
                builder.require(
                    role in ["internal", "external"]
                    and source_path
                    == native["Dir"].removeprefix("/workspace/repository/")
                    + "/"
                    + source_path.rsplit("/", 1)[-1]
                    and source_path.rsplit("/", 1)[-1] in native.get(source_field, []),
                    "source role/package membership",
                )
                builder.require(
                    declaration["kind"] == kind
                    and isinstance(declaration["name"], str)
                    and bool(declaration["name"]),
                    "declaration kind/name",
                )
                for key in ["line", "column", "offset", "endOffset"]:
                    builder.require(type(declaration[key]) is int, "literal integer position")
                builder.require(
                    declaration["line"] > 0
                    and declaration["column"] > 0
                    and 0 <= declaration["offset"] < declaration["endOffset"] <= item["bytes"],
                    "declaration physical position",
                )
                expected_id = builder.sha(
                    "\x00".join(
                        [
                            row["importPath"],
                            source_path,
                            item["sha256"],
                            role,
                            kind,
                            declaration["name"],
                            str(declaration["offset"]),
                        ]
                    ).encode()
                )
                builder.require(
                    declaration["id"] == expected_id and expected_id not in seen_ids,
                    "stable unique declaration ID",
                )
                seen_ids.add(expected_id)
    builder.require(
        value["state"]
        == ("unresolved-source-discovery" if unresolved else "source-derived-uncompiled"),
        "global state disagrees",
    )
    return {
        "state": "received-source-registry-uncompiled-unqualified",
        "packages": len(rows),
        "declarations": count,
        "hasSourceDiagnostics": unresolved,
        "nativeCollectionOccurred": False,
        "taskOutcomeObserved": False,
        "collectionGateChanged": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gzip", required=True, type=Path)
    parser.add_argument("--provenance", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    builder.require(args.gzip.stat().st_size <= MAX_COMPRESSED, "wire file size")
    wire = args.gzip.read_bytes()
    raw = inflate(wire)
    value = builder.load(raw)
    provenance = builder.load(args.provenance.read_bytes())
    package_raw = Path(provenance["packageInventoryPath"]).read_bytes()
    builder.require(
        builder.sha(package_raw) == provenance["sourceContext"]["packageInventorySha256"],
        "package inventory hash",
    )
    receipt = validate(value, provenance, builder.load(package_raw))
    receipt.update(
        wireSha256=builder.sha(wire),
        wireBytes=len(wire),
        jsonSha256=builder.sha(raw),
        expandedBytes=len(raw),
    )
    with args.output.open("x") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
