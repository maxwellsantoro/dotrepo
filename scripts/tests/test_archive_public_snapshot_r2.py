import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "archive_public_snapshot_r2.py"
SPEC = importlib.util.spec_from_file_location("archive_public_snapshot_r2", SCRIPT)
archive = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(archive)


def test_snapshot_files_selects_snapshot_tree_only(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    snapshot = public_root / "v0" / "snapshots" / "abc123"
    snapshot.mkdir(parents=True)
    (snapshot / "files.json").write_text("{}\n")
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

    assert command[:6] == ["npx", "wrangler", "r2", "object", "put", "dotrepo-archive/v0/snapshots/abc123/repos/index.json"]
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
