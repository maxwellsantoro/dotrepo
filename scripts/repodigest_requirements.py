"""Experimental reviewed source assessments for exact, scoped requirement checks."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from repodigest_acquire import canonical, identity, safe_path, sha
from repodigest_source_cache import Reader
from repodigest_store import MAX_RECORD, Store, connect_writer
from source_status import source_state, source_status

MAX_BODY = 32768
MAX_TARGETS = 4
MAX_REQUIREMENTS = 8
MAX_SETS = 32
KEY = re.compile(r"[a-z][a-z0-9.-]{0,95}")
SCHEMA = """
CREATE TABLE IF NOT EXISTS requirement_sets(
 repository TEXT, revision TEXT, component TEXT, source_record TEXT, policy TEXT,
 digest TEXT REFERENCES objects(digest),
 PRIMARY KEY(repository,revision,component,source_record,policy,digest));
"""


@lru_cache(maxsize=1)
def policy_id():
    return sha(
        Path(__file__).read_bytes()
        + b"\0"
        + (Path(__file__).with_name("source_status.py")).read_bytes()
    )


def target(value):
    if not isinstance(value, dict) or set(value) != {"repository", "revision", "component"}:
        raise ValueError("target requires repository, exact revision and component")
    if not isinstance(value["repository"], str):
        raise ValueError("repository identity must be a string")
    repo = identity(value["repository"])
    revision, component = value["revision"], value["component"]
    if not isinstance(revision, str) or not re.fullmatch("[0-9a-f]{40}", revision):
        raise ValueError("exact revision required")
    if component != ".":
        safe_path(component)
    return {"repository": repo, "revision": revision, "component": component}


def source_record(store, request):
    row = store.db.execute(
        "SELECT r.digest,r.body FROM versions v JOIN records r ON r.digest=v.digest "
        "WHERE v.identity=? AND v.revision=? AND v.component=?",
        tuple(request[k] for k in ("repository", "revision", "component")),
    ).fetchone()
    if (
        not row
        or not isinstance(row[1], bytes)
        or len(row[1]) > MAX_RECORD
        or sha(row[1]) != row[0]
    ):
        raise ValueError("source record unavailable or corrupt")
    record = json.loads(row[1])
    if (
        record["repository"],
        record["revision"],
        record["component"]["path"],
        record["policySha256"],
    ) != (
        request["repository"],
        request["revision"],
        request["component"],
        store.policy,
    ):
        raise ValueError("source scope/policy changed; re-admit source")
    return row[0], record


def admit(database, assessment_path, review_path):
    """Trusted operator admission; review establishes meaning, this checks source bindings."""
    raw, review_raw = assessment_path.read_bytes(), review_path.read_bytes()
    if max(len(raw), len(review_raw)) > MAX_BODY:
        raise ValueError("assessment/review exceeds32KiB")
    assessment, review = json.loads(raw), json.loads(review_raw)
    if review.get("approved") is not True or review.get("assessmentSha256") != sha(raw):
        raise ValueError("approved review must bind exact assessment bytes")
    if not isinstance(review.get("reviewer"), str) or not 1 <= len(review["reviewer"]) <= 160:
        raise ValueError("reviewer identity required")
    request = target(assessment["target"])
    claims = assessment["claims"]
    if not isinstance(claims, list) or not 1 <= len(claims) <= 16:
        raise ValueError("1..16 assessed claims required")
    store = Store(database)
    try:
        root_digest, root = source_record(store, request)
        reader = Reader(store)
        compiled = []
        for claim in claims:
            key, value, reason = claim["key"], claim["value"], claim["reason"]
            if not isinstance(key, str) or not KEY.fullmatch(key) or type(value) is not bool:
                raise ValueError("bounded claim key and boolean value required")
            if not isinstance(reason, str) or not 1 <= len(reason) <= 320:
                raise ValueError("bounded assessment reasoning required")
            basis = claim["basis"]
            if basis not in {"publisher-declaration", "source-analysis"}:
                raise ValueError("explicit assessment basis required")
            limitations = claim["limitations"]
            if not isinstance(limitations, str) or not 1 <= len(limitations) <= 320:
                raise ValueError("bounded limitations required")
            evidence = claim["evidence"]
            if not isinstance(evidence, list) or not 1 <= len(evidence) <= 4:
                raise ValueError("1..4 retained source references required")
            sources = []
            for reference in evidence:
                path, start, end = reference["path"], reference["startLine"], reference["endLine"]
                if (
                    type(start) is not int
                    or type(end) is not int
                    or not 1 <= start <= end < start + 40
                ):
                    raise ValueError("source reference must span1..40 positive numbered lines")
                _, _, digest, body, _ = reader.body(
                    request["repository"], request["revision"], path
                )
                if reference["sha256"] != digest:
                    raise ValueError("assessment source hash changed")
                lines = body.decode().splitlines()
                if end > len(lines):
                    raise ValueError("source reference outside retained body")
                excerpt = "\n".join(lines[start - 1 : end])
                sources.append(
                    {
                        "path": path,
                        "sha256": digest,
                        "startLine": start,
                        "endLine": end,
                        "excerpt": excerpt[:180],
                        "excerptTruncated": len(excerpt) > 180,
                    }
                )
            compiled.append(
                {
                    "key": key,
                    "value": value,
                    "basis": basis,
                    "reason": reason,
                    "limitations": limitations,
                    "evidence": sources,
                }
            )
        capsule = {
            "target": request,
            "sourceRecordSha256": root_digest,
            "sourcePolicySha256": store.policy,
            "policySha256": policy_id(),
            "sourceCheckedAt": root["checkedAt"],
            "assessmentSha256": sha(raw),
            "reviewSha256": sha(review_raw),
            "reviewer": review["reviewer"],
            "claims": compiled,
            "meaning": "Reviewed interpretation of retained source at an exact scope/revision. Admission validates references, not semantic entailment or reviewer independence; a trusted operator chooses the reviewer. This is not execution evidence or authority.",
        }
    finally:
        store.close()
    body = canonical(capsule)
    if len(body) > MAX_BODY:
        raise ValueError("compiled assessment exceeds32KiB")
    digest = sha(body)
    db = connect_writer(database)
    try:
        db.executescript(SCHEMA)
        with db:
            existing = db.execute("SELECT body FROM objects WHERE digest=?", (digest,)).fetchone()
            for saved in (raw, review_raw, body):
                prior = db.execute(
                    "SELECT body FROM objects WHERE digest=?", (sha(saved),)
                ).fetchone()
                if prior and prior[0] != saved:
                    raise ValueError("existing assessment/review corrupt")
                db.execute("INSERT OR IGNORE INTO objects VALUES(?,?)", (sha(saved), saved))
            count = db.execute(
                "SELECT COUNT(*) FROM requirement_sets WHERE repository=? AND component=? AND policy=?",
                (request["repository"], request["component"], policy_id()),
            ).fetchone()[0]
            if count >= MAX_SETS and not existing:
                raise ValueError("assessment set limit reached")
            db.execute(
                "INSERT OR IGNORE INTO requirement_sets VALUES(?,?,?,?,?,?)",
                (*request.values(), root_digest, policy_id(), digest),
            )
    finally:
        db.close()
    return {"assessmentRecordSha256": digest, "claims": len(compiled), "target": request}


def load(store, request):
    source_record(store, request)
    try:
        rows = store.db.execute(
            "SELECT digest,source_record FROM requirement_sets WHERE repository=? AND component=? AND policy=? LIMIT ?",
            (request["repository"], request["component"], policy_id(), MAX_SETS + 1),
        ).fetchall()
    except sqlite3.OperationalError as error:
        if "no such table" not in str(error):
            raise
        rows = []
    if len(rows) > MAX_SETS:
        raise ValueError("assessment set limit exceeded")
    reader = Reader(store)
    try:
        _, _, index, checked_at = reader.index(request["repository"], request["revision"])
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(checked_at)).total_seconds()
        if not 0 <= age <= 30 * 86400:
            raise ValueError("source admission stale or future")
        source_error = None
    except (ValueError, KeyError, TypeError) as error:
        index, source_error = None, str(error)
    claims = []
    for digest, root_digest in rows:
        row = store.db.execute("SELECT body FROM objects WHERE digest=?", (digest,)).fetchone()
        if (
            not row
            or not isinstance(row[0], bytes)
            or len(row[0]) > MAX_BODY
            or sha(row[0]) != digest
        ):
            raise ValueError("assessment record integrity failure")
        capsule = json.loads(row[0])
        if (
            capsule["target"]["repository"] != request["repository"]
            or capsule["target"]["component"] != request["component"]
            or capsule["sourceRecordSha256"] != root_digest
            or capsule["sourcePolicySha256"] != store.policy
            or capsule["policySha256"] != policy_id()
        ):
            raise ValueError("assessment binding/policy mismatch")
        for claim in capsule["claims"]:
            states, reasons = [], []
            for reference in claim["evidence"]:
                entry = index["files"].get(reference["path"]) if index else None
                observed = None
                if (
                    source_error
                    or not entry
                    or entry.get("mode") not in {"100644", "100755"}
                    or not entry.get("sourceSha256")
                ):
                    reasons.append(
                        source_error
                        or "declared source missing, uninspected or not regular:"
                        + reference["path"]
                    )
                else:
                    observed = entry["sourceSha256"]
                retained = bool(
                    store.db.execute(
                        "SELECT 1 FROM source_blobs WHERE digest=?", (reference["sha256"],)
                    ).fetchone()
                )
                state = source_state(reference["sha256"], observed, retained)
                if state == "changed":
                    reasons.append("declared source bytes changed:" + reference["path"])
                elif state == "unknown" and observed is not None:
                    reasons.append("declared source body unavailable:" + reference["path"])
                states.append(state)
            status = source_status(states)
            claims.append(
                {
                    **claim,
                    "assessmentRecordSha256": digest,
                    "reviewer": capsule["reviewer"],
                    "assessedRevision": capsule["target"]["revision"],
                    "sourceStatus": status,
                    "sourceReasons": reasons,
                }
            )
    return claims


def available(store, request):
    try:
        claims = load(store, target(request))
        return {
            "claimKeys": sorted({c["key"] for c in claims if c["sourceStatus"] == "current"}),
            "meaning": "Exact experimental claim keys, not a universal capability vocabulary. Consult qualify for assessments; absence is unknown.",
        }
    except (ValueError, KeyError, TypeError) as error:
        return {"claimKeys": [], "missingEvidence": [str(error)]}


def qualify(store, candidates, requirements):
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= MAX_TARGETS:
        raise ValueError("1..4 exact candidates required")
    if not isinstance(requirements, list) or not 1 <= len(requirements) <= MAX_REQUIREMENTS:
        raise ValueError("1..8 requirements required")
    for requirement in requirements:
        if (
            not isinstance(requirement, dict)
            or set(requirement) != {"key", "expected"}
            or not isinstance(requirement["key"], str)
            or not KEY.fullmatch(requirement["key"])
            or type(requirement["expected"]) is not bool
        ):
            raise ValueError("each requirement needs exact claim key and boolean expected")
    result = {
        "candidates": [],
        "meaning": "Supported/contradicted mean the recorded reviewed source assessment agrees/disagrees with the requested value. Unknown includes absent, stale, conflicting or refused evidence. No free-text inference, tested functionality or execution authorization. Claim keys require semantic alignment by the caller.",
        "authorized": "not-granted",
    }
    for candidate in candidates:
        request = target(candidate)
        try:
            claims, missing = load(store, request), []
        except (ValueError, KeyError, TypeError) as error:
            claims, missing = [], [str(error)]
        findings = []
        for requirement in requirements:
            evidence = [c for c in claims if c["key"] == requirement["key"]]
            current = [c for c in evidence if c["sourceStatus"] == "current"]
            values = {c["value"] for c in current}
            status = (
                "unknown"
                if len(values) != 1
                else "supported"
                if requirement["expected"] in values
                else "contradicted"
            )
            findings.append(
                {
                    **requirement,
                    "status": status,
                    "sourceStatus": "current"
                    if current
                    else "changed"
                    if any(c["sourceStatus"] == "changed" for c in evidence)
                    else "unknown",
                    "reason": "conflicting source assessments"
                    if len(values) > 1
                    else "no current scoped assessment; source silence does not establish absence"
                    if not values
                    else "reviewed source assessment",
                    "assessments": evidence,
                }
            )
        result["candidates"].append({**request, "findings": findings, "missingEvidence": missing})
    if len(canonical(result)) > MAX_BODY:
        raise ValueError("response exceeds32KiB; request fewer candidates or requirements")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--assessment", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(admit(args.database, args.assessment, args.review), indent=2))


if __name__ == "__main__":
    main()
