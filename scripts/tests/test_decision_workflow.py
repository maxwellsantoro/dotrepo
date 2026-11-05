"""Fresh-process durability and refusal controls; synthetic assessments are not utility evidence."""

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import decision_workflow as workflow  # noqa: E402
import test_repodigest_requirements as fixtures  # noqa: E402
from repodigest_acquire import canonical, sha  # noqa: E402


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    return fixtures.admitted.__wrapped__(tmp_path_factory)


@pytest.fixture
def setup(source, tmp_path):
    original, request, _ = source
    database = tmp_path / "source.sqlite"
    shutil.copy2(original, database)
    return database, request, tmp_path / "workspace"


def run(*args, expected=0):
    done = subprocess.run(
        [sys.executable, str(ROOT / "scripts/decision_workflow.py"), *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert done.returncode == expected, (done.stdout, done.stderr)
    assert not done.stderr, done.stderr
    return json.loads(done.stdout)


def invoke(workspace, tool, request, expected=0):
    path = workspace.parent / "request.json"
    path.write_bytes(canonical(request))
    return run(
        "call", "--workspace", workspace, "--tool", tool, "--request", path, expected=expected
    )


def start(setup):
    database, request, workspace = setup
    run("init", "--workspace", workspace, "--database", database)
    return database, request, workspace


def test_fresh_process_decision_and_offline_restart_inspection(setup):
    database, request, workspace = start(setup)
    found = invoke(workspace, "find", {"query": "markitdown"})
    assert found["result"]["repositories"][0]["repository"] == request["repository"]
    lead = invoke(workspace, "shortlist", {"queries": ["markitdown"]})
    assert lead["result"]["selectionId"] == "selection-1"
    described = invoke(workspace, "describe", {"repository": request["repository"]})
    assert described["result"]["requirementKnowledge"][0]["claimKeys"] == ["python.declared-3-12"]
    args = {
        "candidates": [request],
        "requirements": [{"key": "python.declared-3-12", "expected": True}],
    }
    qualified = invoke(workspace, "qualify", args)
    assert qualified["result"]["candidates"][0]["findings"][0]["status"] == "supported"
    decided = invoke(workspace, "decide", {"selectionId": "selection-1", **args})
    assert decided["result"]["disposition"] == "preliminary-selection"
    evidence = decided["result"]["candidates"][0]["findings"][0]["assessments"][0]
    assert evidence["evidence"] and decided["policies"]["requirements"]
    binding = decided["assessmentBindings"][0]
    assert binding["target"]["revision"] == evidence["assessedRevision"]
    assert binding["sourceCheckedAt"] == lead["result"]["repositories"][0]["sourceCheckedAt"]
    assert binding["sourceCheckedAt"] != decided["recordedAt"]
    assert decided["storeIntegrityBytesRead"] == 2 * database.stat().st_size
    before = run("inspect", "--workspace", workspace)
    assert before["databaseSha256"] == sha(database.read_bytes())
    database.unlink()
    after = run("inspect", "--workspace", workspace, "--selection", "selection-1")
    assert after["selections"] == before["selections"]
    assert after["calls"][-1] == before["calls"][-1]
    assert after["selections"]["selection-1"]["decision"] == decided["result"]
    assert "Historical" in after["meaning"]


def test_completed_results_are_immutable_and_failed_attempt_is_retained(setup):
    _, request, workspace = start(setup)
    invoke(workspace, "shortlist", {"queries": ["markitdown"]})
    args = {"selectionId": "selection-1", "candidates": [request], "requirements": []}
    first = invoke(workspace, "decide", args)
    failed = invoke(workspace, "decide", args, expected=2)
    assert "already finalized" in failed["error"]
    saved = run("inspect", "--workspace", workspace)
    assert saved["selections"]["selection-1"]["decision"] == first["result"]
    assert saved["calls"][-1]["state"] == "failed"


def test_restart_honors_search_budget_and_preserves_unknown(setup):
    _, request, workspace = start(setup)
    invoke(workspace, "shortlist", {"queries": ["markitdown"]})
    again = invoke(
        workspace, "shortlist", {"selectionId": "selection-1", "queries": [" MARKITDOWN "]}
    )
    assert again["result"]["reusedQueries"] == 1
    exhausted = invoke(
        workspace, "shortlist", {"selectionId": "selection-1", "queries": ["a", "b", "c"]}
    )
    assert exhausted["result"]["remainingQueries"] == 0
    assert len(exhausted["result"]["searches"]) == 3
    # A fresh selection finds a real target, but an unmapped requirement stays unknown.
    invoke(workspace, "shortlist", {"queries": ["markitdown"]})
    decision = invoke(
        workspace,
        "decide",
        {
            "selectionId": "selection-2",
            "candidates": [request],
            "requirements": [{"key": "external.libreoffice.required", "expected": False}],
        },
    )["result"]
    assert decision["disposition"] == "none-established"
    assert decision["candidates"][0]["findings"][0]["status"] == "unknown"


def test_missing_database_is_not_created_and_exact_restore_recovers(setup):
    database, _, workspace = start(setup)
    original = database.read_bytes()
    database.unlink()
    failed = invoke(workspace, "shortlist", {"queries": ["markitdown"]}, expected=2)
    assert "database missing" in failed["error"]
    assert not database.exists()
    database.write_bytes(original)
    resumed = invoke(workspace, "shortlist", {"queries": ["markitdown"]})
    assert resumed["result"]["selectionId"] == "selection-1"
    assert run("inspect", "--workspace", workspace)["calls"][0]["state"] == "failed"


def test_changed_database_refuses_and_missing_body_is_explicit(setup):
    database, request, workspace = start(setup)
    original = database.read_bytes()
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE unexpected(value TEXT)")
    failed = invoke(workspace, "shortlist", {"queries": ["markitdown"]}, expected=2)
    assert "source database changed" in failed["error"]
    database.write_bytes(original)
    missing = invoke(workspace, "source.read", {**request, "path": "not-present.txt"}, expected=2)
    # component is not a source-tool argument; invalid requests remain failed calls.
    assert "unexpected keyword" in missing["error"]
    source_request = {key: request[key] for key in ("repository", "revision")}
    refused = invoke(
        workspace, "source.read", {**source_request, "path": "not-present.txt"}, expected=2
    )
    assert "path not in pinned source inventory" in refused["error"]
    missing = invoke(
        workspace,
        "source.read",
        {
            **source_request,
            "revision": "a" * 40,
            "path": "packages/markitdown/pyproject.toml",
        },
    )
    assert missing["result"]["state"] == "unavailable"
    recovered = invoke(
        workspace, "source.read", {**source_request, "path": "packages/markitdown/pyproject.toml"}
    )
    assert "3.10" in str(recovered["result"])


def test_corrupt_state_never_resets_or_overwrites_saved_decision(setup):
    _, _, workspace = start(setup)
    invoke(workspace, "shortlist", {"queries": ["markitdown"]})
    with sqlite3.connect(workspace / workflow.STATE_NAME) as db:
        original_events = db.execute("SELECT * FROM events").fetchall()
        db.execute("UPDATE state SET body=? WHERE id=1", (b"broken",))
    refused = invoke(workspace, "shortlist", {"queries": ["markitdown"]}, expected=1)
    assert "corrupt workspace" in refused["error"]
    with sqlite3.connect(workspace / workflow.STATE_NAME) as db:
        assert db.execute("SELECT * FROM events").fetchall() == original_events


def test_corrupt_saved_event_refuses_calls_and_inspection_without_modifying_workspace(setup):
    _, _, workspace = start(setup)
    invoke(workspace, "shortlist", {"queries": ["markitdown"]})
    path = workspace / workflow.STATE_NAME
    # Incremental BLOB writes can corrupt bytes without executing SQL update triggers.
    with sqlite3.connect(path) as db:
        with db.blobopen("events", "body", 1) as blob:
            original = blob.read()
            changed = original.replace(b'"completed"', b'"Completed"', 1)
            assert changed != original
            blob.seek(0)
            blob.write(changed)
    before = path.read_bytes()
    refused = invoke(workspace, "shortlist", {"queries": ["new"]}, expected=1)
    assert "corrupt saved call ledger" in refused["error"]
    assert path.read_bytes() == before
    refused = run("inspect", "--workspace", workspace, expected=1)
    assert "corrupt saved call ledger" in refused["error"]
    assert path.read_bytes() == before


def test_event_sequence_gaps_refuse_before_new_work(setup):
    _, _, workspace = start(setup)
    with sqlite3.connect(workspace / workflow.STATE_NAME) as db:
        body = canonical({"state": "failed", "error": "synthetic gap"})
        db.execute("INSERT INTO events VALUES(?,?,?)", (2, body, sha(body)))
    refused = invoke(workspace, "shortlist", {"queries": ["markitdown"]}, expected=1)
    assert "corrupt saved call ledger" in refused["error"]


def test_call_capacity_and_json_key_refusal_leave_original_state(setup):
    _, _, workspace = start(setup)
    with sqlite3.connect(workspace / workflow.STATE_NAME) as db:
        body = canonical({"state": "failed", "error": "synthetic capacity fixture"})
        db.executemany(
            "INSERT INTO events VALUES(?,?,?)",
            [(i + 1, body, sha(body)) for i in range(workflow.MAX_EVENTS)],
        )
    refused = invoke(workspace, "shortlist", {"queries": ["markitdown"]}, expected=1)
    assert "ledger is full" in refused["error"]
    path = workspace.parent / "bad.json"
    path.write_text('{"queries":["a"],"queries":["b"]}')
    refused = run(
        "call", "--workspace", workspace, "--tool", "shortlist", "--request", path, expected=1
    )
    assert "duplicate JSON key" in refused["error"]
    assert run("inspect", "--workspace", workspace)["selections"] == {}


def test_many_selections_survive_canonical_key_sorting(setup):
    _, _, workspace = start(setup)
    for _ in range(12):
        invoke(workspace, "shortlist", {"queries": ["unfindablexyz"]})
    saved = run("inspect", "--workspace", workspace)
    assert len(saved["selections"]) == 12


def test_source_store_size_is_separate_from_workspace_ledger_bound(setup):
    database, _, workspace = setup
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE large_source_fixture(body BLOB)")
        db.execute("INSERT INTO large_source_fixture VALUES(zeroblob(?))", (17 * 1024 * 1024,))
    run("init", "--workspace", workspace, "--database", database)
    completed = invoke(workspace, "shortlist", {"queries": ["markitdown"]})
    assert completed["state"] == "completed"
    assert completed["storeIntegrityBytesRead"] == 2 * database.stat().st_size


def test_bad_tool_argument_and_nested_json_have_structured_failures(setup):
    _, _, workspace = start(setup)
    failed = invoke(workspace, "describe", {"repository": 123}, expected=2)
    assert failed["state"] == "failed"
    assert run("inspect", "--workspace", workspace)["calls"][-1]["state"] == "failed"
    path = workspace.parent / "nested.json"
    path.write_text("[" * 2000 + "0" + "]" * 2000)
    refused = run(
        "call", "--workspace", workspace, "--tool", "shortlist", "--request", path, expected=1
    )
    assert refused["state"] == "refused"


def test_policy_change_and_wal_refuse_without_reusing_old_shortlist(setup, monkeypatch):
    database, _, workspace = start(setup)
    invoke(workspace, "shortlist", {"queries": ["markitdown"]})
    monkeypatch.setattr(workflow.assessments, "policy_id", lambda: "different-policy")
    failed = workflow.call(workspace, "shortlist", {"selectionId": "selection-1", "queries": ["a"]})
    assert failed["state"] == "failed" and "policy changed" in failed["error"]
    assert len(workflow.inspect(workspace)["selections"]["selection-1"]["searches"]) == 1
    monkeypatch.undo()
    with sqlite3.connect(database) as db:
        assert db.execute("PRAGMA journal_mode=wal").fetchone()[0] == "wal"
    refused = run(
        "init",
        "--workspace",
        workspace.parent / "wal-workspace",
        "--database",
        database,
        expected=1,
    )
    assert "WAL" in refused["error"]
