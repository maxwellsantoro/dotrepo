"""Read-only derivation review; never establishes a runtime manifest or outcome."""

from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROPOSAL = ROOT / "benchmarks/head-to-head/f05-go01-source-oracle-decision-20261029"
HELPER = ROOT / "benchmarks/head-to-head/f05-go01-source-registry-20261029"
RESULT = ROOT / "benchmarks/head-to-head/f05-go01-source-registry-result-20261029"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def derive(registry, packages):
    assert registry["state"] == "source-derived-uncompiled"
    rows = registry["packages"]
    assert [r["importPath"] for r in rows] == sorted(packages)
    expected = {}
    for row in rows:
        assert not row["diagnostics"] and row["state"] == "source-derived-uncompiled"
        names = sorted(d["name"] for key in ["tests", "examples", "fuzzTargets"] for d in row[key])
        assert len(names) == len(set(names))
        expected[row["importPath"]] = names
    return expected


def main():
    assert (
        sha((PROPOSAL / "FREEZE.json").read_bytes())
        == "22e72402f3cadf7f5ea214a546a3dcaf18b968c67da81e9e03427436c4d10ed5"
    )
    freeze = json.loads((PROPOSAL / "FREEZE.json").read_bytes())
    for name, digest in freeze["artifactSha256"].items():
        assert sha((PROPOSAL / name).read_bytes()) == digest
    sources = json.loads((PROPOSAL / "source-bindings.json").read_bytes())["files"]
    for item in sources:
        raw = (ROOT / item["path"]).read_bytes()
        assert len(raw) == item["bytes"] and sha(raw) == item["sha256"], item["path"]
    sys.path.insert(0, str(HELPER / "amendment-1"))
    builder = importlib.import_module("build_input")
    receiver = importlib.import_module("read_registry")
    wire = (RESULT / "evidence/registry.gz").read_bytes()
    raw = receiver.inflate(wire)
    value = builder.load(raw)
    provenance = builder.load((HELPER / "input-provenance.json").read_bytes())
    packages = builder.load(Path(provenance["packageInventoryPath"]).read_bytes())
    receiver.validate(value, provenance, packages)
    recipe = builder.load((PROPOSAL / "expectation-recipe.json").read_bytes())
    assert (
        sha(wire) == recipe["registryGzipSha256"] and sha(raw) == recipe["registryExpandedSha256"]
    )
    assert value["sourceContext"] == recipe["sourceContext"]
    expected = derive(value, packages)
    encoded = canonical(expected)
    target = recipe["canonicalExpectedNameMap"]
    assert sha(encoded) == target["sha256"] and len(encoded) == target["bytes"]
    assert len(expected) == target["packages"] == 104
    assert sum(len(v) for v in expected.values()) == target["names"] == 5972
    assert sum(not v for v in expected.values()) == target["emptyNamePackages"] == 40
    assert recipe["requiredKinds"] == ["tests", "examples", "fuzzTargets"]
    per_package = [
        {"package": p, "requiredTopLevelNames": len(names), "namesSha256": sha(canonical(names))}
        for p, names in expected.items()
    ]
    assert per_package == recipe["perPackage"]
    cases = []

    def rejects(name, mutate):
        candidate = deepcopy(value)
        mutate(candidate)
        try:
            derive(candidate, packages)
        except (AssertionError, KeyError, TypeError):
            cases.append({"case": name, "passed": True})
            return
        raise AssertionError("bad derivation admitted: " + name)

    rejects("missing package", lambda v: v["packages"].pop())
    rejects("duplicate package", lambda v: v["packages"].append(deepcopy(v["packages"][0])))
    rejects("unresolved registry", lambda v: v.update(state="unresolved-source-discovery"))
    rejects(
        "diagnostic package", lambda v: v["packages"][0]["diagnostics"].append({"code": "owned"})
    )
    rejects(
        "duplicate runtime name",
        lambda v: v["packages"][0]["tests"].append(deepcopy(v["packages"][0]["tests"][0])),
    )
    changed = deepcopy(value)
    for row in changed["packages"]:
        row["benchmarks"] = [{"name": "BenchmarkOwnedMutation"}]
        row["testMains"] = [{"name": "TestMainOwnedMutation"}]
    assert derive(changed, packages) == expected
    cases.append(
        {
            "case": "benchmarks and wrapper metadata excluded from required runtime case names",
            "passed": True,
        }
    )
    assert len(expected) == 104 and sum(not v for v in expected.values()) == 40
    cases.append(
        {"case": "all empty-name packages preserved for package-level coverage", "passed": True}
    )
    assert value["nativeCollectionOccurred"] is False and value["taskOutcomeObserved"] is False
    cases.append(
        {"case": "source input carries no native collection or task outcome", "passed": True}
    )
    report = {
        "state": "prospective-recipe-reproduced-not-admitted",
        "proposalFreezeSha256": sha((PROPOSAL / "FREEZE.json").read_bytes()),
        "sourceBindingsVerified": len(sources),
        "packages": 104,
        "requiredNames": 5972,
        "emptyNamePackages": 40,
        "mapSha256": sha(encoded),
        "mapBytes": len(encoded),
        "fullMapRetainedAsAcceptedManifest": False,
        "perPackageHashesReproduced": 104,
        "cases": cases,
        "currentGateChanged": False,
        "oracleQualified": False,
        "newGoNodeDockerNativeNetworkProviderActions": 0,
    }
    with (HERE / "recipe-verification.json").open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        json.dumps(
            {
                "packages": 104,
                "names": 5972,
                "empty": 40,
                "cases": len(cases),
                "mapSha256": sha(encoded),
            }
        )
    )


if __name__ == "__main__":
    main()
