"""Shared, reviewed request settings for narrow factual model calls.

Capabilities checked against https://openrouter.ai/api/v1/models on 2026-10-04.
These settings are configuration, not model quality claims or protocol constants.
"""

from __future__ import annotations

import json
from typing import Any


DEFAULT_PRIMARY_MODEL = "openai/gpt-6-luna"
DEFAULT_SECOND_OPINION_MODEL = "qwen/qwen3.8-flash"
DEFAULT_TAIL_MODEL = "z-ai/glm-5.3-flash"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5-5"

# Total completion budgets include reasoning. Never disable mandatory reasoning.
# Tuple: total token cap, reasoning settings, temperature support.
MODEL_POLICIES = {
    DEFAULT_PRIMARY_MODEL: (4096, {"effort": "low"}, False),
    DEFAULT_SECOND_OPINION_MODEL: (4096, {"max_tokens": 1024}, True),
    DEFAULT_TAIL_MODEL: (8192, {"effort": "high"}, True),
    "google/gemini-3.8-flash": (4096, {"effort": "low"}, True),
    "anthropic/claude-sonnet-5.5": (4096, {"effort": "low"}, False),
    "google/gemma-4-26b-a4b-it": (1024, {"enabled": False}, True),
    "qwen/qwen3.5-9b": (1024, {"enabled": False}, True),
    "z-ai/glm-5.2": (8192, {"effort": "high"}, True),
}

# USD per million tokens. Keep the selected cheap tiers cheap across routing
# fallback; unavailable rates fail rather than silently choosing a dearer route.
MODEL_PRICE_LIMITS = {
    DEFAULT_PRIMARY_MODEL: {"prompt": 0.10, "completion": 0.50},
    DEFAULT_SECOND_OPINION_MODEL: {"prompt": 0.15, "completion": 0.47},
    DEFAULT_TAIL_MODEL: {"prompt": 0.15, "completion": 0.50},
}


def build_completion_body(
    model: str, prompt: str, *, response_schema: dict[str, Any] | None = None
) -> dict[str, Any]:
    if not model.strip():
        raise ValueError("request missing model")
    # Custom models retain provider defaults for reasoning and omit temperature.
    # They must support JSON mode; reviewed profiles additionally use JSON schema.
    cap, reasoning, temperature = MODEL_POLICIES.get(model, (8192, None, False))
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Return strict JSON only. Never wrap in markdown fences.",
            },
            {"role": "user", "content": prompt},
        ],
        "max_tokens": cap,
        "response_format": {"type": "json_object"},
        "provider": {"require_parameters": True},
    }
    if reasoning is not None:
        body["reasoning"] = dict(reasoning)
    if temperature:
        body["temperature"] = 0
    if model in MODEL_PRICE_LIMITS:
        body["provider"]["max_price"] = dict(MODEL_PRICE_LIMITS[model])
    if response_schema is not None and model in MODEL_POLICIES:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "adjudication", "strict": True, "schema": response_schema},
        }
    return body


def completion_usage(payload: dict[str, Any]) -> dict[str, Any]:
    """Retain usage before parsing an answer, including billed unusable answers."""
    usage = payload.get("usage") or {}
    choice = (payload.get("choices") or [{}])[0]
    return {
        "generationId": payload.get("id"),
        "model": payload.get("model"),
        "provider": payload.get("provider"),
        "finishReason": choice.get("finish_reason"),
        "promptTokens": usage.get("prompt_tokens"),
        "completionTokens": usage.get("completion_tokens"),
        "reasoningTokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
        "tokensUsed": int(usage.get("total_tokens") or 0),
        "cost": usage.get("cost"),
    }


def build_anthropic_body(model: str, prompt: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }
    if model == DEFAULT_ANTHROPIC_MODEL:
        body.update(thinking={"type": "adaptive"}, output_config={"effort": "low"})
    return body


class CompletionError(RuntimeError):
    def __init__(self, message: str, usage: dict[str, Any]):
        super().__init__(message)
        self.usage = usage


def completion_text(payload: dict[str, Any]) -> str:
    usage = completion_usage(payload)
    choices = payload.get("choices") or []
    if not choices:
        raise CompletionError("OpenRouter returned no completion choices", usage)
    choice = choices[0]
    if choice.get("finish_reason") in {"length", "content_filter", "error"}:
        raise CompletionError(f"OpenRouter finish_reason={choice['finish_reason']}", usage)
    content = (choice.get("message") or {}).get("content")
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    if not isinstance(content, str) or not content.strip():
        raise CompletionError("OpenRouter returned an empty completion", usage)
    return content


def log_completion(usage: dict[str, Any], *, requested_model: str, outcome: str) -> None:
    # No candidate contents, prompts, or credentials in operational usage logs.
    import sys

    print(
        json.dumps(
            {
                "event": "openrouter-completion",
                "requestedModel": requested_model,
                "outcome": outcome,
                **usage,
            },
            sort_keys=True,
        ),
        file=sys.stderr,
        flush=True,
    )
