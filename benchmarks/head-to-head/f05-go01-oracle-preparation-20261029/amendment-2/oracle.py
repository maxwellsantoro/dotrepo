"""Task-specific post-run Go JSON checks. This module never launches a process.

Source expectations replace only the former native-listing origin predicate.
Actual evaluation is blocked while the reviewed full-task capture join is absent.
Synthetic results cannot report an actual task outcome. Never use this scorer to gate an agent's shell decisions.
"""

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

import derive

HERE = Path(__file__).resolve().parent
EXPECTATION_SHA = "65d861a2c8d082fceb00fc77f1befce47b463aa272b69a71248a1f9973f3700b"


def load_expectation():
    derive.bound_sources()
    raw = (HERE / "expectation.json").read_bytes()
    require(hashlib.sha256(raw).hexdigest() == EXPECTATION_SHA, "changed expectation subject")
    expected = json.loads(raw, object_pairs_hook=unique_object)
    raw_map = (HERE / "expected-map.json").read_bytes()
    require(
        hashlib.sha256(raw_map).hexdigest() == derive.MAP_SHA and len(raw_map) == 242536,
        "changed frozen source map",
    )
    names = json.loads(raw_map, object_pairs_hook=unique_object)
    require(derive.canonical(names) == raw_map, "noncanonical source map")
    return expected, names


REVISION = "25f823dc198a00744b458a7bc6984359f0dd7cac"
SOURCE = "c583f28324d455b559bb232e7a280581fe874850f805decfb5947febfa91ee0f"
COMMAND = (
    'GOTESTSUM_JSONFILE=/workspace/go-test-events.jsonl GOFLAGS="-p=1 -count=1" npx hereby test'
)
PREFIX = "github.com/microsoft/TypeScript/tsc"
BINDING_KEYS = {
    "revision",
    "sourceArchiveSha256",
    "imageId",
    "environmentSha256",
    "command",
    "scope",
}
HEX = re.compile(r"[0-9a-f]{64}")
EXCLUSION_SET_SHA256 = "810908e7a942ee3b049ac57873051057cf8ab3817dc6160f7a90430c5ff321b4"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def ancestors(test):
    """Existing slash-delimited identity contract; no unobserved children inferred."""
    parts = test.split("/")
    return ["/".join(parts[:end]) for end in range(1, len(parts))]


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def timestamp(value):
    require(isinstance(value, str), "missing timestamp")
    result = datetime.fromisoformat(value)
    require(result.tzinfo is not None, "timestamp lacks timezone")
    return result


def binding(value):
    require(isinstance(value, dict) and set(value) == BINDING_KEYS, "incomplete binding")
    require(all(isinstance(v, str) for v in value.values()), "binding types")
    require(
        value["revision"] == REVISION and value["sourceArchiveSha256"] == SOURCE, "wrong source"
    )
    require(
        value["command"] == COMMAND and value["scope"] == "repository-default",
        "wrong command/scope",
    )
    require(
        value["imageId"].startswith("sha256:") and HEX.fullmatch(value["imageId"][7:]),
        "image digest",
    )
    require(HEX.fullmatch(value["environmentSha256"]), "environment digest")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def parse_events(raw):
    require(isinstance(raw, str) and raw.strip(), "missing raw events")
    require(raw.endswith("\n"), "unterminated raw event stream")
    rows = []
    for line in raw.splitlines():
        require(bool(line), "blank event line")
        row = json.loads(line, object_pairs_hook=unique_object)
        require(isinstance(row, dict), "nonobject event")
        require(
            isinstance(row.get("Action"), str) and isinstance(row.get("Package"), str),
            "event types",
        )
        if "Test" in row:
            require(isinstance(row["Test"], str) and row["Test"], "test identity type")
        if "Output" in row:
            require(isinstance(row["Output"], str), "output type")
        rows.append(row)
    return rows


