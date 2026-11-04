import importlib.util
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "r2_archive_upload.py"
SPEC = importlib.util.spec_from_file_location("r2_archive_upload", SCRIPT)
api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(api)


@pytest.fixture
def uploader(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a" * 32)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "fixture-secret-never-print")
    return api.Uploader("test-archive", 2)


def test_retry_is_per_object_and_request_keeps_bytes_metadata_and_existing_auth(
    uploader, monkeypatch, capsys
):
    calls, sleeps = [], []

    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            assert timeout == 30
            if len(calls) == 1:
                raise HTTPError(request.full_url, 500, "transient", {}, BytesIO())
            return BytesIO(b"ok")

    handlers = []

    def opener(handler):
        handlers.append(handler)
        return Opener()

    monkeypatch.setattr(api, "build_opener", opener)
    monkeypatch.setattr(api.time, "sleep", sleeps.append)
    uploader.put(
        "v0/snapshots/abc/repos/index.json", b"exact bytes", "application/json", "immutable"
    )
    assert len(calls) == 2 and sleeps == [1]
    assert all(request.data == b"exact bytes" for request in calls)
    assert calls[0].get_header("Authorization") == "Bearer fixture-secret-never-print"
    assert calls[0].get_header("Cache-control") == "immutable"
    assert all(isinstance(handler, api.NoRedirect) for handler in handlers)
    assert "fixture-secret" not in capsys.readouterr().out


@pytest.mark.parametrize("status", [302, 401, 403, 404])
def test_permanent_refusal_does_not_retry_or_follow_another_identity(uploader, monkeypatch, status):
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            raise HTTPError(request.full_url, status, "refused", {}, BytesIO())

    monkeypatch.setattr(api, "build_opener", lambda *_: Opener())
    with pytest.raises(RuntimeError, match=f"HTTP {status}") as error:
        uploader.put("v0/snapshots/abc/files.json", b"{}", "application/json", "immutable")
    assert len(calls) == 1
    assert "fixture-secret" not in str(error.value)


def test_transient_failure_has_three_attempt_ceiling(uploader, monkeypatch):
    calls, sleeps = [], []

    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            raise HTTPError(request.full_url, 503, "transient", {}, BytesIO())

    monkeypatch.setattr(api, "build_opener", lambda *_: Opener())
    monkeypatch.setattr(api.time, "sleep", sleeps.append)
    with pytest.raises(RuntimeError, match="HTTP 503"):
        uploader.put("v0/snapshots/abc/files.json", b"{}", "application/json", "immutable")
    assert len(calls) == 3 and sleeps == [1, 2]


def test_rolling_budget_counts_every_attempt_and_bounds_sleep_chunks(monkeypatch):
    now, sleeps = [0], []
    monkeypatch.setattr(api.time, "monotonic", lambda: now[0])

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(api.time, "sleep", sleep)
    budget = api.RequestBudget(limit=2, window=125)
    budget.reserve()
    budget.reserve()
    budget.reserve()
    assert now[0] == 125 and sleeps == [60, 60, 5]


@pytest.mark.parametrize("key", ["v0/snapshots/../escape", "other/key", "v0/snapshots/a/\\escape"])
def test_keys_cannot_leave_the_existing_archive_namespace(uploader, key):
    with pytest.raises(ValueError, match="under v0/snapshots"):
        uploader.put(key, b"{}", "application/json", "immutable")


def test_no_redirect_handler_refuses_to_forward_credentials():
    assert (
        api.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://other.test")
        is None
    )


def test_parallel_failure_stops_new_submission_before_advertising_more(
    uploader, monkeypatch, tmp_path
):
    paths = []
    for index in range(20):
        path = tmp_path / f"v0/snapshots/abc/{index}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"{}")
        paths.append(path)
    called = []

    def put(key, *_):
        called.append(key)
        if key.endswith("/0.json"):
            raise RuntimeError("permanent write refusal")

    monkeypatch.setattr(uploader, "put", put)
    with pytest.raises(RuntimeError, match="permanent"):
        uploader.payloads(paths, tmp_path, lambda _: "application/json")
    assert 1 <= len(called) <= uploader.concurrency
