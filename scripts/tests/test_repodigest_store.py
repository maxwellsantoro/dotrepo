"""Real import/export, compiled lookup, invalidation, and metered source controls."""

from __future__ import annotations

import copy
import hashlib
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
import repodigest_store as store  # noqa: E402
from repodigest_acquire import acquire, canonical, identity, sha  # noqa: E402
from repodigest_observed_cache import admit  # noqa: E402
from repodigest_source_tools import Sources  # noqa: E402

PACKET = FIXTURES / "repodigest-multirepo-service-20261029"
SOURCE = PACKET / "acquisition-001/sindresorhus__p-limit"
SNAPSHOT = json.loads((SOURCE / "snapshot.json").read_text())
REPO = SNAPSHOT["repository"]
REV = SNAPSHOT["revision"]
PILOT = FIXTURES / "digest-exchange-observed-recipe-consumer-pilot-20261029/reader-amendment"
TRUST = "88c72106333af8bdfbf4c5936cf414431d3653825cbf01cff34e1a6712fc46ba"


@pytest.fixture(scope="module")
def admitted(tmp_path_factory):
    root = tmp_path_factory.mktemp("compiled-repodigest")
    db = root / "store.sqlite"
    store.ingest(SOURCE, db, root / "source", ROOT / "target/debug/dotrepo")
    admit(
        PILOT / "capsule.json",
        FIXTURES / "digest-exchange-r1-iniconfig-execution-20261029",
        TRUST,
        db,
        root / "observed",
    )
    return db


@pytest.fixture
def database(admitted, tmp_path):
    path = tmp_path / "store.sqlite"
    shutil.copy2(admitted, path)
    return path


def replace_body(path, mutate):
    db = sqlite3.connect(path)
    old, raw = db.execute(
        "SELECT r.digest,r.body FROM versions v JOIN records r ON r.digest=v.digest WHERE v.identity=?",
        (REPO,),
    ).fetchone()
    body = json.loads(raw)
    mutate(body)
    encoded = canonical(body)
    new = sha(encoded)
    with db:
        db.execute("INSERT OR IGNORE INTO records VALUES(?,?)", (new, encoded))
        db.execute("UPDATE versions SET digest=? WHERE identity=?", (new, REPO))
    db.close()


