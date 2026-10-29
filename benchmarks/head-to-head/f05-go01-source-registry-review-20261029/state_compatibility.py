"""Python-only valid-state/partial-comparison checks on disclosed owned fixtures."""

from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
AUTHOR = Path(json.loads((HERE / "author-binding.json").read_text())["packet"])
sys.path.insert(0, str(AUTHOR))
receiver = importlib.import_module("read_registry")
crosscheck = importlib.import_module("crosscheck_registry")


def main():
    observations = {}
    rows = []
    for n in range(104):
        name = "owned/" + str(n)
        status = "pass" if n < 25 else "skip" if n < 43 else "fail"
        observations[name] = {
            "nativeListingTerminal": status,
            "observedNameLines": ["TestOwned"] if status == "pass" else [],
            "noTestFilesDiagnostic": status == "skip",
            "selectedTestSourceFiles": 1 if status == "pass" else 0,
        }
        row = {"importPath": name, **{f: [] for f in receiver.FIELDS}, "diagnostics": []}
        if status == "pass":
            row["tests"] = [{"name": "TestOwned"}]
        rows.append(row)
    base = {"packages": rows}
    obs = {"packages": observations}
    checks = []
    result = crosscheck.compare(base, obs)
    assert (
        result["differences"] == []
        and len(result["matchedPassPackages"]) == 25
        and len(result["matchedNoTestPackages"]) == 18
        and len(result["unvalidatedFailedPackages"]) == 61
    )
    checks.append({"case": "ordinary owned partial comparison", "passed": True})
    for index, expected_difference in [(0, True), (25, True), (43, False)]:
        value = deepcopy(base)
        value["packages"][index]["diagnostics"] = [
            {
                "code": "parse-error",
                "sourcePath": "owned_test.go",
                "message": "owned unresolved source",
            }
        ]
        compared = crosscheck.compare(value, obs)
        name = value["packages"][index]["importPath"]
        assert name in compared["sourceRegistryDiagnosticsPackages"]
        assert bool(compared["differences"]) == expected_difference
        if index == 43:
            assert name in compared["unvalidatedFailedPackages"]
        assert (
            compared["nativeFullCollectionExists"] is False
            and compared["compileValidityUnestablished"] is True
            and compared["collectionGateChanged"] is False
        )
        checks.append(
            {
                "case": "diagnostics preserved for native "
                + observations[name]["nativeListingTerminal"],
                "passed": True,
                "partialState": compared["state"],
                "diagnosticPackage": name,
                "failedStillSourceOnly": index == 43,
            }
        )
    source = (AUTHOR / "registry.go").read_text()
    assert 'if out.State != "source-derived-uncompiled" {\n\t\tos.Exit(1)' in source
    result = {
        "state": "valid-state static/Python compatibility passed",
        "checks": checks,
        "producerExitSemanticsStatic": "main exits0 after source-derived,1 after fully emitted unresolved,2 on input/encoding/transport errors; Go unrun",
        "receiverGap": "Malformed diagnostic/optional/nonfinite cases retained separately as findingF1; these checks do not bless schema completeness.",
        "diagnosticRetention": "Partial comparison names diagnostic packages; full codes/messages remain in retained raw source-registry output. Failed61never become live validated.",
        "fixtureDisclosure": "104owned synthetic package labels, not corpus source-registry or Go helper output",
        "GoCompiledOrRun": False,
        "newNativeOrNetworkActions": 0,
    }
    with (HERE / "state-compatibility.json").open("x") as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps({"passed": len(checks), "GoCompiledOrRun": False}))


if __name__ == "__main__":
    main()
