"""Owned synthetic phase traces only: no imports/tests of the retained workload."""

import argparse
from copy import deepcopy
import json
from pathlib import Path

import oracle


def fixture():
    source = oracle.manifest()
    events = [{"kind": "run-start", "manifestSha256": oracle.MANIFEST_SHA}]
    for suite in oracle.SUITES:
        cases = [row for row in source["cases"] if row["suite"] == suite]
        events += [
            {
                "kind": "suite-start",
                "suite": suite,
                "runner": "unittest" if suite == oracle.SUITES[0] else "pytest",
            },
            {
                "kind": "collection",
                "suite": suite,
                "ids": [row["id"] for row in cases],
                "deselected": [],
            },
        ]
        for case in cases:
            identity = case["id"]
            events.append({"kind": "case-start", "suite": suite, "id": identity})
            for phase in oracle.PHASES[suite]:
                events += [
                    {"kind": "phase-start", "suite": suite, "id": identity, "phase": phase},
                    {
                        "kind": "phase-result",
                        "suite": suite,
                        "id": identity,
                        "phase": phase,
                        "outcome": "passed",
                        "exception": None,
                    },
                ]
            events.append({"kind": "case-end", "suite": suite, "id": identity})
        events.append({"kind": "suite-end", "suite": suite, "exitCode": 0})
    events.append({"kind": "run-end"})
    execution = {
        "state": "owned-synthetic-process-and-context-fixture-not-native-evidence",
        "manifestSha256": oracle.MANIFEST_SHA,
        "rawEventsSha256": "",
        "sourceArchiveSha256": source["sourceArchiveSha256"],
        "environmentSubject": "owned-synthetic-unqualified-environment",
        "sourceState": "owned-synthetic-unchanged-source-fixture",
        "suiteProcesses": [
            {
                "suite": suite,
                "exitCode": 0,
                "error": None,
                "signal": None,
                "truncated": False,
                "startedAt": f"2026-10-30T00:0{n}:00+00:00",
                "completedAt": f"2026-10-30T00:0{n}:30+00:00",
            }
            for n, suite in enumerate(oracle.SUITES)
        ],
    }
    return events, execution


def raw(events):
    return b"".join(oracle.encode({"seq": n, **row}) + b"\n" for n, row in enumerate(events, 1))


def score(data, *, synthetic=True, value=None):
    value = raw(data[0]) if value is None else value
    execution = deepcopy(data[1])
    execution["rawEventsSha256"] = oracle.sha(value)
    return oracle.evaluate(value, execution, synthetic=synthetic)


def first(data, phase="call", suite="root-unittest"):
    return next(
        r
        for r in data[0]
        if r["kind"] == "phase-result" and r["suite"] == suite and r["phase"] == phase
    )


def failing(
    data,
    *,
    phase="call",
    suite="root-unittest",
    outcome="assertion-failed",
    type_name="builtins.AssertionError",
    errno=None,
):
    row = first(data, phase, suite)
    row.update(
        outcome=outcome,
        exception={"type": type_name, "message": "owned synthetic diagnostic", "errno": errno}
        if outcome in {"error", "assertion-failed"}
        else None,
    )
    if outcome in {"error", "assertion-failed", "xpass"}:
        next(r for r in data[0] if r["kind"] == "suite-end" and r["suite"] == suite)["exitCode"] = 1
        next(r for r in data[1]["suiteProcesses"] if r["suite"] == suite)["exitCode"] = 1


