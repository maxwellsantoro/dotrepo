"""Admission-bound source bytes and tree inventory; no model or network here."""

from __future__ import annotations

import fnmatch
import hashlib
import re
from collections import OrderedDict

import observed_recipe
from repodigest_acquire import canonical, identity, safe_path, sha
from repodigest_source_tools import bounded_payload

MAX_INDEX_BYTES = 4194304
MAX_BLOB_BYTES = 1048576
MAX_BLOB_CACHE_BYTES = 8388608


class Unavailable(ValueError):
    """A genuine source-cache miss, eligible for separately configured fallback."""


def prepare(snapshot, blobs, contents):
    files = {}
    bodies = {}
    for path, entry in sorted(blobs.items()):
        safe_path(path)
        if not re.fullmatch("[0-9a-f]{40}", entry["sha"]) or entry["mode"] not in {
            "100644",
            "100755",
            "120000",
        }:
            raise ValueError("invalid source index entry")
        item = {"gitBlob": entry["sha"], "mode": entry["mode"], "sourceSha256": None}
        if path in contents:
            body = contents[path].encode("utf-8")
            if len(body) > MAX_BLOB_BYTES or sha(body) != snapshot["files"][path]["sha256"]:
                raise ValueError("source body exceeds budget or changed")
            item["sourceSha256"] = sha(body)
            bodies[sha(body)] = body
        files[path] = item
    index = canonical(
        {
            "repository": snapshot["repository"],
            "revision": snapshot["revision"],
            "tree": snapshot["tree"],
            "files": files,
        }
    )
    if len(index) > MAX_INDEX_BYTES:
        raise ValueError("compiled source inventory exceeds budget")
    return index, bodies


def write(db, index, bodies):
    prior = db.execute("SELECT body FROM objects WHERE digest=?", (sha(index),)).fetchone()
    if prior and prior[0] != index:
        raise ValueError("existing source inventory corrupt")
    db.execute("INSERT OR IGNORE INTO objects VALUES(?,?)", (sha(index), index))
    for digest, body in bodies.items():
        prior = db.execute("SELECT body FROM source_blobs WHERE digest=?", (digest,)).fetchone()
        if prior and prior[0] != body:
            raise ValueError("existing source body corrupt")
        db.execute("INSERT OR IGNORE INTO source_blobs VALUES(?,?)", (digest, body))


