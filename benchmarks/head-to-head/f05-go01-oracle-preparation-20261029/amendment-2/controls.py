"""Only synthetic post-run traces and local data mutations; no native processes."""

import argparse
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import shutil

sys.dont_write_bytecode = True
import derive  # noqa: E402
import oracle  # noqa: E402

HERE = Path(__file__).resolve().parent


def event(package, action, test=None, output=None):
    row = {"Package": package, "Action": action}
    if test is not None:
        row["Test"] = test
    if output is not None:
        row["Output"] = output
    return row


def fixture():
    metadata, names = oracle.load_expectation()
    binding = {
        "revision": oracle.REVISION,
        "sourceArchiveSha256": oracle.SOURCE,
        "imageId": metadata["sourceSubject"]["sourceContext"]["imageId"],
        "environmentSha256": metadata["sourceSubject"]["sourceContext"]["environmentSha256"],
        "command": oracle.COMMAND,
        "scope": "repository-default",
    }
    expectation = {
        "state": "source-expectation-frozen-before-execution",
        "synthetic": True,
        "binding": binding,
        "nativeCollection": False,
        "sourceSubject": metadata["sourceSubject"],
        "expectedMapSha256": derive.MAP_SHA,
        "frozenAt": "2026-10-29T00:00:00+00:00",
        "packages": names,
    }
    policy = {
        "state": "accepted-before-execution",
        "synthetic": True,
        "binding": binding,
        "acceptanceSha256": "3" * 64,
        "acceptedAt": "2026-10-29T00:00:00+00:00",
        "exclusionSetSha256": oracle.EXCLUSION_SET_SHA256,
        "exclusions": [],
    }
    execution = {
        "synthetic": True,
        "binding": binding,
        "startedAt": "2026-10-30T00:00:00+00:00",
        "setupComplete": True,
        "wrapperCompleted": True,
        "trackedSourceIntact": True,
        "eventsComplete": True,
        "truncated": False,
        "resourceFailure": False,
        "timedOut": False,
        "error": None,
        "exitCode": 0,
        "stderr": "",
        "effectiveSelectionContext": metadata["sourceSubject"]["sourceContext"],
    }
    rows = []
    for package, tests in names.items():
        rows.append(event(package, "start"))
        for test in tests:
            rows += [event(package, "run", test), event(package, "pass", test)]
        if package in metadata["noSelectedTestSourcePackages"]:
            rows += [
                event(package, "output", output="? synthetic [no test files]\n"),
                event(package, "skip"),
            ]
        else:
            rows.append(event(package, "pass"))
    return deepcopy((rows, expectation, policy, execution))


def score(data, *, synthetic=True, raw=None, rebind=True):
    rows, expectation, policy, execution = data
    raw = raw if raw is not None else "".join(json.dumps(r) + "\n" for r in rows)
    if rebind:
        execution["rawEventsSha256"] = hashlib.sha256(raw.encode()).hexdigest()
        execution["expectationSha256"] = oracle.digest(expectation)
        execution["policySha256"] = oracle.digest(policy)
        execution["syntheticCapture"] = {
            "state": "synthetic-full-task-capture-fixture",
            "synthetic": True,
            "command": oracle.COMMAND,
            "rawEventsSha256": hashlib.sha256(raw.encode()).hexdigest(),
            "sourceSubjectSha256": oracle.digest(expectation["sourceSubject"]),
            "setupRole": "full-normal-setup",
            "eventOrigin": "owned-synthetic-fixture-not-arbitrary-agent-file",
        }
    return oracle.evaluate(raw, expectation, policy, execution, synthetic=synthetic)


def first(data):
    return next(r for r in data[0] if r["Action"] == "run")


def assertion(data):
    row = first(data)
    package, test = row["Package"], row["Test"]
    index = data[0].index(row)
    data[0].insert(index + 1, event(package, "output", test, f"--- FAIL: {test} (0.01s)\n"))
    next(
        r
        for r in data[0]
        if r["Package"] == package and r.get("Test") == test and r["Action"] == "pass"
    )["Action"] = "fail"
    next(
        r for r in data[0] if r["Package"] == package and "Test" not in r and r["Action"] == "pass"
    )["Action"] = "fail"
    data[3]["exitCode"] = 1


