#!/usr/bin/env -S uv run python
"""Capture the already enrolled F-05 tasks from one advertised public snapshot."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parent
ORIGIN = "https://dotrepo.org"
LIMIT = 2 * 1024 * 1024


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def main():
    out = ROOT / "profile-capture"
    out.mkdir(exist_ok=False)
    meta_raw = (ROOT / "meta.json").read_bytes()
    meta = json.loads(meta_raw)
    snapshot = meta["snapshotId"]
    assert re.fullmatch(r"[0-9a-f]{64}", snapshot)
    prefix = f"v0/snapshots/{snapshot}"
    assert meta["paths"]["root"] == f"/{prefix}"
    inventory_raw = (ROOT / "inventory-identified.json").read_bytes()
    inventory = json.loads(inventory_raw)
    files = json.loads((ROOT / "files-identified.json").read_bytes())
    leaves = {entry["path"]: entry for entry in files["files"]}
    assert len(leaves) == files["fileCount"]
    assert all(path.startswith(prefix + "/") for path in leaves)
    for payload in (inventory, files):
        assert payload["freshness"]["snapshotDigest"] == meta["snapshotDigest"]
        assert payload["freshness"]["generatedAt"] == meta["generatedAt"]
    inventory_leaf = leaves[prefix + "/repos/index.json"]
    assert inventory_leaf["sha256"] == digest(inventory_raw)
    assert inventory_leaf["bytes"] == len(inventory_raw)
    identities = {}
    for repo in inventory["repositories"]:
        identity = repo["identity"]
        name = "/".join(identity[key] for key in ("host", "owner", "repo"))
        assert name.lower() not in identities
        identities[name.lower()] = name
    tasks_path = ROOT.parent / "f05-agent-tasks-20261029/tasks.json"
    tasks_raw = tasks_path.read_bytes()
    tasks = json.loads(tasks_raw)["tasks"]
    opener = build_opener(NoRedirect)
    profiles, receipts = {}, []
    for task in tasks:
        enrolled = task["repository"]
        canonical = identities.get(enrolled.lower(), enrolled)
        path = f"{prefix}/repos/{canonical}/profile.json"
        leaf = leaves.get(path)
        request = Request(
            ORIGIN + "/" + path,
            headers={"User-Agent": "dotrepo-f05-snapshot/1.0", "Accept": "application/json"},
        )
        try:
            response = opener.open(request, timeout=30)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read(LIMIT + 1)
            assert len(raw) <= LIMIT
            assert response.geturl() == request.full_url
            filename = task["id"] + ".body"
            (out / filename).write_bytes(raw)
            receipt = {
                "taskId": task["id"],
                "enrolledRepository": enrolled,
                "canonicalRepository": canonical,
                "observedAt": datetime.now(timezone.utc).isoformat(),
                "url": request.full_url,
                "requestHeaders": dict(request.headers),
                "status": response.status,
                "headers": dict(response.headers),
                "body": filename,
                "sha256": digest(raw),
                "decodedBytes": len(raw),
                "advertisedLeaf": leaf,
            }
            # Preserve failures before asserting. A transport failure is never
            # reclassified as an unindexed repository or a correct abstention.
            receipts.append(receipt)
            (out / "receipts.json").write_text(json.dumps(receipts, indent=2) + "\n")
            if leaf:
                assert response.status == 200, receipt
                assert leaf["sha256"] == digest(raw) and leaf["bytes"] == len(raw), receipt
                json.loads(raw)
            else:
                assert enrolled.lower() not in identities and response.status == 404, receipt
            profiles[enrolled] = {"status": response.status, "body": raw.decode("utf-8")}
    (out / "responses.json").write_text(
        json.dumps({"snapshotSha256": digest(meta_raw), "profiles": profiles}, indent=2) + "\n"
    )
    (out / "capture.json").write_text(
        json.dumps(
            {
                "schema": "dotrepo-f05-profile-capture/v1",
                "tasksSha256": digest(tasks_raw),
                "sourceFreezeSha256": digest(
                    (tasks_path.parent / "SOURCE_FREEZE.json").read_bytes()
                ),
                "collectorSha256": digest(Path(__file__).read_bytes()),
                "snapshotId": snapshot,
                "snapshotMetadataSha256": digest(meta_raw),
                "status": "captured; consumer policy and campaign launch remain unqualified",
                "profiles": len(profiles),
                "profileRequests": len(receipts),
                "profileDecodedBytes": sum(item["decodedBytes"] for item in receipts),
                "selection": "All twelve tasks enrolled before index consultation; no replacement",
                "limitations": [
                    "Manifest and payload hashes establish internal consistency, not independent authenticity",
                    "Full export identity was not recomputed from every public and private payload",
                    "HTTP decoded bytes exclude transport overhead; preparation costs are unpriced",
                    "Capture contains access-arm data and must never enter source-first tool artifacts",
                ],
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps({"profiles": len(profiles), "statuses": [r["status"] for r in receipts]}))


if __name__ == "__main__":
    main()