def test_lookup_never_replays_or_reads_source_receipts(database, monkeypatch):
    reader = store.Store(database)

    def forbidden(*args, **kwargs):
        raise AssertionError("warm lookup attempted expensive work")

    monkeypatch.setattr(store.observed_recipe, "replay", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    result = reader.lookup(REPO, REV, include_leads=True)
    assert result["facts"]["package.json"]["declarations"]["scripts"]["test"] == "xo && ava && tsd"
    assert result["instruction"] is None
    assert result["authorized"] == "not-granted"
    assert [r["repository"] for r in reader.find("p-limit")["repositories"]] == [REPO]
    reader.close()


def test_miss_revision_component_and_policy_abstain(database):
    reader = store.Store(database)
    assert reader.lookup("github.com/unknown/missing", "0" * 40)["missingEvidence"] == [
        "repository-not-indexed"
    ]
    assert "revision-not-qualified" in reader.lookup(REPO, "0" * 40)["missingEvidence"]
    assert reader.lookup(REPO, REV, component="missing")["missingEvidence"] == [
        "component-not-indexed"
    ]
    reader.policy = "new-policy"
    assert reader.lookup(REPO, REV)["missingEvidence"] == [
        "admission-policy-changed-recompile-required"
    ]
    reader.close()


def test_immutable_rows_and_cross_key_pointer_refused(database):
    db = sqlite3.connect(database)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE records SET body='{}'")
    db.rollback()
    other = db.execute("SELECT digest FROM versions WHERE identity!=?", (REPO,)).fetchone()[0]
    with db:
        db.execute("UPDATE versions SET digest=? WHERE identity=?", (other, REPO))
    db.close()
    reader = store.Store(database)
    assert reader.lookup(REPO, REV)["missingEvidence"] == ["compiled-record-key-mismatch"]
    reader.close()


def test_stale_qualified_fixture_is_not_suggested(database):
    replace_body(database, lambda body: body.update(checkedAt="2000-01-01T00:00:00+00:00"))
    reader = store.Store(database)
    assert "source-assessment-stale-or-future" in reader.lookup(REPO, REV)["missingEvidence"]
    reader.close()


def test_cache_integrity_failure_cannot_suggest(database):
    db = sqlite3.connect(database)
    db.execute("DROP TRIGGER records_no_update")
    with db:
        db.execute("UPDATE records SET body='{}'")
    db.close()
    reader = store.Store(database)
    assert reader.lookup(REPO, REV)["missingEvidence"] == ["compiled-record-integrity-failure"]
    reader.close()


def test_observed_cache_matches_original_exact_contract_and_never_authorizes(database, monkeypatch):
    request = json.loads((PILOT / "request.json").read_text())
    reader = store.Store(database)
    monkeypatch.setattr(
        store.observed_recipe,
        "replay",
        lambda *a: (_ for _ in ()).throw(AssertionError("replayed")),
    )
    repo = request["task"]["repository"]
    rev = request["task"]["revision"]
    good = reader.lookup(repo, rev, observed_request=request, opt_in=True)
    assert good["observedRecipe"] is not None and good["authorized"] == "not-granted"
    for field in (
        "task",
        "files",
        "environment",
        "dependencies",
        "acceptedLimitations",
        "requirements",
        "recipeSha256",
    ):
        bad = copy.deepcopy(request)
        bad[field] = None
        assert reader.lookup(repo, rev, observed_request=bad, opt_in=True)["observedRecipe"] is None
    assert (
        reader.lookup(repo, "f" * 40, observed_request=request, opt_in=True)["observedRecipe"]
        is None
    )
    for value in (False, 1, "true", None):
        assert (
            reader.lookup(repo, rev, observed_request=request, opt_in=value)["observedRecipe"]
            is None
        )
    historical = reader.lookup(repo, rev, include_leads=True, opt_in=True)
    assert (
        historical["historicalObservations"][0]["recipe"]["containerWorkingDirectory"]
        == "/work/checkout"
    )
    reader.close()


def test_source_mutation_rejected_before_import(tmp_path):
    source = tmp_path / "source"
    shutil.copytree(SOURCE, source)
    (source / "files/package.json").write_text("{}")
    with pytest.raises(ValueError, match="source bytes changed"):
        store.ingest(source, tmp_path / "db", tmp_path / "out", ROOT / "target/debug/dotrepo")


def test_unchanged_admission_skips_import_but_compiler_change_does_not(
    database, tmp_path, monkeypatch
):
    original = store.export_profiles
    calls = []

    def tracked(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(store, "export_profiles", tracked)
    result = store.ingest(SOURCE, database, tmp_path / "unchanged", ROOT / "target/debug/dotrepo")
    assert result["state"] == "unchanged" and not calls
    fake = tmp_path / "dotrepo"
    fake.write_bytes((ROOT / "target/debug/dotrepo").read_bytes() + b"\0")
    # Different producer identity must not use no-op. Deliberately stop before running a modified binary.
    monkeypatch.setattr(
        store, "export_profiles", lambda *a: (_ for _ in ()).throw(ValueError("recompile-needed"))
    )
    with pytest.raises(ValueError, match="recompile-needed"):
        store.ingest(SOURCE, database, tmp_path / "changed", fake)


@pytest.mark.parametrize(
    "value",
    ["github.com/../repo", "github.com/a/..", "https://example.com/a/b", "github.com/a/b/extra"],
)
def test_repository_paths_rejected(value):
    with pytest.raises(ValueError):
        identity(value)


def test_source_blob_verification_and_named_tree_file_do_not_collide(tmp_path):
    raw = b"public source\n"
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    tree = {
        "sha": "a" * 40,
        "tree": [{"path": "tree", "type": "blob", "mode": "100644", "sha": blob}],
    }
    tree_path = tmp_path / "tree.json"
    tree_path.write_bytes(canonical(tree))
    catalog = tmp_path / "catalog.json"
    catalog.write_bytes(
        canonical(
            {
                REPO: {
                    "revision": REV,
                    "tree": "a" * 40,
                    "treePath": str(tree_path),
                    "treeSha256": sha(tree_path.read_bytes()),
                }
            }
        )
    )
    sources = Sources(catalog, tmp_path / "traffic.json")
    sources.http.get = lambda url, limit=0: canonical(tree) if "api.github" in url else raw
    assert sources.list(REPO, REV)["paths"] == ["tree"]
    assert "public source" in sources.read(REPO, REV, "tree")["lines"]
    with pytest.raises(ValueError, match="not a regular blob"):
        sources.read(REPO, REV, "secret")
    sources.cache.clear()
    sources.http.get = lambda *a: b"wrong source"
    with pytest.raises(ValueError, match="pinned Git blob"):
        sources.read(REPO, REV, "tree")


def test_incremental_acquisition_reuses_unchanged_blobs(tmp_path):
    commit = (SOURCE / "commit.json").read_bytes()

    class HTTP:
        def __init__(self):
            self.urls = []

        def get(self, url, limit=0):
            self.urls.append(url)
            if "/commits/" in url:
                return commit
            raise AssertionError("unchanged tree/blobs must use retained content")

    http = HTTP()
    result = acquire(REPO, tmp_path / "refresh", http, previous=SOURCE, revision=REV)
    assert len(http.urls) == 1 and result["files"] == SNAPSHOT["files"]
    refresh = json.loads((tmp_path / "refresh/refresh.json").read_text())
    assert refresh["fetchedFiles"] == [] and len(refresh["reusedFiles"]) == 3


def test_stdio_service_has_no_write_or_execution_tool(database):
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "repodigest.lookup",
                "arguments": {"repository": REPO, "revision": REV},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "execute", "arguments": {}},
        },
    ]
    done = subprocess.run(
        [
            "uv",
            "run",
            "--offline",
            "python",
            str(ROOT / "scripts/repodigest_service.py"),
            "--database",
            str(database),
        ],
        input="".join(json.dumps(m) + "\n" for m in messages),
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert done.returncode == 0, done.stderr
    rows = [json.loads(line) for line in done.stdout.splitlines()]
    assert {t["name"] for t in rows[1]["result"]["tools"]} == {
        "repodigest.find",
        "repodigest.describe",
        "repodigest.lookup",
    }
    result = json.loads(rows[2]["result"]["content"][0]["text"])
    assert result["authorized"] == "not-granted"
    assert rows[3]["error"]["code"] == -32602


def test_malformed_absolute_tree_path_never_writes_outside_snapshot(tmp_path):
    commit = json.loads((SOURCE / "commit.json").read_text())
    tree = {
        "sha": commit["commit"]["tree"]["sha"],
        "truncated": False,
        "tree": [{"path": "/tmp/Cargo.toml", "type": "blob", "mode": "100644", "sha": "0" * 40}],
    }

    class HTTP:
        def get(self, url, limit=0):
            if "/commits/" in url:
                return canonical(commit)
            if "/git/trees/" in url:
                return canonical(tree)
            raise AssertionError("malformed path should fail before raw-file access")

    with pytest.raises(ValueError, match="unsafe repository path"):
        acquire(REPO, tmp_path / "source", HTTP())


def test_observation_overflow_cannot_hide_qualification_conflicts(database):
    request = json.loads((PILOT / "request.json").read_text())
    db = sqlite3.connect(database)
    raw = db.execute("SELECT body FROM observations").fetchone()[0]
    original = json.loads(raw)
    with db:
        for n in range(11):
            row = copy.deepcopy(original)
            row["capsuleSha256"] = str(n)
            body = canonical(row)
            db.execute(
                "INSERT INTO observations VALUES(?,?,?,?,?,?,?)",
                (
                    sha(body),
                    row["repository"],
                    row["component"],
                    row["revision"],
                    row["purpose"],
                    store.policy_id(),
                    body,
                ),
            )
    db.close()
    reader = store.Store(database)
    result = reader.lookup(
        original["repository"], original["revision"], observed_request=request, opt_in=True
    )
    assert result["observedRecipe"] is None
    assert result["observedRefusal"] == ["observation-cohort-over-budget"]
    reader.close()


def test_observation_admission_preserves_existing_source_record(database, tmp_path):
    request = json.loads((PILOT / "request.json").read_text())
    repo = request["task"]["repository"]
    rev = request["task"]["revision"]
    db = sqlite3.connect(database)
    raw = db.execute(
        "SELECT r.body FROM versions v JOIN records r ON r.digest=v.digest WHERE v.identity=?",
        (repo,),
    ).fetchone()[0]
    body = json.loads(raw)
    body["knowledgeClass"] = "extracted-instruction"
    body["facts"] = {"preserved-source-record": True}
    encoded = canonical(body)
    with db:
        db.execute("INSERT INTO records VALUES(?,?)", (sha(encoded), encoded))
        db.execute("UPDATE versions SET digest=? WHERE identity=?", (sha(encoded), repo))
    db.close()
    admit(
        PILOT / "capsule.json",
        FIXTURES / "digest-exchange-r1-iniconfig-execution-20261029",
        TRUST,
        database,
        tmp_path / "admit-again",
    )
    reader = store.Store(database)
    result = reader.lookup(repo, rev, observed_request=request, opt_in=True)
    assert result["facts"] == {"preserved-source-record": True}
    assert result["observedRecipe"] is not None
    reader.close()


def test_cached_positive_instruction_preserves_existing_exporter_policy(database, tmp_path):
    # First-party fixture only; do not count it as a successful public-repository extraction.
    from test_contextual_instruction_path import exported_control

    profile = exported_control(tmp_path / "export", component=False)
    repo = "github.com/example/control"
    revision = "1" * 40
    result = store.consumer.interpret_http_response(identity=repo, status_code=200, body=profile)
    selected = store.consumer.select_instruction(
        result, "test", request={"scope": "repository", "workingDirectory": "."}
    )
    assert selected["instruction"] is not None
    db = sqlite3.connect(database)
    raw = db.execute(
        "SELECT r.body FROM versions v JOIN records r ON r.digest=v.digest WHERE v.identity=?",
        (REPO,),
    ).fetchone()[0]
    row = json.loads(raw)
    row.update(repository=repo, revision=revision)
    row["selections"]["test"] = selected
    encoded = canonical(row)
    with db:
        db.execute("INSERT INTO records VALUES(?,?)", (sha(encoded), encoded))
        db.execute("INSERT INTO versions VALUES(?,?,?,?)", (repo, revision, ".", sha(encoded)))
        db.execute(
            "INSERT INTO current VALUES(?,?,?,?,?)",
            (repo, revision, row["tree"], row["checkedAt"], "fixture"),
        )
    db.close()
    reader = store.Store(database)
    hit = reader.lookup(repo, revision)
    assert hit["instruction"]["command"] == selected["instruction"]["command"]
    assert hit["instruction"]["execution"] == "unestablished" and hit["authorized"] == "not-granted"
    assert reader.lookup(repo, "2" * 40)["instruction"] is None
    reader.close()


def test_corruption_cannot_reduce_observation_ambiguity(database):
    request = json.loads((PILOT / "request.json").read_text())
    db = sqlite3.connect(database)
    raw = db.execute("SELECT body FROM observations").fetchone()[0]
    row = json.loads(raw)
    row["capsuleSha256"] = "second-assessment"
    body = canonical(row)
    digest = sha(body)
    with db:
        db.execute(
            "INSERT INTO observations VALUES(?,?,?,?,?,?,?)",
            (
                digest,
                row["repository"],
                row["component"],
                row["revision"],
                row["purpose"],
                store.policy_id(),
                body,
            ),
        )
    reader = store.Store(database)
    assert (
        reader.lookup(row["repository"], row["revision"], observed_request=request, opt_in=True)[
            "observedRecipe"
        ]
        is None
    )
    reader.close()
    db.execute("DROP TRIGGER observations_no_update")
    with db:
        db.execute("UPDATE observations SET body=? WHERE digest=?", (b"corrupt", digest))
    db.close()
    reader = store.Store(database)
    result = reader.lookup(
        row["repository"], row["revision"], observed_request=request, opt_in=True
    )
    assert result["observedRecipe"] is None
    assert "invalid-observation-cohort" in result["observedRefusal"]
    reader.close()


def test_lazy_details_corruption_and_size_fail_closed(database):
    db = sqlite3.connect(database)
    db.execute("DROP TRIGGER objects_no_update")
    with db:
        db.execute("UPDATE objects SET body=?", (b"x" * (store.MAX_DETAILS + 1),))
    db.close()
    reader = store.Store(database)
    result = reader.lookup(REPO, REV, include_leads=True)
    assert result["instruction"] is None
    assert "compiled-detail-integrity-failure" in result["missingEvidence"]
    reader.close()


def test_large_source_lines_are_not_copied_into_lookup_passages():
    snapshot = {"files": {"README.md": {"sha256": "source"}}}
    leads = store.source_leads(".", snapshot, {"README.md": "test " + ("x" * 1000000)})
    assert leads == []
