"""Read-only integrity checks for retained Go01 preparation; not an independent audit."""

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PREP = HERE.parent / "f05-go01-dependency-preparation-20261029"
sys.path.insert(0, str(PREP))
import prepare  # noqa: E402


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            result.update(chunk)
    return result.hexdigest()


def verify():
    prepare.load_plan()
    root = HERE / "evidence"
    result = json.loads((root / "result.json").read_text())
    provenance = json.loads((root / "provenance.json").read_text())
    inventory = json.loads((root / "inventory.json").read_text())
    authorization = json.loads((HERE / "authorization.json").read_text())
    assert result["state"] == "download-cache-retained-unqualified"
    assert result["synthetic"] is False and result["taskOutcomeObserved"] is False
    assert result["nativeCollectionOccurred"] is False and result["modelCalls"] == 0
    assert result["cacheAuditQualified"] is False
    assert all(value is False for value in result["draftAuditFlags"].values())
    assert result["costUsd"] is None
    assert result["planSha256"] == digest(PREP / "plan.json")
    assert result["authorizationSha256"] == digest(HERE / "authorization.json")
    assert authorization["synthetic"] is False and authorization["maxAttempts"] == 1
    assert result["sourceArchiveSha256"] == prepare.SOURCE
    assert result["imageId"] == prepare.IMAGE
    receipts = list((root / "logs").glob("*/receipt.json"))
    for path in receipts:
        receipt = json.loads(path.read_text())
        assert receipt["stdoutSha256"] == digest(path.parent / "stdout.bin")
        assert receipt["stderrSha256"] == digest(path.parent / "stderr.bin")
        assert receipt["error"] is None
        assert receipt["costUsd"] is None
        if path.parent.name != "post-cleanup-inspect":
            assert receipt["exitCode"] == 0
    assert len(receipts) == result["daemonCalls"] == 24
    source = json.loads((root / "logs/source-provision/receipt.json").read_text())
    assert source["stdinSha256"] == prepare.SOURCE
    assert source["stdinBytes"] == 280422400
    for number, command in enumerate(prepare.COMMANDS):
        receipt = json.loads((root / f"logs/download-{number}/receipt.json").read_text())
        assert receipt["argv"][-1] == prepare.watched_download(command)
    assert (root / "logs/tools-before/stdout.bin").read_bytes() == (
        root / "logs/tools-after/stdout.bin"
    ).read_bytes()
    archive = Path(result["cacheArchivePath"])
    assert archive.stat().st_size == provenance["archiveBytes"] <= 512 * 1048576
    assert digest(archive) == result["cacheArchiveSha256"] == provenance["archiveSha256"]
    assert (
        sum(row["bytes"] for row in inventory["members"].values()) == result["cacheExpandedBytes"]
    )
    assert len(inventory["files"]) == result["cacheFiles"]
    assert result["cacheExpandedBytes"] <= 1073741824
    assert result["workBudgetExceeded"] is False and result["cleanupBudgetExceeded"] is False
    assert result["containerAbsent"] is True and result["cleanupExitCode"] == 0
    assert json.loads((HERE / "host-absence.json").read_text())["absent"] is True
    return {
        "state": "passed-retained-integrity",
        "receiptCount": len(receipts),
        "cacheBytes": archive.stat().st_size,
        "independentContentAudit": False,
        "daemonCalls": 0,
        "nativeCalls": 0,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, sort_keys=True))
