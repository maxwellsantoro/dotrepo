"""Independent read-only raw evidence analysis; no executable target/tool calls."""

import base64
from collections import Counter
import hashlib
import importlib
import io
import json
from pathlib import Path
import re
import sys
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RAW = Path("/private/tmp/dotrepo-go01-owned-registry-result-20261029-1")
HELPER = ROOT / "benchmarks/head-to-head/f05-go01-source-registry-20261029"
NATIVE = ROOT / "benchmarks/head-to-head/f05-go01-collection-result-20261029/amendment-2"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def output(name, value):
    with (HERE / name).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def freeze(path, expected):
    assert sha(path.read_bytes()) == expected, str(path)
    value = read(path)
    entries = value.get("artifactSha256", value.get("artifacts"))
    assert isinstance(entries, dict)
    for name, item in entries.items():
        member = path.parent / name
        raw = member.read_bytes()
        assert sha(raw) == (item if isinstance(item, str) else item["sha256"]), name
        if isinstance(item, dict):
            assert len(raw) == item["bytes"], name
    return len(entries)


def main():
    raw_count = freeze(
        RAW / "FREEZE.json", "1ea59ba97218067be4bef04852d2063a25063531b6ceca0de88c83a6d07f5770"
    )
    result = read(RAW / "result.json")
    auth = result["authorization"]
    raw_freeze = read(RAW / "FREEZE.json")
    auth_path = Path(raw_freeze["authorizationPath"])
    assert sha(auth_path.read_bytes()) == raw_freeze["authorizationSha256"]
    assert read(auth_path) == auth
    closure_counts = {}
    for role, binding in auth["fullClosuresVerified"].items():
        closure_counts[role] = freeze(Path(binding["path"]), binding["sha256"])
        assert closure_counts[role] == binding["verifiedArtifacts"]
    runtime_path = Path(auth["fullClosuresVerified"]["runtime"]["path"]).parent
    plan = read(runtime_path / "plan.json")
    assert sha((runtime_path / "plan.json").read_bytes()) == auth["runtimeSubject"]["planSha256"]
    assert auth["runtimeSubject"]["packetIdentity"] == plan["identity"]
    assert auth["helperSubject"] == plan["helperSubject"]
    for key, state in [
        ("runtimeReview", "independent-owned-registry-runtime-review-passed"),
        ("helperReview", "independent-owned-registry-helper-review-passed"),
    ]:
        item = auth[key]
        assert sha(Path(item["path"]).read_bytes()) == item["sha256"]
        decision = read(Path(item["path"]))
        assert decision["state"] == state and decision["findings"] == []
        assert decision["subject"] == auth[key.replace("Review", "Subject")]
        assert decision["executionAuthorized"] is False
    receipts = read(RAW / "trace.json")["receipts"]
    assert len(receipts) == result["daemonCalls"] == 18
    for name, receipt in receipts.items():
        path = RAW / name
        assert read(path) == receipt
        for stream in ["stdout", "stderr"]:
            assert sha((path.parent / (stream + ".bin")).read_bytes()) == receipt[stream + "Sha256"]
        assert receipt["costUsd"] is None and receipt["costExclusions"]
        assert receipt["error"] is None and receipt["cancelled"] is False
        assert receipt["exitCode"] == (1 if "post-cleanup-inspect" in name else 0)
    assert result["costUsd"] is None and result["modelCalls"] == 0
    assert result["elapsedSeconds"] <= plan["limits"]["workSecondsIncludingPreflight"]
    assert result["cleanupSeconds"] <= plan["limits"]["cleanupSeconds"]
    input_raw = Path(plan["input"]["path"]).read_bytes()
    assert sha(input_raw) == plan["input"]["sha256"] == result["inputSha256"]
    assert len(input_raw) == plan["input"]["bytes"]
    cli = receipts["logs/owned-cli/receipt.json"]
    assert cli["stdinSha256"] == sha(input_raw) and cli["stdinBytes"] == len(input_raw)
    wire = (RAW / "registry.gz").read_bytes()
    assert cli["binarySha256"] == sha(wire) and cli["binaryBytes"] == len(wire)
    sys.path.insert(0, str(HELPER / "amendment-1"))
    builder = importlib.import_module("build_input")
    receiver = importlib.import_module("read_registry")
    comparator = importlib.import_module("crosscheck_registry")
    json_raw = receiver.inflate(wire)
    registry = builder.load(json_raw)
    provenance = builder.load((HELPER / "input-provenance.json").read_bytes())
    packages = builder.load(Path(provenance["packageInventoryPath"]).read_bytes())
    assert (
        sha(Path(provenance["packageInventoryPath"]).read_bytes()) == builder.PACKAGE_INVENTORY_SHA
    )
    received = receiver.validate(registry, provenance, packages)
    assert received["packages"] == 104 and received["declarations"] == 6031
    assert not received["hasSourceDiagnostics"] and registry["state"] == "source-derived-uncompiled"
    retained_received = read(RAW / "received.json")
    for key, value in received.items():
        assert retained_received[key] == value
    assert retained_received["jsonSha256"] == sha(json_raw)
    assert retained_received["expandedBytes"] == len(json_raw)
    # A separate physical-source check, rather than trusting only output metadata.
    inputs = builder.load(input_raw)
    sources = {}
    for package in inputs["packages"]:
        for field in ["testGoFiles", "xTestGoFiles"]:
            for item in package[field]:
                data = base64.b64decode(item["dataBase64"], validate=True)
                assert sha(data) == item["sha256"] and len(data) == item["bytes"]
                sources[item["path"]] = data
    kinds = Counter()
    for package in registry["packages"]:
        for field in receiver.FIELDS:
            for item in package[field]:
                data = sources[item["sourcePath"]]
                start, end = item["offset"], item["endOffset"]
                assert re.match(
                    rb"func\s+" + re.escape(item["name"].encode()) + rb"\s*[\[(]", data[start:end]
                )
                assert data[:start].count(b"\n") + 1 == item["line"]
                assert start - data.rfind(b"\n", 0, start) == item["column"]
                kinds[item["kind"]] += 1
    # Module inventories are exactly the three owned sources; upstream input was stdin.
    for phase in ["before", "after"]:
        manifest = read(RAW / ("module-" + phase + ".json"))["manifest"]
        assert manifest == plan["moduleFiles"]
        observed = {}
        with tarfile.open(
            fileobj=io.BytesIO((RAW / ("module-" + phase + ".tar")).read_bytes())
        ) as archive:
            for member in archive:
                if member.isdir():
                    continue
                assert member.isreg()
                name = member.name.removeprefix("./")
                data = archive.extractfile(member).read()
                observed[name] = {"bytes": len(data), "sha256": sha(data)}
        assert observed == plan["moduleFiles"]
    assert (RAW / "logs/tools-before/stdout.bin").read_bytes() == (
        RAW / "logs/tools-after/stdout.bin"
    ).read_bytes()
    units = [
        builder.load(line)
        for line in (RAW / "logs/owned-tests/stdout.bin").read_bytes().splitlines()
    ]
    runs = [r["Test"] for r in units if r["Action"] == "run"]
    terminals = [r for r in units if r.get("Test") and r["Action"] in ["pass", "fail", "skip"]]
    assert len(runs) == len(set(runs)) == 29
    assert sorted(runs) == sorted(plan["expectedTestIds"]) == sorted(result["ownedTestIds"])
    assert Counter(r["Test"] for r in terminals) == Counter(runs)
    assert all(r["Action"] == "pass" for r in terminals)
    assert [
        r["Action"] for r in units if not r.get("Test") and r["Action"] in ["pass", "fail", "skip"]
    ] == ["pass"]
    assert not any(r["Action"] in ["build-fail", "fail", "skip"] for r in units)
    # Reconstruct the prior partial observations directly from its retained raw stream.
    freeze(
        NATIVE / "FREEZE.json", "f2588d3ee2bdee8c5b40d5f5a328d72dd07c0f093fd6e36904a9dcecec5256a2"
    )
    native_raw = (NATIVE / "evidence/logs/go-test-list/stdout.bin").read_bytes()
    assert sha(native_raw) == "3e35220c5d834daec10a374f21b7855e57da27d7788f1b83af123f6e5e55f202"
    events = [builder.load(line) for line in native_raw.splitlines()]
    observations = builder.load((HELPER / "partial-listing-observations.json").read_bytes())
    rows = {p: {"names": [], "terminal": None, "noTest": False} for p in packages}
    for event in events:
        name = event.get("Package")
        if name not in rows:
            continue
        assert not event.get("Test")
        row = rows[name]
        if event["Action"] in ["pass", "fail", "skip"]:
            assert row["terminal"] is None
            row["terminal"] = event["Action"]
        if event["Action"] == "output":
            for line in event["Output"].splitlines():
                if re.fullmatch(r"(?:Test|Benchmark|Fuzz|Example)\S*", line):
                    row["names"].append(line)
                row["noTest"] |= "[no test files]" in line
    for name, row in rows.items():
        observation = observations["packages"][name]
        assert row["terminal"] == observation["nativeListingTerminal"]
        assert row["names"] == observation["observedNameLines"]
        assert row["noTest"] == observation["noTestFilesDiagnostic"]
        assert observation["selectedTestSourceFiles"] == len(
            packages[name].get("TestGoFiles", [])
        ) + len(packages[name].get("XTestGoFiles", []))
    independent = {
        "matchedPassPackages": [],
        "matchedNoTestPackages": [],
        "unvalidatedFailedPackages": [],
        "differences": [],
    }
    for package in registry["packages"]:
        name = package["importPath"]
        observed = rows[name]
        names = [
            item["name"]
            for field in ["tests", "benchmarks", "fuzzTargets", "examples"]
            for item in package[field]
        ]
        if observed["terminal"] == "fail":
            independent["unvalidatedFailedPackages"].append(name)
        elif (
            observed["terminal"] == "pass"
            and names == observed["names"]
            and not package["diagnostics"]
        ):
            independent["matchedPassPackages"].append(name)
        elif (
            observed["terminal"] == "skip"
            and observed["noTest"]
            and not names
            and not package["diagnostics"]
            and not packages[name].get("TestGoFiles", [])
            and not packages[name].get("XTestGoFiles", [])
        ):
            independent["matchedNoTestPackages"].append(name)
        else:
            independent["differences"].append(name)
    compared = comparator.compare(registry, observations)
    for key, values in independent.items():
        assert sorted(compared[key]) == sorted(values)
    assert [len(independent[k]) for k in independent] == [25, 18, 61, 0]
    for flag in [
        "nativeCollectionOccurred",
        "taskOutcomeObserved",
        "campaignAdmitted",
        "oracleQualified",
        "cacheGloballyQualified",
    ]:
        assert result[flag] is False
    output(
        "independent-partial-comparison.json",
        {
            **independent,
            "sourceDiagnostics": [],
            "rawNativeEvents": len(events),
            "rawNativeSha256": sha(native_raw),
            "nativeFullCollectionExists": False,
            "compileValidityUnestablished": True,
            "taskOutcomeObserved": False,
            "collectionGateChanged": False,
        },
    )
    output(
        "raw-verification.json",
        {
            "state": "raw-owned-tool-evidence-verified-unqualified",
            "rawFreezeSha256": sha((RAW / "FREEZE.json").read_bytes()),
            "rawArtifacts": raw_count,
            "closureCounts": closure_counts,
            "daemonReceiptsVerified": len(receipts),
            "ownedUnitIds": sorted(runs),
            "ownedUnitsPassed": 29,
            "registry": {
                "wireSha256": sha(wire),
                "wireBytes": len(wire),
                "jsonSha256": sha(json_raw),
                "jsonBytes": len(json_raw),
                "packages": 104,
                "declarations": dict(kinds),
                "physicalSourceLocationsChecked": sum(kinds.values()),
                "sourceDiagnostics": [],
            },
            "sourceFiles": len(sources),
            "moduleFilesBeforeAfterMatched": 3,
            "toolHashBeforeAfterMatched": True,
            "newRuntimeActions": 0,
            "elapsedSeconds": result["elapsedSeconds"],
            "costUsd": None,
            "nativeCollectionOccurred": False,
            "taskOutcomeObserved": False,
        },
    )
    print(
        json.dumps(
            {
                "rawArtifacts": raw_count,
                "units": len(runs),
                "declarations": dict(kinds),
                "partial": {k: len(v) for k, v in independent.items()},
            }
        )
    )


if __name__ == "__main__":
    main()
