"""Bounded offline retention of user interpretations, separate from qualifications."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path

from decision_workflow import database_digest, decode
from repodigest_acquire import canonical, identity, safe_path, sha
from repodigest_source_cache import Reader
from repodigest_store import Store, stamp

FORMAT = "lazycollective.finding-handoff/1"
RECORD_FORMAT = "dotrepo-user-finding/1"
RECEIPT_FORMAT = "dotrepo-finding-receipt/1"
REPRESENTATION = "git-blob:utf-8"
MEANING = "User source interpretation; no semantic qualification or execution authority."
MAX_BYTES = 65536
MAX_FILES = 256
FIELDS = {
    "id",
    "origin",
    "claim",
    "taskScope",
    "limitations",
    "assumptions",
    "attribution",
    "findingCreatedAt",
    "originEvidence",
    "sources",
}


def text(value, name, *, limit=8192):
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > limit:
        raise ValueError(name + " must be nonempty bounded text")
    if any(ord(c) < 32 and c not in "\n\t\r" for c in value):
        raise ValueError(name + " contains control characters")
    return value


def digest(value):
    if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value):
        raise ValueError("expected full lowercase SHA256")
    return value


def date(value, name, *, nullable=False):
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)", value
    ):
        raise ValueError(name + " must be a UTC timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError(name + " must be a UTC timestamp")
    if parsed > datetime.now(timezone.utc):
        raise ValueError(name + " cannot be in the future")
    return parsed


def exact(value, fields, name):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError("invalid " + name + " fields")


def local_path(value):
    """Refuse symlinks in every existing path component, including the parent."""
    path = Path(value)
    if ".." in path.parts:
        raise ValueError("parent traversal refused")
    absolute = path.absolute()
    if any(part.is_symlink() for part in (absolute, *absolute.parents)):
        raise ValueError("symlink path refused")
    return absolute


def read_file(path, limit=MAX_BYTES):
    path = local_path(path)
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError("missing, nonregular or oversized input")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("oversized input")
    return raw


def evidence(value):
    exact(value, {"locator", "sha256"}, "evidence")
    text(value["locator"], "evidence locator", limit=4096)
    digest(value["sha256"])


def validate_finding(value):
    exact(value, FIELDS, "finding")
    # IDs and origins are labels only; neither ever becomes an output path.
    text(value["id"], "id", limit=256)
    text(value["origin"], "origin", limit=512)
    exact(value["claim"], {"text"}, "claim")
    text(value["claim"]["text"], "claim.text", limit=32768)
    text(value["taskScope"], "taskScope")
    for name in ("limitations", "assumptions"):
        if not isinstance(value[name], list) or len(value[name]) > 32:
            raise ValueError(name + " must be a bounded list")
        for item in value[name]:
            text(item, name)
    exact(value["attribution"], {"author", "product", "recordId"}, "attribution")
    for key, item in value["attribution"].items():
        if item is not None:
            text(item, "attribution." + key, limit=512)
    date(value["findingCreatedAt"], "findingCreatedAt", nullable=True)
    evidence(value["originEvidence"])
    sources = value["sources"]
    if not isinstance(sources, list) or not 1 <= len(sources) <= 16:
        raise ValueError("finding needs 1..16 sources")
    seen = set()
    for source in sources:
        exact(
            source,
            {
                "kind",
                "repository",
                "revision",
                "path",
                "sha256",
                "representation",
                "lineRange",
                "originalObservedAt",
                "originalTimeReason",
                "originalObservationEvidence",
            },
            "source",
        )
        if source["kind"] != "repository":
            raise ValueError("this adapter supports repository sources only")
        if (
            not isinstance(source["repository"], str)
            or identity(source["repository"]) != source["repository"]
        ):
            raise ValueError("repository must be its exact normalized admitted identity")
        if not isinstance(source["revision"], str) or not re.fullmatch(
            "[0-9a-f]{40}", source["revision"]
        ):
            raise ValueError("exact Git revision required")
        safe_path(source["path"])
        digest(source["sha256"])
        text(source["representation"], "representation", limit=256)
        key = (source["repository"], source["revision"], source["path"])
        if key in seen:
            raise ValueError("duplicate source identity")
        seen.add(key)
        lines = source["lineRange"]
        if lines is not None and (
            not isinstance(lines, list)
            or len(lines) != 2
            or any(type(n) is not int for n in lines)
            or not 1 <= lines[0] <= lines[1] <= 1048576
        ):
            raise ValueError("invalid source lineRange")
        observed = date(source["originalObservedAt"], "originalObservedAt", nullable=True)
        if observed is None:
            text(source["originalTimeReason"], "originalTimeReason")
            if source["originalObservationEvidence"] is not None:
                raise ValueError("unknown original time cannot claim an observation receipt")
        else:
            if source["originalTimeReason"] is not None:
                raise ValueError("known original time must have null originalTimeReason")
            evidence(source["originalObservationEvidence"])
            created = date(value["findingCreatedAt"], "findingCreatedAt", nullable=True)
            if created is not None and observed > created:
                raise ValueError("source observation cannot postdate original finding")
    if len(canonical(value)) > MAX_BYTES:
        raise ValueError("finding exceeds 64 KiB")
    return value


def store_file(store, category, raw):
    """Content addressed writes never truncate or replace an existing object."""
    store = local_path(store)
    store.mkdir(parents=True, exist_ok=True)
    entries = list(islice(store.iterdir(), MAX_FILES + 1))
    if any(p.is_symlink() or not p.is_file() for p in entries):
        raise ValueError("finding store contains unsafe entries")
    key = sha(raw)
    path = store / (category + "-" + key + ".json")
    if path.exists():
        if read_file(path) != raw:
            raise ValueError("immutable finding store integrity failure")
        return key, path
    if len(entries) >= MAX_FILES:
        raise ValueError("finding store is full; preserve it and choose a new store")
    if len(raw) > MAX_BYTES:
        raise ValueError("stored object exceeds 64 KiB")
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return key, path


def evidence_file(root, locator, *, limit=MAX_BYTES):
    root = local_path(root)
    path = Path(locator)
    path = local_path(path if path.is_absolute() else root / path)
    if not path.is_relative_to(root):
        raise ValueError("evidence locator is outside explicit evidence root")
    return read_file(path, limit=limit)


def verify_observation(source, evidence_root, finding_created_at):
    """Read only an explicit local receipt; never dereference imported locators."""
    if source["originalObservedAt"] is None:
        return 0
    item = source["originalObservationEvidence"]
    raw = evidence_file(evidence_root, item["locator"])
    if sha(raw) != item["sha256"]:
        raise ValueError("original observation receipt digest mismatch")
    result = decode(raw)
    # Require a dated completed call, rather than a result generated after the
    # finding that happens to expose an old admission's sourceCheckedAt.
    if (
        not isinstance(result, dict)
        or result.get("tool") != "source.read"
        or result.get("state") != "completed"
    ):
        raise ValueError("original observation requires a dated completed source.read receipt")
    recorded = date(result.get("recordedAt"), "original receipt recordedAt")
    created = date(finding_created_at, "findingCreatedAt", nullable=True)
    observed = date(source["originalObservedAt"], "originalObservedAt")
    if created is None or not observed <= recorded <= created:
        raise ValueError("original source receipt must predate the original finding")
    result = result["result"]
    if (
        not isinstance(result, dict)
        or any(
            result.get(key) != source[key] for key in ("repository", "revision", "path", "sha256")
        )
        or result.get("sourceCheckedAt") != source["originalObservedAt"]
    ):
        raise ValueError("original observation receipt does not bind exact source and time")
    return len(raw)


def source_checks(database, finding, *, max_age=None):
    """Verify the recipient's current admitted body; never trust sender current labels."""
    database = local_path(database)
    checks, stats = [], {}
    before, database_bytes = database_digest(database)
    store = Store(database)
    try:
        store.db.execute("BEGIN")
        reader = Reader(store)
        for source in finding["sources"]:
            result = {
                "repository": source["repository"],
                "path": source["path"],
                "sourceStatus": "unknown",
                "reasons": [],
            }
            try:
                row = store.db.execute(
                    "SELECT revision FROM current WHERE identity=?", (source["repository"],)
                ).fetchone()
                if not row:
                    raise ValueError("repository missing from own current store")
                revision = row[0]
                _, admission, current_index, checked = reader.index(source["repository"], revision)
                current_item = current_index["files"].get(source["path"])
                result.update(
                    {
                        "recipientRevision": revision,
                        "admissionSha256": admission,
                        "sourceCheckedAt": checked,
                        "recipientGitBlob": current_item["gitBlob"] if current_item else None,
                    }
                )
                # A repository advance alone does not change this dependency.
                # Verify the bound historical body before comparing its path's
                # admitted Git identity with the current frontier. This proof
                # survives a current missing body, while retaining that unknown.
                if revision != source["revision"]:
                    try:
                        _, _, original_sha, _, _ = reader.body(
                            source["repository"], source["revision"], source["path"]
                        )
                        if original_sha != source["sha256"]:
                            raise ValueError("historical body does not match finding binding")
                        _, _, original_index, _ = reader.index(
                            source["repository"], source["revision"]
                        )
                        original_item = original_index["files"][source["path"]]
                        result["boundHistoricalGitBlob"] = original_item["gitBlob"]
                        if (
                            current_item is not None
                            and current_item["gitBlob"] != original_item["gitBlob"]
                        ):
                            result["sourceStatus"] = "changed"
                            result["reasons"].append(
                                "own current admitted Git blob differs from verified historical binding"
                            )
                    except (ValueError, TypeError, KeyError, sqlite3.Error, UnicodeError) as error:
                        result["historicalBindingIssue"] = str(error)
                repo, admission, body_sha, body, checked = reader.body(
                    source["repository"], revision, source["path"]
                )
                result.update(
                    {
                        "recipientRevision": revision,
                        "recipientSha256": body_sha,
                        "admissionSha256": admission,
                        "sourceCheckedAt": checked,
                        "bodyBytesVerified": len(body),
                    }
                )
                if body_sha != source["sha256"]:
                    result["sourceStatus"] = "changed"
                    result["reasons"].append("own current full body differs")
                elif result["sourceStatus"] != "changed":
                    result["sourceStatus"] = "current"
                if source["representation"] != REPRESENTATION:
                    result["reasons"].append("representation not verified by this reader")
                    if result["sourceStatus"] != "changed":
                        result["sourceStatus"] = "unknown"
                checked_date = date(checked, "recipient sourceCheckedAt")
                if (
                    max_age is not None
                    and (datetime.now(timezone.utc) - checked_date).total_seconds() > max_age
                ):
                    result["reasons"].append("own admitted source observation exceeds policy age")
                    if result["sourceStatus"] != "changed":
                        result["sourceStatus"] = "unknown"
                lines = source["lineRange"]
                if lines and lines[1] > len(body.decode("utf-8").splitlines()):
                    result["reasons"].append("declared lineRange outside current body")
                    if result["sourceStatus"] != "changed":
                        result["sourceStatus"] = "unknown"
            except (ValueError, TypeError, KeyError, sqlite3.Error, UnicodeError) as error:
                if result["sourceStatus"] == "current":
                    result["sourceStatus"] = "unknown"
                result["reasons"].append(str(error))
            checks.append(result)
        stats = dict(reader.stats)
        policy = store.policy
    finally:
        store.close()
    after, after_bytes = database_digest(database)
    if before != after:
        raise ValueError("source database changed during verification")
    status = next(
        (s for s in ("changed", "unknown") if any(x["sourceStatus"] == s for x in checks)),
        "current",
    )
    return {
        "sourceStatus": status,
        "sources": checks,
        "storePolicySha256": policy,
        "databaseSha256": before,
        "storeIntegrityBytesRead": database_bytes + after_bytes,
        "cacheStatistics": stats,
    }


