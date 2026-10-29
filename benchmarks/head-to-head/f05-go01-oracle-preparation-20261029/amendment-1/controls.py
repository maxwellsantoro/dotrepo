"""Synthetic counterexamples only; no collected/native outcomes or process calls."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import oracle

HERE = Path(__file__).resolve().parent.parent
PROPOSED = json.loads((HERE / "policy-proposal.json").read_text())["exclusions"]
P = oracle.PREFIX + "/internal/fourslash/tests"
Q = oracle.PREFIX + "/internal/project/ata"
EMPTY = oracle.PREFIX + "/synthetic-no-tests"
DISABLED = "TestAliasMergingWithNamespace"
TODO = "TestATA/deduplicate_from_local_@types_packages"


def row(package, action, test=None, output=None):
    value = {"Package": package, "Action": action}
    if test is not None:
        value["Test"] = test
    if output is not None:
        value["Output"] = output
    return value


def fixture():
    events = [
        row(P, "start"),
        row(P, "run", "TestSyntheticActive"),
        row(P, "run", "TestSyntheticActive/child"),
        row(P, "pass", "TestSyntheticActive/child"),
        row(P, "pass", "TestSyntheticActive"),
        row(P, "run", DISABLED),
        row(P, "output", DISABLED, "    disabled_test.go:11: Known failing fourslash test\n"),
        row(P, "skip", DISABLED),
        row(P, "pass"),
        row(Q, "start"),
        row(Q, "run", "TestATA"),
        row(Q, "run", TODO),
        row(
            Q,
            "output",
            TODO,
            "    ata_test.go:518: Todo - implement removing local @types from include list\n",
        ),
        row(Q, "skip", TODO),
        row(Q, "pass", "TestATA"),
        row(Q, "pass"),
        row(EMPTY, "start"),
        row(EMPTY, "output", output="? synthetic [no test files]\n"),
        row(EMPTY, "skip"),
    ]
    binding = {
        "revision": oracle.REVISION,
        "sourceArchiveSha256": oracle.SOURCE,
        "imageId": "sha256:" + "1" * 64,
        "environmentSha256": "2" * 64,
        "command": oracle.COMMAND,
        "scope": "repository-default",
    }
    policy = {
        "state": "accepted-before-execution",
        "synthetic": True,
        "binding": binding,
        "acceptanceSha256": "3" * 64,
        "acceptedAt": "2026-10-29T00:00:00+00:00",
        "exclusionSetSha256": oracle.EXCLUSION_SET_SHA256,
        "exclusions": [deepcopy(v) for v in PROPOSED if v["test"] in (DISABLED, TODO)],
    }
    collection = {
        "state": "complete-native-collection-frozen-before-execution",
        "synthetic": True,
        "binding": binding,
        "exitCode": 0,
        "error": None,
        "completedAt": "2026-10-29T00:01:00+00:00",
        "frozenAt": "2026-10-29T00:02:00+00:00",
        "rawEventsSha256": "4" * 64,
        "packageInventorySha256": "5" * 64,
        "receiptSha256": "6" * 64,
        "packages": {P: ["TestSyntheticActive", DISABLED], Q: ["TestATA"], EMPTY: []},
    }
    execution = {
        "synthetic": True,
        "binding": binding,
        "startedAt": "2026-10-29T00:03:00+00:00",
        "setupComplete": True,
        "wrapperCompleted": True,
        "trackedSourceIntact": True,
        "eventsComplete": True,
        "truncated": False,
        "resourceFailure": False,
        "timedOut": False,
        "error": None,
        "exitCode": 0,
        "stderr": "",
    }
    return deepcopy((events, collection, policy, execution))


def score(data, *, raw=None, rebind=True):
    events, collection, policy, execution = data
    raw = raw if raw is not None else "".join(json.dumps(r) + "\n" for r in events)
    if rebind:
        execution["rawEventsSha256"] = hashlib.sha256(raw.encode()).hexdigest()
        execution["collectionSha256"] = oracle.digest(collection)
        execution["policySha256"] = oracle.digest(policy)
    return oracle.evaluate(raw, collection, policy, execution, synthetic=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = []

    def check(name, mutate=None, expected=False, raw=None):
        data = fixture()
        if mutate:
            mutate(*data)
        result = score(data, raw=raw)
        assert result["candidateOutcomeObserved"] is expected, (name, result)
        assert result["taskOutcomeObserved"] is False
        results.append(
            {
                "name": name,
                "expectedCandidateCompletion": expected,
                "observed": result,
                "passed": True,
            }
        )

    check("complete active coverage with exact source-declared exclusions", expected=True)

    def assertion(events, collection, policy, execution):
        events.insert(
            2, row(P, "output", "TestSyntheticActive", "--- FAIL: TestSyntheticActive (0.01s)\n")
        )
        next(r for r in events if r.get("Test") == "TestSyntheticActive" and r["Action"] == "pass")[
            "Action"
        ] = "fail"
        next(r for r in events if r["Package"] == P and r["Action"] == "pass" and "Test" not in r)[
            "Action"
        ] = "fail"
        execution["exitCode"] = 1

    check("complete assertion failure remains an observed default outcome", assertion, True)

    def bare_skip(events, collection, policy, execution):
        test = "TestAutoImportPackageRootPathTypeModule"
        for event in events:
            if event.get("Test") == DISABLED:
                event["Test"] = test
                if event["Action"] == "output":
                    event["Output"] = f"--- SKIP: {test} (0.00s)\n"
        collection["packages"][P][1] = test
        policy["exclusions"] = [e for e in policy["exclusions"] if e["test"] != DISABLED]
        policy["exclusions"].append(deepcopy(next(e for e in PROPOSED if e["test"] == test)))

    check("source-declared bare skip needs exact terminal diagnostic", bare_skip, True)
    check(
        "bare skip without terminal diagnostic",
        lambda e, c, p, x: (bare_skip(e, c, p, x), e[6].update(Output="")),
    )

    def replay(events, collection, policy, execution):
        package = oracle.PREFIX + "/internal/lsp"
        collection["packages"][package] = ["TestReplay"]
        policy["exclusions"].append(
            deepcopy(next(e for e in PROPOSED if e["test"] == "TestReplay"))
        )
        events.extend(
            [
                row(package, "start"),
                row(package, "run", "TestReplay"),
                row(
                    package, "output", "TestReplay", "replay_test.go:45: no replay file specified\n"
                ),
                row(package, "skip", "TestReplay"),
                row(package, "pass"),
            ]
        )

    check("source-default no-replay exclusion", replay, True)
    check(
        "native collection absent", lambda e, c, p, x: c.update(state="missing-native-collection")
    )
    check("empty native collection", lambda e, c, p, x: c.update(packages={}))

    def only_excluded(events, collection, policy, execution):
        collection["packages"] = {P: [DISABLED]}
        policy["exclusions"] = [e for e in policy["exclusions"] if e["test"] == DISABLED]
        events[:] = [
            row(P, "start"),
            row(P, "run", DISABLED),
            row(P, "output", DISABLED, "Known failing fourslash test\n"),
            row(P, "skip", DISABLED),
            row(P, "pass"),
        ]

    check("excluded-only stand-in supplies no active outcome", only_excluded)
    check("policy unaccepted", lambda e, c, p, x: p.update(state="proposal-unaccepted"))
    check("collection late freeze", lambda e, c, p, x: c.update(frozenAt=x["startedAt"]))
    check(
        "policy accepted after execution",
        lambda e, c, p, x: p.update(acceptedAt="2026-10-29T00:04:00+00:00"),
    )
    check("collection failure", lambda e, c, p, x: c.update(exitCode=1))
    check("collection bool-zero alias", lambda e, c, p, x: c.update(exitCode=False))
    check("duplicate collected identity", lambda e, c, p, x: c["packages"][P].append(DISABLED))
    check("changed source revision", lambda e, c, p, x: x["binding"].update(revision="0" * 40))
    check(
        "changed environment",
        lambda e, c, p, x: x.update(binding={**x["binding"], "environmentSha256": "9" * 64}),
    )
    check(
        "narrowed command",
        lambda e, c, p, x: x["binding"].update(command="go test ./internal/parser"),
    )
    for flag in ["setupComplete", "wrapperCompleted", "trackedSourceIntact", "eventsComplete"]:
        check("missing control " + flag, lambda e, c, p, x, f=flag: x.pop(f))
    for flag in ["truncated", "resourceFailure", "timedOut"]:
        check("failed control " + flag, lambda e, c, p, x, f=flag: x.update({f: True}))
    check("missing execution control not false", lambda e, c, p, x: x.pop("timedOut"))
    check("wrapper error", lambda e, c, p, x: x.update(error="synthetic transport failure"))
    check("wrapper bool-zero alias", lambda e, c, p, x: x.update(exitCode=False))
    check("all pass but nonzero wrapper", lambda e, c, p, x: x.update(exitCode=1))
    check("wrong package", lambda e, c, p, x: e[0].update(Package="other/module"))
    check("missing zero-test package terminal", lambda e, c, p, x: e.pop())
    check(
        "zero-test skip without native no-test diagnostic",
        lambda e, c, p, x: e[-2].update(Output=""),
    )
    check("no package start", lambda e, c, p, x: e.pop(0))
    check("missing top-level terminal", lambda e, c, p, x: e.pop(4))
    check("missing nested terminal", lambda e, c, p, x: e.pop(3))
    check("nested run without parent", lambda e, c, p, x: e.pop(1))
    check(
        "unexpected collected-test prefix collision",
        lambda e, c, p, x: e[1].update(Test="TestSyntheticActiveExtra"),
    )
    check("duplicate run", lambda e, c, p, x: e.insert(2, deepcopy(e[1])))
    check("terminal without run", lambda e, c, p, x: e.pop(5))
    check(
        "post-terminal event",
        lambda e, c, p, x: e.insert(5, row(P, "output", "TestSyntheticActive", "extra")),
    )
    check("unexpected top-level skip", lambda e, c, p, x: e[4].update(Action="skip"))
    check(
        "unexpected nested skip with passing parent", lambda e, c, p, x: e[3].update(Action="skip")
    )

    def deep_skip(events, collection, policy, execution):
        events[3:3] = [
            row(P, "run", "TestSyntheticActive/child/deep"),
            row(P, "skip", "TestSyntheticActive/child/deep"),
        ]

    check("unexpected deeper skip", deep_skip)
    check(
        "declared skip changed message", lambda e, c, p, x: e[6].update(Output="different reason")
    )
    check(
        "exact nested exclusion rejects prefix collision",
        lambda e, c, p, x: e[11].update(Test=TODO + "Extra"),
    )
    check(
        "unqualified capability not added to allowlist",
        lambda e, c, p, x: p["exclusions"].append(
            {**p["exclusions"][0], "test": "TestSyntheticActive/child"}
        ),
    )
    check(
        "posthoc exclusion reason mutation",
        lambda e, c, p, x: p["exclusions"][0].update(reason="new condition"),
    )
    check("unbound exclusion set", lambda e, c, p, x: p.update(exclusionSetSha256="0" * 64))
    check(
        "panic not assertion outcome",
        lambda e, c, p, x: (
            assertion(e, c, p, x),
            x.update(stderr="panic: synthetic runtime failure\n"),
        ),
    )
    check(
        "compile failure after partial test events",
        lambda e, c, p, x: x.update(stderr="FAIL other/package [build failed]\n", exitCode=1),
    )
    check(
        "resource diagnostic",
        lambda e, c, p, x: x.update(stderr="write: no space left on device\n"),
    )
    check("nonobject raw JSON", raw="[]\n")
    check("invalid test type", lambda e, c, p, x: e[1].update(Test=False))
    check("malformed raw JSON", raw="{\n")
    check("duplicate raw key", raw='{"Package":"x","Package":"y","Action":"start"}\n')
    check("unterminated events", raw=json.dumps(row(P, "start")))
    check(
        "listing-only stream",
        raw=json.dumps(row(P, "output", output="TestSyntheticActive\n")) + "\n",
    )
    data = fixture()
    result = score(data)
    data[3]["rawEventsSha256"] = "0" * 64
    result = score(data, rebind=False)
    assert not result["candidateOutcomeObserved"]
    results.append({"name": "changed raw event hash", "passed": True, "observed": result})
    data = fixture()
    score(data)
    data[3]["collectionSha256"] = "0" * 64
    result = score(data, rebind=False)
    assert not result["candidateOutcomeObserved"]
    results.append({"name": "changed collection digest", "passed": True, "observed": result})
    for filename in ["collection-required.json", "policy-proposal.json"]:
        data = fixture()
        data[1 if filename.startswith("collection") else 2].update(
            json.loads((HERE / filename).read_text())
        )
        result = score(data)
        assert not result["candidateOutcomeObserved"]
        results.append(
            {
                "name": "actual unready artifact rejected: " + filename,
                "passed": True,
                "observed": result,
            }
        )
    with args.output.open("x") as stream:
        json.dump(
            {
                "identity": "synthetic-only-go01-controls",
                "controls": results,
                "passed": len(results),
                "nativeCollectionOccurred": False,
                "newProcessNetworkDockerProviderCalls": 0,
            },
            stream,
            indent=2,
        )
        stream.write("\n")


if __name__ == "__main__":
    main()
