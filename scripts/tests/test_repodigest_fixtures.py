"""Protect relocated, byte-bound regression inputs from accidental alteration."""

import hashlib
import json
from pathlib import Path


FIXTURES = Path(__file__).resolve().parent / "fixtures/repodigest"


def test_retained_source_and_receipt_manifest_matches():
    manifest = json.loads((FIXTURES / "MANIFEST.json").read_text())
    rows = manifest["files"]
    assert manifest["fileCount"] == len(rows)
    assert len({row["path"] for row in rows}) == len(rows)
    assert manifest["retainedBytes"] == sum(row["bytes"] for row in rows)
    for row in rows:
        path = FIXTURES / row["path"]
        assert path.resolve().is_relative_to(FIXTURES)
        assert not path.is_symlink()
        assert row["sourcePath"] == "benchmarks/head-to-head/" + row["path"]
        raw = path.read_bytes()
        assert len(raw) == row["bytes"], row["path"]
        assert hashlib.sha256(raw).hexdigest() == row["sha256"], row["path"]
