"""Default Cargo phase accounting for one source-frozen parser task.

This is a bounded post-run oracle amendment, not a general Rust result parser.
It preserves the pinned Go/Vitest checks and records default fail-fast exclusions.
"""

import re

from oracle import rust_outcome as unit_outcome

SUMMARY = re.compile(
    r"^test result: (ok|FAILED)\. (\d+) passed; (\d+) failed; (\d+) ignored; (\d+) measured; (\d+) filtered out",
    re.M,
)
UNIT_MARKER = re.compile(r"^\s*Running unittests src/lib\.rs\b", re.M)
DOC_MARKER = re.compile(r"^\s*Doc-tests sniffnet_packet_parser\s*$", re.M)
LIB_FAILURE = re.compile(r"^\s*error: test failed, to rerun pass [`']?--lib[`']?\s*$", re.M)


def rust_default_outcome(native, expected_names, policy):
    stdout, stderr = native.get("stdout"), native.get("stderr")
    result = {
        "qualified": False,
        "reason": "unknown/incomplete native default phases",
        "processExitCode": native.get("exitCode"),
        "processError": native.get("error"),
        "phaseCoverageComplete": False,
        "unitPhase": {"terminal": False},
        "docPhase": {"state": "unknown", "exercised": False, "terminal": False},
    }
    if not isinstance(stdout, str) or not isinstance(stderr, str):
        return result
    summaries = [
        {
            "status": row[0],
            **dict(
                zip(
                    ("passed", "failed", "ignored", "measured", "filtered"),
                    map(int, row[1:]),
                    strict=True,
                )
            ),
        }
        for row in SUMMARY.findall(stdout)
    ]
    result["summaries"] = summaries
    result["unitMarkerCount"] = len(UNIT_MARKER.findall(stderr))
    result["docMarkerCount"] = len(DOC_MARKER.findall(stderr))
    result["unitMarkerObserved"] = result["unitMarkerCount"] > 0
    result["docMarkerObserved"] = result["docMarkerCount"] > 0
    if native.get("error") is not None or type(native.get("exitCode")) is not int:
        result["reason"] = "native transport/timeout/process identity unresolved"
        return result
    units = unit_outcome(stdout, expected_names)
    if not units["qualified"] or not summaries or result["unitMarkerCount"] != 1:
        result["reason"] = "unit scope/terminal report missing"
        return result
    unit = summaries[0]
    cases = re.findall(r"^test (\S+) \.\.\. (ok|FAILED)$", stdout, re.M)
    if (
        not isinstance(policy.get("expectedUnitCaseIds"), list)
        or len(set(policy["expectedUnitCaseIds"])) != len(expected_names)
        or sorted(name for name, _ in cases) != sorted(policy["expectedUnitCaseIds"])
        or len(cases) != len(expected_names)
        or sum(status == "FAILED" for _, status in cases) != unit["failed"]
        or sum(status == "ok" for _, status in cases) != unit["passed"]
    ):
        result["reason"] = (
            "exact case identities or terminal states contradict frozen scope/summary"
        )
        return result
    result["unitPhase"] = {
        "terminal": True,
        "exercised": True,
        **unit,
        "cases": sorted(name for name, _ in cases),
        "expectedCaseIds": sorted(policy["expectedUnitCaseIds"]),
    }
    if unit["status"] != ("FAILED" if unit["failed"] else "ok"):
        result["reason"] = "contradictory unit summary"
        return result
    error_lines = [
        line for line in stderr.splitlines() if re.match(r"^\s*error(?:\[[^\]]+\])?:", line)
    ]
    unexpected_diagnostics = [line for line in error_lines if not LIB_FAILURE.fullmatch(line)]
    compiler_failure = bool(unexpected_diagnostics) or bool(
        re.search(
            r"rustdoc compile failed|could not compile|couldn't compile|process didn't exit successfully|^\s*Caused by:",
            stderr,
            re.I | re.M,
        )
    )
    result["unexpectedFailureDiagnostics"] = unexpected_diagnostics
    if compiler_failure:
        result["reason"] = "compile/setup/unknown diagnostic prevents complete default outcome"
        return result
    if unit["failed"] == 0:
        doc_complete = (
            len(summaries) == 2
            and result["docMarkerCount"] == 1
            and summaries[1]
            == {
                "status": "ok",
                "passed": 0,
                "failed": 0,
                "ignored": 0,
                "measured": 0,
                "filtered": 0,
            }
            and native["exitCode"] == 0
            and not error_lines
        )
        result["docPhase"] = {
            "state": "zero-case-phase-terminal" if doc_complete else "missing-or-failed",
            "exercised": doc_complete,
            "terminal": doc_complete,
            "testCases": 0 if doc_complete else None,
        }
        result["qualified"] = result["phaseCoverageComplete"] = doc_complete
        result["reason"] = (
            "units and zero-case default doc phase terminal"
            if doc_complete
            else "unit success does not establish remaining default phases/process success"
        )
        return result
    fail_fast = (
        policy.get("unitAssertionFailureStopsDefault") is True
        and native["exitCode"] == 101
        and len(summaries) == 1
        and not result["docMarkerObserved"]
        and bool(LIB_FAILURE.search(stderr))
    )
    result["qualified"] = fail_fast
    result["docPhase"] = {
        "state": "unexecuted-default-stop" if fail_fast else "unknown-after-unit-failure",
        "exercised": False,
        "terminal": False,
        "testCases": None,
    }
    result["reason"] = (
        "terminal unit assertion failure is frozen default-command outcome; doc phase unexecuted"
        if fail_fast
        else "unit failure/default-stop policy or remaining phases unresolved"
    )
    return result
