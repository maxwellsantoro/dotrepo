"""Owned synthetic phase-state regressions, including all three frozen before cases."""

import argparse
import importlib.util
import json
from pathlib import Path

import controls

HERE = Path(__file__).resolve().parent
OLD_SHA = "d891d5f944417dd7bc4f1c3d9be3b4a0990b7ec0f74d719109a9f7b2465a8428"


def load_old(parent):
    path = parent / "oracle.py"
    assert controls.oracle.sha(path.read_bytes()) == OLD_SHA
    spec = importlib.util.spec_from_file_location("original_owned_oracle", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def score_with(module, data, synthetic=True):
    raw = controls.raw(data[0])
    execution = dict(data[1], rawEventsSha256=module.sha(raw))
    return module.evaluate(raw, execution, synthetic=synthetic)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    old = load_old(args.parent)
    observations = []

    def check(name, mutation, *, before_accepts=False):
        data = controls.fixture()
        mutation(data)
        after = controls.score(data)
        assert not after["candidateOutcomeObserved"], name
        assert not after["casePhaseReportCoverageComplete"], name
        actual = controls.score(data, synthetic=False)
        assert not actual["taskOutcomeObserved"] and not actual["candidateOutcomeObserved"]
        row = {
            "name": name,
            "rawFixtureSha256": controls.oracle.sha(controls.raw(data[0])),
            "after": after,
            "actualModeRemainsClosed": True,
        }
        if before_accepts:
            before = score_with(old, data)
            assert before["candidateOutcomeObserved"]
            assert before["casePhaseReportCoverageComplete"] and before["testsPassed"]
            row["before"] = before
        observations.append(row)

    def missing_start(data, suite, phase, null=False):
        report = controls.first(data, suite=suite, phase=phase)
        start = next(
            row
            for row in data[0]
            if row["kind"] == "phase-start"
            and row["suite"] == suite
            and row["id"] == report["id"]
            and row["phase"] == phase
        )
        data[0].remove(start)
        if null:
            report["phase"] = None

    for suite in controls.oracle.SUITES:
        check(
            "missing-" + suite + "-setup-start-null-result",
            lambda data, suite=suite: missing_start(data, suite, "setup", True),
            before_accepts=True,
        )

    def all_missing(data):
        data[0][:] = [row for row in data[0] if row["kind"] != "phase-start"]
        for row in data[0]:
            if row["kind"] == "phase-result":
                row["phase"] = None

    check("all-phase-starts-absent-and-all-phase-results-null", all_missing, before_accepts=True)
    for suite in controls.oracle.SUITES:
        for phase in controls.oracle.PHASES[suite]:
            check(
                suite + "-" + phase + "-missing-start",
                lambda data, suite=suite, phase=phase: missing_start(data, suite, phase),
            )
            check(
                suite + "-" + phase + "-missing-start-null-result",
                lambda data, suite=suite, phase=phase: missing_start(data, suite, phase, True),
            )
        for invalid in (None, "", "not-a-phase", 1, [], {}):
            for kind in ("phase-start", "phase-result"):

                def change(data, suite=suite, invalid=invalid, kind=kind):
                    next(r for r in data[0] if r["kind"] == kind and r["suite"] == suite)[
                        "phase"
                    ] = invalid

                check(suite + "-" + kind + "-invalid-" + repr(invalid), change)

        def early_result(data, suite=suite):
            report = controls.first(data, suite=suite, phase="setup")
            index = data[0].index(report)
            data[0][index - 1], data[0][index] = data[0][index], data[0][index - 1]

        check(suite + "-result-before-start", early_result)

        def duplicate_start(data, suite=suite):
            row = next(r for r in data[0] if r["kind"] == "phase-start" and r["suite"] == suite)
            data[0].insert(data[0].index(row), dict(row))

        check(suite + "-duplicate-start", duplicate_start)
    report = {
        "allPassed": True,
        "count": len(observations),
        "exactBeforeCases": 3,
        "beforeOracleSha256": OLD_SHA,
        "afterOracleSha256": controls.oracle.sha((HERE / "oracle.py").read_bytes()),
        "cases": observations,
        "actualAdmission": False,
        "sourceOrNativeExecution": False,
    }
    with args.output.open("x") as stream:
        json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key: report[key] for key in ("allPassed", "count", "exactBeforeCases")}))


if __name__ == "__main__":
    main()