def nested(data, *, after=False, unfinished=False, child_failure=False):
    row = first(data)
    package, test = row["Package"], row["Test"]
    index = data[0].index(row) + (2 if after else 1)
    child = test + "/owned-synthetic-child"
    rows = [event(package, "run", child)]
    if not unfinished:
        if child_failure:
            rows.append(event(package, "output", child, f"--- FAIL: {child} (0.01s)\n"))
        rows.append(event(package, "fail" if child_failure else "pass", child))
    data[0][index:index] = rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    checks = []
    base = fixture()

    def check(name, mutate=None, accepted=False, **kwargs):
        data = deepcopy(base)
        if mutate:
            mutate(data)
        result = score(data, **kwargs)
        assert result["candidateOutcomeObserved"] is accepted, (name, result)
        assert all(
            result[k] is False
            for k in [
                "taskOutcomeObserved",
                "oracleQualified",
                "campaignAdmitted",
                "nativeCollectionOccurred",
            ]
        )
        checks.append({"case": name, "candidateAccepted": accepted, "result": result})

    check("complete104package5972name synthetic trace", accepted=True)
    check("complete terminal assertion failure", assertion, accepted=True)
    check("complete observed nested lifecycle", nested, accepted=True)
    proposed = json.loads((HERE.parent / "policy-proposal.json").read_text())["exclusions"]

    def declared_skip(data, bare=False, wrong_reason=False):
        test = (
            "TestAutoImportPackageRootPathTypeModule" if bare else "TestAliasMergingWithNamespace"
        )
        entry = next(row for row in proposed if row["test"] == test)
        package = entry["package"]
        terminal = next(
            row
            for row in data[0]
            if row["Package"] == package and row.get("Test") == test and row["Action"] == "pass"
        )
        index = data[0].index(terminal)
        terminal["Action"] = "skip"
        message = f"--- SKIP: {test} (0.01s)\n" if bare else entry["outputReason"] + "\n"
        data[0].insert(
            index, event(package, "output", test, "wrong diagnostic\n" if wrong_reason else message)
        )
        data[2]["exclusions"] = [deepcopy(entry)]

    check("exact existing declared skip", declared_skip, accepted=True)
    check("exact existing bare skip", lambda d: declared_skip(d, bare=True), accepted=True)
    check("declared skip without witnessed reason", lambda d: declared_skip(d, wrong_reason=True))
    check(
        "skip policy cannot widen",
        lambda d: d[2]["exclusions"].append(
            {
                "package": first(d)["Package"],
                "test": first(d)["Test"],
                "conditionSatisfied": True,
                "reason": "new observed failure",
            }
        ),
    )

    check("missing source expectation", lambda d: d[1].update(state="missing"))
    check(
        "fake native origin",
        lambda d: d[1].update(
            state="complete-native-collection-frozen-before-execution", nativeCollection=True
        ),
    )
    check(
        "edited source subject",
        lambda d: d[1]["sourceSubject"].update(registryExpandedSha256="0" * 64),
    )
    check(
        "changed source selection",
        lambda d: d[3]["effectiveSelectionContext"].update(selectionSha256="0" * 64),
    )
    check("changed wrapper command", lambda d: d[3]["binding"].update(command="go test ./..."))
    check("changed image", lambda d: d[3]["binding"].update(imageId="sha256:" + "0" * 64))
    check(
        "missing empty-scope package in expectations",
        lambda d: d[1]["packages"].pop(next(k for k, v in d[1]["packages"].items() if not v)),
    )
    check(
        "missing observed package",
        lambda d: d[0].__setitem__(
            slice(None), [r for r in d[0] if r["Package"] != d[0][0]["Package"]]
        ),
    )
    check(
        "missing top-level identity",
        lambda d: d[0].__setitem__(
            slice(None),
            [
                r
                for r in d[0]
                if (r["Package"], r.get("Test")) != (first(d)["Package"], first(d)["Test"])
            ],
        ),
    )
    check(
        "benchmark promoted to required event",
        lambda d: d[1]["packages"][first(d)["Package"]].append("BenchmarkSynthetic"),
    )
    check(
        "TestMain wrapper promoted to event",
        lambda d: d[1]["packages"][first(d)["Package"]].append("TestMain"),
    )
    check("late descendant", lambda d: nested(d, after=True))
    check("unfinished descendant", lambda d: nested(d, unfinished=True))
    check("failed descendant with passing parent", lambda d: nested(d, child_failure=True))
    check(
        "unexpected top-level skip",
        lambda d: next(
            r for r in d[0] if r.get("Test") == first(d)["Test"] and r["Action"] == "pass"
        ).update(Action="skip"),
    )
    check(
        "unexpected nested skip",
        lambda d: (
            nested(d),
            next(
                r
                for r in d[0]
                if "/owned-synthetic-child" in r.get("Test", "") and r["Action"] == "pass"
            ).update(Action="skip"),
        ),
    )
    check(
        "build killed disguised as full assertion failure",
        lambda d: (assertion(d), d[3].update(stderr="signal: killed\n")),
    )
    check(
        "resource failure despite complete synthetic events",
        lambda d: d[3].update(resourceFailure=True),
    )
    check("setup incomplete", lambda d: d[3].update(setupComplete=False))
    check("wrapper incomplete", lambda d: d[3].update(wrapperCompleted=False))
    check("source changed after selection", lambda d: d[3].update(trackedSourceIntact=False))
    check("truncated events", lambda d: d[3].update(truncated=True))
    check(
        "listing-only",
        lambda d: d[0].__setitem__(slice(None), [r for r in d[0] if "Test" not in r]),
    )

    def empty_test_source_skip(data):
        terminal = next(
            row
            for row in data[0]
            if "Test" not in row
            and row["Action"] == "pass"
            and not data[1]["packages"][row["Package"]]
        )
        index = data[0].index(terminal)
        data[0].insert(
            index, event(terminal["Package"], "output", output="? synthetic [no test files]\n")
        )
        terminal["Action"] = "skip"

    check(
        "zero-name selected-test-source package cannot claim no-test-files", empty_test_source_skip
    )
    # Capture fields are deliberately synthetic, never an external authenticity proof.
    data = deepcopy(base)
    score(data)
    data[3]["syntheticCapture"]["eventOrigin"] = "agent-writable-json-file"
    result = score(data, rebind=False)
    assert result["candidateOutcomeObserved"] is False
    checks.append(
        {
            "case": "forged standalone file rejected in synthetic join",
            "candidateAccepted": False,
            "result": result,
        }
    )
    for synthetic in [False, None, 1]:
        check(
            "actual or invalid synthetic mode remains blocked " + repr(synthetic),
            synthetic=synthetic,
        )
    check(
        "changed expectations frozen during execution",
        lambda d: d[1].update(frozenAt=d[3]["startedAt"]),
    )
    check("unaccepted skip policy", lambda d: d[2].update(state="proposal"))

    # Pure derivation mutations use the actual captured JSON as inert data.
    registry = json.loads(gzip.decompress((derive.RESULT / "evidence/registry.gz").read_bytes()))
    inventory = json.loads((derive.RESULT / "bindings/native/package-inventory.json").read_bytes())
    for name, mutation in [
        (
            "registry selection context changed",
            lambda value: value["sourceContext"].update(selectionSha256="0" * 64),
        ),
        ("registry package lost", lambda value: value["packages"].pop()),
        (
            "registry identity edited",
            lambda value: value["packages"][0]["tests"][0].update(name="TestEdited"),
        ),
        (
            "registry diagnostic",
            lambda value: value["packages"][0].update(
                diagnostics=[{"code": "synthetic", "message": "unresolved"}]
            ),
        ),
        (
            "registry fake compile validity",
            lambda value: value.update(universalCompileValidityUnestablished=False),
        ),
    ]:
        value = deepcopy(registry)
        mutation(value)
        try:
            derive.names_from_registry(value, inventory)
        except ValueError as exc:
            checks.append({"case": name, "candidateAccepted": False, "error": str(exc)})
        else:
            raise AssertionError(name)
    original_root = derive.ROOT
    with tempfile.TemporaryDirectory(
        prefix="dotrepo-source-oracle-source-mutation-", dir="/tmp"
    ) as temporary:
        root = Path(temporary)
        bindings = json.loads((HERE / "source-bindings.json").read_text())
        for row in bindings["files"]:
            destination = root / row["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original_root / row["path"], destination)
        derive.ROOT = root
        try:
            derive.bound_sources()
            target = root / bindings["files"][0]["path"]
            target.write_bytes(target.read_bytes() + b" ")
            try:
                derive.bound_sources()
            except ValueError as exc:
                checks.append(
                    {"case": "bound source edited", "candidateAccepted": False, "error": str(exc)}
                )
            else:
                raise AssertionError("edited bound source admitted")
            target.unlink()
            try:
                derive.bound_sources()
            except FileNotFoundError as exc:
                checks.append(
                    {
                        "case": "bound source deleted",
                        "candidateAccepted": False,
                        "error": str(exc).replace(str(root), "SYNTHETIC_ROOT"),
                    }
                )
            else:
                raise AssertionError("deleted bound source admitted")
        finally:
            derive.ROOT = original_root
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(
            {
                "synthetic": True,
                "nativeActions": False,
                "actualAdmissions": False,
                "checks": checks,
            },
            stream,
            indent=2,
        )
        stream.write("\n")
    print(json.dumps({"passed": len(checks), "actualAdmissions": False}))


if __name__ == "__main__":
    main()