def record(store, database, finding_path, evidence_root):
    finding_raw = read_file(finding_path)
    finding = validate_finding(decode(finding_raw))
    raw_evidence = evidence_file(
        evidence_root, finding["originEvidence"]["locator"], limit=2 * 1024 * 1024
    )
    if sha(raw_evidence) != finding["originEvidence"]["sha256"]:
        raise ValueError("origin evidence digest mismatch")
    evidence_bytes = len(raw_evidence)
    for source in finding["sources"]:
        evidence_bytes += verify_observation(source, evidence_root, finding["findingCreatedAt"])
    checked = source_checks(database, finding)
    if checked["sourceStatus"] != "current" or any(
        "historicalBindingIssue" in source for source in checked["sources"]
    ):
        raise ValueError(
            "record requires exact verified current admitted source bindings: "
            + json.dumps(checked["sources"])
        )
    raw = canonical({"format": RECORD_FORMAT, **finding})
    key, path = store_file(store, "finding", raw)
    receipt = {
        "format": RECEIPT_FORMAT,
        "operation": "record",
        "findingSha256": key,
        "checkedAt": stamp(),
        "interpretation": {"disposition": "unreviewed"},
        "meaning": MEANING,
        "findingInputBytesRead": len(finding_raw),
        "evidenceBytesRead": evidence_bytes,
        **checked,
    }
    receipt_key, _ = store_file(store, "receipt", canonical(receipt))
    return {"findingSha256": key, "findingPath": str(path), "receiptSha256": receipt_key}


