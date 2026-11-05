"""Durable, offline source decision workflow over an explicitly admitted store.

This command retains tool results and selection accounting, not inferred answers.
The source store remains read-only; a saved decision is a historical observation.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import repodigest_requirements as assessments
from repodigest_acquire import canonical, sha
from repodigest_cached_tools import CachedSources
from repodigest_selection import MAX_SELECTIONS, Selection
from repodigest_service import registry
from repodigest_store import Store, stamp

FORMAT = "dotrepo-decision-source/1"
STATE_NAME = "workflow.sqlite3"
MAX_REQUEST = 65536
MAX_STATE = 2 * 1024 * 1024
MAX_EVENTS = 256
MAX_LEDGER = 16 * 1024 * 1024
TOOLS = (
    "find",
    "shortlist",
    "describe",
    "qualify",
    "decide",
    "selection_status",
    "source.list",
    "source.read",
)


def database_digest(path):
    """Pin the ordinary SQLite file; no concurrent admission/WAL writer is supported."""
    if (
        path.is_symlink()
        or not path.is_file()
        or any(Path(str(path) + suffix).exists() for suffix in ("-wal", "-journal"))
    ):
        raise ValueError("source database missing, unsafe or has a journal; use a frozen store")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def decode(raw):
    """Refuse duplicate object keys and non-JSON numeric extensions."""

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result

    def constant(value):
        raise ValueError("invalid JSON number: " + value)

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def assessment_bindings(store, result):
    """Retain the original source date omitted by the compact qualification view."""
    digests = set()

    def visit(value):
        if isinstance(value, dict):
            digest = value.get("assessmentRecordSha256")
            if isinstance(digest, str):
                digests.add(digest)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(result)
    bindings = []
    for digest in sorted(digests):
        row = store.db.execute("SELECT body FROM objects WHERE digest=?", (digest,)).fetchone()
        if not row or sha(row[0]) != digest:
            raise ValueError("assessment binding integrity failure")
        capsule = decode(row[0])
        bindings.append(
            {
                "assessmentRecordSha256": digest,
                "target": capsule["target"],
                "sourceCheckedAt": capsule["sourceCheckedAt"],
                "sourceRecordSha256": capsule["sourceRecordSha256"],
                "sourcePolicySha256": capsule["sourcePolicySha256"],
                "policySha256": capsule["policySha256"],
            }
        )
    return bindings


def connect(workspace, *, writable=False):
    path = workspace / STATE_NAME
    if not path.is_file() or path.is_symlink():
        raise ValueError("workspace is missing or unsafe; run init for a new workspace")
    mode = "rw" if writable else "ro"
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=" + mode, uri=True, timeout=5)
    try:
        row = db.execute(
            "SELECT format,database_path,database_sha256,store_policy,requirements_policy "
            "FROM metadata WHERE id=1"
        ).fetchone()
        if row is None or row[0] != FORMAT:
            raise ValueError("unsupported or corrupt workspace format; preserve it for recovery")
        return db, row[1], row[2], {"store": row[3], "requirements": row[4]}
    except BaseException:
        db.close()
        raise


def read_state(db):
    row = db.execute("SELECT body,digest FROM state WHERE id=1").fetchone()
    if row is None or len(row[0]) > MAX_STATE or sha(row[0]) != row[1]:
        raise ValueError("corrupt workspace state; restore a verified workspace backup")
    sessions = decode(row[0])
    if not isinstance(sessions, dict) or len(sessions) > MAX_SELECTIONS:
        raise ValueError("invalid saved selection state")
    if set(sessions) != {f"selection-{index}" for index in range(1, len(sessions) + 1)}:
        raise ValueError("invalid saved selection IDs")
    for key, session in sessions.items():
        if (
            not isinstance(session, dict)
            or session.get("selectionId") != key
            or session.get("state") not in {"unfinished", "completed"}
            or not isinstance(session.get("searches"), list)
            or len(session["searches"]) > 3
            or not isinstance(session.get("repositories"), list)
            or not isinstance(session.get("leadGroups"), list)
            or (session["state"] == "completed" and not isinstance(session.get("decision"), dict))
        ):
            raise ValueError("invalid saved selection state")
    return sessions


def read_events(db):
    """Check all bounded history before either returning it or extending the workspace."""
    events, size = [], 0
    for sequence, body, digest in db.execute(
        "SELECT sequence,body,digest FROM events ORDER BY sequence"
    ):
        if (
            sequence != len(events) + 1
            or len(events) >= MAX_EVENTS
            or not isinstance(body, bytes)
            or len(body) > MAX_LEDGER - size
            or sha(body) != digest
        ):
            raise ValueError("corrupt saved call ledger; restore a verified workspace backup")
        event = decode(body)
        if not isinstance(event, dict) or event.get("state") not in {"completed", "failed"}:
            raise ValueError("invalid saved call ledger")
        size += len(body)
        events.append(event)
    return events, size


def init(workspace, database):
    if database.is_symlink():
        raise ValueError("choose a regular frozen source database, not a symlink")
    database = database.resolve()
    digest, size = database_digest(database)
    # Store uses SQLite read-only mode, so absence cannot create a new empty catalog.
    store = Store(database)
    try:
        store.db.execute("SELECT 1 FROM records LIMIT 1")
        if store.db.execute("PRAGMA journal_mode").fetchone()[0] == "wal":
            raise ValueError("WAL source databases require a separate frozen rollback-journal copy")
        policies = {"store": store.policy, "requirements": assessments.policy_id()}
    finally:
        store.close()
    workspace.mkdir(parents=True, exist_ok=False)
    path = workspace / STATE_NAME
    db = sqlite3.connect(path)
    try:
        with db:
            db.executescript(
                "CREATE TABLE metadata(id INTEGER PRIMARY KEY CHECK(id=1),format TEXT,"
                "database_path TEXT,database_sha256 TEXT,store_policy TEXT,"
                "requirements_policy TEXT,created_at TEXT);"
                "CREATE TABLE state(id INTEGER PRIMARY KEY CHECK(id=1),body BLOB,digest TEXT);"
                "CREATE TABLE events(sequence INTEGER PRIMARY KEY,body BLOB,digest TEXT);"
                "CREATE TRIGGER events_no_update BEFORE UPDATE ON events BEGIN "
                "SELECT RAISE(ABORT,'saved calls are immutable'); END;"
                "CREATE TRIGGER events_no_delete BEFORE DELETE ON events BEGIN "
                "SELECT RAISE(ABORT,'saved calls are immutable'); END;"
            )
            db.execute(
                "INSERT INTO metadata VALUES(1,?,?,?,?,?,?)",
                (
                    FORMAT,
                    str(database),
                    digest,
                    policies["store"],
                    policies["requirements"],
                    stamp(),
                ),
            )
            body = canonical({})
            db.execute("INSERT INTO state VALUES(1,?,?)", (body, sha(body)))
    finally:
        db.close()
    return {
        "format": FORMAT,
        "workspace": str(workspace.resolve()),
        "database": str(database),
        "databaseSha256": digest,
        "storeIntegrityBytesRead": size,
    }


def call(workspace, tool, request):
    if tool not in TOOLS or not isinstance(request, dict):
        raise ValueError("choose an advertised tool and a JSON object request")
    if len(canonical(request)) > MAX_REQUEST:
        raise ValueError("request exceeds 64 KiB")
    db, database, expected_digest, expected_policies = connect(workspace, writable=True)
    store = None
    try:
        db.execute("BEGIN IMMEDIATE")
        sessions = read_state(db)
        events, ledger_size = read_events(db)
        count = len(events)
        # Reserve enough for a bounded request/result/failure record before doing work.
        if count >= MAX_EVENTS or ledger_size + 2 * MAX_REQUEST + 4096 > MAX_LEDGER:
            raise ValueError("workspace call ledger is full; preserve it and init a new workspace")
        old = copy.deepcopy(sessions)
        event = {"tool": tool, "request": request, "recordedAt": stamp()}
        sources = None
        try:
            digest, size = database_digest(Path(database))
            event["storeIntegrityBytesRead"] = size
            if digest != expected_digest:
                raise ValueError(
                    "source database changed; restore exact bytes or init a new workspace"
                )
            store = Store(Path(database))
            store.db.execute("BEGIN")
            current_policies = {"store": store.policy, "requirements": assessments.policy_id()}
            if current_policies != expected_policies:
                raise ValueError(
                    "reader policy changed; preserve old results and init a new workspace"
                )
            sources = CachedSources(store)
            tools = registry(store, requirements=True, sources=sources)
            selection = Selection(
                store, tools["dotrepo.decision.find"][1], tools["dotrepo.decision.describe"][1]
            )
            selection.sessions = sessions
            functions = {name.rsplit(".", 1)[-1]: fn for name, (_, fn) in tools.items()}
            functions.update(
                {
                    "shortlist": selection.shortlist,
                    "decide": selection.decide,
                    "selection_status": selection.status,
                    "source.list": tools["source.list"][1],
                    "source.read": tools["source.read"][1],
                }
            )
            event["policies"] = current_policies
            result = functions[tool](**request)
            if len(canonical(result)) > MAX_REQUEST:
                raise ValueError("tool result exceeds 64 KiB; narrow the request")
            event.update(state="completed", result=result)
            event["assessmentBindings"] = assessment_bindings(store, result)
            digest, size = database_digest(Path(database))
            event["storeIntegrityBytesRead"] += size
            if digest != expected_digest:
                sessions.clear()
                sessions.update(old)
                raise ValueError("source database changed during call; restore it before retrying")
        except (
            OSError,
            sqlite3.Error,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            OverflowError,
            RecursionError,
        ) as error:
            event.pop("result", None)
            event.update(state="failed", error=str(error)[:1000])
        if sources is not None and tool.startswith("source."):
            event["sourceAccounting"] = {
                "retrievals": sources.retrievals,
                "cacheStatistics": sources.reader.stats,
            }
        for key, prior in old.items():
            if prior["state"] == "completed" and sessions.get(key) != prior:
                raise ValueError("refusing to alter a completed selection")
        body = canonical(sessions)
        if len(body) > MAX_STATE:
            raise ValueError("selection state exceeds 2 MiB; preserve this workspace")
        db.execute("UPDATE state SET body=?,digest=? WHERE id=1", (body, sha(body)))
        body = canonical(event)
        if ledger_size + len(body) > MAX_LEDGER:
            raise ValueError("call ledger exceeds 16 MiB; preserve this workspace")
        db.execute("INSERT INTO events VALUES(?,?,?)", (count + 1, body, sha(body)))
        db.commit()
        return {"format": FORMAT, "sequence": count + 1, **event}
    finally:
        if store is not None:
            store.close()
        db.close()


def inspect(workspace, selection=None):
    db, database, digest, policies = connect(workspace)
    try:
        db.execute("BEGIN")
        sessions = read_state(db)
        if selection is not None and selection not in sessions:
            raise ValueError("unknown saved selection")
        events, _ = read_events(db)
        return {
            "format": FORMAT,
            "database": database,
            "databaseSha256": digest,
            "policies": policies,
            "selections": {selection: sessions[selection]} if selection else sessions,
            "calls": events,
            "meaning": "Historical saved calls and decisions. Inspection performs no source "
            "revalidation and never renews source observation dates or grants execution authority.",
        }
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=FORMAT)
    commands = parser.add_subparsers(dest="command", required=True)
    first = commands.add_parser("init", help="create a new workspace bound to an admitted store")
    first.add_argument("--workspace", type=Path, required=True)
    first.add_argument("--database", type=Path, required=True)
    invoke = commands.add_parser(
        "call", help="run one offline tool and retain its result or failure"
    )
    invoke.add_argument("--workspace", type=Path, required=True)
    invoke.add_argument("--tool", choices=TOOLS, required=True)
    invoke.add_argument("--request", type=Path, required=True, help="UTF-8 JSON object file")
    saved = commands.add_parser("inspect", help="inspect retained results without the source store")
    saved.add_argument("--workspace", type=Path, required=True)
    saved.add_argument("--selection")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = init(args.workspace, args.database)
        elif args.command == "inspect":
            result = inspect(args.workspace, args.selection)
        else:
            with args.request.open("rb") as stream:
                raw = stream.read(MAX_REQUEST + 1)
            if len(raw) > MAX_REQUEST:
                raise ValueError("request exceeds 64 KiB")
            result = call(args.workspace, args.tool, decode(raw))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get("state") == "failed" else 0
    except (
        OSError,
        sqlite3.Error,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        OverflowError,
        RecursionError,
    ) as error:
        print(json.dumps({"format": FORMAT, "state": "refused", "error": str(error)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
