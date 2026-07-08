from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

SPEC = importlib.util.spec_from_file_location("language_family", SCRIPTS / "language_family.py")
language_family = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(language_family)


def test_classifies_by_dominant_language_only() -> None:
    record = {"repo": {"languages": ["Go", "Rust", "Shell"]}}
    assert language_family.inferred_language_family(record) == "Go"


def test_typescript_family_aliases() -> None:
    assert (
        language_family.inferred_language_family({"repo": {"languages": ["TypeScript"]}})
        == "TypeScript / JavaScript"
    )
    assert (
        language_family.inferred_language_family({"repo": {"languages": ["vue"]}})
        == "TypeScript / JavaScript"
    )


def test_empty_languages_are_other() -> None:
    assert language_family.inferred_language_family({"repo": {}}) == "Other"
    assert language_family.inferred_language_family(None) == "Other"
