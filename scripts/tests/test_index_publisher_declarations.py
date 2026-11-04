"""Captured publisher source remains byte-bound when index metadata changes."""

import hashlib
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[2]


def test_index_publisher_declarations_keep_their_captured_bytes():
    declarations = []
    for path in sorted((ROOT / "index/repos").rglob("record.toml")):
        record = tomllib.loads(path.read_text())
        declaration = record.get("x", {}).get("dotrepo", {}).get("publisher_declaration")
        if declaration is not None:
            declarations.append((path, declaration))

    assert declarations, "the index should exercise retained publisher declarations"
    for path, declaration in declarations:
        actual = hashlib.sha256(declaration["manifest_toml"].encode("utf-8")).hexdigest()
        assert actual == declaration["sha256"], (
            f"{path.relative_to(ROOT)}: captured publisher bytes differ from their digest; "
            "restore the source at the recorded revision rather than rehashing edited evidence"
        )
