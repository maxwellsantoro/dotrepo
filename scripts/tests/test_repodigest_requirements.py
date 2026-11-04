"""Reviewed requirement checks: binding, scope, conflicts and actual MCP."""

import gzip
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures/repodigest"
sys.path.insert(0, str(ROOT / "scripts"))
import repodigest_requirements as requirements  # noqa: E402
import repodigest_store as store  # noqa: E402
from repodigest_acquire import canonical, sha  # noqa: E402
from repodigest_service import registry  # noqa: E402

SOURCE = FIXTURES / "repodigest-discovery100-comparison-20261030/acquisition/microsoft__markitdown"
COMPONENT = "packages/markitdown"


def input_files(directory, request, name="assessment", value=True):
    manifest = SOURCE / "files/packages/markitdown/pyproject.toml"
    number = next(
        n
        for n, line in enumerate(manifest.read_text().splitlines(), 1)
        if line.startswith("requires-python")
    )
    assessment = {
        "target": request,
        "claims": [
            {
                "key": "python.declared-3-12",
                "value": value,
                "basis": "source-analysis",
                "reason": "3.12 lies within the declared >=3.10,<3.15 range.",
                "limitations": "Synthetic test assessment; declaration only, not execution.",
                "evidence": [
                    {
                        "path": "packages/markitdown/pyproject.toml",
                        "sha256": sha(manifest.read_bytes()),
                        "startLine": number,
                        "endLine": number,
                    }
                ],
            }
        ],
    }
    path = directory / (name + ".json")
    path.write_bytes(canonical(assessment))
    review = directory / (name + "-review.json")
    review.write_bytes(
        canonical(
            {
                "approved": True,
                "assessmentSha256": sha(path.read_bytes()),
                "reviewer": "synthetic test fixture",
            }
        )
    )
    return path, review


@pytest.fixture(scope="module")
def admitted(tmp_path_factory):
    directory = tmp_path_factory.mktemp("requirements")
    source = directory / "source"
    shutil.copytree(SOURCE, source)
    (source / "tree.json").write_bytes(gzip.decompress((SOURCE / "tree.json.gz").read_bytes()))
    database = directory / "store.sqlite"
    store.ingest(source, database, directory / "source-admission", ROOT / "target/debug/dotrepo")
    snapshot = json.loads((source / "snapshot.json").read_text())
    request = {
        "repository": snapshot["repository"],
        "revision": snapshot["revision"],
        "component": COMPONENT,
    }
    assessment, review = input_files(directory, request)
    receipt = requirements.admit(database, assessment, review)
    return database, request, receipt


@pytest.fixture
def database(admitted, tmp_path):
    original, request, receipt = admitted
    path = tmp_path / "store.sqlite"
    shutil.copy2(original, path)
    return path, request, receipt


def test_three_states_and_no_lookup_source_replay(database, monkeypatch):
    path, request, _ = database
    reader = store.Store(path)
    requirements.policy_id()
    monkeypatch.setattr(
        requirements.Reader, "body", lambda *a: pytest.fail("lookup replayed source")
    )
    monkeypatch.setattr(Path, "read_bytes", lambda *a: pytest.fail("lookup read evidence files"))
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("lookup executed process"))
    result = requirements.qualify(
        reader,
        [request],
        [
            {"key": "python.declared-3-12", "expected": True},
            {"key": "python.declared-3-12", "expected": False},
            {"key": "external.libreoffice.required", "expected": False},
        ],
    )
    findings = result["candidates"][0]["findings"]
    assert [f["status"] for f in findings] == ["supported", "contradicted", "unknown"]
    assert findings[0]["assessments"][0]["evidence"][0]["path"].endswith("pyproject.toml")
    assert "silence" in findings[2]["reason"]
    assert result["authorized"] == "not-granted" and len(canonical(result)) <= requirements.MAX_BODY
    reader.close()


def test_scope_revision_and_reader_policy_changes_abstain(database, monkeypatch):
    path, request, _ = database
    reader = store.Store(path)
    conditions = [{"key": "python.declared-3-12", "expected": True}]
    for changed in ({**request, "revision": "a" * 40}, {**request, "component": "."}):
        assert (
            requirements.qualify(reader, [changed], conditions)["candidates"][0]["findings"][0][
                "status"
            ]
            == "unknown"
        )
    monkeypatch.setattr(requirements, "policy_id", lambda: "new-reader-policy")
    assert (
        requirements.qualify(reader, [request], conditions)["candidates"][0]["findings"][0][
            "status"
        ]
        == "unknown"
    )
    reader.close()


def test_conflicts_are_unknown(database, tmp_path):
    path, request, _ = database
    assessment, review = input_files(tmp_path, request, value=False)
    requirements.admit(path, assessment, review)
    reader = store.Store(path)
    result = requirements.qualify(
        reader, [request], [{"key": "python.declared-3-12", "expected": True}]
    )
    finding = result["candidates"][0]["findings"][0]
    assert finding["status"] == "unknown" and "conflicting" in finding["reason"]
    assert len(finding["assessments"]) == 2
    reader.close()