class Reader:
    def __init__(self, store):
        self.store = store
        self.indices = OrderedDict()
        self.bodies = OrderedDict()
        self.body_bytes = 0
        self.stats = {
            "logicalIndexBytesRead": 0,
            "logicalBlobBytesRead": 0,
            "indexCacheHits": 0,
            "blobCacheHits": 0,
        }

    def index(self, repository, revision):
        repo = identity(repository)
        root = self.store.lookup(repo, revision)
        if root.get("recordedRevision") != revision:
            if any(
                reason in root["missingEvidence"]
                for reason in ("repository-not-indexed", "revision-not-qualified")
            ):
                raise Unavailable("exact source revision not cached")
            raise ValueError("compiled source root refused:" + ",".join(root["missingEvidence"]))
        receipt_id = root["evidenceAdmission"]
        row = self.store.db.execute(
            "SELECT body FROM admissions WHERE digest=?", (receipt_id,)
        ).fetchone()
        if (
            not row
            or not isinstance(row[0], bytes)
            or len(row[0]) > 65536
            or sha(row[0]) != receipt_id
        ):
            raise ValueError("source admission integrity failure")
        receipt = observed_recipe.decode(row[0])
        if (
            receipt.get("repository"),
            receipt.get("revision"),
            receipt.get("tree"),
            receipt.get("policySha256"),
        ) != (repo, revision, root["sourceTree"], self.store.policy):
            raise ValueError("source admission binding mismatch")
        digest = receipt.get("sourceIndexSha256")
        if not digest:
            raise ValueError("source cache was not admitted; operator re-admission required")
        if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
            raise ValueError("invalid source inventory reference")
        if digest in self.indices:
            self.stats["indexCacheHits"] += 1
            self.indices.move_to_end(digest)
            index = self.indices[digest]
        else:
            row = self.store.db.execute(
                "SELECT body FROM objects WHERE digest=?", (digest,)
            ).fetchone()
            if (
                not row
                or not isinstance(row[0], bytes)
                or len(row[0]) > MAX_INDEX_BYTES
                or sha(row[0]) != digest
            ):
                raise ValueError("compiled source inventory integrity failure")
            self.stats["logicalIndexBytesRead"] += len(row[0])
            index = observed_recipe.decode(row[0])
            if not isinstance(index, dict) or not isinstance(index.get("files"), dict):
                raise ValueError("invalid source inventory")
            for path, item in index["files"].items():
                safe_path(path)
                if (
                    not isinstance(item, dict)
                    or item.get("mode") not in {"100644", "100755", "120000"}
                    or not isinstance(item.get("gitBlob"), str)
                    or not re.fullmatch("[0-9a-f]{40}", item["gitBlob"])
                ):
                    raise ValueError("invalid source inventory entry")
                body_digest = item.get("sourceSha256")
                if body_digest is not None and (
                    not isinstance(body_digest, str)
                    or not re.fullmatch("[0-9a-f]{64}", body_digest)
                ):
                    raise ValueError("invalid source body reference")
            self.indices[digest] = index
            if len(self.indices) > 4:
                self.indices.popitem(last=False)
        if (index.get("repository"), index.get("revision"), index.get("tree")) != (
            repo,
            revision,
            root["sourceTree"],
        ):
            raise ValueError("source inventory binding mismatch")
        return repo, receipt_id, index, receipt["checkedAt"]

    def list(self, repository, revision, pattern="*", offset=0, limit=60):
        if not isinstance(pattern, str) or len(pattern) > 200:
            raise ValueError("pattern must be a string of at most200 characters")
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("offset must be >=0 and limit an integer in1..100")
        repo, receipt, index, checked_at = self.index(repository, revision)
        paths = sorted(p for p in index["files"] if fnmatch.fnmatchcase(p, pattern))
        selected = paths[offset : offset + limit]
        out = {
            "repository": repo,
            "revision": revision,
            "paths": selected,
            "cachedPaths": [p for p in selected if index["files"][p]["sourceSha256"] is not None],
            "totalPaths": len(paths),
            "nextOffset": offset + limit if len(paths) > offset + limit else None,
            "retrieval": "compiled-source-cache",
            "admissionSha256": receipt,
            "sourceCheckedAt": checked_at,
            "meaning": "Tracked blob paths; cachedPaths have admitted bodies. Membership alone is not file inspection or procedure qualification.",
            "authorized": "not-granted",
        }
        return bounded_payload(out)

    def body(self, repository, revision, path):
        safe_path(path)
        repo, receipt, index, checked_at = self.index(repository, revision)
        item = index["files"].get(path)
        if item is None:
            raise ValueError("path not in pinned source inventory")
        if item["mode"] not in {"100644", "100755"}:
            raise ValueError("path is not a regular source blob")
        digest = item["sourceSha256"]
        if digest is None:
            raise Unavailable("source file not inspected at admission:" + path)
        if digest in self.bodies:
            self.stats["blobCacheHits"] += 1
            self.bodies.move_to_end(digest)
            body = self.bodies[digest]
        else:
            row = self.store.db.execute(
                "SELECT body FROM source_blobs WHERE digest=?", (digest,)
            ).fetchone()
            if (
                not row
                or not isinstance(row[0], bytes)
                or len(row[0]) > MAX_BLOB_BYTES
                or sha(row[0]) != digest
            ):
                raise ValueError("compiled source body integrity failure")
            body = row[0]
            self.stats["logicalBlobBytesRead"] += len(body)
            while self.body_bytes + len(body) > MAX_BLOB_CACHE_BYTES and self.bodies:
                _, expired = self.bodies.popitem(last=False)
                self.body_bytes -= len(expired)
            self.bodies[digest] = body
            self.body_bytes += len(body)
        if (
            hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()
            != item["gitBlob"]
        ):
            raise ValueError("cached source Git blob mismatch")
        return repo, receipt, digest, body, checked_at

    def read(self, repository, revision, path, start=1, end=None):
        if end is None and type(start) is int:
            end = start + 99
        if (
            type(start) is not int
            or type(end) is not int
            or start < 1
            or not start <= end < start + 120
        ):
            raise ValueError("read at most120 numbered lines with positive indices")
        repo, receipt, digest, body, checked_at = self.body(repository, revision, path)
        lines = body.decode("utf-8").splitlines()
        out = {
            "repository": repo,
            "revision": revision,
            "path": path,
            "sha256": digest,
            "startLine": start,
            "endLine": min(end, len(lines)),
            "totalLines": len(lines),
            "lines": "\n".join(
                f"{n + 1}: {line}" for n, line in enumerate(lines[start - 1 : end], start - 1)
            ),
            "retrieval": "compiled-source-cache",
            "admissionSha256": receipt,
            "sourceCheckedAt": checked_at,
            "knowledgeClass": "publisher-source",
            "meaning": "Exact admitted source bytes at this revision, not a complete instruction, current-environment applicability, execution success or permission.",
            "authorized": "not-granted",
        }
        return bounded_payload(out)
