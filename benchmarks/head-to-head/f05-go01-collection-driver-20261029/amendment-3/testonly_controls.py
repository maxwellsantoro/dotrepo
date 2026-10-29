"""Static/raw-fixture and fake test-only Go-package admission controls."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile

import collection
import controls  # Prohibits real process/socket access.
import listing

HERE = Path(__file__).resolve().parent


def refused(operation):
    try:
        operation()
    except (ValueError, KeyError, TypeError):
        return True
    raise AssertionError("invalid package observation accepted")


def encoded(rows):
    return b"\n".join(json.dumps(row).encode() for row in rows) + b"\n"


def main():
    plan = collection.load_plan()
    before = json.loads((HERE.parent / "amendment-2/plan.json").read_bytes())
    for key in [
        "commands",
        "limits",
        "environment",
        "environmentSha256",
        "expectedGoEnv",
        "projection",
        "imageId",
        "sourceArchiveSha256",
        "cwd",
    ]:
        assert plan[key] == before[key], key
    path = HERE.parent / "amendment-2/listing.py"
    spec = importlib.util.spec_from_file_location("before_listing_testonly", path)
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    raw = (HERE / "actual-go-list-stdout.bin").read_bytes()
    receipt = json.loads((HERE / "actual-go-list-receipt.json").read_bytes())
    assert collection.file_sha(HERE / "actual-go-list-stdout.bin") == receipt["stdoutSha256"]
    assert receipt["exitCode"] == 0 and receipt["error"] is None
    provenance = json.loads((HERE / "test-only-source-semantics.json").read_bytes())
    inventory = json.loads(Path(provenance["sourceInventory"]["path"]).read_bytes())["files"]
    actual = listing.packages(raw, inventory)
    assert len(actual) == 104
    target = listing.PREFIX + "/internal/fourslash/tests"
    assert (
        target in actual
        and len(actual[target]["TestGoFiles"]) == 3
        and len(actual[target]["XTestGoFiles"]) == 4368
    )
    checks = [
        {
            "case": "all104 genuine raw packages accepted with source membership; required test-only package retained",
            "passed": True,
        },
        {
            "case": "parent rejects exact genuine raw listing",
            "passed": refused(lambda: previous.packages(raw, inventory)),
        },
    ]
    base = controls.package_rows()
    index = next(i for i, row in enumerate(base) if row["ImportPath"] == target)
    for field in ["TestGoFiles", "XTestGoFiles"]:
        rows = deepcopy(base)
        rows[index].update(GoFiles=[], CgoFiles=[], TestGoFiles=[], XTestGoFiles=[])
        rows[index][field] = ["owned_test.go"]
        listing.packages(encoded(rows), controls.FILES)
        checks.append({"case": "positive only " + field, "passed": True})
    rows = deepcopy(base)
    rows[index].update(
        GoFiles=[], CgoFiles=[], TestGoFiles=["owned_test.go"], XTestGoFiles=["external_test.go"]
    )
    files = {
        **controls.FILES,
        "tsc/internal/fourslash/tests/external_test.go": controls.FILES["README"],
    }
    listing.packages(encoded(rows), files)
    checks.append({"case": "positive mixed internal/external test-only", "passed": True})

    for name, mutate in [
        (
            "no selected files",
            lambda r: r.update(GoFiles=[], CgoFiles=[], TestGoFiles=[], XTestGoFiles=[]),
        ),
        (
            "ignored-only source",
            lambda r: r.update(
                GoFiles=[],
                CgoFiles=[],
                TestGoFiles=[],
                XTestGoFiles=[],
                IgnoredGoFiles=["owned_test.go"],
            ),
        ),
        ("test path traversal", lambda r: r.update(GoFiles=[], TestGoFiles=["../owned_test.go"])),
        (
            "external absolute path",
            lambda r: r.update(GoFiles=[], TestGoFiles=[], XTestGoFiles=["/owned_test.go"]),
        ),
        ("test absent inventory", lambda r: r.update(GoFiles=[], TestGoFiles=["missing_test.go"])),
        (
            "external absent inventory",
            lambda r: r.update(GoFiles=[], TestGoFiles=[], XTestGoFiles=["missing_test.go"]),
        ),
        (
            "duplicate internal",
            lambda r: r.update(GoFiles=[], TestGoFiles=["owned_test.go", "owned_test.go"]),
        ),
        (
            "duplicate across internal/external",
            lambda r: r.update(
                GoFiles=[], TestGoFiles=["owned_test.go"], XTestGoFiles=["owned_test.go"]
            ),
        ),
        (
            "duplicate production/test",
            lambda r: r.update(GoFiles=["owned_test.go"], TestGoFiles=["owned_test.go"]),
        ),
        ("null test field", lambda r: r.update(GoFiles=[], TestGoFiles=None)),
        ("error with valid tests", lambda r: r.update(GoFiles=[], Error={"Err": "owned error"})),
        ("incomplete with valid tests", lambda r: r.update(GoFiles=[], Incomplete=True)),
        (
            "wrong module",
            lambda r: r.update(GoFiles=[], Module={"Path": "other", "Dir": listing.CWD}),
        ),
        ("wrong directory", lambda r: r.update(GoFiles=[], Dir=listing.CWD + "/wrong")),
    ]:
        rows = deepcopy(base)
        mutate(rows[index])
        checks.append(
            {
                "case": "reject " + name,
                "passed": refused(lambda: listing.packages(encoded(rows), controls.FILES)),
            }
        )

    original = controls.package_rows

    def testonly_rows():
        rows = original()
        next(row for row in rows if row["ImportPath"] == target)["GoFiles"] = []
        return rows

    controls.package_rows = testonly_rows
    try:
        with tempfile.TemporaryDirectory(prefix="dotrepo-testonly-amendment3-fake-") as temporary:
            temp = Path(temporary)
            auth = temp / "auth.json"
            auth.write_text("{}")
            clock = [0]
            fake = controls.Fake(plan, clock=clock)

            def inputs(*args):
                source, cache = temp / "source.bytes", temp / "cache.bytes"
                source.write_bytes(b"owned")
                cache.write_bytes(b"cache")
                return (
                    source,
                    cache,
                    controls.FILES,
                    {"go/pkg/mod/owned": controls.FILES["README"]},
                    collection.tree_expected(controls.FILES),
                )

            result = collection.run(
                auth,
                temp / "output",
                temp / "scratch",
                backend=fake,
                plan_loader=lambda: deepcopy(plan),
                authorization_check=lambda *args: {"syntheticOwnedAssertion": True},
                input_check=inputs,
                clock=lambda: clock[0],
            )
            assert (
                result["synthetic"] is True
                and result["state"] == "native-top-level-collection-observed"
            )
            assert all(
                result[key] is False
                for key in [
                    "taskOutcomeObserved",
                    "nativeTaskAdmitted",
                    "campaignAdmitted",
                    "cacheGloballyQualified",
                ]
            )
            assert result["containerAbsent"] is True
            checks.append(
                {
                    "case": "full fake driver retains required internal test-only package",
                    "passed": True,
                    "result": result,
                }
            )
    finally:
        controls.package_rows = original
    collection.write(
        HERE / "testonly-controls.json",
        {
            "passed": len(checks),
            "controls": checks,
            "genuineRawListFixtureSha256": receipt["stdoutSha256"],
            "realGoDaemonNodeNetworkPackageProviderCalls": 0,
            "actualNativeCollectionOccurred": False,
        },
    )
    print(json.dumps({"passed": len(checks), "realGoDaemonNodeNetworkPackageProviderCalls": 0}))


if __name__ == "__main__":
    main()
