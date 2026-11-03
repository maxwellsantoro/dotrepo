"""Actual admission/transport, cache controls and fail-closed source provenance."""

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
from repodigest_acquire import canonical, sha  # noqa: E402
from repodigest_source_cache import Reader, Unavailable  # noqa: E402
from repodigest_cached_tools import CachedSources  # noqa: E402
from repodigest_source_tools import Sources  # noqa: E402

PACKET = FIXTURES / "repodigest-multirepo-service-20261029"
DEMAND = FIXTURES / "repodigest-demand-reuse-20261029"
SOURCE = PACKET / "acquisition-001/sindresorhus__p-limit"
SNAPSHOT = json.loads((SOURCE / "snapshot.json").read_text())
REPO, REV = SNAPSHOT["repository"], SNAPSHOT["revision"]


@pytest.fixture(scope="module")
def admitted(tmp_path_factory):
    root = tmp_path_factory.mktemp("source-cache")
    db = root / "store.sqlite"
    store.ingest(SOURCE, db, root / "admission", ROOT / "target/debug/dotrepo")
    return db


@pytest.fixture
def database(admitted, tmp_path):
    path = tmp_path / "store.sqlite"
    shutil.copyfile(admitted, path)
    return path


def fallback(tmp_path):
    # Relocate only the pinned fixture target. The historical study catalog's
    # absolute /private/tmp paths and unrelated targets are not test inputs.
    catalog = tmp_path / "source-catalog.json"
    catalog.write_bytes(
        canonical(
            {
                REPO: {
                    "revision": REV,
                    "tree": SNAPSHOT["tree"],
                    "treePath": str(SOURCE / "tree.json"),
                    "treeSha256": SNAPSHOT["treeSha256"],
                }
            }
        )
    )
    source = Sources(catalog, tmp_path / "http.json")
    raw = (
        DEMAND / "consumer-006-p-limit-repodigest/source-responses/sindresorhus/p-limit/.npmrc"
    ).read_bytes()

    def get(url, limit=1048576):
        assert url.endswith("/.npmrc")
        source.http.events.append({"url": url, "responseBodyBytes": len(raw), "status": 200})
        return raw

    source.http.get = get
    return source


def retarget_index(database, mutate, body=None):
    """Synthetic integrity counterexample, never an upstream evidence receipt."""
    db = sqlite3.connect(database)
    raw = db.execute(
        "SELECT r.body FROM versions v JOIN records r ON r.digest=v.digest WHERE v.identity=? AND v.component='.'",
        (REPO,),
    ).fetchone()[0]
    record = json.loads(raw)
    receipt = json.loads(
        db.execute(
            "SELECT body FROM admissions WHERE digest=?", (record["admissionSha256"],)
        ).fetchone()[0]
    )
    index = json.loads(
        db.execute(
            "SELECT body FROM objects WHERE digest=?", (receipt["sourceIndexSha256"],)
        ).fetchone()[0]
    )
    mutate(index)
    encoded = canonical(index)
    receipt["sourceIndexSha256"] = sha(encoded)
    receipt_body = canonical(receipt)
    record["admissionSha256"] = sha(receipt_body)
    record_body = canonical(record)
    with db:
        db.execute("INSERT INTO objects VALUES(?,?)", (sha(encoded), encoded))
        db.execute("INSERT INTO admissions VALUES(?,?)", (sha(receipt_body), receipt_body))
        db.execute("INSERT INTO records VALUES(?,?)", (sha(record_body), record_body))
        db.execute(
            "UPDATE versions SET digest=? WHERE identity=? AND component='.'",
            (sha(record_body), REPO),
        )
        if body is not None:
            db.execute("INSERT INTO source_blobs VALUES(?,?)", (sha(body), body))
    db.close()


