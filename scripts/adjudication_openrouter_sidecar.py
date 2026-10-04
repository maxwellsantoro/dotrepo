#!/usr/bin/env -S uv run python
"""Thin HTTP sidecar: dotrepo adjudication JSON -> OpenRouter chat completions."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from openrouter_request_policy import (
    CompletionError,
    build_completion_body,
    completion_text,
    completion_usage,
    log_completion,
)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--api-key-env",
        default="OPENROUTER_API_KEY",
        help="Environment variable holding the OpenRouter API key",
    )
    return parser.parse_args()


def load_api_key(env_name: str) -> str:
    key = os.environ.get(env_name, "").strip()
    if not key:
        raise RuntimeError(f"{env_name} is not set")
    return key


def build_prompt(payload: dict[str, Any]) -> str:
    field = payload.get("field", "unknown")
    candidates = payload.get("candidates") or []
    lines = [
        "You are a narrow factual adjudicator for repository metadata import.",
        "Choose exactly one candidate value for the field, or return null if no single primary value is honest.",
        "Rules:",
        "- value MUST be one of the listed candidate values, or null",
        "- do not invent commands or sources",
        "- prefer manifest/CI primary workflows over release-only workflows when both exist",
        "- broader command coverage (such as --workspace) does not establish a repository default",
        "- ordinary workflow names such as check or verify do not establish primacy",
        "- conflicting same-tier normal CI workflows are tied unless evidence identifies a primary",
        "- if candidates are genuinely tied, return null with high confidence",
        "- when value is null, source must also be null",
        "",
        f"Field: {field}",
        "Candidates:",
    ]
    for candidate in candidates:
        value = candidate.get("value", "")
        source_path = candidate.get("sourcePath") or candidate.get("source_path", "")
        source_tier = candidate.get("sourceTier") or candidate.get("source_tier", "")
        lines.append(f"- value={value!r} source={source_path!r} tier={source_tier!r}")
    lines.extend(
        [
            "",
            "Respond with JSON only, no markdown:",
            '{"field":"...", "value":"..." or null, "confidence":"high|medium|low", "reason":"...", "source":"..." or null}',
        ]
    )
    return "\n".join(lines)


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("model response did not contain JSON object")
    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("model response must be a JSON object")
    return parsed


def adjudication_schema(payload: dict[str, Any]) -> dict[str, Any]:
    candidates = payload.get("candidates") or []
    values = sorted({candidate["value"] for candidate in candidates})
    sources = sorted(
        {
            candidate.get("sourcePath") or candidate.get("source_path")
            for candidate in candidates
            if candidate.get("sourcePath") or candidate.get("source_path")
        }
    )
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["field", "value", "confidence", "reason", "source"],
        "properties": {
            "field": {"type": "string", "enum": [payload["field"]]},
            "value": {"type": ["string", "null"], "enum": [*values, None]},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "reason": {"type": "string"},
            "source": {"type": ["string", "null"], "enum": [*sources, None]},
        },
    }


def call_openrouter(
    *,
    api_key: str,
    model: str,
    prompt: str,
    response_schema: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    body = build_completion_body(model, prompt, response_schema=response_schema)

    request = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/maxwellsantoro/dotrepo",
            "X-Title": "dotrepo-adjudication-sidecar",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter HTTP {exc.code}: {detail}") from exc

    usage = completion_usage(payload)
    try:
        parsed = extract_json_object(completion_text(payload))
    except (ValueError, CompletionError) as exc:
        log_completion(usage, requested_model=model, outcome="invalid-answer")
        raise CompletionError(str(exc), usage) from exc
    log_completion(usage, requested_model=model, outcome="answered")
    return parsed, usage["tokensUsed"]


def normalize_response(
    request_payload: dict[str, Any], model_payload: dict[str, Any], tokens_used: int
) -> dict[str, Any]:
    confidence = str(model_payload.get("confidence", "medium")).lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"
    return {
        "field": model_payload.get("field") or request_payload.get("field"),
        "value": model_payload.get("value"),
        "confidence": confidence,
        "reason": str(model_payload.get("reason") or "adjudicated by OpenRouter"),
        "source": model_payload.get("source"),
        "tokensUsed": tokens_used,
    }


def make_handler(api_key: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:  # noqa: A003
            sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/adjudicate":
                self.send_error(404, "expected POST /adjudicate")
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
                model = payload.get("model")
                if not model:
                    raise ValueError("request missing model")
                parsed, tokens_used = call_openrouter(
                    api_key=api_key,
                    model=model,
                    prompt=build_prompt(payload),
                    response_schema=adjudication_schema(payload),
                )
                response = normalize_response(payload, parsed, tokens_used)
                body = json.dumps(response).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:  # noqa: BLE001 - surface provider errors to client
                error = {"error": str(exc)}
                if isinstance(exc, CompletionError):
                    error.update(exc.usage)
                body = json.dumps(error).encode("utf-8")
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                body = b'{"ok":true}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

    return Handler


def main() -> int:
    args = parse_args()
    api_key = load_api_key(args.api_key_env)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(api_key))
    print(
        f"adjudication sidecar listening on http://{args.host}:{args.port}/adjudicate",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("shutting down", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