def inspect(store, key):
    raw = read_file(local_path(store) / ("finding-" + digest(key) + ".json"))
    if sha(raw) != key:
        raise ValueError("immutable finding integrity failure")
    value = decode(raw)
    if not isinstance(value, dict) or value.get("format") != RECORD_FORMAT:
        raise ValueError("unsupported finding format")
    validate_finding({k: v for k, v in value.items() if k != "format"})
    return value


def export(store, key, output):
    value = inspect(store, key)
    envelope = {**value, "format": FORMAT, "exportedAt": stamp(), "meaning": MEANING}
    raw = canonical(envelope)
    if len(raw) > MAX_BYTES:
        raise ValueError("envelope exceeds 64 KiB")
    output = local_path(output)
    # Caller chooses one explicit destination; imported labels never choose it.
    with output.open("xb") as stream:
        stream.write(raw)
    return {"envelopeSha256": sha(raw), "output": str(output), "bytes": len(raw)}


def receive(store, database, envelope_path, policy_path, review_path=None):
    raw = read_file(envelope_path)
    value = decode(raw)
    exact(value, FIELDS | {"format", "exportedAt", "meaning"}, "envelope")
    if value["format"] != FORMAT or value["meaning"] != MEANING:
        raise ValueError("unsupported envelope format or meaning")
    exported = date(value["exportedAt"], "exportedAt")
    finding = validate_finding({k: value[k] for k in FIELDS})
    created = date(finding["findingCreatedAt"], "findingCreatedAt", nullable=True)
    if created is not None and created > exported:
        raise ValueError("export cannot predate original finding")
    policy_raw = read_file(policy_path)
    policy = decode(policy_raw)
    exact(policy, {"id", "taskScope", "maxSourceAgeSeconds"}, "recipient policy")
    text(policy["id"], "policy id", limit=256)
    text(policy["taskScope"], "policy taskScope")
    age = policy["maxSourceAgeSeconds"]
    # The bounded comparison also rejects nonfinite floats, without converting
    # arbitrarily large JSON integers to floats.
    if type(age) not in {int, float} or not 0 <= age <= 31536000:
        raise ValueError("source age must be finite seconds in 0..31536000")
    key = sha(raw)
    checked = source_checks(database, finding, max_age=age)
    issues = []
    if finding["taskScope"] != policy["taskScope"]:
        issues.append("recipient task scope differs; finding cannot establish broader scope")
    if any(v is None for v in finding["attribution"].values()):
        issues.append("original attribution is incomplete")
    if finding["findingCreatedAt"] is None:
        issues.append("original finding time is unknown")
    if any(s["originalObservedAt"] is None for s in finding["sources"]):
        issues.append("original source observation time is unknown")
    interpretation = {"disposition": "unreviewed", "issues": issues}
    review_bytes = 0
    if review_path is not None:
        review_raw = read_file(review_path)
        review_bytes = len(review_raw)
        review = decode(review_raw)
        exact(
            review,
            {"envelopeSha256", "taskScope", "reviewer", "disposition", "reason"},
            "recipient review",
        )
        if digest(review["envelopeSha256"]) != key or review["taskScope"] != policy["taskScope"]:
            raise ValueError("review must bind this envelope and exact recipient task scope")
        text(review["reviewer"], "reviewer", limit=512)
        text(review["reason"], "review reason")
        if review["disposition"] not in {"accepted", "rejected", "conflicting"}:
            raise ValueError("unsupported explicit interpretation disposition")
        if review["disposition"] == "accepted" and (checked["sourceStatus"] != "current" or issues):
            raise ValueError(
                "accepted interpretation requires current own sources and complete scope/time/attribution"
            )
        interpretation.update(review)
    receipt = {
        "format": RECEIPT_FORMAT,
        "operation": "receive",
        "envelopeSha256": key,
        "policy": policy,
        "policySha256": sha(canonical(policy)),
        "checkedAt": stamp(),
        "interpretation": interpretation,
        "inputBytesRead": {"envelope": len(raw), "policy": len(policy_raw), "review": review_bytes},
        "senderEvidenceHandling": "Preserved metadata; locators never dereferenced or authenticated.",
        "meaning": MEANING,
        **checked,
    }
    _, path = store_file(store, "envelope", raw)
    receipt_key, receipt_path = store_file(store, "receipt", canonical(receipt))
    return {
        "envelopeSha256": key,
        "envelopePath": str(path),
        "receiptSha256": receipt_key,
        "receiptPath": str(receipt_path),
        **receipt,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("record", "inspect", "export", "receive"):
        command = commands.add_parser(name)
        command.add_argument("--store", type=Path, required=True)
        if name in {"record", "receive"}:
            command.add_argument("--database", type=Path, required=True)
        if name in {"inspect", "export"}:
            command.add_argument("--sha256", required=True)
        if name == "record":
            command.add_argument("--finding", type=Path, required=True)
            command.add_argument("--evidence-root", type=Path, required=True)
        if name == "export":
            command.add_argument("--output", type=Path, required=True)
        if name == "receive":
            command.add_argument("--envelope", type=Path, required=True)
            command.add_argument("--policy", type=Path, required=True)
            command.add_argument("--review", type=Path)
    args = vars(parser.parse_args())
    command = args.pop("command")
    if "sha256" in args:
        args["key"] = args.pop("sha256")
    for name in ("finding", "envelope", "policy", "review"):
        if name in args:
            args[name + "_path"] = args.pop(name)
    try:
        result = globals()[command](**args)
    except (ValueError, OSError, TypeError, KeyError, sqlite3.Error, RecursionError) as error:
        print(json.dumps({"state": "refused", "error": str(error)}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
