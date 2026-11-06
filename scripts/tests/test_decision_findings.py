"""Synthetic mechanics controls; these tests do not measure useful finding transfer."""

import copy
import hashlib
import json
import shutil
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import decision_findings as findings  # noqa: E402
import test_repodigest_source_cache as fixtures  # noqa: E402
from repodigest_acquire import canonical, sha  # noqa: E402
from repodigest_source_cache import Reader  # noqa: E402
from repodigest_store import Store  # noqa: E402
from repodigest_store import stamp  # noqa: E402


@pytest.fixture(scope="module")
def admitted(tmp_path_factory):
    return fixtures.admitted.__wrapped__(tmp_path_factory)


@pytest.fixture
def packet(admitted, tmp_path):
    database = tmp_path / "source.sqlite"
    shutil.copyfile(admitted, database)
    store = Store(database)
    try:
        source_read = Reader(store).read(fixtures.REPO, fixtures.REV, "package.json", 1, 3)
    finally:
        store.close()
    observation = tmp_path / "observation.json"
    observation.write_bytes(
        canonical(
            {
                "tool": "source.read",
                "state": "completed",
                "recordedAt": stamp(),
                "result": source_read,
            }
        )
    )
    origin = tmp_path / "original-user-answer.txt"
    origin.write_text("Synthetic user interpretation, never a semantic qualification.\n")
    finding = {
        "id": "developer-control-1",
        "origin": "synthetic-local-test",
        "claim": {"text": "This source declares a package name; execution remains unknown."},
        "taskScope": "Inspect the declared package name only.",
        "limitations": ["Synthetic developer control, not an outcome."],
        "assumptions": ["Declaration is applicable to this exact captured source."],
        "attribution": {"author": "developer control", "product": "test", "recordId": "1"},
        "findingCreatedAt": stamp(),
        "originEvidence": {"locator": str(origin), "sha256": sha(origin.read_bytes())},
        "sources": [
            {
                "kind": "repository",
                "repository": fixtures.REPO,
                "revision": fixtures.REV,
                "path": "package.json",
                "sha256": source_read["sha256"],
                "representation": findings.REPRESENTATION,
                "lineRange": [1, 3],
                "originalObservedAt": source_read["sourceCheckedAt"],
                "originalTimeReason": None,
                "originalObservationEvidence": {
                    "locator": str(observation),
                    "sha256": sha(observation.read_bytes()),
                },
            }
        ],
    }
    input_path = tmp_path / "finding-input.json"
    input_path.write_bytes(canonical(finding))
    policy = {
        "id": "synthetic-freshness-1",
        "taskScope": finding["taskScope"],
        "maxSourceAgeSeconds": 31536000,
    }
    policy_path = tmp_path / "policy.json"
    policy_path.write_bytes(canonical(policy))
    return {
        "root": tmp_path,
        "database": database,
        "finding": finding,
        "input": input_path,
        "policy": policy_path,
        "store": tmp_path / "sender",
    }


def save_input(packet):
    packet["input"].write_bytes(canonical(packet["finding"]))


def transfer(packet):
    saved = findings.record(packet["store"], packet["database"], packet["input"], packet["root"])
    envelope = packet["root"] / "export.json"
    exported = findings.export(packet["store"], saved["findingSha256"], envelope)
    return saved, envelope, exported


def receive(packet, envelope, review=None):
    return findings.receive(
        packet["root"] / "recipient", packet["database"], envelope, packet["policy"], review
    )


