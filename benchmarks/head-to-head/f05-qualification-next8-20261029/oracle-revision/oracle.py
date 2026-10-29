"""Post-run native-test evidence checks; never used to authorize agent shell choices."""

import json
import re


def go_outcome(listing, actual, expected_prefix):
    expected, ran, terminal, skipped, packages, ended = set(), set(), set(), set(), set(), set()
    for row in map(json.loads, listing.splitlines()):
        package = row.get("Package", "")
        if package == expected_prefix or package.startswith(expected_prefix + "/"):
            for line in row.get("Output", "").splitlines():
                if re.fullmatch(r"(?:Test|Example|Fuzz)\S+", line):
                    expected.add((package, line))
    for row in map(json.loads, actual.splitlines()):
        package, test, action = row.get("Package", ""), row.get("Test"), row.get("Action")
        if not (package == expected_prefix or package.startswith(expected_prefix + "/")):
            return {"qualified": False, "reason": "wrong package scope"}
        packages.add(package)
        if test and "/" not in test:
            if action == "run":
                ran.add((package, test))
            if action in ("pass", "fail"):
                terminal.add((package, test))
        if test and action == "skip":
            skipped.add((package, test))
        if not test and action in ("pass", "fail", "skip"):
            ended.add(package)
    qualified = bool(expected) and expected <= ran & terminal and not skipped and packages <= ended
    return {
        "qualified": qualified,
        "reason": "complete native events"
        if qualified
        else "missing/listed-only/skipped/incomplete events",
        "expectedTopLevelTests": len(expected),
        "ranTopLevelTests": len(ran),
        "missingTests": sorted(expected - ran),
        "skippedTests": sorted(skipped),
        "packages": sorted(packages),
        "endedPackages": sorted(ended),
    }


def rust_outcome(stdout, expected_names):
    ran = {
        name
        for name in expected_names
        if re.search(r"^test \S*" + re.escape(name) + r" \.\.\. (?:ok|FAILED)$", stdout, re.M)
    }
    summary = re.search(
        r"test result: (?:ok|FAILED)\. (\d+) passed; (\d+) failed; (\d+) ignored; (\d+) measured; (\d+) filtered out",
        stdout,
    )
    qualified = bool(expected_names) and ran == set(expected_names) and bool(summary)
    if summary:
        passed, failed, ignored, measured, filtered = map(int, summary.groups())
        qualified = (
            qualified
            and passed + failed == len(expected_names)
            and ignored == measured == filtered == 0
        )
    return {
        "qualified": qualified,
        "reason": "complete component native tests"
        if qualified
        else "missing/listed-only/skipped/narrowed tests",
        "expectedTests": sorted(expected_names),
        "observedTests": sorted(ran),
    }


def vitest_outcome(report, expected_names, suite):
    rows = report.get("testResults", [])
    cases = [case for row in rows for case in row.get("assertionResults", [])]
    observed = {case.get("title") for case in cases}
    qualified = len(rows) == 1 and rows[0].get("name", "").endswith("/" + suite)
    qualified = qualified and observed == set(expected_names) and len(cases) == len(expected_names)
    qualified = qualified and all(case.get("status") in ("passed", "failed") for case in cases)
    return {
        "qualified": qualified,
        "reason": "entire launcher suite executed"
        if qualified
        else "wrong/listed-only/skipped/narrowed suite",
        "expectedTests": sorted(expected_names),
        "observedTests": sorted(name for name in observed if name),
    }


def controls():
    package = "example/api"
    listing = json.dumps({"Package": package, "Action": "output", "Output": "TestOne\n"})
    actual = "\n".join(
        json.dumps(row)
        for row in [
            {"Package": package, "Action": "run", "Test": "TestOne"},
            {"Package": package, "Action": "pass", "Test": "TestOne"},
            {"Package": package, "Action": "pass"},
        ]
    )
    assert go_outcome(listing, actual, package)["qualified"]
    assert not go_outcome(listing, listing, package)["qualified"]
    assert not go_outcome(listing, actual.replace('"pass", "Test"', '"skip", "Test"'), package)[
        "qualified"
    ]
    assert not go_outcome(listing, actual.replace(package, "example/other"), package)["qualified"]
    assert not go_outcome(listing, json.dumps({"Package": package, "Action": "pass"}), package)[
        "qualified"
    ]
    skipped_child = (
        actual + "\n" + json.dumps({"Package": package, "Action": "skip", "Test": "TestOne/child"})
    )
    assert not go_outcome(listing, skipped_child, package)["qualified"]
    native = "test link_type::tests::test_one ... ok\ntest result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out\n"
    assert rust_outcome(native, ["test_one"])["qualified"]
    assert not rust_outcome("test_one: test\n", ["test_one"])["qualified"]
    assert not rust_outcome(native.replace("0 ignored", "1 ignored"), ["test_one"])["qualified"]
    assert not rust_outcome(native, ["test_one", "test_two"])["qualified"]
    report = {
        "testResults": [
            {
                "name": "/repo/__tests__/bin/agent-canvas.test.ts",
                "assertionResults": [{"title": "one", "status": "passed"}],
            }
        ]
    }
    assert vitest_outcome(report, ["one"], "__tests__/bin/agent-canvas.test.ts")["qualified"]
    assert not vitest_outcome(report, ["one", "two"], "__tests__/bin/agent-canvas.test.ts")[
        "qualified"
    ]
    assert not vitest_outcome(report, ["one"], "unrelated.test.ts")["qualified"]
    report["testResults"][0]["assertionResults"][0]["status"] = "pending"
    assert not vitest_outcome(report, ["one"], "__tests__/bin/agent-canvas.test.ts")["qualified"]
    return {
        "positiveControls": 3,
        "negativeControls": 11,
        "status": "passed",
        "limits": "Synthetic native-format controls establish rejection behavior; actual source/environment execution is separately required.",
    }
