"""Independent coherent mocked inspect controls; no daemon or task execution."""

import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
AUTHOR = (
    ROOT / "benchmarks/head-to-head/f05-go01-oracle-preparation-20261029/amendment-3/amendment-1"
)
AUTHOR_SHA = "bad0a161c9d84d923e0431dfac39d20dcd03a0d5fe916ce19e56c96e89c8768f"


def main():
    assert hashlib.sha256((AUTHOR / "FREEZE.json").read_bytes()).hexdigest() == AUTHOR_SHA
    sys.path.insert(0, str(AUTHOR))
    controls = importlib.import_module("controls")
    adapter = controls.adapter
    rows = []
    changes = [
        ("default-safe-shape", {}, (), True),
        ("capadd-empty", {"CapAdd": []}, (), True),
        (
            "all-absent-grants-null",
            dict.fromkeys(
                ["CapAdd", "Devices", "DeviceRequests", "DeviceCgroupRules", "Binds", "VolumesFrom"]
            ),
            (),
            True,
        ),
        (
            "all-absent-grants-empty",
            {
                key: []
                for key in (
                    "CapAdd",
                    "Devices",
                    "DeviceRequests",
                    "DeviceCgroupRules",
                    "Binds",
                    "VolumesFrom",
                )
            },
            (),
            True,
        ),
        ("original-extra-capability", {"CapAdd": ["SYS_ADMIN"], "Privileged": False}, (), False),
        ("original-privileged", {"CapAdd": None, "Privileged": True}, (), False),
        ("privileged-missing", {}, ("Privileged",), False),
        ("privileged-integer-zero", {"Privileged": 0}, (), False),
        ("privileged-integer-one", {"Privileged": 1}, (), False),
        ("privileged-null", {"Privileged": None}, (), False),
        ("privileged-string-false", {"Privileged": "false"}, (), False),
        ("capadd-missing", {}, ("CapAdd",), False),
        ("capadd-boolean", {"CapAdd": False}, (), False),
        ("capadd-zero", {"CapAdd": 0}, (), False),
        ("capadd-object", {"CapAdd": {}}, (), False),
        ("capadd-empty-string", {"CapAdd": ""}, (), False),
        ("capadd-nested-empty", {"CapAdd": [[]]}, (), False),
        ("device-sys-admin-grant", {"DeviceCgroupRules": ["a *:* rwm"]}, (), False),
        ("host-bind", {"Binds": ["/tmp:/workspace"]}, (), False),
        ("volume-source", {"VolumesFrom": ["another:ro"]}, (), False),
    ]
    for name, updates, removed, expected in changes:
        with tempfile.TemporaryDirectory(
            prefix="dotrepo-adapter-after-review-", dir="/tmp"
        ) as directory:
            case = controls.fixture(Path(directory))

            def mutate(descriptor):
                folder = case["root"] / Path(case["relative"]).parent
                for label in ("inspect-before", "inspect-after"):
                    path = folder / label / "stdout.bin"
                    previous = path.read_bytes()
                    observations = adapter.load(previous)
                    host = observations[0]["HostConfig"]
                    host.update(updates)
                    for key in removed:
                        host.pop(key)
                    raw = json.dumps(observations).encode()
                    path.write_bytes(raw)
                    descriptor[label] = observations[0]
                    operation = next(
                        row for row in descriptor["operations"] if row["label"] == label
                    )
                    operation["stdoutBytes"] = len(raw)
                    operation["stdoutSha256"] = adapter.sha(raw)
                    operation["observedTransportBytes"] += len(raw) - len(previous)
                    descriptor["transportBytes"] += len(raw) - len(previous)

            controls.mutate_descriptor(case, mutate)
            scored = controls.score(case)
            assert scored["captureAssociationValidated"] is expected, (name, scored)
            assert scored["candidateOutcomeObserved"] is expected, (name, scored)
            actual = controls.score(case, synthetic=False)
            assert not actual["candidateOutcomeObserved"] and not actual["taskOutcomeObserved"]
            assert not actual["oracleQualified"] and not actual["campaignAdmitted"]
            if expected:
                assert actual["captureAssociationValidated"]
                assert actual["reason"] == (
                    "actual-full-task-setup-tool-effective-context-join-unavailable"
                ), actual
                assert len(actual["remainingJoins"]) == 3
            rows.append(
                {
                    "case": name,
                    "expectedAssociation": expected,
                    "syntheticResult": scored,
                    "actualResult": actual,
                }
            )
    output = {
        "state": "independent-coherent-isolation-after-controls-passed",
        "subjectFreezeSha256": AUTHOR_SHA,
        "count": len(rows),
        "cases": rows,
        "newDaemonNativeGoNodeNetworkProviderActions": 0,
        "executionAuthorized": False,
        "oracleQualified": False,
        "campaignAdmitted": False,
    }
    with (HERE / "challenge.json").open("x") as stream:
        json.dump(output, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"count": len(rows), "allPassed": True}))


if __name__ == "__main__":
    main()
