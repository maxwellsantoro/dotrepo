import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_release_version as versions  # noqa: E402


def test_stable_tag_matches_workspace():
    version, errors = versions.check(Path(__file__).resolve().parents[2], tag="v1.0.3")
    assert version == "1.0.3"
    assert errors == []


def test_wrong_tag_is_rejected():
    _, errors = versions.check(Path(__file__).resolve().parents[2], tag="v1.0.1")
    assert any("does not match workspace version" in error for error in errors)


def test_registry_description_fits_declared_schema():
    # The declared MCP registry schema limits ServerDetail.description to 100.
    # The original 205-character template caused a real publication rejection.
    root = Path(__file__).resolve().parents[2]
    server = json.loads((root / "server.json").read_text())
    assert server["$schema"] == (
        "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
    )
    assert 1 <= len(server["description"]) <= 100
