"""Operator-only reuse of retained pinned source HTTP responses. Never executes them."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from observed_recipe import decode
from repodigest_acquire import canonical, safe_path, sha
from repodigest_demand import MAX_FILE_BYTES, MAX_NEW_BYTES, MAX_NEW_FILES, MAX_TOTAL_FILES

MAX_EVENTS_BYTES = 2097152
MAX_TRAFFIC_BYTES = 1048576


def retained_file(root, relative, limit):
    safe_path(relative)
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("retained evidence outside session")
    # Refuse aliases in descendants even when they resolve back inside root.
    cursor = root
    for part in relative.split("/"):
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("retained evidence symlink refused")
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError("retained evidence missing or exceeds budget")
    raw = path.read_bytes()
    if len(raw) > limit:
        raise ValueError("retained evidence exceeds budget")
    return raw


def trusted_file(session, name, digest, limit):
    if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
        raise ValueError("explicit trusted receipt SHA256 required")
    raw = retained_file(session, name, limit)
    if sha(raw) != digest:
        raise ValueError("trusted receipt digest mismatch:" + name)
    return raw


def lineage(snapshot):
    """Validate recorded content witnesses before carrying them through refresh."""
    values = snapshot.get("sourceReuse", {})
    if not isinstance(values, dict):
        raise ValueError("invalid source reuse provenance")
    for path, item in values.items():
        safe_path(path)
        binding = snapshot["files"].get(path)
        if (
            not isinstance(item, dict)
            or not binding
            or item.get("repository") != snapshot["repository"]
            or item.get("gitBlob") != binding["gitBlob"]
            or item.get("sha256") != binding["sha256"]
            or not isinstance(item.get("sourceRevision"), str)
            or not re.fullmatch("[0-9a-f]{40}", item["sourceRevision"])
        ):
            raise ValueError("source reuse provenance binding mismatch")
    return values


def source_read(events, repository, revision, path, raw):
    for number, event in enumerate(events, 1):
        if not isinstance(event, dict):
            raise ValueError("invalid source event")
        item = event.get("item", {})
        if not isinstance(item, dict):
            continue
        args = item.get("arguments", {})
        result = item.get("result") or {}
        if not isinstance(args, dict) or not isinstance(result, dict):
            continue
        if (
            event.get("type") != "item.completed"
            or item.get("type") != "mcp_tool_call"
            or item.get("tool") != "source.read"
            or item.get("status") != "completed"
            or item.get("error") is not None
            or result.get("isError", False) is not False
            or (args.get("repository"), args.get("revision"), args.get("path"))
            != (repository, revision, path)
        ):
            continue
        content = result.get("content", [])
        if (
            not isinstance(content, list)
            or len(content) != 1
            or not isinstance(content[0], dict)
            or content[0].get("type") != "text"
        ):
            continue
        value = decode(content[0]["text"])
        if not isinstance(value, dict):
            continue
        if (
            (value.get("repository"), value.get("revision"), value.get("path"))
            != (repository, revision, path)
            or value.get("sha256") != sha(raw)
            or value.get("retrieval") not in (None, "verified-source-http")
        ):
            continue
        start = args.get("start", 1)
        end = args.get("end")
        if end is None and type(start) is int:
            end = start + 99
        if type(start) is not int or type(end) is not int or not 1 <= start <= end < start + 120:
            continue
        lines = raw.decode("utf-8").splitlines()
        expected = "\n".join(
            f"{n + 1}: {line}" for n, line in enumerate(lines[start - 1 : end], start - 1)
        )
        if (
            all(type(value.get(key)) is int for key in ("startLine", "endLine", "totalLines"))
            and value.get("startLine") == start
            and value.get("endLine") == min(end, len(lines))
            and value.get("totalLines") == len(lines)
            and value.get("lines") == expected
        ):
            return {"eventLine": number, "resultSha256": sha(canonical(value))}
    raise ValueError("no successful matching source-read receipt:" + path)


def reuse(previous, session, output, *, paths, trusted_events_sha256, trusted_traffic_sha256):
    from repodigest_store import validate_snapshot

    old, blobs, contents = validate_snapshot(previous)
    lineage(old)
    if not paths or len(paths) > MAX_NEW_FILES or len(set(paths)) != len(paths):
        raise ValueError("request1..8 unique source paths")
    if output.exists():
        raise FileExistsError(output)
    events_raw = trusted_file(session, "events.jsonl", trusted_events_sha256, MAX_EVENTS_BYTES)
    traffic_raw = trusted_file(session, "traffic.json", trusted_traffic_sha256, MAX_TRAFFIC_BYTES)
    events = [decode(line) for line in events_raw.splitlines()]
    traffic = decode(traffic_raw)
    if not isinstance(traffic, dict) or not isinstance(traffic.get("http"), list):
        raise ValueError("invalid HTTP receipt")
    if not all(isinstance(event, dict) for event in traffic["http"]):
        raise ValueError("invalid HTTP receipt event")
    accepted = {}
    byte_count = 0
    for path in paths:
        safe_path(path)
        blob = blobs.get(path)
        if not blob or blob.get("mode") not in {"100644", "100755"}:
            raise ValueError("requested source not a regular pinned blob")
        raw = retained_file(
            session,
            "source-responses/" + old["repository"].split("/", 1)[1] + "/" + path,
            MAX_FILE_BYTES,
        )
        raw.decode("utf-8")
        if hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() != blob["sha"]:
            raise ValueError("retained source does not match pinned Git blob")
        url = f"https://raw.githubusercontent.com/{old['repository'].split('/', 1)[1]}/{old['revision']}/{quote(path, safe='/')}"
        matching = [
            (n, item)
            for n, item in enumerate(traffic["http"])
            if item.get("url") == url
            and type(item.get("status")) is int
            and item["status"] == 200
            and type(item.get("responseBodyBytes")) is int
            and item["responseBodyBytes"] == len(raw)
        ]
        if not matching:
            raise ValueError("no successful matching HTTP body receipt:" + path)
        read = source_read(events, old["repository"], old["revision"], path, raw)
        byte_count += len(raw)
        if byte_count > MAX_NEW_BYTES:
            raise ValueError("retained source total byte budget exceeded")
        accepted[path] = (raw, matching[0][0], read)
    new = sorted(set(paths) - set(contents))
    if len(contents) + len(new) > MAX_TOTAL_FILES:
        raise ValueError("total inspected-file budget exceeded")
    # Nothing is published until every selected source and receipt has checked.
    output.mkdir(parents=True, exist_ok=False)
    for name in ("commit.json", "tree.json"):
        shutil.copyfile(previous / name, output / name)
    for path in contents:
        dest = output / "files" / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(contents[path].encode("utf-8"))
    snapshot = copy.deepcopy(old)
    imported_at = datetime.now(timezone.utc).isoformat()
    for path in new:
        raw, http_index, read = accepted[path]
        dest = output / "files" / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        binding = {"sha256": sha(raw), "gitBlob": blobs[path]["sha"], "bytes": len(raw)}
        snapshot["files"][path] = binding
        snapshot.setdefault("sourceReuse", {})[path] = {
            "repository": old["repository"],
            "sourceRevision": old["revision"],
            "gitBlob": binding["gitBlob"],
            "sha256": binding["sha256"],
            "importedAt": imported_at,
            "sessionDirectory": str(session.resolve()),
            "eventsSha256": sha(events_raw),
            "trafficSha256": sha(traffic_raw),
            "httpEventIndex": http_index,
            **read,
            "meaning": "Retained source HTTP/read evidence rechecked against the pinned Git blob, not command success, environment applicability or execution permission. Original source revision remains explicit through unchanged-blob refresh.",
        }
    snapshot["coverage"]["inspectedFiles"] = len(snapshot["files"])
    (output / "snapshot.json").write_bytes(canonical(snapshot) + b"\n")
    report = {
        "state": "extended" if new else "cached",
        "repository": old["repository"],
        "revision": old["revision"],
        "baseSnapshotSha256": sha(canonical(old)),
        "importedFiles": new,
        "validatedReceiptFiles": list(paths),
        "retainedSourceBodyBytes": byte_count,
        "newPublisherRequests": 0,
        "newPublisherResponseBodyBytes": 0,
        "originalReceiptHttpEvents": [accepted[path][1] for path in paths],
        "meaning": "Original fetch cost belongs to the retained consumer receipt. This local import is not another HTTP transfer or new execution evidence. Admission remains separate.",
    }
    (output / "reuse-report.json").write_text(json.dumps(report, indent=2) + "\n")
    return snapshot, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("previous", "session", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--path", action="append", required=True)
    parser.add_argument("--trusted-events-sha256", required=True)
    parser.add_argument("--trusted-traffic-sha256", required=True)
    args = parser.parse_args()
    _, report = reuse(
        args.previous,
        args.session,
        args.output,
        paths=args.path,
        trusted_events_sha256=args.trusted_events_sha256,
        trusted_traffic_sha256=args.trusted_traffic_sha256,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
