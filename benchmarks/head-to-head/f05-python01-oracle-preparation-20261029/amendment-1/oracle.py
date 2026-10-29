"""Bounded Python01 post-run phase scorer preparation; never launches/tests/imports source.

Synthetic source-candidate fixtures exercise lifecycle rules. Actual admission is
closed until native collection, dependency environment and trusted observer/capture
joins are implemented, frozen and independently reviewed. No summary/flag opens it.
"""

from datetime import datetime
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST_SHA = "e141c87f452f021a3a9e7ced5c3bb1b2efc8691a06d925cde0cebdabddf09339"
SUITES = ("root-unittest", "backend-pytest")
PHASES = {
    "root-unittest": ("setup", "call", "teardown", "cleanup"),
    "backend-pytest": ("setup", "call", "teardown"),
}
OUTCOMES = {"passed", "assertion-failed", "error", "skipped", "xfail", "xpass"}
MAX_BYTES, MAX_EVENTS, MAX_CASES, MAX_SUBTESTS = 8 * 1024**2, 100000, 10000, 10000
GAPS = [
    "complete-native-collection-and-static-source-reconciliation-unavailable",
    "qualified-interpreter-pytest-plugins-dependency-and-import-root-context-unavailable",
    "trusted-unittest-phase/subtest-and-pytest-report-observer-unavailable",
    "same-process/raw-host-capture-source-environment-setup-and-budget-join-unavailable",
]


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate JSON key")
        value[key] = item
    return value


def nonfinite(value):
    raise ValueError("nonfinite JSON: " + value)


def encode(value):
    return json.dumps(value, sort_keys=True, allow_nan=False).encode()


def load(raw):
    require(isinstance(raw, bytes) and len(raw) <= MAX_BYTES, "raw JSON byte cap/type")
    return json.loads(
        raw.decode("utf-8", errors="strict"), object_pairs_hook=unique, parse_constant=nonfinite
    )


def stamp(value):
    require(isinstance(value, str), "timestamp type")
    result = datetime.fromisoformat(value)
    require(result.tzinfo is not None, "timestamp timezone")
    return result


def manifest():
    raw = (HERE / "synthetic-case-manifest.json").read_bytes()
    require(sha(raw) == MANIFEST_SHA, "changed source-candidate fixture")
    value = load(raw)
    require(
        value["state"] == "owned-synthetic-source-candidate-fixture-not-native-collection"
        and value["nativeCollectionOccurred"] is False
        and value["nativeIdsEstablished"] is False,
        "fixture mislabeled native",
    )
    require(0 < len(value["cases"]) <= MAX_CASES, "case bound")
    require(
        len({row["id"] for row in value["cases"]}) == len(value["cases"]), "duplicate case identity"
    )
    for row in value["cases"]:
        require(
            row["id"].startswith("owned-synthetic::") and row["suite"] in SUITES,
            "case fixture identity",
        )
        raw = (HERE / "sources" / row["sourcePath"]).read_bytes()
        require(sha(raw) == row["sourceSha256"], "changed test source")
    return value


def exception(value, outcome):
    if outcome not in {"assertion-failed", "error"}:
        require(value is None, "exception on nonfailure outcome")
        return
    require(
        isinstance(value, dict) and set(value) == {"type", "message", "errno"},
        "failure exception schema",
    )
    require(
        isinstance(value["type"], str)
        and 0 < len(value["type"]) <= 200
        and isinstance(value["message"], str)
        and len(value["message"].encode()) <= 4096
        and (value["errno"] is None or type(value["errno"]) is int),
        "failure exception fields",
    )
    if outcome == "assertion-failed":
        require(
            value["type"] == "builtins.AssertionError", "assertion classification/type mismatch"
        )


def rows(raw):
    require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_BYTES, "event byte cap/type")
    require(raw.endswith(b"\n"), "unterminated event stream")
    lines = raw.splitlines()
    require(0 < len(lines) <= MAX_EVENTS and all(lines), "event count/blank line")
    result = [load(line) for line in lines]
    require(all(isinstance(row, dict) for row in result), "nonobject event")
    require(
        all(type(row.get("seq")) is int and row["seq"] == i for i, row in enumerate(result, 1)),
        "event sequence",
    )
    return result


