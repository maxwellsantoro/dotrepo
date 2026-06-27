import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "diff_public_export_files.py"
SPEC = importlib.util.spec_from_file_location("diff_public_export_files", SCRIPT)
file_delta = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(file_delta)


def write_manifest(path: Path, files: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps(
            {
                "apiVersion": "v0",
                "freshness": {
                    "generatedAt": "2026-03-10T18:30:00Z",
                    "snapshotDigest": "fixture",
                },
                "fileCount": len(files),
                "files": files,
            },
            indent=2,
        )
        + "\n"
    )


def test_compare_manifests_reports_refetch_set(tmp_path: Path) -> None:
    old = tmp_path / "old-files.json"
    new = tmp_path / "new-files.json"
    write_manifest(
        old,
        [
            {"path": "v0/meta.json", "bytes": 100, "sha256": "aaa"},
            {"path": "v0/repos/a/index.json", "bytes": 50, "sha256": "bbb"},
            {"path": "v0/repos/removed/index.json", "bytes": 25, "sha256": "ccc"},
        ],
    )
    write_manifest(
        new,
        [
            {"path": "v0/meta.json", "bytes": 110, "sha256": "changed"},
            {"path": "v0/repos/a/index.json", "bytes": 50, "sha256": "bbb"},
            {"path": "v0/repos/new/index.json", "bytes": 40, "sha256": "ddd"},
        ],
    )

    report = file_delta.compare_manifests(old, new)

    assert report["schema"] == "dotrepo-public-file-delta/v0"
    assert report["summary"]["addedCount"] == 1
    assert report["summary"]["changedCount"] == 1
    assert report["summary"]["removedCount"] == 1
    assert report["summary"]["unchangedCount"] == 1
    assert report["summary"]["refetchBytes"] == 150
    assert report["summary"]["refetchByteRatio"] == 0.75
    assert report["refetch"] == ["v0/repos/new/index.json", "v0/meta.json"]


def test_render_markdown_lists_refetch_files(tmp_path: Path) -> None:
    old = tmp_path / "old-files.json"
    new = tmp_path / "new-files.json"
    write_manifest(old, [{"path": "v0/meta.json", "bytes": 100, "sha256": "aaa"}])
    write_manifest(new, [{"path": "v0/meta.json", "bytes": 110, "sha256": "bbb"}])

    markdown = file_delta.render_markdown(file_delta.compare_manifests(old, new))

    assert "# dotrepo public file delta" in markdown
    assert "| Changed files | 1 |" in markdown
    assert "- `v0/meta.json`" in markdown


def test_duplicate_manifest_paths_exit_with_message(tmp_path: Path) -> None:
    old = tmp_path / "old-files.json"
    new = tmp_path / "new-files.json"
    duplicate = [
        {"path": "v0/meta.json", "bytes": 100, "sha256": "aaa"},
        {"path": "v0/meta.json", "bytes": 100, "sha256": "aaa"},
    ]
    write_manifest(old, duplicate)
    write_manifest(new, duplicate)

    try:
        file_delta.compare_manifests(old, new)
    except SystemExit as exc:
        message = str(exc)
    else:
        raise AssertionError("duplicate manifest path should exit")

    assert "duplicate file manifest path v0/meta.json" in message
