"""Read-only source/contract checks; optional existing archive read, no execution."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tarfile

import oracle

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "f05-go01-requalification-proposal-20261029"


def sha(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while raw := stream.read(1024**2):
            value.update(raw)
    return value.hexdigest()


def verify(archive):
    bindings = json.loads((HERE / "source-bindings.json").read_text())
    assert sha(PRIOR / "freeze.json") == bindings["proposalFreezeSha256"]
    for item in bindings["proposalBindings"]:
        assert sha(PRIOR / item["path"]) == item["sha256"], item["path"]
    contracts = json.loads((HERE / "contract-bindings.json").read_text())
    for item in contracts["files"]:
        assert sha(Path(item["path"])) == item["sha256"], item["path"]
    policy = json.loads((HERE / "policy-proposal.json").read_text())
    assert oracle.digest(policy["exclusions"]) == oracle.EXCLUSION_SET_SHA256
    assert policy["state"] == "proposal-unaccepted" and policy["acceptedAt"] is None
    assert policy["acceptanceSha256"] is None
    assert len(policy["exclusions"]) == 380
    assert len({(e["package"], e["test"]) for e in policy["exclusions"]}) == 380
    collection = json.loads((HERE / "collection-required.json").read_text())
    assert collection["packages"] == {} and collection["state"] == "missing-native-collection"
    controls = json.loads((HERE / "controls-final2.json").read_text())
    assert controls["passed"] == len(controls["controls"]) == 60
    assert all(
        case["passed"] and case["observed"]["taskOutcomeObserved"] is False
        for case in controls["controls"]
    )
    ledger = json.loads((HERE / "skip-source-ledger.json").read_text())
    sites = ledger["lexicalTestFileSites"] + ledger["nonTestHelperSites"]
    assert len(ledger["lexicalTestFileSites"]) == 469 and len(ledger["nonTestHelperSites"]) == 11
    if archive:
        archive_path = Path(bindings["sourceArchive"]["path"])
        assert sha(archive_path) == oracle.SOURCE
        by_path = {}
        for site in sites:
            by_path.setdefault(site["path"], []).append(site)
        for entry in policy["exclusions"]:
            by_path.setdefault(entry["sourcePath"], []).append(entry)
        with tarfile.open(archive_path) as tar:
            for path, rows in by_path.items():
                raw = tar.extractfile(path).read()
                digest = hashlib.sha256(raw).hexdigest()
                lines = raw.decode().splitlines()
                for entry in rows:
                    assert digest == entry["sourceSha256"], path
                    assert (
                        "\n".join(lines[entry["startLine"] - 1 : entry["endLine"]])
                        == entry["excerpt"]
                    ), path
                    if "text" in entry:
                        assert lines[entry["line"] - 1].strip() == entry["text"], path
    return {
        "state": "passed",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "proposalBindings": len(bindings["proposalBindings"]),
        "contractBindings": len(contracts["files"]),
        "sourceArchiveRehashedAndAllSpansChecked": archive,
        "exactProposedExclusions": 380,
        "lexicalTestSkipSites": 469,
        "additionalHelperSkipSites": 11,
        "syntheticControlsPassed": 60,
        "nativeCollectionOccurred": False,
        "nativeCounts": None,
        "policyAccepted": False,
        "newDockerNetworkUpstreamProviderCalls": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive", action="store_true", help="read and hash existing archive only"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.output.open("x") as stream:
        json.dump(verify(args.archive), stream, indent=2)
        stream.write("\n")
