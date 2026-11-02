"""Real retained consumer receipts, admission, provenance and refusal controls."""

import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures/repodigest"
sys.path.insert(0, str(ROOT / "scripts"))
from repodigest_acquire import acquire, canonical, sha  # noqa: E402
from repodigest_reuse import lineage, reuse  # noqa: E402
from repodigest_source_cache import Reader, Unavailable  # noqa: E402
from repodigest_store import Store, ingest, validate_snapshot  # noqa: E402

PACKET = FIXTURES / "repodigest-source-cache-20261030"
SOURCE = (
    FIXTURES / "repodigest-multirepo-service-20261029/acquisition-001/agronholm__exceptiongroup"
)
SESSION = PACKET / "consumer-004-exceptiongroup-source-cache"
PATH = "tests/check_types.py"
SNAPSHOT = json.loads((SOURCE / "snapshot.json").read_text())
REPO, REV = SNAPSHOT["repository"], SNAPSHOT["revision"]


def digests(session):
    return {
        "trusted_events_sha256": sha((session / "events.jsonl").read_bytes()),
        "trusted_traffic_sha256": sha((session / "traffic.json").read_bytes()),
    }


def run(output, *, previous=SOURCE, session=SESSION, paths=(PATH,), **kw):
    return reuse(previous, session, output, paths=paths, **(digests(session) | kw))


def copy_session(tmp_path):
    session = tmp_path / "session"
    body = session / "source-responses/agronholm/exceptiongroup" / PATH
    body.parent.mkdir(parents=True)
    shutil.copyfile(SESSION / "source-responses/agronholm/exceptiongroup" / PATH, body)
    for name in ("events.jsonl", "traffic.json"):
        shutil.copyfile(SESSION / name, session / name)
    return session


def test_actual_source_receipt_import_is_repeatable_and_preserves_source_age(tmp_path):
    snapshot, report = run(tmp_path / "import")
    assert report["importedFiles"] == [PATH]
    assert report["newPublisherRequests"] == report["newPublisherResponseBodyBytes"] == 0
    assert report["retainedSourceBodyBytes"] == 1377
    assert snapshot["checkedAt"] == SNAPSHOT["checkedAt"]
    assert snapshot["files"].items() >= SNAPSHOT["files"].items()
    assert validate_snapshot(tmp_path / "import")[0] == snapshot
    receipt = snapshot["sourceReuse"][PATH]
    assert (
        receipt["sourceRevision"] == REV
        and receipt["eventsSha256"] == digests(SESSION)["trusted_events_sha256"]
    )
    assert receipt["httpEventIndex"] == 0 and receipt["eventLine"] > 0
    again, repeat = run(tmp_path / "repeat", previous=tmp_path / "import")
    assert again == snapshot and repeat["state"] == "cached"


def test_reused_body_becomes_offline_source_without_procedure_promotion(tmp_path):
    database = tmp_path / "compiled.sqlite"
    cli = ROOT / "target/debug/dotrepo"
    ingest(SOURCE, database, tmp_path / "before", cli)
    before = Store(database)
    with pytest.raises(Unavailable):
        Reader(before).read(REPO, REV, PATH)
    before.close()
    run(tmp_path / "import")
    ingest(tmp_path / "import", database, tmp_path / "after", cli)
    after = Store(database)
    result = Reader(after).read(REPO, REV, PATH)
    raw = (SESSION / "source-responses/agronholm/exceptiongroup" / PATH).read_bytes()
    assert result["sha256"] == sha(raw) and result["retrieval"] == "compiled-source-cache"
    assert after.lookup(REPO, REV)["instruction"] is None
    assert after.lookup(REPO, REV)["authorized"] == "not-granted"
    assert after.db.execute("SELECT count(*) FROM records").fetchone()[0] == 2
    after.close()


@pytest.mark.parametrize(
    "mutation",
    [
        "digest",
        "body",
        "http-status",
        "http-bytes",
        "http-url",
        "read-error",
        "read-error-empty-object",
        "read-error-empty-list",
        "read-error-false",
        "read-error-zero",
        "read-error-empty-string",
        "read-digest",
        "read-lines",
        "read-status",
        "read-is-error",
        "read-cache-origin",
        "revision",
    ],
)
def test_contradictory_or_missing_receipt_refuses_before_output(tmp_path, mutation):
    session = copy_session(tmp_path)
    options = {}
    if mutation == "digest":
        options["trusted_events_sha256"] = "0" * 64
    elif mutation == "body":
        body = session / "source-responses/agronholm/exceptiongroup" / PATH
        body.write_bytes(body.read_bytes() + b"changed")
    elif mutation.startswith("http-"):
        file = session / "traffic.json"
        traffic = json.loads(file.read_text())
        item = traffic["http"][0]
        item[
            {"http-status": "status", "http-bytes": "responseBodyBytes", "http-url": "url"}[
                mutation
            ]
        ] = {"http-status": 500, "http-bytes": True, "http-url": "https://example.invalid/source"}[
            mutation
        ]
        file.write_bytes(canonical(traffic))
    else:
        file = session / "events.jsonl"
        events = [json.loads(line) for line in file.read_text().splitlines()]
        for event in events:
            item = event.get("item", {})
            if (
                event.get("type") != "item.completed"
                or item.get("tool") != "source.read"
                or item.get("arguments", {}).get("path") != PATH
            ):
                continue
            if mutation.startswith("read-error"):
                item["error"] = {
                    "read-error": {"message": "failed"},
                    "read-error-empty-object": {},
                    "read-error-empty-list": [],
                    "read-error-false": False,
                    "read-error-zero": 0,
                    "read-error-empty-string": "",
                }[mutation]
            elif mutation == "read-status":
                item["status"] = "failed"
            elif mutation == "read-is-error":
                item["result"]["isError"] = True
            elif mutation == "revision":
                item["arguments"]["revision"] = "0" * 40
            else:
                block = item["result"]["content"][0]
                value = json.loads(block["text"])
                field = {
                    "read-digest": "sha256",
                    "read-lines": "lines",
                    "read-cache-origin": "retrieval",
                }[mutation]
                value[field] = (
                    "compiled-source-cache" if mutation == "read-cache-origin" else "invalid"
                )
                block["text"] = json.dumps(value)
        file.write_bytes(b"\n".join(canonical(e) for e in events) + b"\n")
    with pytest.raises(ValueError):
        run(tmp_path / "output", session=session, **options)
    assert not (tmp_path / "output").exists()


