"""Bounded independent synthetic hierarchy regressions; no process/native calls."""

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
PREPARATION = ROOT / "benchmarks/head-to-head/f05-go01-oracle-preparation-20261029"
AMENDMENT = PREPARATION / "amendment-1"
BEFORE_REVIEW = ROOT / "benchmarks/head-to-head/f05-go01-oracle-review-20261029"
sys.path.insert(0, str(AMENDMENT))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


controls = load("amended_go01_controls", AMENDMENT / "controls.py")
new = load("amended_go01_oracle", AMENDMENT / "oracle.py")
old = load("original_go01_oracle", PREPARATION / "oracle.py")
P = controls.P
TOP = "TestSyntheticActive"


def score(data, module=new):
    events, collection, policy, execution = deepcopy(data)
    raw = "".join(json.dumps(row) + "\n" for row in events)
    execution.update(
        rawEventsSha256=hashlib.sha256(raw.encode()).hexdigest(),
        collectionSha256=module.digest(collection),
        policySha256=module.digest(policy),
    )
    result = module.evaluate(raw, collection, policy, execution, synthetic=True)
    assert result["taskOutcomeObserved"] is False
    return result


def row(action, test, output=None):
    return controls.row(P, action, test, output)


def segment(data, events):
    data[0][2:5] = events


def set_failure(data):
    next(
        event
        for event in data[0]
        if event["Package"] == P and event["Action"] == "pass" and "Test" not in event
    )["Action"] = "fail"
    data[3]["exitCode"] = 1


def fail(test):
    return [row("output", test, f"--- FAIL: {test} (0.01s)\n"), row("fail", test)]


def main():
    results = []
    exact = {
        "child-starts-after-parent-terminal",
        "parent-terminal-while-child-running",
        "failing-child-with-passing-parent",
    }
    frozen = json.loads((BEFORE_REVIEW / "challenge-results.json").read_text())
    for case in frozen["results"]:
        if case["case"] not in exact:
            continue
        data = controls.fixture()
        data[0][:] = deepcopy(case["events"])
        if case["case"] == "failing-child-with-passing-parent":
            data[3]["exitCode"] = 1
        before, after = score(data, old), score(data)
        assert before["candidateOutcomeObserved"] is True
        assert after["candidateOutcomeObserved"] is False
        results.append({"case": case["case"], "before": before, "after": after, "passed": True})
    assert len(results) == 3

    def check(name, mutate, expected):
        data = controls.fixture()
        mutate(data)
        result = score(data)
        assert result["candidateOutcomeObserved"] is expected, (name, result)
        results.append(
            {
                "case": name,
                "expectedCandidateCompletion": expected,
                "observed": result,
                "passed": True,
            }
        )

    def parallel_prefix(data):
        a, b, deep = TOP + "/child", TOP + "/childish", TOP + "/childish/deep"
        segment(
            data,
            [
                row("run", a),
                row("pause", a),
                row("run", b),
                row("pause", b),
                row("cont", b),
                row("run", deep),
                row("pass", deep),
                row("pass", b),
                row("cont", a),
                row("pass", a),
                row("pass", TOP),
            ],
        )

    check("parallel-prefix-siblings-with-nested-work", parallel_prefix, True)

    def own_assertion(data):
        a, b = TOP + "/child", TOP + "/second"
        segment(data, [row("run", a), row("pass", a), row("run", b), row("pass", b), *fail(TOP)])
        set_failure(data)

    check("parent-own-assertion-with-passing-children", own_assertion, True)

    def deep_failure(data):
        a, b, c, leaf = (
            TOP + "/child",
            TOP + "/childish",
            TOP + "/childish/deep",
            TOP + "/childish/deep/leaf",
        )
        segment(
            data,
            [
                row("run", a),
                row("run", b),
                row("run", c),
                row("run", leaf),
                *fail(leaf),
                *fail(c),
                *fail(b),
                row("pass", a),
                *fail(TOP),
            ],
        )
        set_failure(data)

    check("deep-failure-propagates-with-prefix-sibling-pass", deep_failure, True)

    def interleave_packages(data):
        package_events = [event for event in data[0] if event["Package"] == controls.Q]
        data[0][:] = [event for event in data[0] if event["Package"] != controls.Q]
        data[0][3:3] = package_events

    check("independent-package-finishes-with-other-parent-active", interleave_packages, True)

    def top_prefix(data):
        other = TOP + "Extra"
        data[1]["packages"][P].append(other)
        data[0][5:5] = [
            row("run", other),
            row("run", other + "/child"),
            row("pass", other + "/child"),
            row("pass", other),
        ]

    check("completed-top-prefix-does-not-block-distinct-tree", top_prefix, True)

    def unfinished_grandchild(data):
        a, b = TOP + "/child", TOP + "/child/deep"
        segment(
            data, [row("run", a), row("run", b), row("pass", a), row("pass", b), row("pass", TOP)]
        )

    check("unfinished-grandchild-prevents-immediate-parent-terminal", unfinished_grandchild, False)

    def failed_grandchild_passing_ancestor(data):
        a, b = TOP + "/child", TOP + "/child/deep"
        segment(data, [row("run", a), row("run", b), *fail(b), *fail(a), row("pass", TOP)])
        set_failure(data)

    check(
        "failed-grandchild-prevents-passing-grandparent", failed_grandchild_passing_ancestor, False
    )
    output = {
        "identity": "independent-go01-amendment-synthetic-controls",
        "passed": len(results),
        "results": results,
        "nativeCollectionOccurred": False,
        "actualTaskOutcomeObserved": False,
        "newDockerNetworkPackageProviderCalls": 0,
    }
    with (Path(__file__).parent / "independent-results.json").open("x") as stream:
        json.dump(output, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
