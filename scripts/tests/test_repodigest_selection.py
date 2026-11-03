"""Complete bounded decisions, including misses, conflicts and unfinished attempts."""

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import test_repodigest_requirements as fixtures  # noqa: E402
from test_repodigest_requirements import input_files  # noqa: E402
import repodigest_requirements as assessments  # noqa: E402
from repodigest_selection import Selection, knowledge, with_limit  # noqa: E402
from repodigest_acquire import canonical  # noqa: E402
from repodigest_service import registry  # noqa: E402
from repodigest_store import Store  # noqa: E402


@pytest.fixture(scope="module")
def selection_source(tmp_path_factory):
    return fixtures.admitted.__wrapped__(tmp_path_factory)


@pytest.fixture
def database(selection_source, tmp_path):
    original, request, receipt = selection_source
    path = tmp_path / "store.sqlite"
    shutil.copy2(original, path)
    return path, request, receipt


def workflow(path, request, find=None):
    store = Store(path)
    describe = registry(store, requirements=True)["repodigest.describe"][1]
    if find is None:

        def find(**kw):
            return {"repositories": [{"repository": request["repository"]}]}

    return store, Selection(store, find, describe)


def test_keys_are_visible_without_manifest_component_pagination(database):
    path, request, _ = database
    store = Store(path)
    tools = registry(store, requirements=True)
    result = tools["repodigest.describe"][1](repository=request["repository"], limit=1)
    assert request["component"] not in result["components"]
    assert result["nextOffset"] is not None
    assert result["requirementKnowledge"][0]["component"] == request["component"]
    assert result["requirementKnowledge"][0]["claimKeys"] == ["python.declared-3-12"]
    assert result["requirementKnowledgeNextOffset"] is None
    store.close()


def test_exact_revision_describe_never_borrows_current_assessments(database):
    path, request, _ = database
    store = Store(path)
    describe = registry(store, requirements=True)["repodigest.describe"][1]
    result = describe(repository=request["repository"], revision=request["revision"])
    assert result["indexedRevision"] == request["revision"]
    missing = describe(repository=request["repository"], revision="a" * 40)
    assert missing["state"] == "unavailable" and not missing["requirementKnowledge"]
    assert missing["requestedRevision"] == "a" * 40
    store.close()
    # Previously admitted revisions remain inspectable after the current pointer advances.
    db = sqlite3.connect(path)
    with db:
        db.execute("UPDATE current SET revision=?", ("a" * 40,))
    db.close()
    store = Store(path)
    historical = registry(store, requirements=True)["repodigest.describe"][1](
        repository=request["repository"], revision=request["revision"]
    )
    assert historical["indexedRevision"] == request["revision"]
    assert historical["currentIndexedRevision"] == "a" * 40
    assert historical["requirementKnowledge"]
    store.close()


def test_oversized_limits_are_explicitly_capped_and_bad_types_refuse(database):
    called = []
    call = with_limit(lambda **args: called.append(args) or {"paths": []}, 100)
    assert call(limit=200)["limitAdjustment"] == {"requested": 200, "applied": 100}
    assert called == [{"limit": 100}]
    for value in (True, -1, 0, "100"):
        with pytest.raises(ValueError, match="positive integer"):
            call(limit=value)
    path, request, _ = database
    store = Store(path)
    described = registry(store, requirements=True)["repodigest.describe"][1](
        repository=request["repository"], limit=200
    )
    assert described["limitAdjustment"]["applied"] == 50
    store.close()


@pytest.mark.parametrize(
    "requirements,unmapped,expected",
    [
        ([{"key": "python.declared-3-12", "expected": True}], [], "preliminary-selection"),
        ([{"key": "python.declared-3-12", "expected": False}], [], "none-established"),
        ([{"key": "external.libreoffice.required", "expected": False}], [], "none-established"),
        (
            [{"key": "python.declared-3-12", "expected": True}],
            ["works offline"],
            "none-established",
        ),
        ([], [], "none-established"),
    ],
)
def test_complete_selection_preserves_requirement_boundaries(
    database, requirements, unmapped, expected
):
    path, request, _ = database
    store, selection = workflow(path, request)
    lead = selection.shortlist(["document conversion"])
    assert lead["repositories"][0]["requirementKnowledge"]
    result = selection.decide(lead["selectionId"], [request], requirements, unmapped)
    assert result["disposition"] == expected and result["authorized"] == "not-granted"
    assert result["state"] == "completed"
    assert selection.status()["completed"] == 1 and selection.status()["unfinished"] == []
    with pytest.raises(ValueError, match="already finalized"):
        selection.decide(lead["selectionId"], [request], requirements)
    store.close()


def test_conflicting_assessments_never_become_preliminary_selection(database, tmp_path):
    path, request, _ = database
    assessment, review = input_files(tmp_path, request, value=False)
    assessments.admit(path, assessment, review)
    store, selection = workflow(path, request)
    started = selection.shortlist(["document"])
    result = selection.decide(
        started["selectionId"], [request], [{"key": "python.declared-3-12", "expected": True}]
    )
    assert result["disposition"] == "none-established"
    assert result["candidates"][0]["findings"][0]["status"] == "unknown"
    assert len(result["candidates"][0]["findings"][0]["assessments"]) == 2
    store.close()