def cli(*args):
    done = subprocess.run(
        [sys.executable, str(ROOT / "scripts/decision_findings.py"), *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert done.returncode == 0, (done.stdout, done.stderr)
    assert not done.stderr
    return json.loads(done.stdout)


def review(packet, envelope, exported, disposition="accepted"):
    value = {
        "envelopeSha256": exported["envelopeSha256"],
        "taskScope": json.loads(packet["policy"].read_text())["taskScope"],
        "reviewer": "explicit synthetic recipient",
        "disposition": disposition,
        "reason": "I inspected the bounded claim under this recipient task.",
    }
    path = packet["root"] / (disposition + "-review.json")
    path.write_bytes(canonical(value))
    return path


def test_cli_restart_dates_export_and_no_overwrite(packet):
    before_database = packet["database"].read_bytes()
    saved = cli(
        "record",
        "--store",
        packet["store"],
        "--database",
        packet["database"],
        "--finding",
        packet["input"],
        "--evidence-root",
        packet["root"],
    )
    inspected = cli("inspect", "--store", packet["store"], "--sha256", saved["findingSha256"])
    assert inspected["claim"] == packet["finding"]["claim"]
    assert inspected["findingCreatedAt"] == packet["finding"]["findingCreatedAt"]
    envelope = packet["root"] / "export.json"
    cli(
        "export",
        "--store",
        packet["store"],
        "--sha256",
        saved["findingSha256"],
        "--output",
        envelope,
    )
    original_export = envelope.read_bytes()
    with pytest.raises(FileExistsError):
        findings.export(packet["store"], saved["findingSha256"], envelope)
    assert envelope.read_bytes() == original_export
    packet["database"].unlink()
    assert (
        findings.inspect(packet["store"], saved["findingSha256"])["sources"] == inspected["sources"]
    )
    packet["database"].write_bytes(before_database)
    receipt = cli(
        "receive",
        "--store",
        packet["root"] / "recipient",
        "--database",
        packet["database"],
        "--envelope",
        envelope,
        "--policy",
        packet["policy"],
    )
    assert receipt["sourceStatus"] == "current"
    assert receipt["interpretation"]["disposition"] == "unreviewed"
    assert json.loads(original_export)["sources"] == inspected["sources"]
    assert packet["database"].read_bytes() == before_database


def test_recall_selects_one_finding_preserves_dates_and_writes_nothing(packet, monkeypatch):
    saved, _, _ = transfer(packet)
    # Original locators are provenance only; recall does not reread their files.
    Path(packet["finding"]["originEvidence"]["locator"]).unlink()
    Path(packet["finding"]["sources"][0]["originalObservationEvidence"]["locator"]).unlink()
    # Unrelated store entries are never loaded or sent to the returning reader.
    (packet["store"] / ("finding-" + "0" * 64 + ".json")).write_text("unrelated corrupt entry")
    before = {p: p.read_bytes() for p in packet["root"].rglob("*") if p.is_file()}

    def forbidden(*args, **kwargs):
        raise AssertionError("recall must not write, invoke a process, or use network")

    monkeypatch.setattr(findings, "store_file", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    result = findings.recall(
        packet["store"], packet["database"], saved["findingSha256"], packet["policy"]
    )
    assert result["format"] == findings.RECALL_FORMAT
    assert result["findingSha256"] == saved["findingSha256"]
    assert result["sourceStatus"] == "current"
    assert result["interpretation"] == {"disposition": "unreviewed", "issues": []}
    assert result["checkedAt"] >= result["findingCreatedAt"]
    for field in findings.FIELDS - {"sources"}:
        assert result[field] == packet["finding"][field]
    for key, value in packet["finding"]["sources"][0].items():
        assert result["sources"][0][key] == value
    assert result["sources"][0]["sourceStatus"] == "current"
    assert "lines" not in result["sources"][0]
    assert result["verification"]["storeIntegrityBytesRead"] == 2 * len(before[packet["database"]])
    assert result["inputBytesRead"]["finding"] == len(Path(saved["findingPath"]).read_bytes())
    assert {p: p.read_bytes() for p in packet["root"].rglob("*") if p.is_file()} == before


@pytest.mark.parametrize(
    "mutation,expected",
    [
        ("unchanged-new-revision", "current"),
        ("changed", "changed"),
        ("changed-uncached", "changed"),
        ("missing", "unknown"),
        ("corrupt", "unknown"),
        ("stale", "unknown"),
        ("scope", "current"),
    ],
)
def test_recall_uses_current_recipient_checks_without_rewriting_original(
    packet, mutation, expected
):
    saved, _, _ = transfer(packet)
    original = Path(saved["findingPath"]).read_bytes()
    body_sha = packet["finding"]["sources"][0]["sha256"]
    if mutation in {"unchanged-new-revision", "changed", "changed-uncached"}:
        advance_current(
            packet["database"],
            changed=mutation != "unchanged-new-revision",
            inspected=mutation != "changed-uncached",
        )
    elif mutation == "missing":
        with sqlite3.connect(packet["database"]) as db:
            db.execute("DROP TRIGGER source_blobs_no_delete")
            db.execute("DELETE FROM source_blobs WHERE digest=?", (body_sha,))
    elif mutation == "corrupt":
        with sqlite3.connect(packet["database"]) as db:
            row = db.execute(
                "SELECT rowid FROM source_blobs WHERE digest=?", (body_sha,)
            ).fetchone()
            with db.blobopen("source_blobs", "body", row[0]) as blob:
                blob.write(b"X")
    else:
        policy = json.loads(packet["policy"].read_bytes())
        if mutation == "stale":
            policy["maxSourceAgeSeconds"] = 0
        else:
            policy["taskScope"] += " Also establish execution safety."
        packet["policy"].write_bytes(canonical(policy))
    before_db = packet["database"].read_bytes()
    result = cli(
        "recall",
        "--store",
        packet["store"],
        "--sha256",
        saved["findingSha256"],
        "--database",
        packet["database"],
        "--policy",
        packet["policy"],
    )
    assert result["sourceStatus"] == expected
    assert result["interpretation"]["disposition"] == "unreviewed"
    if mutation == "scope":
        assert "scope differs" in result["interpretation"]["issues"][0]
    assert result["findingCreatedAt"] == packet["finding"]["findingCreatedAt"]
    assert (
        result["sources"][0]["originalObservedAt"]
        == packet["finding"]["sources"][0]["originalObservedAt"]
    )
    assert result["sources"][0]["sha256"] == body_sha
    assert Path(saved["findingPath"]).read_bytes() == original
    assert packet["database"].read_bytes() == before_db


def test_recall_refuses_corrupt_selected_finding_and_missing_database(packet):
    saved, _, _ = transfer(packet)
    original = Path(saved["findingPath"]).read_bytes()
    Path(saved["findingPath"]).write_bytes(original + b" ")
    with pytest.raises(ValueError, match="integrity"):
        findings.recall(
            packet["store"], packet["database"], saved["findingSha256"], packet["policy"]
        )
    Path(saved["findingPath"]).write_bytes(original)
    packet["database"].unlink()
    with pytest.raises(ValueError, match="missing"):
        findings.recall(
            packet["store"], packet["database"], saved["findingSha256"], packet["policy"]
        )
    assert not packet["database"].exists()


def test_recall_refuses_oversize_without_truncating_claim_or_original(packet):
    packet["finding"]["claim"]["text"] = "x" * 32000
    packet["finding"]["taskScope"] = "s" * 8000
    packet["finding"]["assumptions"] = ["a" * 8000, "b" * 8000]
    policy = json.loads(packet["policy"].read_bytes())
    policy["taskScope"] = packet["finding"]["taskScope"]
    packet["policy"].write_bytes(canonical(policy))
    save_input(packet)
    saved, _, _ = transfer(packet)
    before = {p: p.read_bytes() for p in packet["root"].rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="recall result exceeds"):
        findings.recall(
            packet["store"], packet["database"], saved["findingSha256"], packet["policy"]
        )
    assert {p: p.read_bytes() for p in packet["root"].rglob("*") if p.is_file()} == before


def test_explicit_review_current_conflict_and_immutable_variants(packet):
    _, envelope, exported = transfer(packet)
    unreviewed = receive(packet, envelope)
    original = Path(unreviewed["envelopePath"]).read_bytes()
    accepted = receive(packet, envelope, review(packet, envelope, exported))
    assert accepted["interpretation"]["disposition"] == "accepted"
    conflict = receive(packet, envelope, review(packet, envelope, exported, "conflicting"))
    assert conflict["sourceStatus"] == "current"
    assert conflict["interpretation"]["disposition"] == "conflicting"
    assert Path(accepted["receiptPath"]).is_file() and Path(unreviewed["receiptPath"]).is_file()
    # A differing sender conclusion is retained as a different immutable envelope.
    value = json.loads(envelope.read_text())
    value["claim"]["text"] = "A differing original interpretation."
    alternative = packet["root"] / "alternative.json"
    alternative.write_bytes(canonical(value))
    second = receive(packet, alternative)
    assert second["envelopePath"] != accepted["envelopePath"]
    assert Path(accepted["envelopePath"]).read_bytes() == original


@pytest.mark.parametrize("mutation", ["scope", "attribution", "finding-time", "source-time"])
def test_current_bytes_do_not_accept_unknown_scope_attribution_or_time(packet, mutation):
    if mutation == "attribution":
        packet["finding"]["attribution"]["author"] = None
    elif mutation == "finding-time":
        packet["finding"]["findingCreatedAt"] = None
        packet["finding"]["sources"][0].update(
            originalObservedAt=None,
            originalTimeReason="Finding date is not retained.",
            originalObservationEvidence=None,
        )
    elif mutation == "source-time":
        source = packet["finding"]["sources"][0]
        source.update(
            originalObservedAt=None,
            originalTimeReason="No retained original receipt.",
            originalObservationEvidence=None,
        )
    save_input(packet)
    saved, envelope, exported = transfer(packet)
    if mutation == "scope":
        policy = json.loads(packet["policy"].read_text())
        policy["taskScope"] += " Also prove runtime compatibility."
        packet["policy"].write_bytes(canonical(policy))
    result = receive(packet, envelope)
    assert result["sourceStatus"] == "current"
    assert result["interpretation"]["issues"]
    recalled = findings.recall(
        packet["store"], packet["database"], saved["findingSha256"], packet["policy"]
    )
    assert recalled["interpretation"] == result["interpretation"]
    assert recalled["sourceStatus"] == result["sourceStatus"]
    with pytest.raises(ValueError, match="complete scope/time/attribution"):
        receive(packet, envelope, review(packet, envelope, exported))


def test_missing_corrupt_changed_representation_and_stale_source(packet):
    _, envelope, exported = transfer(packet)
    original = packet["database"].read_bytes()
    digest = packet["finding"]["sources"][0]["sha256"]
    # Integrity failures are unknown, never cached as a current binding.
    with sqlite3.connect(packet["database"]) as db:
        db.execute("DROP TRIGGER source_blobs_no_delete")
        db.execute("DELETE FROM source_blobs WHERE digest=?", (digest,))
    result = receive(packet, envelope)
    assert result["sourceStatus"] == "unknown"
    with pytest.raises(ValueError, match="current own sources"):
        receive(packet, envelope, review(packet, envelope, exported))
    packet["database"].write_bytes(original)
    with sqlite3.connect(packet["database"]) as db:
        with db.blobopen(
            "source_blobs",
            "body",
            db.execute("SELECT rowid FROM source_blobs WHERE digest=?", (digest,)).fetchone()[0],
        ) as blob:
            blob.write(b"X")
    assert receive(packet, envelope)["sourceStatus"] == "unknown"
    packet["database"].write_bytes(original)
    # Synthetic admitted current body retarget uses the existing cache test helper.
    new_body = b'{"name":"synthetic changed name"}\n'
    import hashlib

    def change(index):
        index["files"]["package.json"].update(
            sourceSha256=sha(new_body),
            gitBlob=hashlib.sha1(
                b"blob " + str(len(new_body)).encode() + b"\0" + new_body
            ).hexdigest(),
        )

    fixtures.retarget_index(packet["database"], change, new_body)
    assert receive(packet, envelope)["sourceStatus"] == "changed"
    packet["database"].write_bytes(original)
    value = json.loads(envelope.read_text())
    value["sources"][0]["representation"] = "different-language"
    envelope.write_bytes(canonical(value))
    assert receive(packet, envelope)["sourceStatus"] == "unknown"
    value["sources"][0]["representation"] = findings.REPRESENTATION
    envelope.write_bytes(canonical(value))
    policy = json.loads(packet["policy"].read_text())
    policy["maxSourceAgeSeconds"] = 0
    packet["policy"].write_bytes(canonical(policy))
    assert receive(packet, envelope)["sourceStatus"] == "unknown"


def test_original_observation_requires_exact_receipt_and_explicit_evidence_root(packet):
    observation = Path(packet["finding"]["sources"][0]["originalObservationEvidence"]["locator"])
    value = json.loads(observation.read_text())
    value["result"]["sha256"] = "0" * 64
    observation.write_bytes(canonical(value))
    packet["finding"]["sources"][0]["originalObservationEvidence"]["sha256"] = sha(
        observation.read_bytes()
    )
    save_input(packet)
    with pytest.raises(ValueError, match="does not bind"):
        findings.record(packet["store"], packet["database"], packet["input"], packet["root"])
    with pytest.raises(ValueError, match="outside explicit evidence root"):
        findings.record(
            packet["store"], packet["database"], packet["input"], packet["root"] / "sender"
        )
    assert not packet["store"].exists()


def test_receive_does_not_dereference_sender_locators_or_execute_or_use_network(
    packet, monkeypatch
):
    _, envelope, exported = transfer(packet)
    value = json.loads(envelope.read_text())
    value["originEvidence"]["locator"] = "/never/read/private-file"
    value["sources"][0]["originalObservationEvidence"]["locator"] = (
        "https://example.invalid/receipt"
    )
    envelope.write_bytes(canonical(value))
    before = packet["database"].read_bytes()
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("network attempted"))
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("execution attempted"))
    original_read = findings.read_file

    def guarded(path, *args, **kwargs):
        assert str(path) not in {"/never/read/private-file", "https://example.invalid/receipt"}
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(findings, "read_file", guarded)
    result = receive(packet, envelope)
    assert result["interpretation"]["disposition"] == "unreviewed"
    assert packet["database"].read_bytes() == before
    assert result["cacheStatistics"]["logicalBlobBytesRead"] > 0
    assert result["storeIntegrityBytesRead"] == 2 * len(before)


@pytest.mark.parametrize(
    "mutation",
    [
        "hash",
        "path",
        "revision",
        "version",
        "duplicate-source",
        "lines",
        "claim-bound",
        "sources-bound",
    ],
)
def test_malformed_or_bounded_envelope_refuses_before_store_writes(packet, mutation):
    _, envelope, _ = transfer(packet)
    value = json.loads(envelope.read_text())
    if mutation == "hash":
        value["sources"][0]["sha256"] = "a" * 63
    elif mutation == "path":
        value["sources"][0]["path"] = "../private"
    elif mutation == "revision":
        value["sources"][0]["revision"] = "main"
    elif mutation == "version":
        value["format"] = "lazycollective.finding-handoff/999"
    elif mutation == "duplicate-source":
        value["sources"] *= 2
    elif mutation == "lines":
        value["sources"][0]["lineRange"] = [True, 2]
    elif mutation == "claim-bound":
        value["claim"]["text"] = "x" * 32769
    elif mutation == "sources-bound":
        value["sources"] *= 17
    envelope.write_bytes(canonical(value))
    with pytest.raises((ValueError, TypeError)):
        receive(packet, envelope)
    assert not (packet["root"] / "recipient").exists()


@pytest.mark.parametrize(
    "raw", [b'{"id":1,"id":2}', b'{"id":NaN}', b"x" * 65537, b"[" * 2000 + b"0" + b"]" * 2000]
)
def test_duplicate_json_nonfinite_oversize_and_deep_json_refuse(packet, raw):
    envelope = packet["root"] / "bad.json"
    envelope.write_bytes(raw)
    with pytest.raises((ValueError, RecursionError)):
        receive(packet, envelope)
    assert not (packet["root"] / "recipient").exists()


def test_symlinks_path_traversal_and_corrupt_saved_record_refuse(packet):
    saved, envelope, _ = transfer(packet)
    link = packet["root"] / "link.json"
    link.symlink_to(envelope)
    with pytest.raises(ValueError, match="symlink"):
        receive(packet, link)
    directory_link = packet["root"] / "linked-parent"
    directory_link.symlink_to(packet["root"], target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        findings.export(packet["store"], saved["findingSha256"], directory_link / "new.json")
    with pytest.raises(ValueError, match="traversal"):
        findings.inspect(packet["root"] / "x" / ".." / "sender", saved["findingSha256"])
    record_path = Path(saved["findingPath"])
    record_path.write_bytes(b"{}")
    with pytest.raises(ValueError, match="integrity"):
        findings.inspect(packet["store"], saved["findingSha256"])


def test_changed_and_missing_status_precedence_is_explicit(packet):
    _, envelope, _ = transfer(packet)
    value = json.loads(envelope.read_text())
    value["sources"][0]["sha256"] = "0" * 64
    missing = copy.deepcopy(value["sources"][0])
    missing["path"] = "not-cached.md"
    value["sources"].append(missing)
    envelope.write_bytes(canonical(value))
    result = receive(packet, envelope)
    assert result["sourceStatus"] == "changed"
    assert [s["sourceStatus"] for s in result["sources"]] == ["changed", "unknown"]


def test_record_refuses_exact_hash_mismatch_without_source_writes(packet):
    packet["finding"]["sources"][0].update(
        sha256="0" * 64,
        originalObservedAt=None,
        originalTimeReason="Unknown for this synthetic mismatched claim.",
        originalObservationEvidence=None,
    )
    save_input(packet)
    original = packet["database"].read_bytes()
    with pytest.raises(ValueError, match="exact verified current"):
        findings.record(packet["store"], packet["database"], packet["input"], packet["root"])
    assert not packet["store"].exists()
    assert packet["database"].read_bytes() == original


def test_later_source_reread_cannot_backfill_original_time(packet):
    source = packet["finding"]["sources"][0]
    observation = Path(source["originalObservationEvidence"]["locator"])
    value = json.loads(observation.read_text())
    # All source identities still match; only the observation receipt is later
    # than this original finding. It cannot supply historical provenance.
    packet["finding"]["findingCreatedAt"] = source["originalObservedAt"]
    observation.write_bytes(canonical(value))
    save_input(packet)
    with pytest.raises(ValueError, match="predate the original finding"):
        findings.record(packet["store"], packet["database"], packet["input"], packet["root"])


def test_finite_store_capacity_refuses_without_replacing_prior_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(findings, "MAX_FILES", 1)
    store = tmp_path / "finite"
    first = canonical({"value": "first"})
    key, path = findings.store_file(store, "finding", first)
    assert findings.store_file(store, "finding", first)[0] == key
    with pytest.raises(ValueError, match="store is full"):
        findings.store_file(store, "finding", canonical({"value": "second"}))
    assert path.read_bytes() == first
    assert len(list(store.iterdir())) == 1


def advance_current(database, *, changed=False, inspected=True, missing_path=False, mode="100644"):
    """Synthetic admitted frontier, retaining the original exact revision and body."""
    with sqlite3.connect(database) as db:
        repo, old = db.execute("SELECT identity,revision FROM current").fetchone()
        record = json.loads(
            db.execute(
                "SELECT r.body FROM versions v JOIN records r ON r.digest=v.digest "
                "WHERE v.identity=? AND v.revision=? AND v.component='.'",
                (repo, old),
            ).fetchone()[0]
        )
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
        revision, tree = "f" * 40, "e" * 40
        for value in (record, admission, index):
            value.update(revision=revision, tree=tree)
        item = index["files"]["package.json"]
        item["mode"] = mode
        if changed:
            body = b'{"name":"a different synthetic source"}\n'
            item.update(
                gitBlob=hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest(),
                sourceSha256=sha(body),
            )
            if inspected:
                db.execute("INSERT INTO source_blobs VALUES(?,?)", (sha(body), body))
        if not inspected:
            item["sourceSha256"] = None
        if missing_path:
            del index["files"]["package.json"]
        raw = canonical(index)
        admission["sourceIndexSha256"] = sha(raw)
        db.execute("INSERT INTO objects VALUES(?,?)", (sha(raw), raw))
        raw = canonical(admission)
        record["admissionSha256"] = sha(raw)
        db.execute("INSERT INTO admissions VALUES(?,?)", (sha(raw), raw))
        raw = canonical(record)
        db.execute("INSERT INTO records VALUES(?,?)", (sha(raw), raw))
        db.execute("INSERT INTO versions VALUES(?,?,'.',?)", (repo, revision, sha(raw)))
        db.execute("UPDATE current SET revision=?,tree=? WHERE identity=?", (revision, tree, repo))


@pytest.mark.parametrize(
    "changed,inspected,expected",
    [
        (True, True, "changed"),
        (True, False, "changed"),
        (False, True, "current"),
        (False, False, "unknown"),
    ],
)
def test_current_blob_identity_survives_unavailable_body_without_revision_inference(
    packet, changed, inspected, expected
):
    _, envelope, _ = transfer(packet)
    advance_current(packet["database"], changed=changed, inspected=inspected)
    before = packet["database"].read_bytes()
    receipt = receive(packet, envelope)
    assert receipt["sourceStatus"] == expected
    source = receipt["sources"][0]
    assert source["recipientRevision"] == "f" * 40
    if changed:
        assert source["recipientGitBlob"] != source["boundHistoricalGitBlob"]
    else:
        assert source["recipientGitBlob"] == source["boundHistoricalGitBlob"]
    if not inspected:
        assert any("not inspected" in reason for reason in source["reasons"])
    assert packet["database"].read_bytes() == before


@pytest.mark.parametrize(
    "missing_path,mode,expected",
    [
        (True, "100644", "unknown"),
        (False, "120000", "unknown"),
        (False, "100755", "current"),
    ],
)
def test_missing_path_or_mode_alone_does_not_prove_different_bytes(
    packet, missing_path, mode, expected
):
    _, envelope, _ = transfer(packet)
    advance_current(packet["database"], missing_path=missing_path, mode=mode)
    assert receive(packet, envelope)["sourceStatus"] == expected


def test_changed_frontier_requires_verified_historical_binding(packet):
    _, envelope, _ = transfer(packet)
    advance_current(packet["database"], changed=True, inspected=False)
    with sqlite3.connect(packet["database"]) as db:
        db.execute("DROP TRIGGER source_blobs_no_delete")
        db.execute(
            "DELETE FROM source_blobs WHERE digest=?", (packet["finding"]["sources"][0]["sha256"],)
        )
    receipt = receive(packet, envelope)
    assert receipt["sourceStatus"] == "unknown"
    assert "historicalBindingIssue" in receipt["sources"][0]


@pytest.mark.parametrize("command", ["record", "receive"])
@pytest.mark.parametrize("bad", [None, 42, [], {}])
def test_malformed_repository_types_are_structured_refusals(packet, command, bad):
    if command == "receive":
        _, path, _ = transfer(packet)
        value = json.loads(path.read_bytes())
    else:
        path, value = packet["input"], copy.deepcopy(packet["finding"])
    value["sources"][0]["repository"] = bad
    path.write_bytes(canonical(value))
    store = packet["root"] / "invalid-store"
    args = [
        sys.executable,
        str(ROOT / "scripts/decision_findings.py"),
        command,
        "--store",
        str(store),
        "--database",
        str(packet["database"]),
    ]
    args += (
        ["--finding", str(path), "--evidence-root", str(packet["root"])]
        if command == "record"
        else ["--envelope", str(path), "--policy", str(packet["policy"])]
    )
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 1 and result.stderr == ""
    assert json.loads(result.stdout)["state"] == "refused"
    assert not store.exists()


@pytest.mark.parametrize("age", [10**400, -(10**400), 1e300, -1e300, True, "86400"])
def test_extreme_and_invalid_policy_ages_are_structured_refusals(packet, age):
    _, envelope, _ = transfer(packet)
    policy = json.loads(packet["policy"].read_bytes())
    policy["maxSourceAgeSeconds"] = age
    packet["policy"].write_bytes(canonical(policy))
    store = packet["root"] / "invalid-age-store"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/decision_findings.py"),
            "receive",
            "--store",
            str(store),
            "--database",
            str(packet["database"]),
            "--envelope",
            str(envelope),
            "--policy",
            str(packet["policy"]),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1 and result.stderr == ""
    assert json.loads(result.stdout)["state"] == "refused"
    assert not store.exists()
