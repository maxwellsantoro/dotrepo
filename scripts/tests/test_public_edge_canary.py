import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "public_edge_canary.py"
SPEC = importlib.util.spec_from_file_location("public_edge_canary", SCRIPT)
canary = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(canary)


def manifest() -> dict:
    return {
        "version": 1,
        "site_rev": 3,
        "generated": "2026-07-03T01:15:11Z",
        "entries": {
            "/v0/repos/github.com/example/orbit/index.json": {"rev": 1},
            "/v0/repos/github.com/example/orbit/profile.json": {"rev": 1},
            "/v0/repos/index.json": {"rev": 1},
        },
    }


def stats() -> dict:
    return {
        "latest": {
            "snapshotId": "abc123",
            "snapshotDigest": "abc123def456",
            "repositoryCount": 1,
        },
        "pagedigest": {
            "version": 1,
            "siteRev": 3,
            "generated": "2026-07-03T01:15:11Z",
            "manifestBytes": 1000,
            "recordsCovered": 3,
            "newRecords": 1,
            "changedRecords": 1,
            "unchangedRecords": 1,
            "removedRecords": 0,
            "recordsNeedingFetch": 2,
            "fetchesAvoided": 1,
            "bytesCovered": 1200,
            "bytesAvoided": 400,
            "estimatedTokensAvoided": 100,
        },
    }


def health() -> dict:
    return {
        "ok": True,
        "canonicalOrigin": "https://dotrepo.org",
        "apiVersion": "v0",
        "snapshotId": "abc123",
        "snapshotDigest": "abc123def456",
        "reposIndexCount": 1,
        "statsRepositoryCount": 1,
        "pagedigestSiteRev": 3,
        "pagedigestRecordsCovered": 3,
        "checkedAt": "2026-07-03T12:00:00Z",
        "homepageDigest": "a" * 64,
        "metaDigest": "b" * 64,
        "statsDigest": "c" * 64,
        "reposIndexDigest": "d" * 64,
        "filesDigest": "e" * 64,
        "pagedigestDigest": "f" * 64,
    }


def test_validate_pagedigest_stats_accepts_coherent_export_economics() -> None:
    summary = canary.validate_pagedigest_stats(stats(), manifest())

    assert summary == {
        "recordsCovered": 3,
        "recordsNeedingFetch": 2,
        "fetchesAvoided": 1,
        "bytesAvoided": 400,
        "estimatedTokensAvoided": 100,
    }


def test_validate_pagedigest_stats_is_optional_until_stats_bearing_export() -> None:
    assert canary.validate_pagedigest_stats({}, manifest()) is None


def test_validate_pagedigest_stats_rejects_manifest_record_mismatch() -> None:
    broken = stats()
    broken["pagedigest"]["recordsCovered"] = 2

    with pytest.raises(canary.CanaryFailure, match="recordsCovered"):
        canary.validate_pagedigest_stats(broken, manifest())


def test_validate_pagedigest_stats_rejects_bad_token_estimate() -> None:
    broken = stats()
    broken["pagedigest"]["estimatedTokensAvoided"] = 99

    with pytest.raises(canary.CanaryFailure, match="estimatedTokensAvoided"):
        canary.validate_pagedigest_stats(broken, manifest())


def test_validate_health_accepts_coherent_public_surface() -> None:
    summary = canary.validate_health(
        health(),
        {
            "apiVersion": "v0",
            "generatedAt": "2026-07-03T12:00:00Z",
            "snapshotId": "abc123",
            "snapshotDigest": "abc123def456",
        },
        {"repositories": [{"identity": {"repo": "alpha"}}]},
        stats(),
    )

    assert summary == {
        "ok": True,
        "snapshotId": "abc123",
        "reposIndexCount": 1,
        "pagedigestSiteRev": 3,
    }


def test_validate_health_rejects_stale_repository_count() -> None:
    broken = health()
    broken["reposIndexCount"] = 2

    with pytest.raises(canary.CanaryFailure, match="reposIndexCount"):
        canary.validate_health(
            broken,
            {
                "apiVersion": "v0",
                "generatedAt": "2026-07-03T12:00:00Z",
                "snapshotId": "abc123",
                "snapshotDigest": "abc123def456",
            },
            {"repositories": [{"identity": {"repo": "alpha"}}]},
            stats(),
        )


def test_validate_pagedigest_homepage_accepts_current_public_copy() -> None:
    homepage = """
    <p>Publish at <code>/.well-known/pagedigest.json</code>.</p>
    <p>PageDigest version 1 is final.</p>
    <p>A Rust generator and a Python consumer library exist today.</p>
    """
    canary.validate_pagedigest_homepage(homepage)


