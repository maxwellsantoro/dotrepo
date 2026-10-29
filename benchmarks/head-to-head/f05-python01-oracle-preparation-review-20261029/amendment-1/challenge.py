"""Independent Python01 successor phase controls; only synthetic source fixtures."""

from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
AUTHOR = Path("/tmp/dotrepo-f05-python01-oracle-preparation-20261029/amendment-1")


def main():
    assert hashlib.sha256((AUTHOR / "FREEZE.json").read_bytes()).hexdigest() == (
        "994f8d9b6196252b763dbb56756dcb96b5c82b61c000164c71bbad23bdcef893"
    )
    sys.path.insert(0, str(AUTHOR))
    controls = importlib.import_module("controls")
    reports = []

    def check(name, change=lambda d: None, *, complete=False, passed=None):
        data = controls.fixture()
        change(data)
        scored = controls.score(data)
        assert scored["candidateOutcomeObserved"] is complete, (name, scored["reason"])
        assert scored["testsPassed"] is passed, (name, scored["reason"])
        data[1].update(trusted=True, nativeCollection=True, phaseCaptureComplete=True)
        actual = controls.score(data, synthetic=False)
        assert not any(
            actual[k]
            for k in (
                "candidateOutcomeObserved",
                "taskOutcomeObserved",
                "oracleQualified",
                "campaignAdmitted",
                "nativeCollectionOccurred",
            )
        )
        assert actual["reason"] == "actual-native-collection-observer-and-capture-join-unavailable"
        reports.append(
            {
                "name": name,
                "candidateOutcomeObserved": scored["candidateOutcomeObserved"],
                "testsPassed": scored["testsPassed"],
                "reason": scored["reason"],
                "rawFixtureSha256": controls.oracle.sha(controls.raw(data[0])),
                "actualModeRefusedSpoofedFlags": True,
            }
        )

    check("full-semantic-union-pass", complete=True, passed=True)
    for suite in controls.oracle.SUITES:
        check(
            "complete-assertion-" + suite,
            lambda d, s=suite: controls.failing(d, suite=s),
            complete=True,
            passed=False,
        )
    check(
        "failed-subtest-parent-returns",
        lambda d: controls.subtest(d, outcome="assertion-failed"),
        complete=True,
        passed=False,
    )
    for suite in controls.oracle.SUITES:

        def null_setup(data, suite=suite):
            result = controls.first(data, phase="setup", suite=suite)
            start = next(
                row
                for row in data[0]
                if row["kind"] == "phase-start"
                and row["suite"] == suite
                and row["id"] == result["id"]
                and row["phase"] == "setup"
            )
            data[0].remove(start)
            result["phase"] = None

        check("missing-" + suite + "-setup-start-null-result", null_setup)

    def all_null(data):
        data[0][:] = [row for row in data[0] if row["kind"] != "phase-start"]
        for row in data[0]:
            if row["kind"] == "phase-result":
                row["phase"] = None

    check("all-phase-starts-absent-and-all-phase-results-null", all_null)
    for suite in controls.oracle.SUITES:
        for bad in [None, False, 0, "cleanup" if suite == "backend-pytest" else "unknown", []]:
            check(
                "bad-result-phase-" + suite + "-" + repr(bad),
                lambda d, s=suite, bad=bad: controls.first(d, suite=s, phase="setup").update(
                    phase=bad
                ),
            )
        for phase in controls.oracle.PHASES[suite]:

            def no_start(data, suite=suite, phase=phase):
                result = controls.first(data, suite=suite, phase=phase)
                start = next(
                    row
                    for row in data[0]
                    if row["kind"] == "phase-start"
                    and row["suite"] == suite
                    and row["id"] == result["id"]
                    and row["phase"] == phase
                )
                data[0].remove(start)

            check("missing-start-" + suite + "-" + phase, no_start)
        for phase in ["setup", "teardown"]:
            check(
                "fixture-assertion-" + suite + "-" + phase,
                lambda d, s=suite, p=phase: controls.failing(d, suite=s, phase=p),
            )
    check(
        "cleanup-error-after-assertion",
        lambda d: (
            controls.failing(d),
            controls.failing(
                d, phase="cleanup", outcome="error", type_name="builtins.RuntimeError"
            ),
        ),
    )
    check(
        "call-import-error",
        lambda d: controls.failing(d, outcome="error", type_name="builtins.ModuleNotFoundError"),
    )
    for outcome in ["skipped", "xfail", "xpass"]:
        check("unadjudicated-" + outcome, lambda d, o=outcome: controls.failing(d, outcome=o))
    check("truncated-process", lambda d: d[1]["suiteProcesses"][0].update(truncated=True))
    check("signal-killed", lambda d: d[1]["suiteProcesses"][1].update(signal=9, exitCode=137))
    check(
        "missing-backend",
        lambda d: d[0].__setitem__(
            slice(None), [row for row in d[0] if row.get("suite") != "backend-pytest"]
        ),
    )

    def duplicate(data):
        result = controls.first(data)
        data[0].insert(data[0].index(result) + 1, deepcopy(result))

    check("duplicate-terminal-result", duplicate)
    report = {
        "state": "independent-python01-phase-successor-controls-passed",
        "count": len(reports),
        "cases": reports,
        "actualAdmission": False,
        "newNativeDaemonNetworkProviderActions": 0,
    }
    with (HERE / "challenge.json").open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"allPassed": True, "count": len(reports)}))


if __name__ == "__main__":
    main()
