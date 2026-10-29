"""Append-only hierarchy counterexamples; no native collection or process calls."""

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import controls
import oracle

HERE = Path(__file__).resolve().parent
AUTHOR = HERE.parent
REVIEW = AUTHOR.parent / "f05-go01-oracle-review-20261029"
spec = importlib.util.spec_from_file_location("frozen_before_go01_oracle", AUTHOR / "oracle.py")
before_oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(before_oracle)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score(data, module=oracle):
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


def replace_children(data, segment):
    data[0][2:5] = segment


def row(action, test, output=None):
    return controls.row(controls.P, action, test, output)


def failure_segment(data, *, child="fail", parent="fail", grandchild=False):
    target = "TestSyntheticActive/child"
    segment = [row("run", target)]
    if grandchild:
        segment.extend(
            [
                row("run", target + "/deep"),
                row("output", target + "/deep", "--- FAIL: " + target + "/deep (0.01s)\n"),
                row("fail", target + "/deep"),
            ]
        )
    if child == "fail":
        segment.append(row("output", target, "--- FAIL: " + target + " (0.01s)\n"))
    segment.append(row(child, target))
    if parent == "fail":
        segment.append(
            row("output", "TestSyntheticActive", "--- FAIL: TestSyntheticActive (0.01s)\n")
        )
    segment.append(row(parent, "TestSyntheticActive"))
    replace_children(data, segment)
    next(
        event
        for event in data[0]
        if event["Package"] == controls.P and event["Action"] == "pass" and "Test" not in event
    )["Action"] = "fail"
    data[3]["exitCode"] = 1