def subtest(data, *, outcome="passed", completed=True):
    row = first(data)
    i = data[0].index(row)
    child = {
        "kind": "subtest-start",
        "suite": row["suite"],
        "id": row["id"],
        "ordinal": 1,
        "label": "owned dynamic child (not a source/native cardinality claim)",
    }
    additions = [child]
    if completed:
        additions.append(
            {
                "kind": "subtest-result",
                "suite": row["suite"],
                "id": row["id"],
                "ordinal": 1,
                "outcome": outcome,
                "exception": {
                    "type": "builtins.AssertionError"
                    if outcome == "assertion-failed"
                    else "builtins.ValueError",
                    "message": "owned child",
                    "errno": None,
                }
                if outcome in {"assertion-failed", "error"}
                else None,
            }
        )
    data[0][i:i] = additions
    if outcome in {"assertion-failed", "error", "xpass"}:
        next(r for r in data[0] if r["kind"] == "suite-end" and r["suite"] == row["suite"])[
            "exitCode"
        ] = 1
        data[1]["suiteProcesses"][0]["exitCode"] = 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reports = []

    def check(
        name,
        mutation=lambda _x: None,
        *,
        complete=False,
        passed=None,
        coverage=None,
        actual=False,
        value=None,
        observed=None,
        assertion_count=None,
        call_type=None,
    ):
        data = fixture()
        mutation(data)
        result = score(data, synthetic=not actual, value=value)
        assert result["candidateOutcomeObserved"] is complete and result["testsPassed"] is passed, (
            name,
            result["reason"],
        )
        if coverage is not None:
            assert result["casePhaseReportCoverageComplete"] is coverage, (name, result)
        if observed is not None:
            assert len(result["observedCases"]) == observed, (name, result)
        if assertion_count is not None:
            assert len(result["assertionFailures"]) == assertion_count, (name, result)
        if call_type is not None:
            assert result["callErrors"][0]["exception"]["type"] == call_type, (name, result)
        assert not any(
            result[key]
            for key in (
                "taskOutcomeObserved",
                "oracleQualified",
                "campaignAdmitted",
                "nativeCollectionOccurred",
            )
        ), result
        reports.append(
            {
                "name": name,
                "reason": result["reason"],
                "classification": result["classification"],
                "candidateOutcomeObserved": result["candidateOutcomeObserved"],
                "testsPassed": result["testsPassed"],
                "casePhaseReportCoverageComplete": result["casePhaseReportCoverageComplete"],
                "observedCaseCount": len(result["observedCases"]),
                "callErrors": result.get("callErrors", []),
                "frameworkErrors": result["frameworkErrors"],
            }
        )

    check(
        "complete-full157-source-fixture-pass",
        complete=True,
        passed=True,
        coverage=True,
        observed=157,
    )
    check(
        "complete-root-assertion-failure-still-runs-backend",
        failing,
        complete=True,
        passed=False,
        coverage=True,
        observed=157,
        assertion_count=1,
    )
    check(
        "complete-backend-assertion-failure",
        lambda d: failing(d, suite="backend-pytest"),
        complete=True,
        passed=False,
        observed=157,
    )
    check(
        "complete-both-suite-assertion-failures",
        lambda d: (failing(d), failing(d, suite="backend-pytest")),
        complete=True,
        passed=False,
        assertion_count=2,
    )
    check("observed-subtest-pass", subtest, complete=True, passed=True)
    check(
        "subtest-failure-parent-call-returns-normally",
        lambda d: subtest(d, outcome="assertion-failed"),
        complete=True,
        passed=False,
        assertion_count=1,
        observed=157,
    )
    check("unfinished-subtest", lambda d: subtest(d, completed=False))
    check(
        "subtest-exception-unresolved",
        lambda d: subtest(d, outcome="error"),
        coverage=True,
        observed=157,
        call_type="builtins.ValueError",
    )

    def setup_no_call(d):
        failing(d, phase="setup", outcome="error", type_name="builtins.ModuleNotFoundError")
        identity = first(d)["id"]
        d[0][:] = [r for r in d[0] if not (r.get("id") == identity and r.get("phase") == "call")]

    check(
        "realistic-setup-error-omits-call-but-preserves-later-cases",
        setup_no_call,
        coverage=False,
        observed=157,
    )
    check(
        "assertion-plus-cleanup-error-is-incomplete",
        lambda d: (
            failing(d),
            failing(d, phase="cleanup", outcome="error", type_name="builtins.RuntimeError"),
        ),
        coverage=True,
        observed=157,
    )

    def child_edit(d, operation):
        subtest(d)
        child = next(r for r in d[0] if r["kind"] == "subtest-result")
        operation(d, child)

    check(
        "duplicate-subtest-result",
        lambda d: child_edit(
            d, lambda d, child: d[0].insert(d[0].index(child) + 1, deepcopy(child))
        ),
    )
    check(
        "boolean-subtest-ordinal",
        lambda d: child_edit(d, lambda d, child: child.update(ordinal=True)),
    )

    def late_child(d):
        subtest(d)
        start = next(r for r in d[0] if r["kind"] == "subtest-start")
        d[0].remove(start)
        d[0].insert(d[0].index(first(d)) + 1, start)

    check("subtest-after-call-result", late_child)
    for phase in ("setup", "teardown", "cleanup"):
        check(
            "unittest-" + phase + "-assertion-is-not-semantic-pass",
            lambda d, phase=phase: failing(d, phase=phase),
            coverage=True,
            observed=157,
        )
    for phase in ("setup", "teardown"):
        check(
            "pytest-" + phase + "-error",
            lambda d, phase=phase: failing(
                d,
                phase=phase,
                suite="backend-pytest",
                outcome="error",
                type_name="builtins.RuntimeError",
            ),
            coverage=True,
            observed=157,
        )
    for t, errno in [
        ("builtins.ValueError", None),
        ("builtins.ModuleNotFoundError", None),
        ("builtins.ImportError", None),
        ("builtins.FileNotFoundError", 2),
        ("builtins.PermissionError", 13),
        ("builtins.MemoryError", None),
        ("builtins.OSError", 28),
        ("builtins.KeyboardInterrupt", None),
    ]:
        check(
            "call-exception-" + t,
            lambda d, t=t, errno=errno: failing(d, outcome="error", type_name=t, errno=errno),
            coverage=True,
            observed=157,
            call_type=t,
        )
    for outcome in ("skipped", "xfail", "xpass"):
        check(
            "unadjudicated-" + outcome,
            lambda d, outcome=outcome: failing(d, outcome=outcome),
            coverage=True,
        )
    for where in (
        "import",
        "collection",
        "setup",
        "teardown",
        "cleanup",
        "internal",
        "resource",
        "interrupted",
    ):

        def framework(d, where=where):
            d[0].insert(
                3,
                {
                    "kind": "framework-error",
                    "suite": "root-unittest",
                    "where": where,
                    "fixture": "owned fixture",
                    "exception": {
                        "type": "builtins.RuntimeError",
                        "message": "owned",
                        "errno": None,
                    },
                },
            )

        check("framework-" + where, framework, coverage=True, observed=157)
    check("actual-mode-cannot-use-owned-fixture", actual=True)
    check(
        "self-authored-origin-flag-cannot-admit-actual",
        lambda d: d[1].update(trusted=True, nativeCollection=True),
        actual=True,
    )
    check("summary-only-is-not-events", value=b"Ran 157 tests\nOK\n")
    check(
        "diagnostic-print-only-is-not-events", value=b"test complete, expected formats displayed\n"
    )
    check(
        "native-collection-only-no-case-run",
        lambda d: d[0].__setitem__(
            slice(None),
            [
                r
                for r in d[0]
                if r["kind"] not in {"case-start", "case-end", "phase-start", "phase-result"}
            ],
        ),
    )
    check(
        "root-only-subset",
        lambda d: d[0].__setitem__(
            slice(None), [r for r in d[0] if r.get("suite") != "backend-pytest"]
        ),
    )
    check(
        "backend-only-subset",
        lambda d: d[0].__setitem__(
            slice(None), [r for r in d[0] if r.get("suite") != "root-unittest"]
        ),
    )
    check(
        "missing-case-terminal",
        lambda d: d[0].remove(next(r for r in d[0] if r["kind"] == "case-end")),
    )
    check("missing-cleanup", lambda d: d[0].remove(first(d, "cleanup")))
    check("duplicate-case-start", lambda d: d[0].insert(4, deepcopy(d[0][3])))
    check(
        "duplicate-phase-result",
        lambda d: d[0].insert(d[0].index(first(d)) + 1, deepcopy(first(d))),
    )
    check(
        "wrong-order-call-before-setup",
        lambda d: next(r for r in d[0] if r["kind"] == "phase-start").update(phase="call"),
    )
    check("event-after-case-terminal", lambda d: d[0].insert(14, deepcopy(first(d))))
    check(
        "assertion-type-spoof",
        lambda d: first(d).update(
            outcome="assertion-failed",
            exception={"type": "builtins.ImportError", "message": "owned", "errno": None},
        ),
    )
    check(
        "exception-schema-number-message",
        lambda d: first(d).update(
            outcome="error", exception={"type": "builtins.ValueError", "message": 42, "errno": None}
        ),
    )
    check(
        "exception-boolean-errno",
        lambda d: first(d).update(
            outcome="error",
            exception={"type": "builtins.ValueError", "message": "owned", "errno": False},
        ),
    )
    check("changed-source-archive", lambda d: d[1].update(sourceArchiveSha256="0" * 64))
    check(
        "changed-environment-subject",
        lambda d: d[1].update(environmentSubject="fake-available-dependencies"),
    )
    check("missing-source-check", lambda d: d[1].pop("sourceState"))
    check("transport-timeout", lambda d: d[1]["suiteProcesses"][0].update(error="timeout"))
    check("signal-kill", lambda d: d[1]["suiteProcesses"][0].update(signal=9, exitCode=137))
    check("output-cap", lambda d: d[1]["suiteProcesses"][0].update(truncated=True))
    check("boolean-exitcode", lambda d: d[1]["suiteProcesses"][0].update(exitCode=False))
    check("suite-process-exit-mismatch", lambda d: d[1]["suiteProcesses"][0].update(exitCode=1))
    check(
        "process-overlap-time",
        lambda d: d[1]["suiteProcesses"][1].update(startedAt="2026-10-30T00:00:00+00:00"),
    )
    check(
        "pytest-collection-exit2-not-complete",
        lambda d: (
            next(r for r in d[0] if r["kind"] == "suite-end").update(exitCode=2),
            d[1]["suiteProcesses"][0].update(exitCode=2),
        ),
        coverage=True,
    )
    check(
        "deselection",
        lambda d: next(r for r in d[0] if r["kind"] == "collection").update(deselected=["owned"]),
    )
    check(
        "empty-collection",
        lambda d: next(r for r in d[0] if r["kind"] == "collection").update(ids=[]),
    )
    check(
        "duplicate-collection-id",
        lambda d: next(r for r in d[0] if r["kind"] == "collection")["ids"].append(
            next(r for r in d[0] if r["kind"] == "collection")["ids"][0]
        ),
    )
    check(
        "diagnostic-injected-as-semantic-case",
        lambda d: next(r for r in d[0] if r["kind"] == "case-start").update(
            id="backend/scripts/test_profile_format.py::test_profile_formats"
        ),
    )
    check("unfinished-full-run", lambda d: d[0].pop())
    for value in (b'{"seq":1,"seq":2}\n', b'{"seq":1,"x":NaN}\n', b"\xff\n", b"{}", b"{}\n\n"):
        check("strict-json-or-framing-refusal", value=value)
    report = {
        "state": "owned-synthetic-phase-controls-passed",
        "count": len(reports),
        "cases": reports,
        "staticCandidateFixtureCases": 157,
        "nativeCasesEstablished": False,
        "newSourceImportsTestsDaemonNetworkProviderActions": 0,
        "actualAdmission": False,
    }
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"allPassed": True, "count": len(reports), "actualAdmission": False}))


if __name__ == "__main__":
    main()
