"""Construct closed source-only registry input from immutable retained bytes."""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RESULT = ROOT / "benchmarks/head-to-head/f05-go01-collection-result-20261029/amendment-2"
SOURCE = Path("/tmp/dotrepo-f05-qualification-20261029-tranche-1/go-01-full/runtime-source.tar")
SOURCE_INVENTORY = (
    ROOT / "benchmarks/head-to-head/f05-qualification-20261029/go-01-full/inventory.json"
)
DRIVER = ROOT / "benchmarks/head-to-head/f05-go01-collection-driver-20261029/amendment-3"
PREFIX = "github.com/microsoft/TypeScript/tsc"
CWD = "/workspace/repository/tsc"
REVISION = "25f823dc198a00744b458a7bc6984359f0dd7cac"
SOURCE_SHA = "c583f28324d455b559bb232e7a280581fe874850f805decfb5947febfa91ee0f"
SOURCE_INVENTORY_SHA = "96c935c31228fa8e05bb836a93257beeb87ac524e5eb30cdde3c546a1ea4be0e"
RESULT_FREEZE_SHA = "f2588d3ee2bdee8c5b40d5f5a328d72dd07c0f093fd6e36904a9dcecec5256a2"
DRIVER_FREEZE_SHA = "bca1522ad5b9d29a52cce68ce2d8b1d14a176511286f97761662337f17a3ecd7"
PACKAGE_INVENTORY_SHA = "764fa272f1c461f4ecc2d6e2b58d641cc65c8e64da23f55981fa12b70c75bc21"
MAX_INPUT = 32 << 20
MAX_FILE = 8 << 20
MAX_SELECTED = 24 << 20


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def load(raw):
    return json.loads(raw, object_pairs_hook=unique_object)


