import json
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
import yaml

sys.path.append(str(Path(__file__).resolve().parents[1]))

import restore_cloudflare_public_state as restore  # noqa: E402
import sync_cloudflare_public_snapshot as sync  # noqa: E402

REPOSITORY = Path(__file__).resolve().parents[2]
FIXTURE = REPOSITORY / "crates/dotrepo-core/tests/fixtures/public-export/expected/public"


def deployed_assets(monkeypatch, *, prefix: str = "/dotrepo"):
    requests = []

    def fetch(url: str, timeout: float) -> bytes:
        path = unquote(urlsplit(url).path)
        assert path.startswith(f"{prefix}/")
        relative = path[len(prefix) + 1 :]
        assert "/query-input/" not in relative
        requests.append(relative)
        body = (FIXTURE / relative).read_bytes()
        if relative == "v0/meta.json":
            meta = json.loads(body)
            meta["paths"] = {key: f"{prefix}{value}" for key, value in meta["paths"].items()}
            return json.dumps(meta).encode()
        return body

    monkeypatch.setattr(restore, "fetch_bytes", fetch)
    return requests


def test_clean_runner_restores_previous_payload_and_seeds_history(
    tmp_path: Path, monkeypatch
) -> None:
    requests = deployed_assets(monkeypatch)
    export_root = tmp_path / "fresh-runner/public"
    staging = tmp_path / "fresh-runner/worker/public-snapshot"
    archived = {
        "snapshotId": "archived-before-edge",
        "snapshotDigest": "older-source",
        "generatedAt": "2026-03-09T18:30:00Z",
        "repositoryCount": 1,
        "fileCount": 6,
    }
    monkeypatch.setattr(restore, "read_archive_log", lambda *_: {"entries": [archived]})
    result = restore.restore_public_state(
        "https://example.test", "/dotrepo", export_root, staging, archive_bucket="archive"
    )
    previous = result["snapshotId"]
    seeded_log = sync.load_json(export_root / "v0/snapshots/log.json")
    assert seeded_log["snapshotCount"] == 2
    assert seeded_log["entries"][0] == archived
    assert (staging / f"v0/snapshots/{previous}/repos/index.json").is_file()
    assert not (staging / f"v0/snapshots/{previous}/query-input").exists()
    assert result["restoredFiles"] == 10
    assert requests.count("v0/meta.json") == 2

    # The next export uses the seeded history. Stage it on this otherwise clean
    # runner and prove public payload retention and log/stats stay coherent.
    shutil.copytree(FIXTURE, export_root, dirs_exist_ok=True)
    new = "new-export-payload"
    (export_root / f"v0/snapshots/{previous}").rename(export_root / f"v0/snapshots/{new}")
    meta = sync.load_json(export_root / "v0/meta.json")
    meta["snapshotId"] = new
    (export_root / "v0/meta.json").write_text(json.dumps(meta))
    current_entry = {
        **seeded_log["entries"][-1],
        "snapshotId": new,
        "generatedAt": "2026-03-11T18:30:00Z",
    }
    current_log = sync.merge_log_documents(seeded_log, {"entries": [current_entry]})
    (export_root / "v0/snapshots/log.json").write_text(json.dumps(current_log))
    monkeypatch.setattr(
        sys, "argv", ["sync", "--input", str(export_root), "--output", str(staging)]
    )
    assert sync.main() == 0
    assert (staging / f"v0/snapshots/{previous}/repos/index.json").is_file()
    assert (staging / f"v0/snapshots/{new}/repos/index.json").is_file()
    assert sync.load_json(staging / "v0/snapshots/log.json") == current_log
    assert sync.load_json(staging / "v0/stats.json")["history"] == current_log["entries"]


@pytest.mark.parametrize("failure", ["hash", "path", "pointer"])
def test_failed_restoration_keeps_existing_local_state(
    tmp_path: Path, monkeypatch, failure: str
) -> None:
    deployed_assets(monkeypatch, prefix="")
    normal_fetch = restore.fetch_bytes
    meta = json.loads((FIXTURE / "v0/meta.json").read_text())
    snapshot = meta["snapshotId"]
    meta_reads = 0

    def broken_fetch(url: str, timeout: float) -> bytes:
        nonlocal meta_reads
        body = normal_fetch(url, timeout)
        path = urlsplit(url).path
        if failure == "hash" and path.endswith("/repos/index.json"):
            return body + b"corrupted"
        if failure == "path" and path.endswith("/files.json"):
            manifest = json.loads(body)
            manifest["files"][0]["path"] = f"v0/snapshots/{snapshot}/../../escape.json"
            return json.dumps(manifest).encode()
        if failure == "pointer" and path == "/v0/meta.json":
            meta_reads += 1
            if meta_reads == 2:
                changed = json.loads(body)
                changed["snapshotId"] = "another-deployment"
                return json.dumps(changed).encode()
        return body

    monkeypatch.setattr(restore, "fetch_bytes", broken_fetch)
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "sentinel").write_text("previous local snapshot")
    export_root = tmp_path / "export"
    with pytest.raises(ValueError):
        restore.restore_public_state("https://example.test", "/", export_root, staging)
    assert (staging / "sentinel").read_text() == "previous local snapshot"
    assert not export_root.exists()


def test_deploy_restores_state_before_export_and_requires_complete_archive_history() -> None:
    workflow = yaml.safe_load((REPOSITORY / ".github/workflows/public-cloudflare.yml").read_text())
    steps = workflow["jobs"]["deploy"]["steps"]
    restoration = next(
        i
        for i, step in enumerate(steps)
        if "restore_cloudflare_public_state.py" in step.get("run", "")
    )
    export = next(
        i for i, step in enumerate(steps) if "--out-dir release-gate/public" in step.get("run", "")
    )
    stage = next(
        i
        for i, step in enumerate(steps)
        if "sync_cloudflare_public_snapshot.py" in step.get("run", "")
    )
    assert restoration < export < stage
    archive = next(step for step in steps if "archive_public_snapshot_r2.py" in step.get("run", ""))
    assert "--require-complete-history" in archive["run"]
