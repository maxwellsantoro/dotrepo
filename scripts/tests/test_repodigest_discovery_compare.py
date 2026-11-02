"""Equal-universe retrieval, metadata fallback and admitted-profile trust checks."""

import json
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures/repodigest"
sys.path.insert(0, str(ROOT / "scripts"))
import repodigest_discovery_compare as compare  # noqa: E402
from repodigest_acquire import canonical  # noqa: E402


@pytest.fixture(scope="module")
def paired(tmp_path_factory):
    packet = tmp_path_factory.mktemp("paired-discovery")
    source = FIXTURES / "repodigest-multirepo-service-20261029/acquisition-001/python-attrs__cattrs"
    snapshot = json.loads((source / "snapshot.json").read_text())
    shutil.copytree(source, packet / "acquisition/python-attrs__cattrs")
    rows = [
        {
            "repository": snapshot["repository"],
            "revision": snapshot["revision"],
            "name": "cattrs",
            "description": "Structured data utilities",
            "topics": [],
            "languages": ["Python"],
            "recordSha256": "b" * 64,
        }
    ]
    rows += [
        {
            "repository": f"github.com/example/config-{n}",
            "revision": "a" * 40,
            "name": f"config-{n}",
            "description": "Configuration command line utility",
            "topics": ["configuration"],
            "languages": ["JavaScript" if n % 2 else "Rust"],
            "recordSha256": "c" * 64,
        }
        for n in range(99)
    ]
    (packet / "metadata.json").write_text(json.dumps(rows))
    output = packet / "compiled"
    result = compare.build(packet, output)
    assert result["repositories"] == 100 and result["sourceProfiles"] == 1
    return output


def test_source_enrichment_preserves_same_universe_and_explicit_fallback(paired):
    reader = compare.Search(paired)
    assert reader.db.execute("SELECT COUNT(*) FROM metadata_search").fetchone()[0] == 100
    assert reader.db.execute("SELECT COUNT(*) FROM repodigest_search").fetchone()[0] == 100
    baseline = reader.find("serialization", mode="metadata", language="Python")
    enriched = reader.find("serialization", mode="repodigest", language="Python")
    assert not baseline["repositories"]
    assert enriched["repositories"][0]["repository"] == "github.com/python-attrs/cattrs"
    assert enriched["repositories"][0]["knowledge"] == "source-profile"
    fallback = reader.find("configuration", mode="repodigest", language="Rust", limit=20)
    control = reader.find("configuration", mode="metadata", language="Rust", limit=20)
    assert fallback["repositories"] == control["repositories"]
    assert all(r["knowledge"] == "metadata-claim" for r in fallback["repositories"])
    assert fallback["moreCandidates"] and len(canonical(fallback)) <= 32768
    described = reader.describe("github.com/python-attrs/cattrs")
    assert not described["discoveryProfile"]["executionEstablished"]
    control_description = reader.describe("github.com/python-attrs/cattrs", mode="metadata")
    assert "discoveryProfile" not in control_description
    assert "hasProfile" not in control_description["metadata"]
    reader.close()


def test_corrupt_metadata_refuses_instead_of_returning_index_text(paired, tmp_path):
    output = tmp_path / "copied"
    shutil.copytree(paired, output)
    db = sqlite3.connect(output / "paired.sqlite")
    with db:
        db.execute(
            "UPDATE catalog SET body=? WHERE repository=?",
            (b"{}", "github.com/python-attrs/cattrs"),
        )
    db.close()
    reader = compare.Search(output)
    result = reader.find("serialization", mode="repodigest")
    assert result["refusedCandidates"] == 1 and not result["repositories"]
    reader.close()


def test_more_candidates_counts_only_language_eligible_rows(paired, tmp_path):
    output = tmp_path / "copied"
    shutil.copytree(paired, output)
    db = sqlite3.connect(output / "paired.sqlite")
    with db:
        for table in ("metadata_search", "repodigest_search"):
            db.execute(
                f"UPDATE {table} SET purpose='shared' WHERE identity IN (?,?)",
                ("github.com/python-attrs/cattrs", "github.com/example/config-0"),
            )
    db.close()
    reader = compare.Search(output)
    for mode in compare.MODES:
        result = reader.find("shared", mode=mode, language="Python", limit=1)
        assert len(result["repositories"]) == 1 and not result["moreCandidates"]
    reader.close()


def test_corrupt_source_profile_cannot_silently_fall_back(paired, tmp_path):
    output = tmp_path / "copied"
    shutil.copytree(paired, output)
    db = sqlite3.connect(output / "source-store.sqlite")
    db.execute("DROP TRIGGER objects_no_update")
    with db:
        db.execute("UPDATE objects SET body=?", (b"{}",))
    db.close()
    reader = compare.Search(output)
    result = reader.find("serialization", mode="repodigest")
    assert result["refusedCandidates"] == 1 and not result["repositories"]
    reader.close()


@pytest.mark.parametrize(
    "options",
    [{"mode": "bad"}, {"limit": True}, {"limit": 21}, {"language": "bad"}, {"query": "x" * 201}],
)
def test_search_arguments_are_bounded(paired, options):
    reader = compare.Search(paired)
    with pytest.raises(ValueError):
        reader.find(**({"query": "configuration"} | options))
    reader.close()
