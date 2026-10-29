"""Verify and bind the bounded C1 qualification handoff; run through host uv."""

import json
from pathlib import Path

from acquire import FROZEN, HERE
from control import sha, write
from oracle import controls

assert (
    sha((FROZEN / "SOURCE_FREEZE.json").read_bytes())
    == "fc756e0d5f8a25cddc9f19ece651b21078a68a1f601febdb8d772208c0a66d41"
)
assert controls() == json.loads((HERE / "oracle-controls.json").read_text())
freezes = {}
for version in (1, 2, 3, 4):
    filename = "execution-freeze.json" if version == 1 else f"execution-freeze.v{version}.json"
    row = json.loads((HERE / filename).read_text())
    runner = HERE / (f"qualify.v{version}.py.txt" if version < 4 else "qualify.py")
    assert row["runnerSha256"] == sha(runner.read_bytes())
    assert row["oracleSha256"] == sha((HERE / "oracle.py").read_bytes())
    if version > 1:
        assert row["captureSha256"] == sha((HERE / "capture.py").read_bytes())
        assert row["controlSha256"] == sha((HERE / "control.py").read_bytes())
    freezes[version] = {"path": filename, "sha256": sha((HERE / filename).read_bytes())}
receipts = 0
for path in HERE.glob("**/receipt.json"):
    row = json.loads(path.read_text())
    suffix = ".bin" if (path.parent / "stdout.bin").exists() else ".txt"
    assert row["stdoutSha256"] == sha((path.parent / ("stdout" + suffix)).read_bytes()), path
    assert row["stderrSha256"] == sha((path.parent / ("stderr" + suffix)).read_bytes()), path
    receipts += 1
source_rows = []
for folder in ("rust-02-full", "typescript-02", "go-01-full", "go-03"):
    root = HERE / folder
    source = json.loads((root / "acquisition.json").read_text())
    archive = Path(source["runtimeArchivePath"])
    assert archive.exists() and sha(archive.read_bytes()) == source["runtimeArchiveSha256"]
    assert source["sourceBundleReady"]
    tree = json.loads((root / "source-tree-validation.json").read_text())
    assert tree["actualTreeSha"] == tree["frozenCommitTreeSha"]
    source_rows.append(
        {
            "taskId": source["task"]["id"],
            "revision": source["task"]["revision"],
            "files": source["sourceFiles"],
            "bytes": source["sourceBytes"],
            "archivePath": str(archive),
            "archiveSha256": source["runtimeArchiveSha256"],
            "inventorySha256": sha((root / "inventory.json").read_bytes()),
            "actualGitTreeSha": tree["actualTreeSha"],
        }
    )
latest = {
    "rust-02": "runs/rust-02/attempt-1",
    "typescript-02": "runs/typescript-02/attempt-1",
    "go-01": "runs/go-01/attempt-2",
    "go-03": "runs/go-03/attempt-2",
}
rows = []
for task, folder in latest.items():
    result = json.loads((HERE / folder / "result.json").read_text())
    assert result["cleanup"] == 0
    gold = json.loads((FROZEN / "curator/gold" / (task + ".json")).read_text())
    rows.append(
        {
            "taskId": task,
            "resultPath": folder + "/result.json",
            "latestResult": result,
            "originalInstructionGold": gold["status"],
            "instructionGoldUnchanged": True,
            "executionFreeze": freezes[4 if task == "go-01" else 3],
        }
    )
for result in HERE.glob("runs/**/result.json"):
    assert json.loads(result.read_text())["cleanup"] == 0, result
run_results = [json.loads(path.read_text()) for path in HERE.glob("runs/**/result.json")]
traffic = [row["setupNetworkBytes"] for row in run_results if "setupNetworkBytes" in row]
retry_events = [
    json.loads(line)
    for line in (HERE / "runs/go-01/attempt-2/logs/posthoc-docker-events/stdout.txt")
    .read_text()
    .splitlines()
]
first_events = [
    json.loads(line)
    for line in (HERE / "runs/go-01/attempt-1/logs/posthoc-docker-events/stdout.txt")
    .read_text()
    .splitlines()
]
assert any(row["Action"] == "oom" for row in first_events)
assert not any(row["Action"] == "oom" for row in retry_events)
assert (
    "no space left on device"
    in (HERE / "runs/go-01/attempt-2/logs/native-test-list/stdout.txt").read_text()
)
report = {
    "identity": "f05-qualification-20261029-four-task-handoff",
    "status": "bounded tranche complete; C1 and twelve-task qualification remain incomplete",
    "tasksWithCompleteNativeOutcome": sum(
        bool(row["latestResult"].get("taskOutcomeObserved")) for row in rows
    ),
    "tasksAttempted": 4,
    "frozenTasksTotal": 12,
    "campaignSessionsRun": 0,
    "modelCalls": 0,
    "sourceFreezeSha256": "fc756e0d5f8a25cddc9f19ece651b21078a68a1f601febdb8d772208c0a66d41",
    "sources": source_rows,
    "tasks": rows,
    "retainedQualificationAttempts": len(run_results),
    "setupNetworkBytesAcrossSuccessfulAndFailedAttempts": {
        "received": sum(row["received"] for row in traffic),
        "sent": sum(row["sent"] for row in traffic),
        "basis": "Per-container interface counters; includes protocol headers/incidental traffic; source/image acquisition excluded and separately retained.",
    },
    "costUsd": None,
    "costExclusions": [
        "No metered host/container dollar receipt.",
        "First Node/Go image-pull complete transfer timing/bytes unavailable; do not infer zero.",
        "Some source Git transfer byte totals unavailable; object/archive bytes retained separately.",
    ],
    "oracleControls": controls(),
    "verifiedCommandReceipts": receipts,
    "remainingGates": [
        "Independent oracle/environment review, including npm install-hook equivalence and API-generation adjudication.",
        "go-01 full default outcome: original OOM, then512MiB temporary-filesystem exhaustion; no further retry authorized in this packet.",
        "Remaining8 task source/scope/environment qualification under next-eight-plan.json after resource review.",
        "Reusable immutable dependency caches and one common source-free image not qualified.",
        "Full campaign model/settings/budgets/costs/assignment/isolation and72 actual independent sessions.",
    ],
    "limits": [
        "Three passing operator execution qualifications, not consumer benefit or instruction-population accuracy.",
        "Original source-gold states preserved; unresolved instruction establishment is not correct task abstention.",
        "Linux ARM64 Docker Desktop on macOS; not native Linux host or all-platform proof.",
        "No evaluated index/profile consulted; only exact upstream source and prospective task/oracle packet inspected.",
        "Full source archives/Git objects remain in declared /tmp scratch; committed evidence contains inventories/provenance rather than whole repositories.",
        "Qualification runs overlapped in pairs; timings are observed operator preparation/execution, not a controlled causal comparison.",
    ],
}
assert report["tasksWithCompleteNativeOutcome"] == 3
write(HERE / "report.json", report)
files = {
    str(path.relative_to(HERE)): sha(path.read_bytes())
    for path in sorted(HERE.rglob("*"))
    if path.is_file() and "__pycache__" not in path.parts and path.name != "artifact-hashes.json"
}
write(HERE / "artifact-hashes.json", {"algorithm": "sha256", "files": files})
print(
    f"Bounded qualification3/4 complete native outcomes; {receipts} receipts and {len(files)} artifacts verified; C1 remains open."
)