def test_corruption_refuses_and_original_review_is_retained(database):
    path, request, receipt = database
    db = sqlite3.connect(path)
    raw = db.execute(
        "SELECT body FROM objects WHERE digest=?", (receipt["assessmentRecordSha256"],)
    ).fetchone()[0]
    capsule = json.loads(raw)
    for digest in (capsule["assessmentSha256"], capsule["reviewSha256"]):
        assert (
            sha(db.execute("SELECT body FROM objects WHERE digest=?", (digest,)).fetchone()[0])
            == digest
        )
    db.execute("DROP TRIGGER objects_no_update")
    with db:
        db.execute(
            "UPDATE objects SET body=? WHERE digest=?", (b"{}", receipt["assessmentRecordSha256"])
        )
    db.close()
    reader = store.Store(path)
    result = requirements.qualify(
        reader, [request], [{"key": "python.declared-3-12", "expected": True}]
    )
    assert result["candidates"][0]["findings"][0]["status"] == "unknown"
    assert result["candidates"][0]["missingEvidence"] == ["assessment record integrity failure"]
    reader.close()


@pytest.mark.parametrize("mutation", ["review", "source", "range"])
def test_unbound_reviews_and_references_are_rejected(database, tmp_path, mutation):
    path, request, _ = database
    assessment, review = input_files(tmp_path, request)
    data = json.loads(assessment.read_text())
    if mutation == "review":
        review.write_text('{"approved":false}')
    else:
        data["claims"][0]["evidence"][0]["sha256" if mutation == "source" else "endLine"] = (
            "0" * 64 if mutation == "source" else 9000
        )
        assessment.write_bytes(canonical(data))
        review.write_bytes(
            canonical(
                {
                    "approved": True,
                    "assessmentSha256": sha(assessment.read_bytes()),
                    "reviewer": "synthetic fixture",
                }
            )
        )
    with pytest.raises(ValueError):
        requirements.admit(path, assessment, review)


