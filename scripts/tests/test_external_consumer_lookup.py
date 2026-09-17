"""Tests for the template-complete external consumer reference client.

Drives the real shipped module under examples/external-consumer/ — no reimplementation
of the lookup decision path inside the test.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys

import pytest
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


def test_task_policy_rejects_fresh_export_with_stale_record_and_allows_explicit_fields():
    from datetime import datetime, timezone

    payload = {
        "apiVersion": "v0",
        "identity": {"host": "github.com", "owner": "example", "repo": "test"},
        "record": {"generatedAt": "2026-07-06T00:00:00Z"},
        "freshness": {"generatedAt": "2026-09-16T00:00:00Z"},
        "purpose": "An example",
        "execution": {"build": "cargo build"},
        "fieldEvidence": {
            "repo.build": {
                "state": "present",
                "method": "extracted",
                "confidence": "high",
                "source": "Cargo.toml",
                "checkedAt": "2026-07-06T00:00:00Z",
            }
        },
        "trust": {"confidence": "high", "selectedStatus": "verified"},
    }
    result = consumer.interpret_http_response(
        identity="github.com/example/test", status_code=200, body=json.dumps(payload)
    )
    now = datetime(2026, 9, 16, tzinfo=timezone.utc)
    consumer.evaluate_for_task(result, now=now, required_fields=["repo.build", "repo.test"])
    assert result.hit and not result.usable
    assert result.fallback_reasons == ["stale-record", "missing:repo.test"]
    result.profile["record"]["generatedAt"] = "2026-09-15T00:00:00Z"
    result.profile["fieldEvidence"]["repo.build"]["checkedAt"] = "2026-09-15T00:00:00Z"
    consumer.evaluate_for_task(result, now=now, required_fields=["repo.build"])
    assert result.usable
    result.profile["fieldEvidence"] = {"repo.build": {"state": "suspect"}}
    consumer.evaluate_for_task(result, now=now, required_fields=["repo.build"])
    assert "unresolved:repo.build" in result.fallback_reasons
    assert not result.usable


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
        "apiVersion": "v0",
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


def test_inferred_commands_require_source_fallback():
    from datetime import datetime, timezone

    payload = {
        "apiVersion": "v0",
        "identity": {"host": "github.com", "owner": "example", "repo": "demo"},
        "record": {"generatedAt": "2026-09-16T00:00:00Z"},
        "execution": {"test": "./gradlew test"},
        "fieldEvidence": {"repo.test": {"state": "present", "method": "inferred"}},
    }
    result = consumer.interpret_http_response(
        identity="github.com/example/demo", status_code=200, body=json.dumps(payload)
    )
    consumer.evaluate_for_task(
        result, required_fields=["repo.test"], now=datetime(2026, 9, 16, tzinfo=timezone.utc)
    )
    assert not result.usable
    assert result.fallback_reasons == ["inferred-command:repo.test"]


def command_profile():
    from datetime import datetime, timezone

    checked = datetime.now(timezone.utc).isoformat()
    return {
        "apiVersion": "v0",
        "identity": {"host": "github.com", "owner": "example", "repo": "demo"},
        "record": {"generatedAt": checked},
        "execution": {"build": "make build", "test": "make test"},
        "trust": {"confidence": "high", "selectedStatus": "verified"},
        "fieldEvidence": {
            path: {
                "state": "present",
                "method": "extracted",
                "confidence": "high",
                "source": "Makefile",
                "checkedAt": checked,
            }
            for path in ["repo.build", "repo.test"]
        },
    }


@pytest.mark.parametrize("field", ["build", "test"])
@pytest.mark.parametrize(
    "mutation",
    [
        "remove-assessment",
        "empty-assessment",
        "malformed-assessment",
        "remove-state",
        "remove-method",
        "remove-confidence",
        "remove-source",
        "remove-checkedAt",
        "unspecified",
        "inferred",
        "low",
        "medium",
        "old-check",
        "unresolved",
        "wrong-value-type",
        "wrong-api",
        "missing-api",
        "malformed-api",
        "malformed-evidence",
    ],
)
def test_http_client_requires_positive_command_evidence(field, mutation):
    payload = command_profile()
    path = "repo." + field

    def fetch():
        return consumer.fetch_profile(
            "github.com/example/demo", opener=_FakeOpener(200, payload), required_fields=[path]
        )

    assert fetch().usable
    assessment = payload["fieldEvidence"][path]
    if mutation == "remove-assessment":
        # This is also the public export's result after a value/time binding changes.
        del payload["fieldEvidence"][path]
    elif mutation == "empty-assessment":
        payload["fieldEvidence"][path] = {}
    elif mutation == "malformed-assessment":
        payload["fieldEvidence"][path] = ["high"]
    elif mutation.startswith("remove-"):
        del assessment[mutation.removeprefix("remove-")]
    elif mutation in {"unspecified", "inferred"}:
        assessment["method"] = mutation
    elif mutation in {"low", "medium"}:
        assessment["confidence"] = mutation
    elif mutation == "old-check":
        assessment["checkedAt"] = "2020-01-01T00:00:00Z"
    elif mutation == "unresolved":
        assessment["state"] = "unresolved"
    elif mutation == "wrong-value-type":
        payload["execution"][field] = ["invented command"]
    elif mutation == "wrong-api":
        payload["apiVersion"] = "unsupported"
    elif mutation == "missing-api":
        del payload["apiVersion"]
    elif mutation == "malformed-api":
        payload["apiVersion"] = []
    elif mutation == "malformed-evidence":
        payload["fieldEvidence"] = ["invalid"]
    result = fetch()
    assert result.hit and not result.usable
    assert result.fallback_reasons


def test_removing_inferred_assessment_cannot_turn_rejection_into_acceptance():
    payload = command_profile()
    payload["fieldEvidence"]["repo.build"]["method"] = "inferred"
    for remove in [False, True]:
        if remove:
            del payload["fieldEvidence"]["repo.build"]
        result = consumer.fetch_profile(
            "github.com/example/demo",
            opener=_FakeOpener(200, payload),
            required_fields=["repo.build"],
        )
        assert not result.usable