def main():
    before = json.loads((HERE / "BEFORE.json").read_text())
    for path, digest in before["bindings"].items():
        assert sha(Path(path)) == digest, path
    results = []
    frozen_challenges = json.loads((REVIEW / "challenge-results.json").read_text())["results"]
    finding_names = {
        "child-starts-after-parent-terminal",
        "parent-terminal-while-child-running",
        "failing-child-with-passing-parent",
    }
    for finding in frozen_challenges:
        if finding["case"] not in finding_names:
            continue
        data = controls.fixture()
        data[0][:] = deepcopy(finding["events"])
        if finding["case"] == "failing-child-with-passing-parent":
            data[3]["exitCode"] = 1
        old, new = score(data, before_oracle), score(data)
        assert old["candidateOutcomeObserved"] is True and new["candidateOutcomeObserved"] is False
        results.append(
            {
                "case": finding["case"],
                "before": old,
                "after": new,
                "frozenBeforeEventIdentityPreserved": True,
                "passed": True,
            }
        )
    assert len(results) == 3

    def check(name, mutate=None, expected=False):
        data = controls.fixture()
        if mutate:
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

    check("valid original parent-child", expected=True)

    def siblings(data):
        replace_children(
            data,
            [
                row("run", "TestSyntheticActive/child"),
                row("pass", "TestSyntheticActive/child"),
                row("run", "TestSyntheticActive/sibling"),
                row("pass", "TestSyntheticActive/sibling"),
                row("pass", "TestSyntheticActive"),
            ],
        )

    check("valid sequential siblings after prior sibling terminal", siblings, True)

    def parallel_siblings(data):
        replace_children(
            data,
            [
                row("run", "TestSyntheticActive/child"),
                row("pause", "TestSyntheticActive/child"),
                row("run", "TestSyntheticActive/sibling"),
                row("pause", "TestSyntheticActive/sibling"),
                row("cont", "TestSyntheticActive/sibling"),
                row("cont", "TestSyntheticActive/child"),
                row("pass", "TestSyntheticActive/child"),
                row("pass", "TestSyntheticActive/sibling"),
                row("pass", "TestSyntheticActive"),
            ],
        )

    check("valid parallel siblings pause-cont remain nonterminal", parallel_siblings, True)

    def sibling_prefix(data):
        replace_children(
            data,
            [
                row("run", "TestSyntheticActive/child"),
                row("run", "TestSyntheticActive/childish"),
                row("run", "TestSyntheticActive/childish/deep"),
                row("pass", "TestSyntheticActive/child"),
                row("pass", "TestSyntheticActive/childish/deep"),
                row("pass", "TestSyntheticActive/childish"),
                row("pass", "TestSyntheticActive"),
            ],
        )

    check("valid sibling prefix collision does not create ancestry", sibling_prefix, True)
    check(
        "grandchild starts after immediate parent terminal",
        lambda data: replace_children(
            data,
            [
                row("run", "TestSyntheticActive/child"),
                row("pass", "TestSyntheticActive/child"),
                row("run", "TestSyntheticActive/child/deep"),
                row("pass", "TestSyntheticActive/child/deep"),
                row("pass", "TestSyntheticActive"),
            ],
        ),
    )
    check(
        "parent terminal while grandchild unfinished",
        lambda data: replace_children(
            data,
            [
                row("run", "TestSyntheticActive/child"),
                row("run", "TestSyntheticActive/child/deep"),
                row("pass", "TestSyntheticActive/child"),
                row("pass", "TestSyntheticActive/child/deep"),
                row("pass", "TestSyntheticActive"),
            ],
        ),
    )
    check(
        "grandparent terminal while descendants unfinished",
        lambda data: replace_children(
            data,
            [
                row("run", "TestSyntheticActive/child"),
                row("run", "TestSyntheticActive/child/deep"),
                row("pass", "TestSyntheticActive"),
                row("pass", "TestSyntheticActive/child/deep"),
                row("pass", "TestSyntheticActive/child"),
            ],
        ),
    )
    check("valid complete child assertion failure propagates to parent", failure_segment, True)
    check(
        "valid deep assertion failure propagates through all ancestors",
        lambda data: failure_segment(data, grandchild=True),
        True,
    )
    check(
        "deep failure with passing immediate parent rejected",
        lambda data: failure_segment(data, grandchild=True, child="pass"),
    )
    check(
        "deep failure with passing grandparent rejected",
        lambda data: failure_segment(data, grandchild=True, parent="pass"),
    )
    check(
        "failed child with skipped parent rejected",
        lambda data: failure_segment(data, parent="skip"),
    )

    def failed_prefix_sibling(data):
        parent, child, sibling, deep = (
            "TestSyntheticActive",
            "TestSyntheticActive/child",
            "TestSyntheticActive/childish",
            "TestSyntheticActive/childish/deep",
        )
        replace_children(
            data,
            [
                row("run", child),
                row("run", sibling),
                row("run", deep),
                row("output", deep, f"--- FAIL: {deep} (0.01s)\n"),
                row("fail", deep),
                row("pass", child),
                row("output", sibling, f"--- FAIL: {sibling} (0.01s)\n"),
                row("fail", sibling),
                row("output", parent, f"--- FAIL: {parent} (0.01s)\n"),
                row("fail", parent),
            ],
        )
        next(
            event
            for event in data[0]
            if event["Package"] == controls.P and event["Action"] == "pass" and "Test" not in event
        )["Action"] = "fail"
        data[3]["exitCode"] = 1

    check("sibling-prefix failure affects only actual slash ancestors", failed_prefix_sibling, True)

    def top_prefix(data):
        other = "TestSyntheticActiveExtra"
        data[1]["packages"][controls.P].append(other)
        data[0][1:1] = [row("run", other), row("pause", other)]
        position = (
            next(
                index
                for index, event in enumerate(data[0])
                if event.get("Test") == "TestSyntheticActive" and event["Action"] == "pass"
            )
            + 1
        )
        data[0][position:position] = [row("cont", other), row("pass", other)]

    check("top-level prefix names remain independent", top_prefix, True)
    data = controls.fixture()
    data[0][:] = [event for event in data[0] if event["Package"] == controls.Q]
    data[1]["packages"] = {controls.Q: ["TestATA"]}
    data[2]["exclusions"] = [
        entry for entry in data[2]["exclusions"] if entry["test"] == controls.TODO
    ]
    result = score(data)
    assert result["candidateOutcomeObserved"] is True
    results.append(
        {
            "case": "excluded-child-only manifest limitation retained",
            "observed": result,
            "classification": "A claimed complete top-level manifest cannot prove unobserved intended children. No generic active-child predicate added; actual native manifest remains missing.",
            "passed": True,
        }
    )
    for path, digest in before["bindings"].items():
        assert sha(Path(path)) == digest, path
    with (HERE / "hierarchy-results.json").open("x") as stream:
        json.dump(
            {
                "controls": results,
                "passed": len(results),
                "originalAndBeforeBindingsUnchanged": True,
                "nativeCollectionOccurred": False,
                "taskOutcomeObserved": False,
                "newDockerNetworkProviderNativeCalls": 0,
            },
            stream,
            indent=2,
        )
        stream.write("\n")


if __name__ == "__main__":
    main()
