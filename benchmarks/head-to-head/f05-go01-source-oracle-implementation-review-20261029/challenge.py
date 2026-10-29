"""Independent synthetic-only successor checks; no runtime/native invocation."""

from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
AUTHOR = ROOT / "benchmarks/head-to-head/f05-go01-oracle-preparation-20261029/amendment-2"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert (
        sha(AUTHOR / "FREEZE.json")
        == "cc12c2fe8ca12e8f2eb15b2ceffc130aa4094b281a3b9057e60749ab09e510b5"
    )
    frozen = json.loads((AUTHOR / "FREEZE.json").read_bytes())
    for name, digest in frozen["artifactSha256"].items():
        assert sha(AUTHOR / name) == digest
    sys.path.insert(0, str(AUTHOR))
    controls = importlib.import_module("controls")
    oracle = importlib.import_module("oracle")
    base = controls.fixture()
    records = []

    def check(name, mutate=None, accepted=False, mode=True, rebind=True):
        data = deepcopy(base)
        if mutate:
            mutate(data)
        result = controls.score(data, synthetic=mode, rebind=rebind)
        assert result["candidateOutcomeObserved"] is accepted, (name, result)
        assert all(
            result[key] is False
            for key in [
                "taskOutcomeObserved",
                "oracleQualified",
                "campaignAdmitted",
                "nativeCollectionOccurred",
            ]
        )
        records.append(
            {
                "case": name,
                "candidateAccepted": accepted,
                "reason": result["reason"],
                "testsPassed": result["testsPassed"],
            }
        )
        return result

    check("full104 and5972 positive remains synthetic", accepted=True)
    result = check(
        "complete assertion failure remains synthetic failed outcome",
        controls.assertion,
        accepted=True,
    )
    assert result["testsPassed"] is False

    def hierarchy(data, case):
        row = controls.first(data)
        p, t = row["Package"], row["Test"]
        start = data[0].index(row)
        event = controls.event
        a, ab, grand = t + "/a", t + "/ab", t + "/a/deep"
        if case == "late":
            data[0][start + 2 : start + 2] = [event(p, "run", a), event(p, "pass", a)]
        elif case == "unfinished":
            data[0][start + 1 : start + 1] = [event(p, "run", a)]
            data[0][start + 3 : start + 3] = [event(p, "pass", a)]
        elif case == "child-fail-parent-pass":
            data[0][start + 1 : start + 1] = [
                event(p, "run", a),
                event(p, "output", a, f"--- FAIL: {a} (0.1s)\n"),
                event(p, "fail", a),
            ]
            next(
                r
                for r in data[0]
                if r["Package"] == p and "Test" not in r and r["Action"] == "pass"
            )["Action"] = "fail"
            data[3]["exitCode"] = 1
        elif case == "prefix-siblings":
            data[0][start + 1 : start + 1] = [
                event(p, "run", a),
                event(p, "pause", a),
                event(p, "run", ab),
                event(p, "pause", ab),
                event(p, "cont", a),
                event(p, "pass", a),
                event(p, "cont", ab),
                event(p, "pass", ab),
            ]
        elif case in ["deep-failure", "deep-failure-pass-ancestor"]:

            def failed(name):
                return [
                    event(p, "output", name, f"--- FAIL: {name} (0.1s)\n"),
                    event(p, "fail", name),
                ]

            data[0][start + 1 : start + 1] = [
                event(p, "run", a),
                event(p, "run", grand),
                *failed(grand),
                *failed(a),
            ]
            top_pass = next(
                r
                for r in data[0]
                if r["Package"] == p and r.get("Test") == t and r["Action"] == "pass"
            )
            if case == "deep-failure":
                index = data[0].index(top_pass)
                data[0].insert(index, event(p, "output", t, f"--- FAIL: {t} (0.1s)\n"))
                top_pass["Action"] = "fail"
            next(
                r
                for r in data[0]
                if r["Package"] == p and "Test" not in r and r["Action"] == "pass"
            )["Action"] = "fail"
            data[3]["exitCode"] = 1

    for case, accepted in [
        ("late", False),
        ("unfinished", False),
        ("child-fail-parent-pass", False),
        ("prefix-siblings", True),
        ("deep-failure", True),
        ("deep-failure-pass-ancestor", False),
    ]:
        check(
            "retained hierarchy " + case, lambda d, case=case: hierarchy(d, case), accepted=accepted
        )
    check(
        "unknown top-level event not silently ignored",
        lambda d: d[0].insert(
            1, controls.event(d[0][0]["Package"], "run", "TestUnknownOwnedMutation")
        ),
    )
    check(
        "Fuzz top-level missing cannot shrink scope",
        lambda d: d[0].__setitem__(
            slice(None), [r for r in d[0] if not r.get("Test", "").startswith("Fuzz")]
        ),
    )
    check(
        "missing zero-name package coverage rejected",
        lambda d: d[0].__setitem__(
            slice(None),
            [
                r
                for r in d[0]
                if r["Package"] != next(p for p, names in d[1]["packages"].items() if not names)
            ],
        ),
    )
    metadata, names = oracle.load_expectation()
    selected_empty = [
        p
        for p, tests in names.items()
        if not tests and p not in metadata["noSelectedTestSourcePackages"]
    ]
    assert selected_empty == ["github.com/microsoft/TypeScript/tsc/internal/binder"]

    def false_notest(data):
        p = selected_empty[0]
        term = next(
            r for r in data[0] if r["Package"] == p and r["Action"] == "pass" and "Test" not in r
        )
        data[0].insert(
            data[0].index(term), controls.event(p, "output", output="? synthetic [no test files]\n")
        )
        term["Action"] = "skip"

    check("binder source-selected file cannot become no-test skip", false_notest)
    check("empty selected-source package can complete at package level", accepted=True)

    def forged_real(data):
        for item in data[1:]:
            item["synthetic"] = False
        data[3].update(
            captureJoinVerified=True,
            eventsComplete=True,
            setupComplete=True,
            trustedCapture=True,
            receiptSha256="f" * 64,
        )
        data[3]["realCapture"] = {"state": "reviewed", "authenticated": True, "sha256": "a" * 64}

    result = check(
        "fabricated actual capture booleans cannot enable outcome", forged_real, mode=False
    )
    assert result["reason"] == "reviewed-full-task-capture-join-unavailable"
    for mode in [False, 1, "true", None]:
        check("actual or nonliteral synthetic selector " + repr(mode), mode=mode)
    check(
        "fake native collection origin cannot replace source",
        lambda d: d[1].update(
            state="complete-native-collection-frozen-before-execution", nativeCollection=True
        ),
    )
    check(
        "effective target context changed",
        lambda d: d[3]["effectiveSelectionContext"].update(environmentSha256="f" * 64),
    )
    check("normal setup cannot be omitted", lambda d: d[3].update(setupComplete=False))
    check(
        "wrapper failure cannot be listing success",
        lambda d: d[3].update(wrapperCompleted=False, exitCode=1),
    )
    check(
        "new skip exclusion cannot be inferred from failure",
        lambda d: d[2]["exclusions"].append(
            {
                "package": controls.first(d)["Package"],
                "test": controls.first(d)["Test"],
                "reason": "observed failure",
            }
        ),
    )
    # Tamper only isolated copies of the newly frozen metadata/map, not source owners.
    original_here = oracle.HERE
    with tempfile.TemporaryDirectory(
        prefix="dotrepo-source-oracle-review-", dir="/tmp"
    ) as directory:
        root = Path(directory)
        for name in ["expectation.json", "expected-map.json"]:
            (root / name).write_bytes((AUTHOR / name).read_bytes())
        oracle.HERE = root
        try:
            oracle.load_expectation()
            for name in ["expected-map.json", "expectation.json"]:
                raw = (root / name).read_bytes()
                (root / name).write_bytes(raw + b" ")
                try:
                    oracle.load_expectation()
                except ValueError:
                    records.append(
                        {"case": "isolated frozen " + name + " edited", "candidateAccepted": False}
                    )
                else:
                    raise AssertionError("changed source subject admitted")
                (root / name).write_bytes(raw)
        finally:
            oracle.HERE = original_here
    for name, digest in frozen["artifactSha256"].items():
        assert sha(AUTHOR / name) == digest
    output = {
        "state": "independent-source-successor-synthetic-controls-passed",
        "cases": records,
        "authorArtifactsUnchanged": len(frozen["artifactSha256"]),
        "captureJoin": "OPEN",
        "actualOutcomeOrOracleAdmission": False,
        "newRuntimeActions": 0,
    }
    with (HERE / "independent-controls.json").open("x") as stream:
        json.dump(output, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"passed": len(records), "actualAdmission": False}))


if __name__ == "__main__":
    main()