def test_opt_in_and_actual_mcp(database):
    path, request, _ = database
    reader = store.Store(path)
    assert "dotrepo.decision.qualify" not in registry(reader)
    assert "dotrepo.decision.qualify" in registry(reader, requirements=True)
    reader.close()
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "dotrepo.decision.describe",
                "arguments": {"repository": request["repository"]},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "dotrepo.decision.qualify",
                "arguments": {
                    "candidates": [request],
                    "requirements": [{"key": "python.declared-3-12", "expected": True}],
                },
            },
        },
    ]
    done = subprocess.run(
        [
            "uv",
            "run",
            "--offline",
            "--no-sync",
            "python",
            str(ROOT / "scripts/repodigest_service.py"),
            "--database",
            str(path),
            "--allow-requirement-assessments",
        ],
        input="".join(json.dumps(m) + "\n" for m in messages),
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert done.returncode == 0, done.stderr
    described = json.loads(json.loads(done.stdout.splitlines()[1])["result"]["content"][0]["text"])
    assert any(
        k["component"] == COMPONENT and "python.declared-3-12" in k["claimKeys"]
        for k in described["requirementKnowledge"]
    )
    result = json.loads(json.loads(done.stdout.splitlines()[2])["result"]["content"][0]["text"])
    assert result["candidates"][0]["findings"][0]["status"] == "supported"


def test_metadata_front_door_and_scoped_assessment_keys(database):
    path, request, _ = database
    reader = store.Store(path)

    class Metadata:
        def find(self, query, *, mode, **kwargs):
            assert query == "document conversion" and mode == "metadata"
            return {"repositories": [{"repository": request["repository"]}], "mode": mode}

        def describe(self, repository, *, mode):
            assert repository == request["repository"] and mode == "metadata"
            return {"metadata": {"repository": repository, "description": "Retained catalog"}}

    tools = registry(reader, metadata=Metadata(), requirements=True)
    schema, find = tools["dotrepo.decision.find"]
    assert set(schema["inputSchema"]["properties"]) == {"query", "limit", "language"}
    assert find("document conversion")["mode"] == "metadata"
    described = tools["dotrepo.decision.describe"][1]("https://github.com/Microsoft/MarkItDown/")
    assert described["metadata"]["repository"] == request["repository"]
    assert any(
        k["component"] == COMPONENT and k["claimKeys"] == ["python.declared-3-12"]
        for k in described["requirementKnowledge"]
    )
    reader.close()


def test_record_check_time_does_not_invalidate_unchanged_sources(database):
    path, request, _ = database
    db = sqlite3.connect(path)
    digest, raw = db.execute(
        "SELECT r.digest,r.body FROM records r JOIN versions v ON r.digest=v.digest "
        "WHERE v.identity=? AND v.revision=? AND v.component=?",
        tuple(request.values()),
    ).fetchone()
    record = json.loads(raw)
    record["checkedAt"] = "2099-01-01T00:00:00Z"
    changed = canonical(record)
    with db:
        db.execute("INSERT INTO records VALUES(?,?)", (sha(changed), changed))
        db.execute(
            "UPDATE versions SET digest=? WHERE identity=? AND revision=? AND component=?",
            (sha(changed), *request.values()),
        )
    assert sha(changed) != digest
    db.close()
    reader = store.Store(path)
    finding = requirements.qualify(
        reader, [request], [{"key": "python.declared-3-12", "expected": True}]
    )["candidates"][0]["findings"][0]
    assert finding["status"] == "supported" and finding["sourceStatus"] == "current"
    assert finding["assessments"][0]["sourceStatus"] == "current"
    reader.close()


@pytest.mark.parametrize("source_state", ["changed", "unknown"])
def test_declared_source_status_is_separate_from_requirement_outcome(
    database, monkeypatch, source_state
):
    path, request, _ = database
    original = requirements.Reader.index

    def changed_index(self, *args):
        repo, receipt, index, checked = original(self, *args)
        index = json.loads(json.dumps(index))
        entry = index["files"]["packages/markitdown/pyproject.toml"]
        entry["sourceSha256"] = "f" * 64 if source_state == "changed" else None
        return repo, receipt, index, checked

    monkeypatch.setattr(requirements.Reader, "index", changed_index)
    reader = store.Store(path)
    finding = requirements.qualify(
        reader, [request], [{"key": "python.declared-3-12", "expected": True}]
    )["candidates"][0]["findings"][0]
    assert finding["status"] == "unknown"
    assert finding["sourceStatus"] == source_state
    assert finding["assessments"][0]["sourceStatus"] == source_state
    reader.close()


def test_missing_retained_body_cannot_support_assessment(database):
    path, request, _ = database
    with sqlite3.connect(path) as db:
        # Simulate loss/corruption of the copied fixture store, outside the
        # normal immutable admission writer.
        db.execute("DROP TRIGGER source_blobs_no_delete")
        db.execute("DELETE FROM source_blobs")
    reader = store.Store(path)
    finding = requirements.qualify(
        reader, [request], [{"key": "python.declared-3-12", "expected": True}]
    )["candidates"][0]["findings"][0]
    assert finding["status"] == "unknown" and finding["sourceStatus"] == "unknown"
    reader.close()


def test_new_admitted_revision_reuses_only_unchanged_declared_sources(database):
    path, request, _ = database
    newer = {**request, "revision": "b" * 40}
    # A new commit can retain the same tree. Admit that exact revision's source
    # inventory independently; the older assessment remains immutable.
    with sqlite3.connect(path) as db:
        rows = db.execute(
            "SELECT v.component,r.body FROM versions v JOIN records r ON r.digest=v.digest WHERE v.identity=? AND v.revision=?",
            (request["repository"], request["revision"]),
        ).fetchall()
        for component, raw in rows:
            record = json.loads(raw)
            admission = json.loads(
                db.execute(
                    "SELECT body FROM admissions WHERE digest=?", (record["admissionSha256"],)
                ).fetchone()[0]
            )
            index = json.loads(
                db.execute(
                    "SELECT body FROM objects WHERE digest=?", (admission["sourceIndexSha256"],)
                ).fetchone()[0]
            )
            index["revision"] = newer["revision"]
            index_raw = canonical(index)
            db.execute("INSERT OR IGNORE INTO objects VALUES(?,?)", (sha(index_raw), index_raw))
            admission.update(revision=newer["revision"], sourceIndexSha256=sha(index_raw))
            admission_raw = canonical(admission)
            db.execute(
                "INSERT OR IGNORE INTO admissions VALUES(?,?)", (sha(admission_raw), admission_raw)
            )
            record.update(revision=newer["revision"], admissionSha256=sha(admission_raw))
            body = canonical(record)
            db.execute("INSERT INTO records VALUES(?,?)", (sha(body), body))
            db.execute(
                "INSERT INTO versions VALUES(?,?,?,?)",
                (newer["repository"], newer["revision"], component, sha(body)),
            )
        db.execute(
            "UPDATE current SET revision=? WHERE identity=?",
            (newer["revision"], newer["repository"]),
        )
    reader = store.Store(path)
    finding = requirements.qualify(
        reader, [newer], [{"key": "python.declared-3-12", "expected": True}]
    )["candidates"][0]["findings"][0]
    assert finding["status"] == "supported" and finding["sourceStatus"] == "current"
    assert finding["assessments"][0]["assessedRevision"] == request["revision"]
    reader.close()


@pytest.mark.parametrize(
    "candidates,conditions",
    [
        ([], [{"key": "python.declared-3-12", "expected": True}]),
        ([None] * 5, [{"key": "python.declared-3-12", "expected": True}]),
        ([None], [{"key": "python.declared-3-12", "expected": True}] * 9),
        ([None], [{"key": "python.declared-3-12", "expected": 1}]),
    ],
)
def test_request_bounds_are_enforced(database, candidates, conditions):
    path, _, _ = database
    reader = store.Store(path)
    with pytest.raises(ValueError):
        requirements.qualify(reader, candidates, conditions)
    reader.close()
