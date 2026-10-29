"""Python-only adversarial controls for future raw gzip/JSON receiving."""

from copy import deepcopy
import gzip
import json
from pathlib import Path
import zlib

import build_input as builder
import read_registry as receiver
import crosscheck_registry as crosscheck

HERE = Path(__file__).resolve().parent


def wire(raw):
    value = bytearray(gzip.compress(raw, compresslevel=9, mtime=0))
    value[9] = 255
    return bytes(value)


def refused(operation):
    try:
        operation()
    except (ValueError, KeyError, TypeError, zlib.error):
        return True
    raise AssertionError("invalid receiver fixture accepted")


def main():
    raw = b'{"owned":true}\n'
    value = wire(raw)
    assert receiver.inflate(value) == raw
    checks = [{"case": "owned single deterministic member", "passed": True}]
    crc = bytearray(value)
    crc[-8] ^= 1
    timestamp = bytearray(value)
    timestamp[4] = 1
    flag = bytearray(value)
    flag[3] = 8
    for name, changed in [
        ("truncated member", value[:-1]),
        ("bad CRC", bytes(crc)),
        ("multiple members", value + value),
        ("trailing bytes", value + b"x"),
        ("timestamp header", bytes(timestamp)),
        ("filename flag", bytes(flag)),
        ("compressed cap", b"x" * (receiver.MAX_COMPRESSED + 1)),
        ("expanded cap", wire(b"x" * (receiver.MAX_EXPANDED + 1))),
    ]:
        checks.append(
            {"case": "reject " + name, "passed": refused(lambda: receiver.inflate(changed))}
        )
    checks.append(
        {
            "case": "reject duplicate expanded JSON key",
            "passed": refused(lambda: builder.load(receiver.inflate(wire(b'{"x":1,"x":2}')))),
        }
    )
    package = builder.PREFIX + "/owned"
    source = "tsc/owned/owned_test.go"
    source_sha = builder.sha(b"owned source")
    declaration = {
        "kind": "test",
        "name": "TestOwned",
        "sourcePath": source,
        "sourceSha256": source_sha,
        "packageRole": "internal",
        "line": 1,
        "column": 1,
        "offset": 0,
        "endOffset": 5,
    }
    declaration["id"] = builder.sha(
        "\x00".join([package, source, source_sha, "internal", "test", "TestOwned", "0"]).encode()
    )
    packages = {package: {"Dir": builder.CWD + "/owned", "TestGoFiles": ["owned_test.go"]}}
    provenance = {
        "sourceContext": {"syntheticOwnedFixture": True},
        "inputSha256": "0" * 64,
        "selectedFiles": {source: {"sha256": source_sha, "bytes": 12}},
    }
    row = {
        "importPath": package,
        "tests": [declaration],
        "benchmarks": [],
        "fuzzTargets": [],
        "examples": [],
        "testMains": [],
        "diagnostics": [],
        "state": "source-derived-uncompiled",
        "compileValidityUnestablished": True,
    }
    registry = {
        "schema": "go01-source-registry-output-v1",
        "state": "source-derived-uncompiled",
        "sourceContext": provenance["sourceContext"],
        "helperGoVersion": "go1.27.3",
        "helperGOOS": "linux",
        "helperGOARCH": "arm64",
        "inputSha256": "0" * 64,
        "packages": [row],
        "universalCompileValidityUnestablished": True,
        "nativeCollectionOccurred": False,
        "taskOutcomeObserved": False,
    }
    receiver.validate(registry, provenance, packages)
    checks.append(
        {"case": "owned synthetic schema/ID validation only, not corpus output", "passed": True}
    )
    for name, mutate in [
        (
            "duplicate declaration ID",
            lambda r: r["packages"][0]["tests"].append(deepcopy(declaration)),
        ),
        ("wrong source hash", lambda r: r["packages"][0]["tests"][0].update(sourceSha256="0" * 64)),
        ("wrong ID", lambda r: r["packages"][0]["tests"][0].update(id="0" * 64)),
        ("missing package", lambda r: r.update(packages=[])),
        ("unknown field", lambda r: r.update(unknown=True)),
        ("native claim", lambda r: r.update(nativeCollectionOccurred=True)),
        ("compile claim", lambda r: r.update(universalCompileValidityUnestablished=False)),
        ("helper version", lambda r: r.update(helperGoVersion="other")),
        ("source context", lambda r: r.update(sourceContext={})),
        ("invalid location", lambda r: r["packages"][0]["tests"][0].update(endOffset=100)),
    ]:
        changed = deepcopy(registry)
        mutate(changed)
        checks.append(
            {
                "case": "reject " + name,
                "passed": refused(lambda: receiver.validate(changed, provenance, packages)),
            }
        )
    # Comparator-only owned data: this is deliberately not a helper-produced registry.
    fixture_observations, fixture_rows = {}, []
    for number in range(104):
        name = "owned/" + str(number)
        status = "pass" if number < 25 else "skip" if number < 43 else "fail"
        fixture_observations[name] = {
            "nativeListingTerminal": status,
            "observedNameLines": ["TestA", "TestB"] if status == "pass" else [],
            "noTestFilesDiagnostic": status == "skip",
            "selectedTestSourceFiles": 1 if status == "pass" else 0,
        }
        fixture_rows.append(
            {"importPath": name, **{field: [] for field in receiver.FIELDS}, "diagnostics": []}
        )
        if status == "pass":
            fixture_rows[-1]["tests"] = [{"name": "TestA"}, {"name": "TestB"}]
    fixture = {"packages": fixture_rows}
    observation_fixture = {"packages": fixture_observations}
    comparison = crosscheck.compare(fixture, observation_fixture)
    assert (
        not comparison["differences"]
        and len(comparison["unvalidatedFailedPackages"]) == 61
        and comparison["compileValidityUnestablished"] is True
    )
    checks.append(
        {
            "case": "owned comparator retains61 unvalidated packages, no native qualification",
            "passed": True,
        }
    )
    for label, mutate in [
        ("missing name", lambda r: r["packages"][0]["tests"].pop()),
        ("extra name", lambda r: r["packages"][0]["tests"].append({"name": "TestOther"})),
        ("name order", lambda r: r["packages"][0]["tests"].reverse()),
        (
            "nonempty no-test package",
            lambda r: r["packages"][25]["tests"].append({"name": "TestOther"}),
        ),
    ]:
        changed = deepcopy(fixture)
        mutate(changed)
        assert crosscheck.compare(changed, observation_fixture)["differences"]
        checks.append({"case": "comparator rejects " + label, "passed": True})
    with (HERE / "receiver-controls.json").open("x") as stream:
        json.dump(
            {
                "state": "passed-python-owned-receiver-controls",
                "passed": len(checks),
                "controls": checks,
                "GoHelperBuiltOrRun": False,
                "nativeCollectionOccurred": False,
                "syntheticFixturesNotCorpusRegistry": True,
            },
            stream,
            indent=2,
        )
        stream.write("\n")
    print(json.dumps({"passed": len(checks), "GoHelperBuiltOrRun": False}))


if __name__ == "__main__":
    main()
