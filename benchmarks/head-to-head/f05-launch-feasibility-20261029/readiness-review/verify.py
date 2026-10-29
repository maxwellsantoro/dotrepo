"""Read-only finite readiness inventory audit; no workload or acquisition."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUTHOR = Path("/tmp/dotrepo-f05-launch-readiness-inventory-20261029")


def read(p):
    return json.loads(p.read_bytes())


def sha(p):
    with p.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def main():
    assert (
        sha(AUTHOR / "FREEZE.json")
        == "378233aabf128c2acd919a589d604c2b972d918518f8d7f7188000cf61f8cb87"
    )
    freeze = read(AUTHOR / "FREEZE.json")
    for name, row in freeze["artifacts"].items():
        p = AUTHOR / name
        assert p.is_file() and not p.is_symlink()
        assert sha(p) == row["sha256"] and p.stat().st_size == row["bytes"], name
    bindings = read(AUTHOR / "evidence-bindings.json")
    for key, row in bindings.items():
        p = Path(row["path"])
        assert p.is_file() and sha(p) == row["sha256"] and p.stat().st_size == row["bytes"], key
        assert row["locator"] and row["role"]
    inventory = read(AUTHOR / "inventory.json")
    roster = read(Path(bindings["roster"]["path"]))["tasks"]
    assert len(roster) == len(inventory["tasks"]) == 12
    keys = ["id", "repository", "revision", "scope", "component", "startingState", "ecosystem"]
    assert [{k: t[k] for k in keys} for t in roster] == [
        {k: t[k] for k in keys} for t in inventory["tasks"]
    ]
    assert len({t["repository"].lower() for t in roster}) == 12
    archives = []
    for t in inventory["tasks"]:
        a = t["source"]["archive"]
        p = Path(a["archivePath"])
        assert (
            p.stat().st_size == a["bytes"]
            and sha(p) == a["retainedExpectedSha256"] == a["observedSha256"]
        )
        assert a["hashMatched"] and a["currentlyPresent"] and a["taskId"] == t["id"]
        assert t["source"]["exactCampaignAdmissionQualified"] is None
        assert t["nativeOutcomeOracle"]["agentSessionCaptureScoringIntegrationQualified"] is False
        assert (
            t["agentRuntime"]["providerLiveQualified"] is False
            and t["agentRuntime"]["assignedAgentSessionsRun"] == 0
        )
        archives.append({"id": t["id"], "bytes": p.stat().st_size, "sha256": a["observedSha256"]})
    qualified = [
        t["id"]
        for t in inventory["tasks"]
        if t["environment"]["boundedNativeScopeQualified"]
        and t["nativeOutcomeOracle"]["boundedNativeOutcomeQualified"]
    ]
    assert qualified == ["rust-02", "typescript-02", "go-03"]
    offline = read(Path(bindings["offline-results"]["path"]))
    assert [t["taskId"] for t in offline["tasks"]] == qualified
    for t in offline["tasks"]:
        assert t["taskOutcomeObserved"] and t["oracle"]["qualified"] and t["nativeError"] is None
        assert (t["repository"], t["revision"], t["scope"], t["component"]) == next(
            (n["repository"], n["revision"], n["scope"], n["component"])
            for n in inventory["tasks"]
            if n["id"] == t["taskId"]
        )
    assert (
        offline["all12EnvironmentQualified"] is False
        and offline["agentCampaignExecuted"] is False
        and offline["modelCalls"] == 0
    )
    shared = inventory["sharedLaunchGates"]
    assert [g["id"] for g in shared] == ["G1", "G2", "G3", "G4", "G5", "G6"] and all(
        g["state"] == "unmet" for g in shared
    )
    assert all(set(t["evidenceRefs"]) <= set(bindings) for t in inventory["tasks"])
    assert all(set(g["evidenceRefs"]) <= set(bindings) for g in shared)
    counts = inventory["counts"]
    assert (
        counts["boundedNativeEnvironmentScopesQualified"]
        == counts["boundedNativeOutcomeOraclesQualified"]
        == 3
    )
    assert counts["tasksWithoutBoundedNativeEnvironmentAndOutcomeQualification"] == 9
    assert (
        counts["exactCampaignSourceAdmissionsEstablished"]
        == counts["agentSessionsRun"]
        == counts["agentSessionCaptureOrProviderLiveQualifiedTasks"]
        == 0
    )
    assert counts["exactCampaignSourceAdmissionsUnverified"] == 12
    assert counts["sharedLaunchGateGroupsUnmet"] == counts["sharedLaunchGateGroupsTotal"] == 6
    app = read(Path(bindings["applicability"]["path"]))["summary"]
    assert app == inventory["sharedFacts"]["applicabilityDiagnostic"]
    assert (
        app["hits"] == 5
        and app["misses"] == 7
        and app["scalarPolicyAccepted"] == 4
        and app["taskSupportedDirectCompleteInstructions"] == 0
    )
    last = read(Path(bindings["go01-latest-collection"]["path"]))
    assert (
        last["packageInventoryCount"] == 104
        and last["nativeCollectionAttempted"]
        and not last["collectionCompleted"]
    )
    assert last["terminationCause"] is None and last["oomProven"] is False
    assert last["taskOutcomeObserved"] is False and last["defaultHerebyTaskExecuted"] is False
    for flag in ["executionAuthorized", "paidLaunchAuthorized", "consumerBenefitEstablished"]:
        assert inventory[flag] is False
    assert inventory["costUsd"] is None
    result = {
        "state": "independent-finite-readiness-inventory-verification-pass",
        "authorArtifacts": len(freeze["artifacts"]),
        "evidenceBindings": len(bindings),
        "unchangedTaskIdentities": 12,
        "archives": archives,
        "archiveBytesRehashed": sum(a["bytes"] for a in archives),
        "boundedKnownNativeScopes": qualified,
        "tasksWithoutThatQualification": 9,
        "sharedGateGroups": 6,
        "campaignSourceAdmissionsEstablished": 0,
        "agentSessionOrProviderLiveQualifications": 0,
        "actualCampaignSessions": 0,
        "countsNotAdditive": "9 task-scope qualification gaps and6 shared gate groups; not15 sequential implementation steps or18 task env/oracle failures.12 source-admission checks overlap shared final-freeze gate.",
        "newNetworkDaemonInstallProviderNativeActions": 0,
        "executionAuthorized": False,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
