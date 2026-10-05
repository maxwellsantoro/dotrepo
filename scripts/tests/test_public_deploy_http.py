import io
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import public_deploy_http as http  # noqa: E402


def test_identified_bounded_read(monkeypatch):
    seen = []

    def open_response(request, timeout):
        seen.append((request, timeout))
        return io.BytesIO(b"payload")

    monkeypatch.setattr(http, "urlopen", open_response)
    assert http.fetch_public_bytes("https://example.test/meta.json", 2, max_bytes=7) == b"payload"
    request, timeout = seen[0]
    assert request.get_header("User-agent") == "dotrepo-public-deploy/1.0"
    assert request.get_header("Cache-control") == "no-cache"
    assert timeout == 2
    with pytest.raises(http.DeploymentFetchError, match="exceeds 6 bytes"):
        http.fetch_public_bytes("https://example.test/meta.json", 2, max_bytes=6)


@pytest.mark.parametrize("code", [401, 403, 404])
def test_persistent_failure_is_bounded_and_not_retried(monkeypatch, code):
    calls = []

    def fail(request, timeout):
        calls.append(request.full_url)
        raise HTTPError(
            request.full_url,
            code,
            "denied",
            {"cf-ray": "test-ray"},
            io.BytesIO(b"denied " + b"x" * 10000),
        )

    monkeypatch.setattr(http, "urlopen", fail)
    with pytest.raises(http.DeploymentFetchError, match=f"HTTP {code}; cf-ray=test-ray") as error:
        http.fetch_public_bytes("https://example.test/meta.json", 2, max_bytes=20)
    assert len(calls) == 1
    assert len(str(error.value)) < 1200


@pytest.mark.parametrize("failure", [503, 429, "network"])
def test_transient_failure_retries_with_bounded_backoff(monkeypatch, failure):
    calls = []
    delays = []

    def open_response(request, timeout):
        calls.append(request.full_url)
        if len(calls) < 3:
            if failure == "network":
                raise URLError("temporary")
            raise HTTPError(request.full_url, failure, "temporary", {}, io.BytesIO(b"retry"))
        return io.BytesIO(b"ok")

    monkeypatch.setattr(http, "urlopen", open_response)
    monkeypatch.setattr(http.time, "sleep", delays.append)
    assert http.fetch_public_bytes("https://example.test/meta.json", 2, max_bytes=20) == b"ok"
    assert len(calls) == 3
    assert delays == [1, 2]