def encode(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode()


def safe_path(value):
    return (
        isinstance(value, str)
        and 0 < len(value) <= 4096
        and not any(c.isspace() or ord(c) < 32 or ord(c) == 127 or c in "\\:" for c in value)
        and all(p not in ("", ".", "..") for p in value.removeprefix("/").split("/"))
    )


def safe_archive_path(value):
    # The exact source archive includes legitimate whitespace-named fixtures.
    # They are never selected Go inputs and are not extracted to the host.
    return (
        isinstance(value, str)
        and 0 < len(value) <= 4096
        and not value.startswith("/")
        and not any(ord(c) < 32 or ord(c) == 127 or c in "\\:" for c in value)
        and all(p not in ("", ".", "..") for p in value.split("/"))
    )


def validate_packages(packages, inventory):
    require(isinstance(packages, dict) and len(packages) == 104, "exact104 package map")
    selected = {}
    for key, row in packages.items():
        name, directory = row.get("ImportPath"), row.get("Dir")
        require(
            key == name
            and safe_path(name)
            and (name == PREFIX or name.startswith(PREFIX + "/"))
            and directory == CWD + name.removeprefix(PREFIX),
            "package/module/cwd identity",
        )
        module = row.get("Module")
        require(
            isinstance(module, dict)
            and module.get("Path") == PREFIX
            and module.get("Dir") == CWD
            and not module.get("Replace")
            and isinstance(row.get("Name"), str)
            and bool(row["Name"])
            and not row.get("Error")
            and not row.get("DepsErrors")
            and not row.get("Incomplete"),
            "package metadata/error",
        )
        seen = set()
        for field in ["GoFiles", "CgoFiles", "TestGoFiles", "XTestGoFiles"]:
            values = row.get(field, [])
            require(isinstance(values, list), "selected list shape")
            for value in values:
                require(
                    safe_path(value)
                    and "/" not in value
                    and value.endswith(".go")
                    and value not in seen,
                    "literal unique selected filename",
                )
                seen.add(value)
                path = directory.removeprefix("/workspace/repository/") + "/" + value
                require(path in inventory, "selected file absent from frozen inventory")
                if field in ["TestGoFiles", "XTestGoFiles"]:
                    require(value.endswith("_test.go"), "test list filename suffix")
                    require(path not in selected, "cross-package selected alias")
                    selected[path] = {"package": key, "field": field, "name": value}
        require(bool(seen), "no selected source")
    require(0 < len(selected) <= 6000, "selected file count")
    return selected


def select_source(archive_path, inventory, selected):
    require(archive_path.stat().st_size <= 512 << 20, "source archive transport bound")
    files, seen, expanded, selected_bytes = {}, set(), 0, 0
    with tarfile.open(archive_path, "r:") as archive:
        for member in archive:
            name = member.name
            require(safe_archive_path(name) and name not in seen, "source path")
            require(member.isfile() and not member.sparse, "regular source member")
            seen.add(name)
            expanded += member.size
            require(expanded <= 256 << 20 and len(seen) <= 70000, "archive expanded/member bound")
            require(name in inventory, "unknown archive member")
            if name not in selected:
                continue
            require(0 <= member.size <= MAX_FILE, "selected source file bound")
            raw = archive.extractfile(member).read(MAX_FILE + 1)
            require(
                len(raw) == member.size and sha(raw) == inventory[name], "selected source byte hash"
            )
            raw.decode("utf-8")
            selected_bytes += len(raw)
            require(selected_bytes <= MAX_SELECTED, "selected total byte bound")
            files[name] = raw
    require(seen == set(inventory), "archive path set")
    require(set(files) == set(selected), "missing selected source")
    return files, expanded, selected_bytes


def verify_freeze(folder, expected):
    require(file_sha(folder / "FREEZE.json") == expected, "frozen packet digest")
    freeze = load((folder / "FREEZE.json").read_bytes())
    for name, digest in freeze["artifactSha256"].items():
        require(file_sha(folder / name) == digest, "changed frozen artifact: " + name)
    return file_sha(folder / "FREEZE.json")


def build(output, provenance):
    # All initial hashes are checked against exact parent freezes before source is read.
    result_freeze = verify_freeze(RESULT, RESULT_FREEZE_SHA)
    driver_freeze = verify_freeze(DRIVER, DRIVER_FREEZE_SHA)
    plan = load((DRIVER / "plan.json").read_bytes())
    require(
        plan["revision"] == REVISION and plan["sourceArchiveSha256"] == SOURCE_SHA,
        "source identity",
    )
    require(file_sha(SOURCE) == SOURCE_SHA, "complete archive digest")
    inventory_raw = SOURCE_INVENTORY.read_bytes()
    require(sha(inventory_raw) == SOURCE_INVENTORY_SHA, "source inventory digest")
    inventory = load(inventory_raw)["files"]
    require(len(inventory) == 68062, "exact full source inventory count")
    package_path = RESULT / "evidence/package-inventory.json"
    package_raw = package_path.read_bytes()
    require(len(package_raw) <= 2 << 20, "package inventory byte bound")
    require(sha(package_raw) == PACKAGE_INVENTORY_SHA, "package inventory digest")
    packages = load(package_raw)
    selected = validate_packages(packages, inventory)
    files, expanded, total = select_source(SOURCE, inventory, selected)
    context = {
        "repository": "github.com/microsoft/TypeScript",
        "revision": REVISION,
        "imageId": plan["imageId"],
        "goVersion": plan["expectedGoEnv"]["GOVERSION"],
        "sourceArchiveSha256": SOURCE_SHA,
        "sourceInventorySha256": SOURCE_INVENTORY_SHA,
        "packageInventorySha256": sha(package_raw),
        "environmentSha256": plan["environmentSha256"],
        "discoverySourcesSha256": file_sha(HERE / "discovery-source-bindings.json"),
    }
    rows = []
    for key, row in sorted(packages.items()):
        normalized = {"importPath": key, "dir": row["Dir"], "name": row["Name"]}
        for field, target in [("TestGoFiles", "testGoFiles"), ("XTestGoFiles", "xTestGoFiles")]:
            normalized[target] = []
            for name in row.get(field, []):
                path = row["Dir"].removeprefix("/workspace/repository/") + "/" + name
                raw = files[path]
                normalized[target].append(
                    {
                        "name": name,
                        "path": path,
                        "sha256": sha(raw),
                        "bytes": len(raw),
                        "dataBase64": base64.b64encode(raw).decode("ascii"),
                    }
                )
        rows.append(normalized)
    selection = bytearray(b"go01-selected-sources-v1\x00")
    for row in rows:
        selection.extend(
            (
                "P\x00" + row["importPath"] + "\x00" + row["dir"] + "\x00" + row["name"] + "\x00"
            ).encode()
        )
        for field in ["testGoFiles", "xTestGoFiles"]:
            selection.extend(("G\x00" + field + "\x00").encode())
            for file in row[field]:
                selection.extend(
                    (
                        "F\x00"
                        + file["path"]
                        + "\x00"
                        + file["sha256"]
                        + "\x00"
                        + str(file["bytes"])
                        + "\x00"
                    ).encode()
                )
    context["selectionSha256"] = sha(selection)
    value = {"schema": "go01-source-registry-input-v1", "sourceContext": context, "packages": rows}
    raw = encode(value)
    require(len(raw) <= MAX_INPUT, "closed JSON input bound")
    require(file_sha(SOURCE) == SOURCE_SHA, "archive changed after reads")
    require(not output.exists() and not provenance.exists(), "exclusive output paths")
    with output.open("xb") as stream:
        stream.write(raw)
    record = {
        "state": "prepared-source-bytes-only-helper-unrun",
        "inputPath": str(output.resolve()),
        "inputSha256": sha(raw),
        "inputBytes": len(raw),
        "sourceContext": context,
        "sourceArchivePath": str(SOURCE),
        "sourceInventoryPath": str(SOURCE_INVENTORY),
        "packageInventoryPath": str(package_path),
        "resultFreezeSha256": result_freeze,
        "driverFreezeSha256": driver_freeze,
        "packageCount": len(rows),
        "selectedFileCount": len(files),
        "selectedBytes": total,
        "archiveExpandedBytes": expanded,
        "sourceOnlyPackagesNotLiveValidated": 61,
        "nativePassPackagesForFutureCrosscheck": 25,
        "nativeNoTestSkipPackages": 18,
        "helperBuilt": False,
        "helperExecuted": False,
        "nativeCollectionOccurred": False,
        "taskOutcomeObserved": False,
        "collectionGateChanged": False,
        "selectedFiles": {
            name: {"sha256": sha(data), "bytes": len(data)} for name, data in sorted(files.items())
        },
    }
    with provenance.open("x") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        json.dumps(
            {key: value for key, value in record.items() if key != "selectedFiles"}, indent=2
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    args = parser.parse_args()
    build(args.output, args.provenance)