def evaluate(raw, execution, *, synthetic=False):
    result = {
        "taskId": "python-01",
        "synthetic": synthetic,
        "casePhaseReportCoverageComplete": False,
        "candidateOutcomeObserved": False,
        "taskOutcomeObserved": False,
        "testsPassed": None,
        "classification": "unresolved",
        "reason": "unresolved",
        "observedCases": [],
        "frameworkErrors": [],
        "oracleQualified": False,
        "campaignAdmitted": False,
        "nativeCollectionOccurred": False,
        "remainingJoins": list(GAPS),
    }
    try:
        require(type(synthetic) is bool, "synthetic type")
        require(synthetic, "actual-native-collection-observer-and-capture-join-unavailable")
        expected = manifest()
        require(
            isinstance(execution, dict)
            and set(execution)
            == {
                "state",
                "manifestSha256",
                "rawEventsSha256",
                "sourceArchiveSha256",
                "environmentSubject",
                "sourceState",
                "suiteProcesses",
            },
            "execution fixture schema",
        )
        require(
            execution["state"] == "owned-synthetic-process-and-context-fixture-not-native-evidence"
            and execution["manifestSha256"] == MANIFEST_SHA
            and execution["rawEventsSha256"] == sha(raw)
            and execution["sourceArchiveSha256"] == expected["sourceArchiveSha256"],
            "execution fixture/source/event binding",
        )
        require(
            execution["environmentSubject"] == "owned-synthetic-unqualified-environment"
            and execution["sourceState"] == "owned-synthetic-unchanged-source-fixture",
            "synthetic context mismatch",
        )
        processes = execution["suiteProcesses"]
        require(
            isinstance(processes, list) and [p["suite"] for p in processes] == list(SUITES),
            "missing/duplicate/reordered suite process",
        )
        for process in processes:
            require(
                set(process)
                == {
                    "suite",
                    "exitCode",
                    "error",
                    "signal",
                    "truncated",
                    "startedAt",
                    "completedAt",
                },
                "process fixture schema",
            )
            require(
                type(process["exitCode"]) is int
                and process["error"] is None
                and process["signal"] is None
                and process["truncated"] is False
                and stamp(process["startedAt"]) <= stamp(process["completedAt"]),
                "incomplete/error process transport",
            )
        require(
            stamp(processes[0]["completedAt"]) <= stamp(processes[1]["startedAt"]),
            "suite process chronology",
        )
        expected_by_suite = {
            suite: {r["id"] for r in expected["cases"] if r["suite"] == suite} for suite in SUITES
        }
        active_suite, suite_index, collection, cases, finished, problems = (
            None,
            0,
            {},
            {},
            set(),
            [],
        )
        began, ended = False, False
        subtest_count = 0
        for row in rows(raw):
            kind = row.get("kind")
            if kind == "run-start":
                require(
                    not began
                    and row == {"seq": 1, "kind": "run-start", "manifestSha256": MANIFEST_SHA},
                    "run-start schema/order",
                )
                began = True
                continue
            require(began and not ended, "event outside run")
            if kind == "run-end":
                require(
                    set(row) == {"seq", "kind"} and active_suite is None and suite_index == 2,
                    "run ended before both suites",
                )
                ended = True
                continue
            suite = row.get("suite")
            require(suite in SUITES, "unknown suite")
            if kind == "suite-start":
                require(
                    set(row) == {"seq", "kind", "suite", "runner"}
                    and active_suite is None
                    and suite_index < 2
                    and suite == SUITES[suite_index]
                    and row["runner"] == ("unittest" if suite == SUITES[0] else "pytest"),
                    "suite-start schema/order/runner",
                )
                active_suite = suite
                continue
            require(active_suite == suite, "event outside active suite")
            if kind == "framework-error":
                require(
                    set(row) == {"seq", "kind", "suite", "where", "fixture", "exception"}
                    and row["where"]
                    in {
                        "import",
                        "collection",
                        "setup",
                        "teardown",
                        "cleanup",
                        "internal",
                        "interrupted",
                        "resource",
                    }
                    and isinstance(row["fixture"], str)
                    and len(row["fixture"].encode()) <= 4096,
                    "framework-error schema",
                )
                exception(row["exception"], "error")
                result["frameworkErrors"].append(row)
                problems.append("incomplete-framework-" + row["where"])
                continue
            if kind == "collection":
                require(
                    set(row) == {"seq", "kind", "suite", "ids", "deselected"}
                    and suite not in collection
                    and not any(k in cases for k in expected_by_suite[suite]),
                    "collection schema/order",
                )
                require(
                    isinstance(row["ids"], list)
                    and all(isinstance(x, str) for x in row["ids"])
                    and len(row["ids"]) <= MAX_CASES
                    and len(set(row["ids"])) == len(row["ids"]),
                    "collection identity types/duplicates",
                )
                require(
                    set(row["ids"]) == expected_by_suite[suite] and row["deselected"] == [],
                    "collection mismatch/deselection",
                )
                collection[suite] = set(row["ids"])
                continue
            if kind == "suite-end":
                require(
                    set(row) == {"seq", "kind", "suite", "exitCode"}
                    and type(row["exitCode"]) is int
                    and suite in collection,
                    "suite-end schema/order",
                )
                if not expected_by_suite[suite] <= finished:
                    problems.append("missing case terminal coverage")
                require(
                    row["exitCode"] == processes[suite_index]["exitCode"],
                    "suite/process exit disagreement",
                )
                suite_states = [cases[x] for x in expected_by_suite[suite] if x in cases]
                failures = any(
                    any(
                        r["outcome"] in {"assertion-failed", "error", "xpass"}
                        for r in [*c["reports"], *c["subtests"].values()]
                    )
                    for c in suite_states
                )
                if row["exitCode"] not in (0, 1):
                    problems.append("incomplete-runner-exit-" + str(row["exitCode"]))
                elif row["exitCode"] != int(failures):
                    problems.append("runner/case-result-disagreement")
                active_suite = None
                suite_index += 1
                continue
            require(suite in collection, "case before collection")
            identity = row.get("id")
            require(
                isinstance(identity, str) and identity in expected_by_suite[suite],
                "case outside intended scope",
            )
            if kind == "case-start":
                require(
                    set(row) == {"seq", "kind", "suite", "id"} and identity not in cases,
                    "duplicate/invalid case start",
                )
                cases[identity] = {
                    "suite": suite,
                    "phaseIndex": 0,
                    "activePhase": None,
                    "reports": [],
                    "activeSubtests": set(),
                    "subtests": {},
                    "subtestNext": 1,
                    "missingPhases": [],
                }
                continue
            require(identity in cases and identity not in finished, "case event outside lifecycle")
            case = cases[identity]
            phases = PHASES[suite]
            if kind == "phase-start":
                require(
                    set(row) == {"seq", "kind", "suite", "id", "phase"}
                    and case["activePhase"] is None
                    and case["phaseIndex"] < len(phases)
                    and row["phase"] in phases[case["phaseIndex"] :],
                    "phase-start order/schema",
                )
                index = phases.index(row["phase"])
                case["missingPhases"].extend(phases[case["phaseIndex"] : index])
                case["phaseIndex"] = index
                case["activePhase"] = row["phase"]
            elif kind == "phase-result":
                require(
                    set(row) == {"seq", "kind", "suite", "id", "phase", "outcome", "exception"}
                    and case["activePhase"] is not None
                    and row["phase"] in phases
                    and case["activePhase"] == row["phase"]
                    and case["phaseIndex"] < len(phases)
                    and row["phase"] == phases[case["phaseIndex"]]
                    and row["outcome"] in OUTCOMES
                    and not case["activeSubtests"],
                    "phase-result order/schema/unfinished-subtest",
                )
                exception(row["exception"], row["outcome"])
                case["reports"].append(row)
                case["activePhase"] = None
                case["phaseIndex"] += 1
            elif kind == "subtest-start":
                require(
                    set(row) == {"seq", "kind", "suite", "id", "ordinal", "label"}
                    and suite == SUITES[0]
                    and case["activePhase"] == "call"
                    and type(row["ordinal"]) is int
                    and row["ordinal"] == case["subtestNext"]
                    and isinstance(row["label"], str)
                    and len(row["label"].encode()) <= 4096,
                    "subtest-start schema/order",
                )
                require(not case["activeSubtests"], "unsupported nested subtest")
                case["activeSubtests"].add(row["ordinal"])
                case["subtestNext"] += 1
                subtest_count += 1
                require(subtest_count <= MAX_SUBTESTS, "subtest count cap")
            elif kind == "subtest-result":
                require(
                    set(row) == {"seq", "kind", "suite", "id", "ordinal", "outcome", "exception"}
                    and type(row["ordinal"]) is int
                    and row["ordinal"] in case["activeSubtests"]
                    and row["outcome"] in OUTCOMES
                    and case["activePhase"] == "call",
                    "subtest-result schema/order",
                )
                exception(row["exception"], row["outcome"])
                case["activeSubtests"].remove(row["ordinal"])
                case["subtests"][row["ordinal"]] = row
            elif kind == "case-end":
                require(
                    set(row) == {"seq", "kind", "suite", "id"}
                    and case["activePhase"] is None
                    and not case["activeSubtests"],
                    "case ended before all phases/subtests",
                )
                case["missingPhases"].extend(phases[case["phaseIndex"] :])
                case["phaseIndex"] = len(phases)
                if case["missingPhases"]:
                    problems.append("missing phase report(s): " + identity)
                finished.add(identity)
                result["observedCases"].append(
                    {
                        "id": identity,
                        "suite": suite,
                        "phases": [
                            {
                                "phase": r["phase"],
                                "outcome": r["outcome"],
                                "exception": r["exception"],
                            }
                            for r in case["reports"]
                        ],
                        "subtests": list(case["subtests"].values()),
                        "missingPhases": list(case["missingPhases"]),
                    }
                )
            else:
                raise ValueError("unknown event kind")
        require(
            began and ended and active_suite is None and suite_index == 2,
            "incomplete run/suite lifecycle",
        )
        full_ids = set().union(*expected_by_suite.values())
        if finished != full_ids:
            problems.append("missing full union case coverage")
        result["startedCaseIds"] = sorted(cases)
        result["unfinishedCaseIds"] = sorted(set(cases) - finished)
        result["missingCaseIds"] = sorted(full_ids - set(cases))
        result["casePhaseReportCoverageComplete"] = finished == full_ids and not any(
            case["missingPhases"] for case in cases.values()
        )
        assertion_failures, call_errors, other_outcomes, phase_errors = [], [], [], []
        for identity, case in cases.items():
            for report in case["reports"]:
                outcome, phase = report["outcome"], report["phase"]
                if outcome == "passed":
                    continue
                record = {
                    "id": identity,
                    "suite": case["suite"],
                    "phase": phase,
                    "outcome": outcome,
                    "exception": report["exception"],
                }
                if phase != "call":
                    phase_errors.append(record)
                elif outcome == "assertion-failed":
                    assertion_failures.append(record)
                elif outcome == "error":
                    call_errors.append(record)
                else:
                    other_outcomes.append(record)
            for sub in case["subtests"].values():
                record = {
                    "id": identity,
                    "suite": case["suite"],
                    "phase": "subtest",
                    "outcome": sub["outcome"],
                    "exception": sub["exception"],
                    "ordinal": sub["ordinal"],
                }
                if sub["outcome"] == "assertion-failed":
                    assertion_failures.append(record)
                elif sub["outcome"] == "error":
                    call_errors.append(record)
                elif sub["outcome"] != "passed":
                    other_outcomes.append(record)
        for record in call_errors:
            error = record["exception"]
            if error["type"] in {"builtins.ImportError", "builtins.ModuleNotFoundError"}:
                record["errorClass"] = "call-import-error-unresolved"
            elif error["type"] in {
                "builtins.MemoryError",
                "builtins.KeyboardInterrupt",
                "builtins.SystemExit",
                "builtins.TimeoutError",
            } or error["errno"] in (12, 28):
                record["errorClass"] = "call-resource-or-interruption-class-unresolved"
            else:
                record["errorClass"] = "semantic-call-exception-unresolved"
        result.update(
            assertionFailures=assertion_failures,
            callErrors=call_errors,
            phaseErrors=phase_errors,
            unadjudicatedOutcomes=other_outcomes,
        )
        if phase_errors:
            problems.append("incomplete-setup-teardown-or-cleanup")
        if call_errors:
            problems.append("complete-call-exception-unresolved")
        if other_outcomes:
            problems.append("unadjudicated-skip-xfail-or-xpass")
        if problems:
            result.update(
                classification="noncompletion-or-unresolved",
                reason=problems[0],
                unresolvedReasons=problems,
            )
        else:
            result.update(
                candidateOutcomeObserved=True,
                testsPassed=not bool(assertion_failures),
                classification="complete-assertion-outcome",
                reason="complete full semantic-union assertion outcome",
            )
    except (
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        AttributeError,
        OSError,
        UnicodeError,
    ) as error:
        result.update(classification="incomplete-or-unqualified", reason=str(error))
    return result