def test_cached_inventory_and_lines_need_no_source_directory_or_subprocess(database, monkeypatch):
    reader = Reader(store.Store(database))
    raw = (SOURCE / "files/package.json").read_bytes()

    def forbidden(*a, **kw):
        raise AssertionError("cached source touched external state")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    listing = reader.list(REPO, REV)
    assert len(listing["paths"]) == SNAPSHOT["coverage"]["trackedBlobs"]
    assert listing["cachedPaths"] == sorted(SNAPSHOT["files"])
    first = reader.read(REPO, REV, "package.json", 1, 40)
    assert first["sha256"] == sha(raw) and "xo && ava && tsd" in first["lines"]
    assert first["knowledgeClass"] == "publisher-source" and first["authorized"] == "not-granted"
    assert first["sourceCheckedAt"] == SNAPSHOT["checkedAt"]
    assert reader.read(REPO, REV, "package.json", 1, 40) == first
    assert reader.stats["logicalBlobBytesRead"] == len(raw) and reader.stats["blobCacheHits"] == 1
    assert reader.stats["logicalIndexBytesRead"] > 0 and reader.stats["indexCacheHits"] > 0
    reader.store.close()


def test_cache_miss_is_explicit_and_http_is_only_used_when_configured(database, tmp_path):
    reader = store.Store(database)
    offline = CachedSources(reader)
    assert offline.read(REPO, REV, ".npmrc")["state"] == "unavailable"
    assert not offline.network_enabled
    http = fallback(tmp_path)
    hybrid = CachedSources(reader, fallback=http, traffic_log=tmp_path / "traffic.json")
    assert hybrid.list(REPO, REV)["retrieval"] == "compiled-source-cache" and not http.http.events
    assert (
        hybrid.read(REPO, REV, "package.json")["retrieval"] == "compiled-source-cache"
        and not http.http.events
    )
    assert hybrid.read(REPO, REV, ".npmrc")["retrieval"] == "verified-source-http"
    assert len(http.http.events) == 1
    hybrid.read(REPO, REV, ".npmrc")
    assert len(http.http.events) == 1
    saved = tmp_path / "source-responses/sindresorhus/p-limit/package.json"
    assert saved.read_bytes() == (SOURCE / "files/package.json").read_bytes()
    reader.close()


@pytest.mark.parametrize("where", ["body", "inventory", "admission"])
def test_corrupt_cache_does_not_trigger_http_fallback(database, tmp_path, where):
    db = sqlite3.connect(database)
    if where == "body":
        db.execute("DROP TRIGGER source_blobs_no_update")
        db.execute("UPDATE source_blobs SET body=?", (b"corrupt",))
    elif where == "inventory":
        db.execute("DROP TRIGGER objects_no_update")
        db.execute("UPDATE objects SET body=?", (b"corrupt",))
    else:
        db.execute("DROP TRIGGER admissions_no_update")
        db.execute("UPDATE admissions SET body=?", (b"corrupt",))
    db.commit()
    db.close()
    http = fallback(tmp_path)
    reader = store.Store(database)
    with pytest.raises(ValueError, match="integrity"):
        CachedSources(reader, fallback=http).read(REPO, REV, "package.json")
    assert not http.http.events
    reader.close()


def test_fallback_catalog_binding_is_checked_before_http(database, tmp_path):
    http = fallback(tmp_path)
    http.catalog[REPO]["tree"] = "0" * 40
    reader = store.Store(database)
    with pytest.raises(ValueError, match="catalog disagrees"):
        CachedSources(reader, fallback=http).read(REPO, REV, ".npmrc")
    assert not http.http.events
    reader.close()


def test_wrong_revision_and_changed_policy_cannot_reuse_cached_sources(database):
    store_reader = store.Store(database)
    reader = Reader(store_reader)
    reader.read(REPO, REV, "package.json")
    with pytest.raises(Unavailable, match="revision"):
        reader.read(REPO, "0" * 40, "package.json")
    store_reader.policy = "changed-policy"
    with pytest.raises(ValueError, match="policy-changed"):
        reader.read(REPO, REV, "package.json")
    store_reader.close()


def test_source_index_cross_identity_binding_is_not_just_a_hash_check(database):
    retarget_index(database, lambda index: index.update(repository="github.com/example/other"))
    reader = Reader(store.Store(database))
    with pytest.raises(ValueError, match="binding mismatch"):
        reader.read(REPO, REV, "package.json")
    reader.store.close()


