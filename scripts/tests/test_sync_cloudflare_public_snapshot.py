import json
import sys
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from sync_cloudflare_public_snapshot import write_stats  # noqa: E402


def test_write_stats_preserves_pagedigest_economics(tmp_path: Path) -> None:
    log = {
        "apiVersion": "v0",
        "snapshotCount": 1,
        "entries": [
            {
                "snapshotId": "abc123",
                "snapshotDigest": "abc123def456",
                "generatedAt": "2026-03-10T18:30:00Z",
                "repositoryCount": 2,
                "fileCount": 11,
            }
        ],
    }
    pagedigest = {
        "recordsCovered": 9,
        "fetchesAvoided": 7,
        "bytesAvoided": 1234,
    }

    write_stats(tmp_path, log, pagedigest)

    stats = json.loads((tmp_path / "v0/stats.json").read_text(encoding="utf-8"))
    assert stats["pagedigest"] == pagedigest
    assert stats["latest"]["snapshotId"] == "abc123"
