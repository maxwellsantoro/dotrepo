"""Mutate owned captured inspect artifacts coherently; no runtime invocation."""

import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
AUTHOR = ROOT / "benchmarks/head-to-head/f05-go01-oracle-preparation-20261029/amendment-3"


def main():
    assert hashlib.sha256((AUTHOR / "FREEZE.json").read_bytes()).hexdigest() == (
        "d7cd2ced83cc27cde9070e457d9fcad2185316b14ac698e83d98f189293f5cbc"
    )
    sys.path.insert(0, str(AUTHOR))
    controls = importlib.import_module("controls")
    adapter = controls.adapter
    reports = []
    for name, additions in [
        ("extra-capability", {"CapAdd": ["SYS_ADMIN"], "Privileged": False}),
        ("privileged", {"CapAdd": None, "Privileged": True}),
    ]:
        with tempfile.TemporaryDirectory(prefix="dotrepo-adapter-review-", dir="/tmp") as directory:
            case = controls.fixture(Path(directory))

            def mutate(descriptor):
                folder = case["root"] / Path(case["relative"]).parent
                for label in ["inspect-before", "inspect-after"]:
                    path = folder / label / "stdout.bin"
                    old = path.read_bytes()
                    rows = adapter.load(old)
                    rows[0]["HostConfig"].update(additions)
                    raw = json.dumps(rows).encode()
                    path.write_bytes(raw)
                    descriptor[label] = rows[0]
                    row = next(r for r in descriptor["operations"] if r["label"] == label)
                    row["stdoutBytes"] = len(raw)
                    row["stdoutSha256"] = adapter.sha(raw)
                    row["observedTransportBytes"] += len(raw) - len(old)
                    descriptor["transportBytes"] += len(raw) - len(old)

            controls.mutate_descriptor(case, mutate)
            result = controls.score(case)
            reports.append(
                {
                    "case": name,
                    "inspectHostConfigMutation": additions,
                    "result": result,
                    "expectedAssociationAccepted": False,
                    "actualAssociationAccepted": result["captureAssociationValidated"],
                }
            )
    with (HERE / "isolation-challenge.json").open("x") as stream:
        json.dump(
            {
                "state": "independent-synthetic-isolation-counterexamples",
                "cases": reports,
                "newDockerGoNodeNativeNetworkProviderActions": 0,
            },
            stream,
            indent=2,
            sort_keys=True,
        )
        stream.write("\n")
    print(
        json.dumps(
            [
                {
                    k: row[k]
                    for k in ["case", "actualAssociationAccepted", "expectedAssociationAccepted"]
                }
                for row in reports
            ]
        )
    )


if __name__ == "__main__":
    main()
