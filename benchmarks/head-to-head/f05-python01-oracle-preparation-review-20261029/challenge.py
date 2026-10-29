"""Frozen Python01 preparation counterexamples; only owned inert fixtures."""

import hashlib
import importlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
AUTHOR = Path("/tmp/dotrepo-f05-python01-oracle-preparation-20261029")


def main():
    assert hashlib.sha256((AUTHOR / "FREEZE.json").read_bytes()).hexdigest() == (
        "83d915e7c465d0291fe72d3178826bd91b26d18c299823273d2e0cc11ca98e9f"
    )
    sys.path.insert(0, str(AUTHOR))
    controls = importlib.import_module("controls")
    cases = []
    for suite in [*controls.oracle.SUITES, None]:
        data = controls.fixture()
        if suite:
            report = controls.first(data, phase="setup", suite=suite)
            start = next(
                row
                for row in data[0]
                if row["kind"] == "phase-start"
                and row["suite"] == suite
                and row["id"] == report["id"]
                and row["phase"] == "setup"
            )
            data[0].remove(start)
            report["phase"] = None
            name = "missing-" + suite + "-setup-start-null-result"
        else:
            data[0][:] = [row for row in data[0] if row["kind"] != "phase-start"]
            for row in data[0]:
                if row["kind"] == "phase-result":
                    row["phase"] = None
            name = "all-phase-starts-absent-and-all-phase-results-null"
        result = controls.score(data)
        actual = controls.score(data, synthetic=False)
        assert result["candidateOutcomeObserved"] and result["casePhaseReportCoverageComplete"]
        assert result["testsPassed"]
        assert not actual["candidateOutcomeObserved"] and not actual["taskOutcomeObserved"]
        assert actual["reason"] == "actual-native-collection-observer-and-capture-join-unavailable"
        cases.append(
            {
                "name": name,
                "rawFixtureSha256": controls.oracle.sha(controls.raw(data[0])),
                "phaseStartsRemaining": sum(row["kind"] == "phase-start" for row in data[0]),
                "nullPhaseResults": sum(
                    row["kind"] == "phase-result" and row["phase"] is None for row in data[0]
                ),
                "candidateOutcomeObserved": result["candidateOutcomeObserved"],
                "casePhaseReportCoverageComplete": result["casePhaseReportCoverageComplete"],
                "testsPassed": result["testsPassed"],
                "reason": result["reason"],
                "actualResult": actual,
                "firstObservedCase": result["observedCases"][0],
            }
        )
    report = {
        "state": "independent-synthetic-phase-coverage-false-acceptances-reproduced",
        "cases": cases,
        "actualAdmission": False,
        "newNativeDaemonNetworkProviderActions": 0,
    }
    with (HERE / "challenge.json").open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"reproduced": len(cases), "actualModeRemainsClosed": True}))


if __name__ == "__main__":
    main()
