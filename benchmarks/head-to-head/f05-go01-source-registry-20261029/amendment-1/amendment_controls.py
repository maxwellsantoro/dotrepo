"""Python-only schema/state challenges; not Go-produced corpus observations."""

from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
AUTHOR = HERE
sys.path.insert(0, str(AUTHOR))
builder = importlib.import_module("build_input")
receiver = importlib.import_module("read_registry")
crosscheck = importlib.import_module("crosscheck_registry")


def accepts(operation):
    try:
        operation()
        return True
    except (ValueError, KeyError, TypeError):
        return False


def main():
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
    cases = []

    def check(name, expected, value):
        observed = accepts(lambda: receiver.validate(value, provenance, packages))
        cases.append({"case": name, "expectedAccepted": expected, "actualAccepted": observed})

    check("valid source-derived state", True, registry)
    unresolved = deepcopy(registry)
    unresolved["packages"][0].update(
        diagnostics=[{"code": "parse-error", "sourcePath": source, "message": "owned error"}],
        state="unresolved-source-discovery",
    )
    unresolved["state"] = "unresolved-source-discovery"
    check("valid unresolved state", True, unresolved)
    inconsistent = deepcopy(unresolved)
    inconsistent["state"] = "source-derived-uncompiled"
    check("state hides diagnostics", False, inconsistent)
    for name, mutate in [
        ("diagnostic scalar", lambda r: r["packages"][0].update(diagnostics=[42])),
        ("diagnostic missing fields", lambda r: r["packages"][0].update(diagnostics=[{}])),
        (
            "diagnostic wrong field types",
            lambda r: r["packages"][0].update(
                diagnostics=[{"code": False, "sourcePath": [], "message": 1}]
            ),
        ),
    ]:
        candidate = deepcopy(unresolved)
        mutate(candidate)
        check(name, False, candidate)
    for key, value in [("output", []), ("emptyOutput", 1), ("unordered", "yes")]:
        candidate = deepcopy(registry)
        candidate["packages"][0]["tests"][0][key] = value
        check("wrong optional declaration type " + key, False, candidate)
    nan_value = deepcopy(registry)
    nan_value["packages"][0]["tests"][0]["output"] = float("nan")
    raw = json.dumps(nan_value).encode()
    cases.append(
        {
            "case": "non-JSON NaN accepted through loader and optional field",
            "expectedAccepted": False,
            "actualAccepted": accepts(
                lambda: receiver.validate(builder.load(raw), provenance, packages)
            ),
        }
    )
    for token in [b"Infinity", b"-Infinity", b"1e999", b"-1e999"]:
        cases.append(
            {
                "case": "reject nonfinite numeric token " + token.decode(),
                "expectedAccepted": False,
                "actualAccepted": accepts(lambda: builder.load(b'{"v":' + token + b"}")),
            }
        )
    for token in [float("nan"), float("inf"), -float("inf")]:
        cases.append(
            {
                "case": "reject nonfinite encoding " + str(token),
                "expectedAccepted": False,
                "actualAccepted": accepts(lambda: builder.encode({"v": token})),
            }
        )
    for diagnostic in [
        {"code": "parse-error", "sourcePath": source, "message": "owned parse error"},
        {"code": "package-clause-mismatch", "sourcePath": source, "message": "other"},
        {"code": "invalid-discovery-signature", "sourcePath": source, "message": "TestOwned"},
        {"code": "example-location-unresolved", "sourcePath": source, "message": "ExampleOwned"},
        {"code": "duplicate-runtime-name-unresolved", "sourcePath": source, "message": "TestOwned"},
        {"code": "multiple-testmain-unresolved", "message": "multiple wrapper declarations"},
    ]:
        candidate = deepcopy(unresolved)
        candidate["packages"][0]["diagnostics"] = [diagnostic]
        check("valid producer diagnostic " + diagnostic["code"], True, candidate)
    for label, diagnostic in [
        ("unknown key", {"code": "parse-error", "message": "owned", "extra": True}),
        ("missing message", {"code": "parse-error"}),
        ("empty code", {"code": "", "message": "owned"}),
        ("empty message", {"code": "parse-error", "message": ""}),
        ("wrong source type", {"code": "parse-error", "message": "owned", "sourcePath": []}),
        (
            "unknown source",
            {"code": "parse-error", "message": "owned", "sourcePath": "tsc/elsewhere_test.go"},
        ),
    ]:
        candidate = deepcopy(unresolved)
        candidate["packages"][0]["diagnostics"] = [diagnostic]
        check("invalid diagnostic " + label, False, candidate)
    example = deepcopy(declaration)
    example.update(kind="example", name="ExampleOwned")
    example["id"] = builder.sha(
        "\x00".join(
            [package, source, source_sha, "internal", "example", "ExampleOwned", "0"]
        ).encode()
    )
    for label, optional in [
        ("nonempty output", {"output": "owned\n"}),
        ("empty output", {"emptyOutput": True}),
        ("unordered output", {"output": "b\na\n", "unordered": True}),
        (
            "literal false and empty string",
            {"output": "", "emptyOutput": False, "unordered": False},
        ),
    ]:
        candidate = deepcopy(registry)
        candidate["packages"][0]["tests"] = []
        candidate["packages"][0]["examples"] = [{**example, **optional}]
        check("valid typed optional example " + label, True, candidate)
    for key, value in [("output", None), ("emptyOutput", False), ("unordered", True)]:
        candidate = deepcopy(registry)
        candidate["packages"][0]["tests"][0][key] = value
        check("optional field literal boundary " + key, key != "output", candidate)
    for label, candidate in [
        ("root scalar", 42),
        ("package scalar", {**registry, "packages": [42]}),
    ]:
        check("reject " + label, False, candidate)
    assert all(row["actualAccepted"] == row["expectedAccepted"] for row in cases), cases
    results = {
        "fixtureDisclosure": "Synthetic Python shapes only, no Go/helper/native observations",
        "cases": cases,
        "unexpectedAcceptances": [r for r in cases if r["actualAccepted"] != r["expectedAccepted"]],
        "newGoDaemonNodePackageNetworkNativeCalls": 0,
        "beforeReviewFreezeSha256": "df6d752afd787928917416664c879a5422edf632750ba3e2d52cb37f2edce074",
        "state": "passed-amended-receiver-python-controls",
    }
    with (HERE / "receiver-challenge.json").open("x") as f:
        json.dump(results, f, indent=2)
        f.write("\n")
    print(json.dumps(results))


if __name__ == "__main__":
    main()