def test_validate_pagedigest_homepage_rejects_stale_rc_copy() -> None:
    homepage = """
    <p>Version 1, release candidate</p>
    <p>Rust generator</p>
    <p>Python consumer</p>
    """
    with pytest.raises(canary.CanaryFailure, match="manifest path"):
        canary.validate_pagedigest_homepage(homepage)


def snapshot_meta() -> dict:
    snapshot_id = "a" * 64
    digest = "b" * 64
    root = f"/v0/snapshots/{snapshot_id}"
    return {
        "snapshotId": snapshot_id,
        "snapshotDigest": digest,
        "validators": {"snapshot": f"sha256:{digest}", "etag": f'"dotrepo-v0-{snapshot_id}"'},
        "paths": {
            "root": root,
            "inventory": f"{root}/repos/index.json",
            "files": f"{root}/files.json",
        },
    }


def test_snapshot_metadata_accepts_independent_payload_and_index_digests():
    snapshot_id, digest, paths = canary.validate_snapshot_metadata(snapshot_meta())
    assert snapshot_id == "a" * 64
    assert digest == "b" * 64
    assert snapshot_id != digest
    assert paths["root"].endswith(snapshot_id)


@pytest.mark.parametrize("field", ["snapshotId", "snapshotDigest"])
def test_snapshot_metadata_rejects_non_sha256_identities(field):
    meta = snapshot_meta()
    meta[field] = "not-a-sha256"
    with pytest.raises(canary.CanaryFailure, match=field):
        canary.validate_snapshot_metadata(meta)


@pytest.mark.parametrize("field", ["snapshot", "etag"])
def test_snapshot_metadata_rejects_mismatched_validators(field):
    meta = snapshot_meta()
    meta["validators"][field] = "incorrect"
    with pytest.raises(canary.CanaryFailure, match="validator|etag"):
        canary.validate_snapshot_metadata(meta)


@pytest.mark.parametrize("field", ["root", "inventory", "files"])
def test_snapshot_metadata_rejects_paths_from_another_export(field):
    meta = snapshot_meta()
    meta["paths"][field] = meta["paths"][field].replace("a" * 64, "c" * 64)
    with pytest.raises(canary.CanaryFailure, match="match snapshotId"):
        canary.validate_snapshot_metadata(meta)


def test_archive_sampling_checks_an_older_payload_with_same_index_digest(monkeypatch):
    old_id = "a" * 64
    latest_id = "b" * 64
    digest = "c" * 64
    entries = [
        {"snapshotId": old_id, "snapshotDigest": digest},
        {"snapshotId": latest_id, "snapshotDigest": digest},
    ]
    fetched = []
    monkeypatch.setattr(
        canary,
        "fetch_json",
        lambda origin, path: {"files": [{"path": f"v0/snapshots/{old_id}/repos/index.json"}]},
    )
    monkeypatch.setattr(canary, "fetch", lambda origin, path: fetched.append(path))
    result = canary.archived_snapshot_sample("https://dotrepo.org", entries, latest_id)
    assert result["snapshotId"] == old_id
    assert fetched == [f"/v0/snapshots/{old_id}/repos/index.json"]


@pytest.mark.parametrize("target", ["log", "stats"])
def test_live_checks_reject_different_export_id_even_when_source_digest_matches(
    monkeypatch, target
):
    meta = snapshot_meta()
    meta["generatedAt"] = "2026-10-03T19:00:00Z"
    freshness = {key: meta[key] for key in ("generatedAt", "snapshotDigest")}
    latest = {
        "snapshotId": meta["snapshotId"],
        "snapshotDigest": meta["snapshotDigest"],
        "repositoryCount": 2,
        "fileCount": 1,
    }
    log = {"entries": [dict(latest)], "snapshotCount": 1}
    stats_document = {"latest": dict(latest), "snapshotCount": 1}
    if target == "log":
        log["entries"][0]["snapshotId"] = "c" * 64
    else:
        stats_document["latest"]["snapshotId"] = "c" * 64
    responses = {
        "/v0/meta.json": meta,
        meta["paths"]["inventory"]: {
            "freshness": freshness,
            "repositoryCount": 2,
            "repositories": [{}, {}],
        },
        meta["paths"]["files"]: {"freshness": freshness, "fileCount": 1, "files": []},
        "/v0/snapshots/log.json": log,
        "/v0/stats.json": stats_document,
        "/v0/health.json": {},
    }
    monkeypatch.setattr(canary, "fetch_json", lambda origin, path: responses[path])
    with pytest.raises(canary.CanaryFailure, match="ID disagrees with pointer"):
        canary.check_dotrepo("https://dotrepo.org", False)
