from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts/fetch_pagedigest_baseline.py"
SPEC = importlib.util.spec_from_file_location("fetch_pagedigest_baseline", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def manifest() -> dict:
    return {
        "version": 1,
        "site_rev": 7,
        "entries": {
            "/v0/repos/github.com/example/project/index.json": {
                "rev": 3,
                "digest": f"sha256:{'a' * 64}",
                "content_digest": f"sha256:{'b' * 64}",
            }
        },
    }


def test_validate_manifest_accepts_revision_baseline() -> None:
    payload = manifest()
    assert MODULE.validate_manifest(payload) is payload


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("site_rev", 0),
        ("site_rev", True),
        ("version", 2),
    ],
)
def test_validate_manifest_rejects_invalid_root_fields(field: str, value: object) -> None:
    payload = manifest()
    payload[field] = value
    with pytest.raises(MODULE.BaselineError):
        MODULE.validate_manifest(payload)


def test_validate_manifest_rejects_invalid_entry_digest() -> None:
    payload = manifest()
    entry = next(iter(payload["entries"].values()))
    entry["content_digest"] = "sha256:not-a-digest"
    with pytest.raises(MODULE.BaselineError):
        MODULE.validate_manifest(payload)


def test_fetch_manifest_bounds_and_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    body = json.dumps(manifest()).encode()
    monkeypatch.setattr(
        MODULE,
        "urlopen",
        lambda request, timeout: Response(body),
    )

    fetched = MODULE.fetch_manifest("https://dotrepo.org/.well-known/pagedigest.json", 1)
    assert fetched["site_rev"] == 7


def test_fetch_with_retries_requires_https() -> None:
    with pytest.raises(MODULE.BaselineError, match="absolute HTTPS"):
        MODULE.fetch_with_retries("http://dotrepo.org/.well-known/pagedigest.json", 1, 1)


def test_write_manifest_replaces_output_atomically(tmp_path: Path) -> None:
    output = tmp_path / "baseline.json"
    output.write_text("{}\n", encoding="utf-8")

    MODULE.write_manifest(output, manifest())

    assert json.loads(output.read_text(encoding="utf-8"))["site_rev"] == 7
    assert not output.with_name(".baseline.json.tmp").exists()
