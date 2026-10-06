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
