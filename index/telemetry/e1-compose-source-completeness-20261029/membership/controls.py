"""Owned parser/selection counterexamples and inert source integrity controls."""

import hashlib
import json
from pathlib import Path
import tarfile

from inspect_headers import header
import membership as m

HERE = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    cases = []

    def check(name, value):
        assert value, name
        cases.append(name)

    for text, tags, expected in [
        ("a", {"a"}, True),
        ("!a", set(), True),
        ("a || b && c", {"a"}, True),
        ("a || b && c", {"b"}, False),
        ("(a || b) && c", {"a"}, False),
        ("!(a && b) || c", {"a"}, True),
        ("linux && !windows", {"linux"}, True),
    ]:
        check(
            "expression-" + text + repr(sorted(tags)), m.Expression(text).evaluate(tags) == expected
        )
    for text in ["", "a b", "a &&", "a | b", "!", "(a", "a)", "a &&&& b"]:
        try:
            m.Expression(text).evaluate(set())
        except ValueError:
            check("invalid-expression-" + text, True)
        else:
            raise AssertionError(text)
    check("legacy-or-and", m.legacy(["linux,!windows darwin", "cgo"], {"linux", "cgo"}))
    check("legacy-lines-AND", not m.legacy(["linux darwin", "cgo"], {"linux"}))
    for name, os, arch, expected in [
        ("x_linux.go", "linux", "arm64", True),
        ("x_linux_test.go", "linux", "amd64", True),
        ("x_windows.go", "linux", "arm64", False),
        ("x_linux_arm64_test.go", "linux", "arm64", True),
        ("x_linux_arm64_test.go", "linux", "amd64", False),
        ("x_unix.go", "linux", "arm64", True),
        ("linux.go", "darwin", "arm64", True),
        ("_ignored.go", "linux", "arm64", False),
    ]:
        check("filename-" + name + os + arch, m.filename_matches(name, os, arch) == expected)
    for prefix in [b"", b"\xef\xbb\xbf", b"// owned\n", b"/* owned */\n"]:
        raw = prefix + b"package owned\nfunc notRead() {}\n"
        retained, package, _ = header(raw)
        check(
            "byte-exact-header-" + repr(prefix),
            retained == prefix + b"package owned\n" and package == "owned",
        )
    for raw in [b"// no package\n", b"/* unclosed", b"func bad() {}"]:
        try:
            header(raw)
        except ValueError:
            check("malformed-header-" + repr(raw), True)
        else:
            raise AssertionError(raw)

    def row(path, expr=None):
        return {
            "path": path,
            "goBuild": [] if expr is None else [expr],
            "plusBuild": [],
            "package": "owned",
        }

    def calculate(rows, modules=("go.mod",), module="example.com/owned", excluded=()):
        return m.calculate(rows, {"entries": dict.fromkeys(modules)}, "arm64", module, excluded)

    result = calculate([row("unit/only_test.go")])[0]
    check("test-only-package-enumerable", result["selectedByProspectiveRelay"])
    result = calculate([row("tagged/only_test.go", "e2e")])[0]
    check("tag-only-unit-omission-detected", result["unitTestPackageOmittedBySourceSelection"])
    result = calculate([row("type2enum/only_test.go")])[0]
    check("substring-not-path-classifier", result["unitTestPackageOmittedBySourceSelection"])
    result = calculate([row("unit/only_test.go")], module="example.com/e2e-project")[0]
    check(
        "module-derived-not-answer-allowlisted", result["unitTestPackageOmittedBySourceSelection"]
    )
    result = calculate([row("nested/only_test.go")], modules=("go.mod", "nested/go.mod"))[0]
    check("nested-module-not-root-walk", not result["mainModuleWalkIncluded"])
    for directory in ["testdata", "vendor", ".hidden", "_ignored"]:
        result = calculate([row(directory + "/only_test.go")])[0]
        check("ignored-directory-" + directory, not result["mainModuleWalkIncluded"])
    result = calculate([row("other/only_test.go", "e2e")], excluded=("other",))[0]
    check("source-scope-data-exclusion", not result["hasIntendedSelectedTests"])

    plan = json.loads((HERE / "plan.json").read_bytes())
    inventory = json.loads((HERE / "acquisition-inventory.json").read_bytes())
    heads = json.loads((HERE / "headers.json").read_bytes())
    observed = json.loads((HERE / "membership.json").read_bytes())
    source = Path(plan["archive"]["path"])
    check("archive-raw-binding", sha(source.read_bytes()) == plan["archive"]["sha256"])
    with tarfile.open(source, "r:") as archive:
        for item in heads["headers"]:
            body = archive.extractfile(item["path"]).read()
            raw = (HERE / "headers" / item["path"]).read_bytes()
            assert body.startswith(raw) and sha(raw) == item["headerSha256"]
            assert sha(body) == item["sourceSha256"]
            assert header(body[:32768])[0] == raw
    check("all-407-byte-exact-headers", len(heads["headers"]) == 407)
    packages = observed["representativeContext"]["packages"]
    check(
        "all-unit-file-sets-identical-between-two-tag-contexts",
        all(
            row["untagged"] == row["intendedE2eTag"]
            for row in packages
            if row["intendedUnitDirectory"]
        ),
    )
    check(
        "actual-source-no-unit-package-omission",
        not any(r["unitTestPackageOmittedBySourceSelection"] for r in packages),
    )
    check(
        "literal-exclusion-only-actual-e2e-directory",
        [
            r["directory"]
            for r in packages
            if r["mainModuleWalkIncluded"] and not r["selectedByProspectiveRelay"]
        ]
        == ["pkg/e2e"],
    )
    check(
        "actual-only-two-module-boundaries",
        sorted(x for x in inventory["entries"] if x.rsplit("/", 1)[-1] == "go.mod")
        == ["go.mod", "relay/go.mod"],
    )
    for packet, expected in [
        (HERE.parent, "921d2e40b8a5cc5609181b2bc384339ccbfd609e3cc369f0138f426fc4cc43dd"),
        (source.parent, plan["acquisitionFreezeSha256"]),
    ]:
        raw = (packet / "FREEZE.json").read_bytes()
        assert sha(raw) == expected
        freeze = json.loads(raw)
        for name, value in freeze["artifacts"].items():
            body = (packet / name).read_bytes()
            assert sha(body) == value["sha256"] and len(body) == value["bytes"]
        check("frozen-parent-integrity-" + packet.name, True)
    report = {
        "allPassed": True,
        "count": len(cases),
        "checks": cases,
        "headersVerified": 407,
        "parentArtifactsUnchanged": 25,
        "acquisitionArtifactsUnchanged": 35,
        "actualSourceUnitTestFilesInIntendedContext": sum(
            len(r["intendedE2eTag"]["test"]) for r in packages if r["intendedUnitDirectory"]
        ),
        "sourceOrGoExecuted": False,
        "nativeCollectionOccurred": False,
        "completeTupleAccepted": False,
    }
    with (HERE / "controls.json").open("x") as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"allPassed": True, "count": len(cases), "headers": 407}))


if __name__ == "__main__":
    main()
