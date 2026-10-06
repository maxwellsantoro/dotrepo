import importlib.util
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

SCRIPT = Path(__file__).resolve().parents[1] / "archive_public_snapshot_r2.py"
SPEC = importlib.util.spec_from_file_location("archive_public_snapshot_r2", SCRIPT)
archive = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(archive)


def write_snapshot(public_root: Path, snapshot: str = "current") -> dict:
    entry = {
        "snapshotId": snapshot,
        "snapshotDigest": "source-digest",
        "generatedAt": "2026-10-03T12:00:00Z",
        "fileCount": 2,
        "repositoryCount": 1,
    }
    root = public_root / "v0/snapshots" / snapshot
    leaves = []
    for suffix in ["repos/index.json", "query-input/github.com/example/repo.json"]:
        path = root / suffix
        path.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps({"snapshot": snapshot}).encode()
        path.write_bytes(body)
        leaves.append(
            {
                "path": path.relative_to(public_root).as_posix(),
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            }
        )
    (root / "files.json").write_text(
        json.dumps({"freshness": entry, "fileCount": len(leaves), "files": leaves})
    )
    return entry


def test_snapshot_files_selects_snapshot_tree_only(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    snapshot = public_root / "v0" / "snapshots" / "abc123"
    snapshot.mkdir(parents=True)
    (snapshot / "files.json").write_text("{}\n")
    private = snapshot / "query-input/repo.json"
    private.parent.mkdir()
    private.write_text("private runtime input")
    (public_root / "v0" / "snapshots" / "log.json").write_text("{}\n")
    (public_root / "v0" / "meta.json").write_text("{}\n")

    files = archive.snapshot_files(public_root)

    assert [path.relative_to(public_root).as_posix() for path in files] == [
        "v0/snapshots/abc123/files.json",
        "v0/snapshots/log.json",
    ]


def test_upload_command_uses_public_key_and_r2_metadata(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    path = public_root / "v0" / "snapshots" / "abc123" / "repos" / "index.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}\n")

    command = archive.upload_command("dotrepo-archive", public_root, path)

    assert command[:6] == [
        "npx",
        "wrangler",
        "r2",
        "object",
        "put",
        "dotrepo-archive/v0/snapshots/abc123/repos/index.json",
    ]
    assert "--remote" in command
    assert command[command.index("--file") + 1] == str(path)
    assert command[command.index("--content-type") + 1] == "application/json; charset=utf-8"
    assert command[command.index("--cache-control") + 1] == "public, max-age=31536000, immutable"


def test_upload_command_marks_snapshot_log_mutable(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    path = public_root / "v0" / "snapshots" / "log.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}\n")

    command = archive.upload_command("dotrepo-archive", public_root, path)

    assert command[command.index("--cache-control") + 1] == "no-cache"


def test_archive_retains_remote_history_and_uploads_log_last(tmp_path: Path, monkeypatch) -> None:
    public_root = tmp_path / "public"
    current = write_snapshot(public_root)
    previous = {"snapshotId": "previous", "generatedAt": "2026-10-02T12:00:00Z"}
    (public_root / "v0/snapshots/log.json").write_text(json.dumps({"entries": [current]}))
    monkeypatch.setattr(archive, "read_archive_log", lambda *_: {"entries": [previous]})
    uploaded = []

    def upload(command, **kwargs):
        if command[3] == "bulk":
            batch = json.loads(Path(command[command.index("--filename") + 1]).read_text())
            assert "--remote" in command
            assert command[command.index("--concurrency") + 1] == "8"
            for item in batch:
                assert "query-input" not in item["key"]
                uploaded.append((f"archive/{item['key']}", Path(item["file"]).read_text()))
        else:
            uploaded.append((command[5], Path(command[command.index("--file") + 1]).read_text()))

    monkeypatch.setattr(archive.subprocess, "run", upload)
    assert archive.archive_snapshots(public_root, "archive", tmp_path) == 3
    assert uploaded[-1][0] == "archive/v0/snapshots/log.json"
    assert json.loads(uploaded[-1][1])["entries"] == [previous, current]
    with pytest.raises(ValueError, match="omits archive history"):
        archive.archive_snapshots(public_root, "archive", tmp_path, require_complete_history=True)


def test_archive_refuses_unbackfilled_published_history_before_any_upload(
    tmp_path: Path, monkeypatch
) -> None:
    public_root = tmp_path / "public"
    current = write_snapshot(public_root)
    old = {**current, "snapshotId": "evicted-old"}
    (public_root / "v0/snapshots/log.json").write_text(json.dumps({"entries": [old, current]}))
    monkeypatch.setattr(archive, "read_archive_log", lambda *_: {})
    uploads = []
    monkeypatch.setattr(archive.subprocess, "run", lambda *args, **kwargs: uploads.append(args))
    with pytest.raises(ValueError, match="backfill"):
        archive.archive_snapshots(public_root, "archive", tmp_path, require_complete_history=True)
    assert uploads == []


def test_archive_skips_already_archived_immutable_payloads(tmp_path: Path, monkeypatch) -> None:
    public_root = tmp_path / "public"
    current = write_snapshot(public_root)
    (public_root / "v0/snapshots/log.json").write_text(json.dumps({"entries": [current]}))
    monkeypatch.setattr(archive, "read_archive_log", lambda *_: {"entries": [current]})
    uploads = []
    monkeypatch.setattr(archive.subprocess, "run", lambda *args, **kwargs: uploads.append(args))
    assert archive.archive_snapshots(public_root, "archive", tmp_path) == 1
    assert len(uploads) == 1
    assert uploads[0][0][5].endswith("/v0/snapshots/log.json")


def test_failed_bulk_upload_never_commits_the_archive_log(tmp_path: Path, monkeypatch) -> None:
    public_root = tmp_path / "public"
    current = write_snapshot(public_root)
    (public_root / "v0/snapshots/log.json").write_text(json.dumps({"entries": [current]}))
    monkeypatch.setattr(archive, "read_archive_log", lambda *_: {})
    calls = []

    def fail(command, **kwargs):
        calls.append(command)
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(archive.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        archive.archive_snapshots(public_root, "archive", tmp_path)
    assert len(calls) == 1
    assert calls[0][3:5] == ["bulk", "put"]


@pytest.mark.parametrize(
    "failure", ["missing", "hash", "traversal", "count", "identity", "symlink"]
)
def test_new_archive_snapshot_requires_valid_manifest_and_payloads(
    tmp_path: Path, failure: str
) -> None:
    public_root = tmp_path / "public"
    entry = write_snapshot(public_root)
    manifest_path = public_root / "v0/snapshots/current/files.json"
    manifest = json.loads(manifest_path.read_text())
    payload = public_root / manifest["files"][0]["path"]
    if failure == "missing":
        payload.unlink()
    elif failure == "hash":
        payload.write_text("corrupted")
    elif failure == "traversal":
        manifest["files"][0]["path"] = "v0/snapshots/current/../../outside.json"
    elif failure == "count":
        entry["fileCount"] += 1
    elif failure == "identity":
        manifest["freshness"]["snapshotDigest"] = "different-source"
    elif failure == "symlink":
        payload.unlink()
        outside = tmp_path / "outside.json"
        outside.write_text("outside")
        payload.symlink_to(outside)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        archive.validated_snapshot_files(public_root, entry)


def test_archive_accepts_restored_public_payloads_without_private_inputs(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    entry = write_snapshot(public_root)
    (public_root / "v0/snapshots/current/query-input/github.com/example/repo.json").unlink()
    files = archive.validated_snapshot_files(public_root, entry)
    assert [path.relative_to(public_root).as_posix() for path in files] == [
        "v0/snapshots/current/repos/index.json",
        "v0/snapshots/current/files.json",
    ]


def test_actual_public_export_manifest_is_complete_for_initial_archiving() -> None:
    public_root = (
        Path(__file__).resolve().parents[2]
        / "crates/dotrepo-core/tests/fixtures/public-export/expected/public"
    )
    entry = json.loads((public_root / "v0/snapshots/log.json").read_text())["entries"][0]
    files = archive.validated_snapshot_files(public_root, entry)
    assert len(files) == entry["fileCount"] + 1


def test_archive_read_treats_only_a_missing_object_as_empty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        archive.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, "", "Authentication error"),
    )
    with pytest.raises(RuntimeError, match="Authentication error"):
        archive.read_archive_log("archive", tmp_path)
    monkeypatch.setattr(
        archive.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 1, "", "The specified key does not exist."
        ),
    )
    assert archive.read_archive_log("archive", tmp_path) == {}