def test_absent_projects_stop_and_unfinished_attempts_stay_in_ledger(database):
    path, request, _ = database
    calls = []
    store, selection = workflow(
        path, request, lambda **kw: calls.append(kw) or {"repositories": []}
    )
    first = selection.shortlist(["missing project"])
    again = selection.shortlist([" MISSING  PROJECT "], selectionId=first["selectionId"])
    assert len(calls) == 1 and again["reusedQueries"] == 1
    stopped = selection.shortlist(
        ["absent one", "absent two", "absent three"], first["selectionId"]
    )
    assert len(calls) == 3 and stopped["remainingQueries"] == 0
    selection.shortlist(["deliberately unfinished"])
    final = selection.decide(first["selectionId"], [], [], ["suitable local application"])
    assert final["disposition"] == "none-established"
    assert "does not prove" in final["meaning"]
    status = selection.status()
    assert status["attempts"] == 2 and status["completed"] == 1
    assert status["unfinished"] == ["selection-2"]
    store.close()


def test_failures_and_invalid_decisions_are_not_dropped(database):
    path, request, _ = database

    def failed(**kw):
        raise ValueError("metadata unavailable")

    store, selection = workflow(path, request, failed)
    first = selection.shortlist(["document"])
    assert first["searches"][0]["state"] == "failed"
    with pytest.raises(ValueError, match="not in this selection"):
        selection.decide(first["selectionId"], [request], [])
    assert selection.status()["unfinished"] == [first["selectionId"]]
    result = selection.decide(first["selectionId"], [], [])
    assert result["searches"][0]["error"] == "metadata unavailable"
    assert selection.status()["failedSearchCalls"] == 1
    store.close()


def test_actual_stdio_shortlist_decide_and_unfinished_accounting(database):
    path, request, _ = database
    calls = [
        ("repodigest.shortlist", {"queries": ["markitdown"]}),
        (
            "repodigest.describe",
            {"repository": request["repository"], "revision": request["revision"], "limit": 200},
        ),
        (
            "repodigest.decide",
            {
                "selectionId": "selection-1",
                "candidates": [request],
                "requirements": [{"key": "python.declared-3-12", "expected": True}],
            },
        ),
        ("repodigest.shortlist", {"queries": ["unfindablexyz"]}),
        ("repodigest.selection_status", {}),
    ]
    messages = [{"jsonrpc": "2.0", "id": 1, "method": "initialize"}]
    messages.extend(
        {
            "jsonrpc": "2.0",
            "id": index + 2,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        }
        for index, (name, args) in enumerate(calls)
    )
    done = subprocess.run(
        [
            "uv",
            "run",
            "--offline",
            "--no-sync",
            "python",
            "scripts/repodigest_service.py",
            "--database",
            str(path),
            "--allow-requirement-assessments",
            "--compiled-sources",
        ],
        cwd=ROOT,
        input="".join(json.dumps(message) + "\n" for message in messages),
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert done.returncode == 0, done.stderr
    rows = [json.loads(line) for line in done.stdout.splitlines()][1:]
    assert all("result" in row for row in rows), rows
    results = [json.loads(row["result"]["content"][0]["text"]) for row in rows]
    assert results[0]["repositories"][0]["repository"] == request["repository"]
    assert results[1]["limitAdjustment"]["applied"] == 50
    assert results[2]["disposition"] == "preliminary-selection"
    assert results[-1]["attempts"] == 2 and results[-1]["unfinished"] == ["selection-2"]


def test_key_page_progress_and_all_views_remain_bounded(database, monkeypatch):
    path, request, _ = database
    store = Store(path)
    monkeypatch.setattr(assessments, "available", lambda *a: {"claimKeys": ["x" * 8060]})
    page = knowledge(store, request["repository"], request["revision"])
    assert len(canonical(page)) <= 8192
    assert page["requirementKnowledgeNextOffset"] is None
    assert page["requirementKnowledge"][0]["missingEvidence"]
    store.close()
    store, selection = workflow(path, request)
    for language in ("X" * 40000, [], True):
        with pytest.raises(ValueError, match="unsupported language"):
            selection.shortlist(["project"], language=language)
    assert selection.status()["attempts"] == 0
    selection.find = lambda **kw: {
        "repositories": [{"repository": f"github.com/fixture/repo{n}"} for n in range(4)]
    }
    selection.describe = lambda **kw: {"requirementKnowledge": [{"claimKeys": ["x" * 7950]}]}
    result = selection.shortlist(["a" * 200, "b" * 200, "c" * 200])
    assert len(canonical(result)) <= 32768
    assert len(canonical(selection.status(result["selectionId"]))) <= 32768
    store.close()


def test_later_precise_query_can_change_shortlist(database):
    path, request, _ = database

    def find(query, **kw):
        repos = (
            [request["repository"]]
            if query == "precise"
            else [f"github.com/fixture/r{n}" for n in range(4)]
        )
        return {"repositories": [{"repository": repo} for repo in repos]}

    store, selection = workflow(path, request, find)
    broad = selection.shortlist(["broad"])
    refined = selection.shortlist(["precise"], broad["selectionId"])
    assert len(refined["repositories"]) == 4
    assert request["repository"] in {item["repository"] for item in refined["repositories"]}
    result = selection.decide(
        broad["selectionId"], [request], [{"key": "python.declared-3-12", "expected": True}]
    )
    assert result["disposition"] == "preliminary-selection"
    store.close()


def test_followup_inherits_language_and_refuses_changed_scope(database):
    path, request, _ = database
    calls = []
    store, selection = workflow(
        path, request, lambda **kw: calls.append(kw) or {"repositories": []}
    )
    first = selection.shortlist(["http client"], language="Python")
    followup = selection.shortlist(["async client"], selectionId=first["selectionId"])
    assert followup["language"] == "Python" and calls[-1]["language"] == "Python"
    with pytest.raises(ValueError, match="original language"):
        selection.shortlist(["another"], selectionId=first["selectionId"], language="Rust")
    assert len(calls) == 2
    store.close()
