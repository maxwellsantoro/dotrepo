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