def test_source_git_blob_binding_is_checked_even_for_hash_valid_artifact(database):
    retarget_index(database, lambda index: index["files"]["package.json"].update(gitBlob="0" * 40))
    reader = Reader(store.Store(database))
    with pytest.raises(ValueError, match="Git blob mismatch"):
        reader.read(REPO, REV, "package.json")
    reader.store.close()


def test_cached_source_response_is_bounded_without_silent_line_truncation(database):
    raw = b"x" * 40000 + b"\n"
    git = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    retarget_index(
        database,
        lambda index: index["files"]["package.json"].update(sourceSha256=sha(raw), gitBlob=git),
        body=raw,
    )
    reader = Reader(store.Store(database))
    with pytest.raises(ValueError, match="32KiB"):
        reader.read(REPO, REV, "package.json", 1, 1)
    assert reader.read(REPO, REV, "package.json", 2, 2)["lines"] == ""
    reader.store.close()


def test_unchanged_admission_verifies_cache_and_rejects_corruption(database, tmp_path):
    db = sqlite3.connect(database)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE source_blobs SET body=?", (b"x",))
    db.rollback()
    db.execute("DROP TRIGGER source_blobs_no_update")
    db.execute("UPDATE source_blobs SET body=?", (b"x",))
    db.commit()
    db.close()
    with pytest.raises(ValueError, match="existing source body corrupt"):
        store.ingest(SOURCE, database, tmp_path / "no-op", ROOT / "target/debug/dotrepo")


def test_http_fallback_and_direct_source_share_payload_limit(database, tmp_path):
    raw = b"x" * 40000 + b"\n"
    git = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    retarget_index(database, lambda index: index["files"][".npmrc"].update(gitBlob=git))
    http = fallback(tmp_path)
    http.blobs[REPO][".npmrc"]["sha"] = git

    def get(url, limit=1048576):
        http.http.events.append({"url": url, "responseBodyBytes": len(raw), "status": 200})
        return raw

    http.http.get = get
    reader = store.Store(database)
    hybrid = CachedSources(reader, fallback=http, traffic_log=tmp_path / "traffic.json")
    with pytest.raises(ValueError, match="32KiB"):
        hybrid.read(REPO, REV, ".npmrc", 1, 1)
    assert len(http.http.events) == 1 and http.http.events[0]["responseBodyBytes"] == len(raw)
    assert hybrid.retrievals[-1]["outcome"] == "refused"
    assert hybrid.retrievals[-1]["origin"] == "verified-source-http"
    with pytest.raises(ValueError, match="32KiB"):
        http.read(REPO, REV, ".npmrc", 1, 1)
    assert len(http.http.events) == 1
    reader.close()


def test_offline_miss_cannot_echo_unbounded_input(database):
    reader = store.Store(database)
    offline = CachedSources(reader)
    with pytest.raises(ValueError, match="32KiB"):
        offline.read("github.com/example/missing", "a" * 40, "x" * 40000)
    assert offline.retrievals[-1]["outcome"] == "refused"
    assert offline.retrievals[-1]["origin"] == "cache-miss"
    reader.close()


def test_stdio_source_only_cache_exposes_no_semantic_or_execution_tool(database, tmp_path):
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "source.read",
                "arguments": {"repository": REPO, "revision": REV, "path": "package.json"},
            },
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
            "--compiled-sources",
            "--source-only",
            "--traffic-log",
            str(tmp_path / "traffic.json"),
        ],
        input="".join(json.dumps(m) + "\n" for m in messages),
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert done.returncode == 0, done.stderr
    rows = [json.loads(line) for line in done.stdout.splitlines()]
    assert {tool["name"] for tool in rows[1]["result"]["tools"]} == {"source.list", "source.read"}
    assert all(not tool["annotations"]["openWorldHint"] for tool in rows[1]["result"]["tools"])
    result = json.loads(rows[2]["result"]["content"][0]["text"])
    assert "xo && ava && tsd" in result["lines"] and result["retrieval"] == "compiled-source-cache"
    assert json.loads((tmp_path / "traffic.json").read_text())["http"] == []
