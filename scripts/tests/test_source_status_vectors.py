"""Shared Lazy Collective source-status vectors, vendored from PageDigest."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from source_status import source_state, source_status  # noqa: E402

VECTORS = json.loads(
    (Path(__file__).parent / "fixtures" / "source-status-vectors.json").read_text(encoding="utf-8")
)


def test_vector_document_version():
    assert VECTORS["name"] == "lazy-collective-source-status"
    assert VECTORS["version"] == 1


@pytest.mark.parametrize("case", VECTORS["cases"], ids=lambda case: case["name"])
def test_source_status_vectors(case):
    states = [
        source_state(s["bound"], s["observed"], s.get("boundBodyRetained", True))
        for s in case["sources"]
    ]
    assert states == case["expectedSources"]
    assert source_status(states) == case["expected"]
