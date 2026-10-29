"""GOENV input/query regressions; only fake transports and retained source bytes."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile

import collection
import controls  # Denies real process/socket access before driver use.
import listing

HERE = Path(__file__).resolve().parent


def refused(operation):
    try:
        operation()
    except (ValueError, KeyError, TypeError):
        return True
    raise AssertionError("incorrect Go context accepted")


def main():
    plan = collection.load_plan()
    before = json.loads((HERE.parent / "amendment-1/plan.json").read_bytes())
    raw = (HERE / "actual-go-env-stdout.bin").read_bytes()
    receipt = json.loads((HERE / "actual-go-env-receipt.json").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == receipt["stdoutSha256"]
    assert receipt["exitCode"] == 0 and receipt["error"] is None
    actual = json.loads(raw)
    assert plan["environment"] == before["environment"]
    assert plan["environmentSha256"] == before["environmentSha256"]
    assert plan["environment"]["GOENV"] == "off" and actual["GOENV"] == ""
    for key in ["limits", "commands", "cwd", "sourceArchiveSha256", "imageId", "projection"]:
        assert plan[key] == before[key], key
    expected = deepcopy(before["expectedGoEnv"])
    assert expected.pop("GOENV") == "off"
    actual_other = deepcopy(actual)
    assert actual_other.pop("GOENV") == ""
    assert actual_other == expected
    listing.environment(raw, plan["expectedGoEnv"])
    checks = [
        {
            "case": "genuine retained native query bytes accepted with unchanged inputoff",
            "passed": True,
        }
    ]
    checks.append(
        {
            "case": "old expected literaloff rejects genuine query",
            "passed": refused(lambda: listing.environment(raw, before["expectedGoEnv"])),
        }
    )
    for key in actual:
        changed = deepcopy(actual)
        changed[key] = "off" if key == "GOENV" else "incorrect"
        checks.append(
            {
                "case": "reject changed query field " + key,
                "passed": refused(
                    lambda: listing.environment(json.dumps(changed).encode(), plan["expectedGoEnv"])
                ),
            }
        )
    for label, changed in [
        ("missing GOENV", {k: v for k, v in actual.items() if k != "GOENV"}),
        ("null GOENV", {**actual, "GOENV": None}),
        ("extra output field", {**actual, "UNKNOWN": "x"}),
    ]:
        checks.append(
            {
                "case": "reject " + label,
                "passed": refused(
                    lambda: listing.environment(json.dumps(changed).encode(), plan["expectedGoEnv"])
                ),
            }
        )
    for label, changed in [
        ("duplicate GOENV", raw.rstrip()[:-1] + b', "GOENV": ""}'),
        ("multiple objects", raw + raw),
        ("invalid JSON", b"{"),
    ]:
        checks.append(
            {
                "case": "reject " + label,
                "passed": refused(lambda: listing.environment(changed, plan["expectedGoEnv"])),
            }
        )
    state = controls.metadata(plan)
    environment = dict(row.split("=", 1) for row in state["Config"]["Env"])
    collection.inspect(state, environment)
    for label, mutate in [
        ("empty input", lambda values: values.update(GOENV="")),
        ("missing input", lambda values: values.pop("GOENV")),
        ("user config input", lambda values: values.update(GOENV="/workspace/home/go.env")),
    ]:
        changed = deepcopy(state)
        values = dict(row.split("=", 1) for row in changed["Config"]["Env"])
        mutate(values)
        changed["Config"]["Env"] = [f"{key}={value}" for key, value in values.items()]
        checks.append(
            {
                "case": "reject container " + label,
                "passed": refused(lambda: collection.inspect(changed, environment)),
            }
        )

    class RecordedQueryFake(controls.Fake):
        def command(self, output, label, argv, **kwargs):
            row = super().command(output, label, argv, **kwargs)
            if label == "go-env":
                row["stdout"] = raw.decode()
                row["stdoutSha256"] = hashlib.sha256(raw).hexdigest()
                folder = output / "logs" / label
                (folder / "stdout.bin").write_bytes(raw)
                (folder / "receipt.json").write_text(
                    json.dumps({k: v for k, v in row.items() if k not in {"stdout", "stderr"}})
                    + "\n"
                )
            return row

    with tempfile.TemporaryDirectory(prefix="dotrepo-goenv-amendment2-fake-") as temporary:
        temp = Path(temporary)
        auth = temp / "auth.json"
        auth.write_text("{}")
        clock = [0]
        fake = RecordedQueryFake(plan, clock=clock)

        def inputs(*args):
            source, cache = temp / "source.bytes", temp / "cache.bytes"
            source.write_bytes(b"owned")
            cache.write_bytes(b"cache")
            return (
                source,
                cache,
                controls.FILES,
                {"go/pkg/mod/owned": controls.FILES["README"]},
                collection.tree_expected(controls.FILES),
            )

        result = collection.run(
            auth,
            temp / "output",
            temp / "scratch",
            backend=fake,
            plan_loader=lambda: deepcopy(plan),
            authorization_check=lambda *args: {"syntheticOwnedAssertion": True},
            input_check=inputs,
            clock=lambda: clock[0],
        )
        assert (
            result["synthetic"] is True
            and result["state"] == "native-top-level-collection-observed"
        )
        assert all(
            result[key] is False
            for key in [
                "taskOutcomeObserved",
                "nativeTaskAdmitted",
                "campaignAdmitted",
                "cacheGloballyQualified",
            ]
        )
        assert result["containerAbsent"] is True
        labels = [row[0] for row in fake.calls]
        assert "go-list" in labels and "go-test-list" in labels and "cleanup" in labels
        checks.append(
            {
                "case": "full fake driver crosses go-env gate using exact historical query bytes",
                "passed": True,
                "commandLabels": labels,
                "result": result,
            }
        )
    collection.write(
        HERE / "goenv-controls.json",
        {
            "passed": len(checks),
            "controls": checks,
            "realDaemonGoNetworkPackageProviderCalls": 0,
            "actualNativeCollectionOccurred": False,
            "historicalRawQueryFixtureOnly": True,
        },
    )
    print(json.dumps({"passed": len(checks), "realDaemonGoNetworkPackageProviderCalls": 0}))


if __name__ == "__main__":
    main()