def evaluate(raw, collection, policy, execution, *, synthetic=False):
    """Return a bounded disposition; any missing control remains unresolved."""
    result = {
        "taskId": "go-01",
        "synthetic": synthetic,
        "taskOutcomeObserved": False,
        "candidateOutcomeObserved": False,
        "testsPassed": None,
        "reason": "unresolved",
        "oracleQualified": False,
        "campaignAdmitted": False,
        "nativeCollectionOccurred": False,
        "captureJoinState": "open-reviewed-full-task-capture-join-required",
    }
    try:
        require(isinstance(raw, str), "raw events must be text")
        require(type(synthetic) is bool, "synthetic type")
        require(synthetic is True, "reviewed-full-task-capture-join-unavailable")
        metadata, frozen_packages = load_expectation()
        for value in [collection, policy, execution]:
            require(isinstance(value, dict), "nonobject input")
            binding(value.get("binding"))
            require(value.get("synthetic") is synthetic, "synthetic/retained evidence mismatch")
        require(
            canonical(collection["binding"])
            == canonical(policy["binding"])
            == canonical(execution["binding"]),
            "changed binding",
        )
        require(policy.get("state") == "accepted-before-execution", "exclusion policy unaccepted")
        proposed = json.loads((Path(__file__).parent.parent / "policy-proposal.json").read_text())[
            "exclusions"
        ]
        require(digest(proposed) == EXCLUSION_SET_SHA256, "changed source exclusion proposal")
        require(policy.get("exclusionSetSha256") == EXCLUSION_SET_SHA256, "unbound exclusion set")
        proposed_by_id = {(entry["package"], entry["test"]): entry for entry in proposed}
        require(
            isinstance(policy.get("acceptanceSha256"), str)
            and HEX.fullmatch(policy["acceptanceSha256"]),
            "missing policy acceptance binding",
        )
        require(
            collection.get("state") == "source-expectation-frozen-before-execution",
            "source expectation missing",
        )
        require(
            collection.get("nativeCollection") is False, "source expectation mislabelled native"
        )
        require(
            collection.get("sourceSubject") == metadata["sourceSubject"]
            and collection.get("expectedMapSha256") == derive.MAP_SHA,
            "source expectation subject mismatch",
        )
        require(
            collection.get("packages") == frozen_packages, "source identity/package set mismatch"
        )
        require(
            collection["binding"]["imageId"]
            == metadata["sourceSubject"]["sourceContext"]["imageId"],
            "selection image mismatch",
        )
        require(
            timestamp(collection["frozenAt"]) < timestamp(execution["startedAt"]),
            "expectation not frozen before execution",
        )
        require(
            execution.get("effectiveSelectionContext")
            == metadata["sourceSubject"]["sourceContext"],
            "selection context mismatch",
        )
        # This fixture tests the required join shape; it is never runtime authentication.
        capture = execution.get("syntheticCapture")
        require(
            isinstance(capture, dict)
            and set(capture)
            == {
                "state",
                "synthetic",
                "command",
                "rawEventsSha256",
                "sourceSubjectSha256",
                "setupRole",
                "eventOrigin",
            },
            "missing synthetic capture fixture",
        )
        require(
            capture
            == {
                "state": "synthetic-full-task-capture-fixture",
                "synthetic": True,
                "command": COMMAND,
                "rawEventsSha256": hashlib.sha256(raw.encode()).hexdigest(),
                "sourceSubjectSha256": digest(metadata["sourceSubject"]),
                "setupRole": "full-normal-setup",
                "eventOrigin": "owned-synthetic-fixture-not-arbitrary-agent-file",
            },
            "unbound/forged synthetic capture fixture",
        )
        require(
            timestamp(policy["acceptedAt"]) < timestamp(execution["startedAt"]),
            "policy not accepted before execution",
        )
        require(
            execution.get("expectationSha256") == digest(collection)
            and execution.get("policySha256") == digest(policy),
            "unbound source expectation/policy",
        )
        for name in ["setupComplete", "wrapperCompleted", "trackedSourceIntact", "eventsComplete"]:
            require(execution.get(name) is True, "incomplete execution control: " + name)
        for name in ["truncated", "resourceFailure", "timedOut"]:
            require(execution.get(name) is False, "failed/unknown execution control: " + name)
        require(
            execution.get("error") is None
            and type(execution.get("exitCode")) is int
            and execution["exitCode"] in (0, 1),
            "wrapper process failure",
        )
        require(
            execution.get("rawEventsSha256") == hashlib.sha256(raw.encode()).hexdigest(),
            "raw event hash mismatch",
        )
        packages = collection.get("packages")
        require(isinstance(packages, dict) and packages, "missing intended packages")
        expected = set()
        for package, tests in packages.items():
            require(
                isinstance(package, str)
                and (package == PREFIX or package.startswith(PREFIX + "/")),
                "source expectation wrong package",
            )
            require(
                isinstance(tests, list)
                and all(
                    isinstance(t, str) and re.fullmatch(r"(?:Test|Example|Fuzz)[^/\s]*", t)
                    for t in tests
                ),
                "source expectation test identities",
            )
            require(len(tests) == len(set(tests)), "duplicate collected identity")
            expected.update((package, test) for test in tests)
        require(bool(expected), "empty source expected test set")
        exclusions = {}
        require(isinstance(policy.get("exclusions"), list), "missing exclusion list")
        for entry in policy["exclusions"]:
            require(isinstance(entry, dict), "exclusion type")
            key = entry.get("package"), entry.get("test")
            require(
                all(isinstance(v, str) and v for v in key) and key not in exclusions,
                "exclusion identity",
            )
            require(
                key in proposed_by_id and canonical(entry) == canonical(proposed_by_id[key]),
                "exclusion outside source proposal",
            )
            require(
                (key[0], key[1].split("/")[0]) in expected,
                "exclusion absent from source expectation",
            )
            require(entry.get("conditionSatisfied") is True, "unresolved exclusion condition")
            require(
                isinstance(entry.get("sourceSha256"), str) and HEX.fullmatch(entry["sourceSha256"]),
                "exclusion source binding",
            )
            require(isinstance(entry.get("reason"), str) and entry["reason"], "exclusion reason")
            require(
                isinstance(entry.get("sourcePath"), str)
                and type(entry.get("line")) is int
                and entry["line"] > 0,
                "exclusion source span",
            )
            exclusions[key] = entry
        require(
            bool(expected - {key for key in exclusions if "/" not in key[1]}),
            "no active intended tests",
        )
        started, ended, ran, terminal = set(), {}, set(), {}
        outputs, package_outputs = {}, {}
        unfinished_descendants, failed_descendants = {}, {}
        for row in parse_events(raw):
            package, test, action = row["Package"], row.get("Test"), row["Action"]
            require(package in packages, "wrong or uncollected package")
            require(package not in ended, "event after package terminal")
            if not test:
                if action == "start":
                    require(package not in started, "duplicate package start")
                    started.add(package)
                else:
                    require(package in started, "package event without start")
                    if action == "output":
                        package_outputs[package] = package_outputs.get(package, "") + row.get(
                            "Output", ""
                        )
                    elif action in ("pass", "fail", "skip"):
                        ended[package] = action
                    else:
                        raise ValueError("unexpected package action")
                continue
            key, top = (package, test), (package, test.split("/")[0])
            require(package in started and top in expected, "test outside collected scope")
            require(key not in terminal, "event after test terminal")
            if action == "run":
                require(key not in ran, "duplicate test run")
                if "/" in test:
                    require((package, test.rsplit("/", 1)[0]) in ran, "nested run without parent")
                    require(
                        all((package, parent) not in terminal for parent in ancestors(test)),
                        "nested run after ancestor terminal",
                    )
                    for parent in ancestors(test):
                        parent_key = package, parent
                        unfinished_descendants[parent_key] = (
                            unfinished_descendants.get(parent_key, 0) + 1
                        )
                ran.add(key)
            else:
                require(key in ran, "test event without run")
                if action == "output":
                    outputs[key] = outputs.get(key, "") + row.get("Output", "")
                elif action in ("pass", "fail", "skip"):
                    require(
                        unfinished_descendants.get(key, 0) == 0,
                        "parent terminal while descendant unfinished",
                    )
                    require(
                        action == "fail" or failed_descendants.get(key, 0) == 0,
                        "failed descendant requires failed parent",
                    )
                    terminal[key] = action
                    for parent in ancestors(test):
                        parent_key = package, parent
                        require(
                            unfinished_descendants.get(parent_key, 0) > 0,
                            "invalid descendant lifecycle count",
                        )
                        unfinished_descendants[parent_key] -= 1
                        if action == "fail":
                            failed_descendants[parent_key] = (
                                failed_descendants.get(parent_key, 0) + 1
                            )
                else:
                    require(action in ("pause", "cont"), "unexpected test action")
        require(started == set(packages) == set(ended), "missing package coverage")
        require(ran == set(terminal) and expected <= ran, "missing run/terminal coverage")
        skipped = {key for key, state in terminal.items() if state == "skip"}
        require(skipped <= exclusions.keys(), "unexpected skip at any nesting depth")
        for key in skipped:
            message = exclusions[key].get("outputReason")
            if message is not None:
                require(
                    isinstance(message, str) and message and message in outputs.get(key, ""),
                    "skip reason not witnessed",
                )
            else:
                require(
                    re.search(
                        r"(?m)^\s*--- SKIP: " + re.escape(key[1]) + r" \(", outputs.get(key, "")
                    ),
                    "bare skip lacks terminal diagnostic",
                )
        for package, state in ended.items():
            if packages[package]:
                require(state in ("pass", "fail"), "test package skipped")
                failed_here = any(p == package and s == "fail" for (p, _), s in terminal.items())
                require((state == "fail") is failed_here, "package/test failure mismatch")
            else:
                require(
                    state == "pass"
                    or (
                        state == "skip"
                        and package in metadata["noSelectedTestSourcePackages"]
                        and "[no test files]" in package_outputs.get(package, "")
                    ),
                    "zero-test package incomplete",
                )
        failed = {key for key, state in terminal.items() if state == "fail"}
        for key in failed:
            require(
                all(terminal.get((key[0], parent)) == "fail" for parent in ancestors(key[1])),
                "failed descendant requires failed ancestors",
            )
            require(
                re.search(r"(?m)^\s*--- FAIL: " + re.escape(key[1]) + r" \(", outputs.get(key, "")),
                "failure lacks terminal assertion diagnostic",
            )
        all_output = (
            "".join(outputs.values())
            + "".join(package_outputs.values())
            + execution.get("stderr", "")
        )
        require(
            not re.search(
                r"(?m)^(?:panic:|fatal error:)|\[build failed\]|no space left on device|signal: killed",
                all_output,
            ),
            "setup/runtime/resource diagnostic",
        )
        require((execution["exitCode"] == 1) is bool(failed), "wrapper/test result mismatch")
        result.update(
            candidateOutcomeObserved=True,
            taskOutcomeObserved=False,
            oracleQualified=False,
            campaignAdmitted=False,
            nativeCollectionOccurred=False,
            testsPassed=not failed,
            reason="complete active default-suite outcome with declared exclusions",
            expectedTopLevelTests=len(expected),
            observedNestedTests=sum("/" in test for _, test in ran),
            packages=len(packages),
            excludedBehavior=[
                {"package": p, "test": t, "reason": exclusions[p, t]["reason"], "exercised": False}
                for p, t in sorted(skipped)
            ],
            failedTests=[{"package": p, "test": t} for p, t in sorted(failed)],
        )
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        result["reason"] = str(error)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["events", "expectation", "policy", "execution", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--synthetic", action="store_true")
    args = parser.parse_args()
    result = evaluate(
        args.events.read_text(),
        *(
            json.loads(getattr(args, name).read_text(), object_pairs_hook=unique_object)
            for name in ["expectation", "policy", "execution"]
        ),
        synthetic=args.synthetic,
    )
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
