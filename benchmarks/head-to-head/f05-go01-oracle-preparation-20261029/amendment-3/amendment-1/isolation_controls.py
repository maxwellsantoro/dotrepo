"""Coherently mutate only owned mocked inspect evidence; never invoke Docker."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import tempfile

import controls

adapter = controls.adapter
ORIGINAL = adapter.module(
    "go01_original_am3_adapter",
    adapter.HERE.parent / "adapter.py",
    "175a15d7406909778fb0d965c4f3cf690998106f1b672ae71feaf7831a6b10ae",
)


def mutate_inspects(case, change):
    def apply(descriptor):
        folder = case["root"] / Path(case["relative"]).parent
        for label in ("inspect-before", "inspect-after"):
            path = folder / label / "stdout.bin"
            previous = path.read_bytes()
            rows = adapter.load(previous)
            change(rows[0])
            raw = json.dumps(rows).encode()
            path.write_bytes(raw)
            descriptor[label] = rows[0]
            operation = next(row for row in descriptor["operations"] if row["label"] == label)
            operation["stdoutBytes"] = len(raw)
            operation["stdoutSha256"] = adapter.sha(raw)
            operation["observedTransportBytes"] += len(raw) - len(previous)
            descriptor["transportBytes"] += len(raw) - len(previous)

    controls.mutate_descriptor(case, apply)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = []

    def check(name, change, *, accepted=False, before=False):
        with tempfile.TemporaryDirectory(prefix="dotrepo-go01-isolation-amendment-") as directory:
            case = controls.fixture(Path(directory))
            mutate_inspects(case, change)
            result = controls.score(case)
            assert result["captureAssociationValidated"] is accepted, (name, result)
            assert result["candidateOutcomeObserved"] is accepted, (name, result)
            assert not any(
                result[key]
                for key in (
                    "taskOutcomeObserved",
                    "oracleQualified",
                    "campaignAdmitted",
                    "nativeCollectionOccurred",
                )
            ), result
            row = {"name": name, "expectedAssociation": accepted, "after": result}
            if before:
                old = ORIGINAL.evaluate(
                    case["root"],
                    case["relative"],
                    case["request"],
                    case["config"],
                    case["trace"],
                    *case["data"][1:],
                    synthetic=True,
                )
                assert old["captureAssociationValidated"] and old["candidateOutcomeObserved"], old
                row["before"] = old
            results.append(row)

    check(
        "exact-independent-extra-capability",
        lambda row: row["HostConfig"].update(CapAdd=["SYS_ADMIN"], Privileged=False),
        before=True,
    )
    check(
        "exact-independent-privileged",
        lambda row: row["HostConfig"].update(CapAdd=None, Privileged=True),
        before=True,
    )
    for key in ("CapAdd", "Devices", "DeviceRequests", "DeviceCgroupRules", "Binds", "VolumesFrom"):
        for value in (None, []):
            check(
                key + "-legitimate-" + ("null" if value is None else "empty"),
                lambda row, key=key, value=value: row["HostConfig"].update({key: value}),
                accepted=True,
            )
    for name, key, value in [
        ("privileged-null", "Privileged", None),
        ("privileged-zero", "Privileged", 0),
        ("capadd-false", "CapAdd", False),
        ("capadd-object", "CapAdd", {}),
        (
            "device",
            "Devices",
            [{"PathOnHost": "/dev/kvm", "PathInContainer": "/dev/kvm", "CgroupPermissions": "rwm"}],
        ),
        (
            "device-request",
            "DeviceRequests",
            [{"Driver": "nvidia", "Count": -1, "Capabilities": [["gpu"]]}],
        ),
        ("device-cgroup-grant", "DeviceCgroupRules", ["c 1:3 rwm"]),
        ("host-bind", "Binds", ["/var/run/docker.sock:/docker.sock"]),
        ("volume-source", "VolumesFrom", ["other:rw"]),
        ("wrong-nofile", "Ulimits", [{"Name": "nofile", "Soft": 2048, "Hard": 2048}]),
        ("log-driver", "LogConfig", {"Type": "json-file", "Config": {}}),
        ("log-options", "LogConfig", {"Type": "none", "Config": {"max-size": "1m"}}),
    ]:
        check(name, lambda row, key=key, value=value: row["HostConfig"].update({key: value}))
    for key in (
        "Privileged",
        "CapAdd",
        "Devices",
        "DeviceRequests",
        "DeviceCgroupRules",
        "Binds",
        "VolumesFrom",
        "Ulimits",
        "LogConfig",
    ):
        check("missing-" + key, lambda row, key=key: row["HostConfig"].pop(key))
    check(
        "legitimate-null-log-options",
        lambda row: row["HostConfig"].update(LogConfig={"Type": "none", "Config": None}),
        accepted=True,
    )
    check(
        "legitimate-zero-health-options",
        lambda row: row["Config"].update(
            Healthcheck={
                "Test": ["NONE"],
                "Interval": 0,
                "Timeout": 0,
                "Retries": 0,
                "StartPeriod": 0,
                "StartInterval": 0,
            }
        ),
        accepted=True,
    )
    check(
        "healthcheck-enabled",
        lambda row: row["Config"].update(Healthcheck={"Test": ["CMD", "curl", "example"]}),
    )
    check("healthcheck-missing", lambda row: row["Config"].pop("Healthcheck"))
    check(
        "healthcheck-boolean-zero",
        lambda row: row["Config"].update(Healthcheck={"Test": ["NONE"], "Interval": False}),
    )
    check(
        "healthcheck-positive-interval",
        lambda row: row["Config"].update(Healthcheck={"Test": ["NONE"], "Interval": 1}),
    )
    with tempfile.TemporaryDirectory(prefix="dotrepo-go01-nonroot-control-") as directory:
        case = controls.fixture(Path(directory))
        descriptor = adapter.load((case["root"] / case["relative"]).read_bytes())
        config = adapter.load(case["config"])
        for user in ("0:0", "0:1000", "1000:0", "root", "1000"):
            bad = deepcopy(config)
            bad["containerUser"] = user
            try:
                adapter.isolation_options(descriptor["inspect-before"], bad)
            except ValueError:
                results.append({"name": "nonroot-config-" + user, "refused": True})
            else:
                raise AssertionError("nonroot policy not checked")
    report = {
        "state": "coherent-owned-isolation-controls-passed",
        "count": len(results),
        "cases": results,
        "beforeSubjectSha256": "175a15d7406909778fb0d965c4f3cf690998106f1b672ae71feaf7831a6b10ae",
        "newDaemonNativeNetworkProviderActions": 0,
        "actualAdmission": False,
    }
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {"allPassed": True, "count": len(results), "independentBeforeAcceptAfterReject": 2}
        )
    )


if __name__ == "__main__":
    main()
