"""Tests for the template-complete external consumer reference client.

Drives the real shipped module under examples/external-consumer/ — no reimplementation
of the lookup decision path inside the test.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

CLIENT = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "external-consumer"
    / "lookup_before_scrape.py"
)
SPEC = importlib.util.spec_from_file_location("lookup_before_scrape", CLIENT)
assert SPEC is not None and SPEC.loader is not None
consumer = importlib.util.module_from_spec(SPEC)
# dataclasses requires the module to be present in sys.modules during class body exec
sys.modules[SPEC.name] = consumer
SPEC.loader.exec_module(consumer)


class _FakeResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class _FakeOpener:
    def __init__(self, status: int, payload: dict | None) -> None:
        self.status = status
        self.payload = payload
        self.urls: list[str] = []

    def open(self, request: object, timeout: float = 0) -> _FakeResponse:
        url = getattr(request, "full_url", None) or request.get_full_url()  # type: ignore[attr-defined]
        self.urls.append(url)
        body = b"" if self.payload is None else json.dumps(self.payload).encode()
        if self.status >= 400:
            import urllib.error

            raise urllib.error.HTTPError(url, self.status, "err", hdrs=None, fp=io.BytesIO(body))
        return _FakeResponse(self.status, body)


def test_parse_repository_identity_from_url_and_short_form() -> None:
    assert consumer.parse_repository_identity("https://github.com/BurntSushi/ripgrep") == (
        "github.com",
        "BurntSushi",
        "ripgrep",
    )
    assert consumer.parse_repository_identity("github.com/cli/cli") == (
        "github.com",
        "cli",
        "cli",
    )
    assert consumer.parse_repository_identity("owner/repo") == (
        "github.com",
        "owner",
        "repo",
    )


def test_hit_surfaces_trust_freshness_and_honest_missing_fields() -> None:
    # Real public profile.json shape (subset)
    payload = {
        "freshness": {
            "generatedAt": "2026-07-08T00:00:00Z",
            "snapshotDigest": "abc",
        },
        "name": "demo",
        "purpose": "A demo",
        "homepage": "https://example.com",
        "execution": {
            # build present, test absent
            "build": "cargo build",
        },
        "ownership": {"securityContact": "unknown"},
        "trust": {
            "selectedStatus": "verified",
            "confidence": "high",
            "provenance": ["verified"],
        },
    }
    opener = _FakeOpener(200, payload)
    result = consumer.fetch_profile(
        "https://github.com/acme/demo",
        base_url="https://dotrepo.org",
        opener=opener,
    )
    assert result.hit is True
    assert result.miss is False
    assert result.record_status == "verified"
    assert result.trust is not None
    assert result.trust["confidence"] == "high"
    assert result.trust["selectedStatus"] == "verified"
    assert result.freshness["snapshotDigest"] == "abc"
    assert "repo.test" in result.missing_fields
    assert "owners.security_contact" in result.missing_fields
    assert "repo.build" not in result.missing_fields
    assert opener.urls == ["https://dotrepo.org/v0/repos/github.com/acme/demo/profile.json"]


def test_404_is_countable_miss_with_worker_compatible_log_line() -> None:
    opener = _FakeOpener(404, None)
    result = consumer.fetch_profile("github.com/missing/repo", opener=opener)
    assert result.hit is False
    assert result.miss is True
    assert result.error == "repository-not-found"
    miss = consumer.result_to_miss(result)
    assert miss is not None
    line = consumer.miss_log_line(miss)
    assert line.startswith("DOTREPO_LOOKUP_MISS ")
    # Real aggregator must accept the client-emitted line.
    scripts = Path(__file__).resolve().parents[1]
    import importlib.util as iu

    agg_path = scripts / "aggregate_lookup_misses.py"
    agg_spec = iu.spec_from_file_location("aggregate_lookup_misses", agg_path)
    assert agg_spec is not None and agg_spec.loader is not None
    agg = iu.module_from_spec(agg_spec)
    sys.modules[agg_spec.name] = agg
    agg_spec.loader.exec_module(agg)
    parsed = agg.parse_line(line)
    assert parsed is not None
    assert parsed["identity"] == "github.com/missing/repo"


def test_main_writes_miss_log_and_json(tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_fetch(repo: str, **kwargs: object) -> consumer.LookupResult:
        calls.append(repo)
        if "missing" in repo:
            return consumer.LookupResult(
                identity="github.com/acme/missing",
                status_code=404,
                hit=False,
                miss=True,
                error="repository-not-found",
            )
        return consumer.LookupResult(
            identity="github.com/acme/present",
            status_code=200,
            hit=True,
            miss=False,
            profile={"name": "present", "execution": {"build": "make", "test": "make test"}},
            trust={"confidence": "high", "selectedStatus": "verified"},
            freshness={"generatedAt": "2026-07-08T00:00:00Z"},
            record_status="verified",
            missing_fields=[],
        )

    original = consumer.fetch_profile
    consumer.fetch_profile = fake_fetch  # type: ignore[assignment]
    try:
        miss_log = tmp_path / "misses.log"
        out_json = tmp_path / "out.json"
        code = consumer.main(
            [
                "github.com/acme/present",
                "github.com/acme/missing",
                "--miss-log",
                str(miss_log),
                "--output-json",
                str(out_json),
            ]
        )
        assert code == 0
        assert miss_log.read_text().count("DOTREPO_LOOKUP_MISS") == 1
        report = json.loads(out_json.read_text())
        assert report["missCount"] == 1
        assert len(report["results"]) == 2
        assert len(calls) == 2
    finally:
        consumer.fetch_profile = original  # type: ignore[assignment]