def test_paths_symlinks_and_budgets_are_refused(tmp_path, monkeypatch):
    for n, paths in enumerate(((), (PATH, PATH), ("../outside",), tuple(str(n) for n in range(9)))):
        with pytest.raises(ValueError):
            run(tmp_path / str(n), paths=paths)
        assert not (tmp_path / str(n)).exists()
    session = copy_session(tmp_path)
    body = session / "source-responses/agronholm/exceptiongroup" / PATH
    inside = body.with_name("alias.py")
    body.rename(inside)
    body.symlink_to(inside.name)
    with pytest.raises(ValueError, match="symlink"):
        run(tmp_path / "alias", session=session)
    body.unlink()
    inside.rename(body)
    monkeypatch.setattr("repodigest_reuse.MAX_NEW_BYTES", 1000)
    with pytest.raises(ValueError, match="total byte budget"):
        run(tmp_path / "budget", session=session)
    assert not (tmp_path / "budget").exists()


@pytest.mark.parametrize("layer", ["traffic", "events", "read-payload"])
@pytest.mark.parametrize("ambiguity", ["duplicate", "nonfinite"])
def test_all_receipt_json_layers_reject_ambiguous_data(tmp_path, layer, ambiguity):
    session = copy_session(tmp_path)
    if layer == "traffic":
        file = session / "traffic.json"
        value = file.read_text()
        value = (
            value.replace('"status": 200', '"status": 500, "status": 200', 1)
            if ambiguity == "duplicate"
            else value.replace('"status": 200', '"status": 200, "invalid": Infinity', 1)
        )
        file.write_text(value)
    else:
        file = session / "events.jsonl"
        lines = []
        for line in file.read_text().splitlines():
            event = json.loads(line)
            item = event.get("item", {})
            match = (
                event.get("type") == "item.completed"
                and item.get("arguments", {}).get("path") == PATH
            )
            if match and layer == "read-payload":
                block = item["result"]["content"][0]
                block["text"] = (
                    block["text"].replace('"sha256":', '"sha256":"wrong","sha256":', 1)
                    if ambiguity == "duplicate"
                    else block["text"].replace('"sha256":', '"invalid":Infinity,"sha256":', 1)
                )
            encoded = canonical(event).decode()
            if match and layer == "events":
                encoded = (
                    encoded.replace(
                        '"status":"completed"', '"status":"failed","status":"completed"', 1
                    )
                    if ambiguity == "duplicate"
                    else encoded.replace(
                        '"status":"completed"', '"invalid":Infinity,"status":"completed"', 1
                    )
                )
            lines.append(encoded)
        file.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="duplicate-json-key|non-finite-json"):
        run(tmp_path / "output", session=session)
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("change", ["unchanged", "changed", "deleted"])
def test_refresh_retains_only_matching_content_witness(tmp_path, change):
    original, _ = run(tmp_path / "import")
    tree = json.loads((SOURCE / "tree.json").read_text())
    new_revision = "a" * 40
    new_body = b"# synthetic changed source; never executed\n"
    git = hashlib.sha1(b"blob " + str(len(new_body)).encode() + b"\0" + new_body).hexdigest()
    if change == "changed":
        next(e for e in tree["tree"] if e["path"] == PATH)["sha"] = git
    elif change == "deleted":
        tree["tree"] = [e for e in tree["tree"] if e["path"] != PATH]
    tree["sha"] = "b" * 40
    commit = {
        "sha": new_revision,
        "commit": {"tree": {"sha": tree["sha"]}},
        "html_url": f"https://{REPO}/commit/{new_revision}",
    }

    class HTTP:
        def __init__(self):
            self.events = []

        def get(self, url, limit=1048576):
            self.events.append(url)
            if "/commits/" in url:
                return canonical(commit)
            if "/git/trees/" in url:
                return canonical(tree)
            assert change == "changed" and url.endswith(PATH)
            return new_body

    http = HTTP()
    result = acquire(
        REPO, tmp_path / "refresh", http, previous=tmp_path / "import", revision=new_revision
    )
    report = json.loads((tmp_path / "refresh/refresh.json").read_text())
    assert validate_snapshot(tmp_path / "refresh")[0] == result
    if change == "unchanged":
        assert result["sourceReuse"] == original["sourceReuse"]
        assert result["sourceReuse"][PATH]["sourceRevision"] == REV != new_revision
        assert report["retainedSourceReuseProvenance"] == [PATH]
    else:
        assert not result.get("sourceReuse")
        assert report["invalidatedSourceReuseProvenance"] == [PATH]
    assert len(http.events) == (3 if change == "changed" else 2)


def test_inconsistent_old_provenance_cannot_be_carried():
    snapshot = copy.deepcopy(SNAPSHOT)
    snapshot["sourceReuse"] = {
        "README.rst": {
            "repository": REPO,
            "sourceRevision": REV,
            "gitBlob": "0" * 40,
            "sha256": snapshot["files"]["README.rst"]["sha256"],
        }
    }
    with pytest.raises(ValueError, match="provenance binding"):
        lineage(snapshot)
