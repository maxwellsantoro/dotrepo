"""Synthetic controls only; deliberately prohibit every Docker command call."""

import copy
import json
from pathlib import Path
import tempfile

import driver
from oracle import controls as oracle_controls

HERE = Path(__file__).resolve().parent


def main():
    def forbidden(*args, **kwargs):
        raise AssertionError("synthetic controls attempted Docker")

    driver.command = driver.checked = forbidden
    plan = json.loads((HERE / "plan.json").read_text())
    plan_sha = driver.file_sha(HERE / "plan.json")
    receipts = {}
    acceptance = {
        "state": "accepted-for-three-scope-offline-requalification",
        "planSha256": plan_sha,
        "imageId": plan["imageId"],
        "cacheAudits": {},
    }
    for task in plan["tasks"]:
        receipt = {
            "state": "qualified-download-cache",
            **driver.audit_binding(plan, task),
            **{
                key: True
                for key in [
                    "downloadOnly",
                    "buildOutputsExcluded",
                    "taskSourceExcluded",
                    "credentialsExcluded",
                    "protectedEvaluationAliasesExcluded",
                ]
            },
        }
        raw = json.dumps(receipt).encode()
        receipts[task] = raw
        acceptance["cacheAudits"][task] = {
            "path": "synthetic-not-an-actual-audit.json",
            "sha256": driver.sha(raw),
        }
    driver.authorize(plan, acceptance, receipts, plan_sha)
    rejected = []

    def refuse(label, approval, audit):
        try:
            driver.authorize(plan, approval, audit, plan_sha)
        except (ValueError, KeyError):
            rejected.append(label)
        else:
            raise AssertionError("accepted " + label)

    changed = copy.deepcopy(acceptance)
    changed["planSha256"] = "0" * 64
    refuse("changed-plan", changed, receipts)
    changed = copy.deepcopy(acceptance)
    changed["imageId"] = "sha256:" + "0" * 64
    refuse("changed-image", changed, receipts)
    changed = copy.deepcopy(acceptance)
    del changed["cacheAudits"]["rust-02"]
    refuse("missing-cache-audit", changed, receipts)
    changed = copy.deepcopy(acceptance)
    changed["state"] = "pending-review"
    refuse("pending-coordinator", changed, receipts)
    for value, label in [(False, "false-audit-flag"), (1, "integer-audit-flag")]:
        altered = dict(receipts)
        receipt = json.loads(receipts["rust-02"])
        receipt["credentialsExcluded"] = value
        altered["rust-02"] = json.dumps(receipt).encode()
        changed = copy.deepcopy(acceptance)
        changed["cacheAudits"]["rust-02"]["sha256"] = driver.sha(altered["rust-02"])
        refuse(label, changed, altered)
    altered = dict(receipts)
    receipt = json.loads(receipts["rust-02"])
    receipt["cacheArchiveSha256"] = "0" * 64
    altered["rust-02"] = json.dumps(receipt).encode()
    changed = copy.deepcopy(acceptance)
    changed["cacheAudits"]["rust-02"]["sha256"] = driver.sha(altered["rust-02"])
    refuse("changed-cache-binding", changed, altered)
    altered = dict(receipts)
    altered["rust-02"] = receipts["rust-02"] + b" "
    refuse("changed-audit-bytes", acceptance, altered)

    flags = driver.container_flags("synthetic", plan, plan["environment"])
    assert "--network=none" in flags and "--read-only" in flags and "--cap-drop=ALL" in flags
    assert not any(
        arg.startswith(("--mount", "--volume", "--pid=host", "--privileged", "--network=host"))
        for arg in flags
    )
    assert "--memory=4g" in flags and "--pids-limit=256" in flags and "--cpus=3" in flags
    assert plan["environment"]["TMPDIR"] == "/workspace/tmp" and not any(
        "TOKEN" in name or "KEY" in name for name in plan["environment"]
    )
    with tempfile.TemporaryDirectory(
        prefix="dotrepo-f05-offline-requalification-controls-", dir="/tmp"
    ) as temporary:
        try:
            driver.run(
                plan,
                "rust-02",
                Path(temporary) / "missing-acceptance.json",
                Path(temporary) / "output",
            )
        except FileNotFoundError:
            rejected.append("run-without-acceptance-before-docker")
        else:
            raise AssertionError("run proceeded without coordinator acceptance")

    task = {
        "kind": "go",
        "packagePrefix": "example/api",
        "expectedPackages": ["example/api"],
        "expectedTopLevelTests": 1,
    }
    listing = json.dumps({"Package": "example/api", "Action": "output", "Output": "TestOne\n"})
    terminal_failure = "\n".join(
        json.dumps(row)
        for row in [
            {"Package": "example/api", "Action": "run", "Test": "TestOne"},
            {"Package": "example/api", "Action": "fail", "Test": "TestOne"},
            {"Package": "example/api", "Action": "fail"},
        ]
    )
    assert driver.score(task, terminal_failure, listing, {})["qualified"]
    skipped = (
        terminal_failure
        + "\n"
        + json.dumps({"Package": "example/api", "Action": "skip", "Test": "TestOne/child"})
    )
    assert not driver.score(task, skipped, listing, {})["qualified"]
    assert not driver.score(task, listing, listing, {})["qualified"]
    print(
        json.dumps(
            {
                "state": "passed",
                "authorizationNegativeControls": rejected,
                "isolationFlagsChecked": True,
                "terminalAssertionFailureCanBeOutcome": True,
                "nestedSkipRejected": True,
                "listingRejected": True,
                "nativeOracleControls": oracle_controls(),
                "dockerCalls": 0,
                "upstreamSourceBytesRead": False,
                "actualTaskOutcomes": None,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
