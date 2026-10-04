from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import adjudication_openrouter_sidecar as sidecar  # noqa: E402
import openrouter_request_policy as policy  # noqa: E402


def candidate_request():
    return {
        "field": "repo.build",
        "candidates": [
            {"value": "cargo build", "sourcePath": ".github/workflows/check.yml"},
            {"value": "cargo build --release", "sourcePath": ".github/workflows/release.yml"},
        ],
    }


def completion(content, *, finish="stop"):
    return {
        "id": "gen-test",
        "model": policy.DEFAULT_PRIMARY_MODEL,
        "provider": "OpenAI",
        "choices": [{"message": {"content": content}, "finish_reason": finish}],
        "usage": {
            "prompt_tokens": 50,
            "completion_tokens": 300,
            "total_tokens": 350,
            "completion_tokens_details": {"reasoning_tokens": 280},
            "cost": 0.000155,
        },
    }


def stub_openrouter(monkeypatch, payload):
    sent = []

    def respond(request, *, timeout):
        sent.append(json.loads(request.data))
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(sidecar.urllib.request, "urlopen", respond)
    return sent


def test_luna_omits_temperature_and_binds_answer_to_candidates(monkeypatch):
    answer = {
        "field": "repo.build",
        "value": "cargo build",
        "confidence": "high",
        "reason": "primary CI",
        "source": ".github/workflows/check.yml",
    }
    sent = stub_openrouter(monkeypatch, completion(json.dumps(answer)))
    parsed, tokens = sidecar.call_openrouter(
        api_key="test-key",
        model=policy.DEFAULT_PRIMARY_MODEL,
        prompt="candidates",
        response_schema=sidecar.adjudication_schema(candidate_request()),
    )
    assert parsed == answer
    assert tokens == 350
    body = sent[0]
    assert "temperature" not in body
    assert body["reasoning"] == {"effort": "low"}
    assert body["max_tokens"] == 4096
    assert body["provider"]["require_parameters"] is True
    assert body["provider"]["max_price"] == {"prompt": 0.10, "completion": 0.50}
    schema = body["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["value"]["enum"] == ["cargo build", "cargo build --release", None]
    assert schema["properties"]["field"]["enum"] == ["repo.build"]
    assert schema["additionalProperties"] is False


@pytest.mark.parametrize(
    "model,effort,cap",
    [
        (policy.DEFAULT_TAIL_MODEL, "high", 8192),
        ("google/gemini-3.8-flash", "low", 4096),
    ],
)
def test_mandatory_reasoning_is_never_disabled(model, effort, cap):
    body = policy.build_completion_body(model, "prompt")
    assert body["reasoning"] == {"effort": effort}
    assert body["max_tokens"] == cap


def test_second_opinion_uses_qwen_without_changing_account_policy():
    assert policy.DEFAULT_SECOND_OPINION_MODEL == "qwen/qwen3.8-flash"
    assert "meta/muse-spark-1.3-contributor" not in policy.MODEL_POLICIES
    body = policy.build_completion_body(policy.DEFAULT_SECOND_OPINION_MODEL, "prompt")
    assert body["reasoning"] == {"max_tokens": 1024}
    assert body["max_tokens"] == 4096
    assert body["provider"]["max_price"] == {"prompt": 0.15, "completion": 0.47}


@pytest.mark.parametrize(
    "payload",
    [
        completion("", finish="length"),
        completion('{"value":null}', finish="length"),
        completion("not JSON"),
        completion(None),
        {**completion(""), "choices": []},
    ],
)
def test_unusable_paid_answers_retain_usage_and_do_not_become_abstention(
    monkeypatch, capsys, payload
):
    stub_openrouter(monkeypatch, payload)
    with pytest.raises(policy.CompletionError) as failure:
        sidecar.call_openrouter(
            api_key="test-key", model=policy.DEFAULT_PRIMARY_MODEL, prompt="secret candidate"
        )
    assert failure.value.usage["tokensUsed"] == 350
    assert failure.value.usage["reasoningTokens"] == 280
    logged = json.loads(capsys.readouterr().err)
    assert logged["outcome"] == "invalid-answer"
    assert logged["cost"] == 0.000155
    assert "secret candidate" not in json.dumps(logged)
    assert "test-key" not in json.dumps(logged)


def test_text_content_blocks_are_supported():
    assert (
        policy.completion_text(completion([{"type": "text", "text": '{"value":null}'}]))
        == '{"value":null}'
    )


def test_custom_model_keeps_reasoning_defaults_and_requires_json_support():
    body = policy.build_completion_body(
        "custom/model", "prompt", response_schema={"type": "object"}
    )
    assert "temperature" not in body
    assert "reasoning" not in body
    assert body["response_format"] == {"type": "json_object"}
    assert body["provider"]["require_parameters"] is True


def test_http_error_carries_measured_usage(monkeypatch):
    def fail(**kwargs):
        raise policy.CompletionError("truncated", {"tokensUsed": 350, "cost": 0.000155})

    monkeypatch.setattr(sidecar, "call_openrouter", fail)
    server = ThreadingHTTPServer(("127.0.0.1", 0), sidecar.make_handler("test-key"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/adjudicate",
            data=json.dumps(
                {**candidate_request(), "model": policy.DEFAULT_PRIMARY_MODEL}
            ).encode(),
            headers={"Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError) as failure:
            urllib.request.urlopen(request, timeout=2)
        assert failure.value.code == 502
        assert json.loads(failure.value.read()) == {
            "error": "truncated",
            "tokensUsed": 350,
            "cost": 0.000155,
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
