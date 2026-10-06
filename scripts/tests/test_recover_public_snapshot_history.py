import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

import recover_public_snapshot_history as recovery  # noqa: E402

REPOSITORY = Path(__file__).resolve().parents[2]


def git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repository, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def recovery_inputs(tmp_path: Path):
    binary = REPOSITORY / "target/debug/dotrepo"
    if not binary.is_file():
        pytest.skip("actual dotrepo CLI must be built for public reconstruction controls")
    repository = tmp_path / "repository"
    repository.mkdir()
    shutil.copytree(
        REPOSITORY / "crates/dotrepo-core/tests/fixtures/public-export/fixture-index",
        repository / "index",
    )
    shutil.copy2(REPOSITORY / "Cargo.toml", repository / "Cargo.toml")
    git(repository, "init", "-q")
    git(repository, "add", "index", "Cargo.toml")
    git(
        repository,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.test",
        "commit",
        "-qm",
        "fixture",
    )
    commit = git(repository, "rev-parse", "HEAD")
    exported = tmp_path / "original"
    subprocess.run(
        [
            str(binary),
            "public",
            "export",
            "--index-root",
            str(repository / "index"),
            "--out-dir",
            str(exported),
            "--generated-at",
            "2026-03-10T18:30:00Z",
            "--stale-after-hours",
            "168",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    log = exported / "v0/snapshots/log.json"
    entry = json.loads(log.read_text())["entries"][0]
    known = f"v0/snapshots/{entry['snapshotId']}/repos/index.json"
    plan = {
        "publishedLogSha256": recovery.sha256(log),
        "exporter": {
            "commit": commit,
            "version": recovery.exporter_version(repository, commit),
            "binarySha256": recovery.sha256(binary),
        },
        "staleAfterHours": 168,
        "sources": {entry["snapshotDigest"]: commit},
        "knownBodies": [
            {
                "snapshotId": entry["snapshotId"],
                "path": known,
                "sha256": recovery.sha256(exported / known),
            }
        ],
    }
    source_map = tmp_path / "source-map.json"
    source_map.write_text(json.dumps(plan))
    return repository, binary, log, source_map, exported, plan


def test_actual_cli_reconstructs_an_immutable_index_and_matches_retained_bytes(
    tmp_path: Path, recovery_inputs
) -> None:
    repository, binary, log, source_map, original, plan = recovery_inputs
    # Dirty checkout inputs must not leak into the immutable archived index.
    (repository / "index/untracked").write_text("never exported")
    output = tmp_path / "recovered"
    receipt = recovery.recover_history(log, source_map, binary, output, repository)
    assert receipt["kind"] == "deterministic_reconstruction"
    assert len(receipt["snapshots"]) == 1
    assert len(receipt["retainedPublishedBodyMatches"]) == 1
    assert (output / "v0/snapshots/log.json").read_bytes() == log.read_bytes()
    for source in (original / "v0/snapshots").rglob("*"):
        if source.is_file():
            assert (output / source.relative_to(original)).read_bytes() == source.read_bytes()
    assert receipt["sourceMapSha256"] == recovery.sha256(source_map)
    assert receipt["exporter"] == plan["exporter"]


@pytest.mark.parametrize(
    "failure", ["log", "binary", "version", "source", "identity", "counts", "known-body", "output"]
)
def test_recovery_refuses_changed_inputs_without_exposing_partial_output(
    tmp_path: Path, recovery_inputs, failure: str
) -> None:
    repository, binary, log, source_map, _original, plan = recovery_inputs
    output = tmp_path / "recovered"
    if failure == "log":
        plan["publishedLogSha256"] = "0" * 64
    elif failure == "binary":
        plan["exporter"]["binarySha256"] = "0" * 64
    elif failure == "version":
        plan["exporter"]["version"] = "different version"
    elif failure == "source":
        plan["sources"] = {}
    elif failure in {"identity", "counts"}:
        document = json.loads(log.read_text())
        if failure == "identity":
            document["entries"][0]["snapshotId"] = "wrong-snapshot"
        else:
            document["entries"][0]["repositoryCount"] += 1
        log.write_text(json.dumps(document))
        plan["publishedLogSha256"] = hashlib.sha256(log.read_bytes()).hexdigest()
    elif failure == "known-body":
        plan["knownBodies"][0]["sha256"] = "0" * 64
    elif failure == "output":
        output.mkdir()
        (output / "sentinel").write_text("preserved")
    source_map.write_text(json.dumps(plan))
    with pytest.raises(ValueError):
        recovery.recover_history(log, source_map, binary, output, repository)
    if failure == "output":
        assert (output / "sentinel").read_text() == "preserved"
    else:
        assert not output.exists()


def test_per_entry_recovery_uses_the_exact_original_exporter_pin(
    tmp_path: Path, recovery_inputs
) -> None:
    repository, binary, log, source_map, _original, plan = recovery_inputs
    entry = json.loads(log.read_text())["entries"][0]
    exporter = dict(plan["exporter"])
    root = tmp_path / "exporters"
    pinned_binary = root / exporter["commit"] / "target/debug/dotrepo"
    pinned_binary.parent.mkdir(parents=True)
    shutil.copy2(binary, pinned_binary)
    plan["entryExporters"] = {entry["snapshotId"]: exporter}
    # Per-entry mode must not silently substitute a shared renderer.
    plan["exporter"] = {"commit": "shared-renderer-must-not-be-used"}
    source_map.write_text(json.dumps(plan))
    receipt = recovery.recover_history(
        log, source_map, None, tmp_path / "recovered", repository, exporter_root=root
    )
    assert receipt["exporterMode"] == "original_per_entry"
    assert receipt["snapshots"][0]["exporter"] == exporter
    assert receipt["snapshots"][0]["command"][0] == str(pinned_binary)


@pytest.mark.parametrize("mutation", ["renderer", "missing-entry"])
def test_per_entry_renderer_swap_or_missing_pin_refuses_before_execution(
    tmp_path: Path, recovery_inputs, mutation: str
) -> None:
    repository, binary, log, source_map, _original, plan = recovery_inputs
    entry = json.loads(log.read_text())["entries"][0]
    exporter = dict(plan["exporter"])
    root = tmp_path / "exporters"
    pinned_binary = root / exporter["commit"] / "target/debug/dotrepo"
    pinned_binary.parent.mkdir(parents=True)
    shutil.copy2(binary, pinned_binary)
    plan["entryExporters"] = {entry["snapshotId"]: exporter}
    if mutation == "renderer":
        # Snapshot identities bind the index and timestamps, so a renderer swap
        # must be refused independently of whether those identities would match.
        pinned_binary.write_bytes(b"different rendering implementation")
    else:
        plan["entryExporters"] = {}
    source_map.write_text(json.dumps(plan))
    output = tmp_path / "recovered"
    with pytest.raises(ValueError):
        recovery.recover_history(log, source_map, None, output, repository, exporter_root=root)
    assert not output.exists()
