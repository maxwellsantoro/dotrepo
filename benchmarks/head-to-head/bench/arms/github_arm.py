"""The baseline. Deliberately competent, not a strawman.

If dotrepo can't beat an honest GitHub-API-plus-README agent, it isn't earning
its existence -- and this arm is built to make that a fair fight. Structured
fields come straight from the REST API (high confidence). Buried fields are
extracted from README/SECURITY.md/CONTRIBUTING with either a regex heuristic
(default, zero API cost, low/medium confidence) or an LLM extractor (opt-in).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Optional

from ..cache import ReplayCacheMiss
from ..model import Answer, Field, FieldClass
from .base import Arm, Http

API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"

_FENCE = re.compile(r"```(?:bash|sh|console|shell|text)?\n(.*?)```", re.S | re.I)

DOC_PATHS = {
    "readme": ("README.md", "README.rst", "README", "Readme.md"),
    "security": ("SECURITY.md", ".github/SECURITY.md"),
    "contributing": (
        "CONTRIBUTING.md",
        ".github/CONTRIBUTING.md",
        "CONTRIBUTING.rst",
        "docs/contributing.md",
        "docs/contributing.rst",
    ),
    "cargo": ("Cargo.toml",),
    "rust_toolchain_toml": ("rust-toolchain.toml",),
    "rust_toolchain": ("rust-toolchain",),
    "pyproject": ("pyproject.toml",),
    "package": ("package.json",),
    "go_mod": ("go.mod",),
    "makefile": ("Makefile",),
    "justfile": ("justfile", "Justfile"),
}


class GitHubArm(Arm):
    name = "github"

    def __init__(self, http: Http, extractor: str = "heuristic", token: Optional[str] = None):
        self.http = http
        self.extractor = extractor  # "heuristic" | "llm"
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self._meta: dict = {}
        self._docs: dict = {}
        self._cost: dict = {}  # field_id -> (bytes, ms) charged once

    def _headers(self):
        h = {"Accept": "application/vnd.github+json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def configuration(self) -> dict:
        config = {"extractor": self.extractor}
        if self.extractor != "llm":
            return config
        if os.environ.get("OPENROUTER_API_KEY"):
            config.update(
                {
                    "provider": "openrouter",
                    "model": os.environ.get("OPENROUTER_MODEL")
                    or os.environ.get("DOTREPO_ADJUDICATION_MODEL")
                    or os.environ.get("DOTREPO_ADJUDICATION_API_MODEL"),
                }
            )
        elif os.environ.get("ANTHROPIC_API_KEY"):
            config.update(
                {
                    "provider": "anthropic",
                    "model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"),
                }
            )
        return config

    def prefetch(self, repo: str):
        self._meta, self._docs, self._cost = {}, {}, {}
        owner, name = _split(repo)
        # 1) structured metadata (one call answers all github-native fields)
        st, text, nb, ms = self.http.get(f"{API}/repos/{owner}/{name}", self._headers())
        if st == 200:
            self._meta = json.loads(text)
        self._cost["__meta__"] = (nb, ms)
        # 2) conventional maintainer docs and manifests for buried fields.
        # Try common filename/location variants rather than silently treating
        # README.rst or .github/SECURITY.md as absent.
        branch = self._meta.get("default_branch", "main")
        for label, paths in DOC_PATHS.items():
            total_bytes = 0
            total_ms = 0.0
            for path in paths:
                st, text, nb, ms = self.http.get(f"{RAW}/{owner}/{name}/{branch}/{path}")
                total_bytes += nb
                total_ms += ms
                if st == 200:
                    self._docs[label] = text
                    break
            self._cost[f"__{label}__"] = (total_bytes, total_ms)

    def answer(self, repo: str, field: Field) -> Answer:
        if field.field_class == FieldClass.GITHUB_NATIVE:
            return self._native(field)
        return self._buried(field)

    # -- structured fields: high confidence, cost charged to the metadata call --
    def _native(self, field: Field) -> Answer:
        nb, ms = self._charge("__meta__")
        m = self._meta
        val = None
        if field.id == "description":
            val = m.get("description")
        elif field.id == "license":
            lic = m.get("license") or {}
            val = lic.get("spdx_id") if lic.get("spdx_id") not in (None, "NOASSERTION") else None
        elif field.id == "language":
            val = m.get("language")
        elif field.id == "homepage":
            val = m.get("homepage") or None
        elif field.id == "archived":
            val = "archived" if m.get("archived") else "active"
        conf = "high" if val is not None else None
        return Answer(
            value=val, confidence=conf, source="github:rest", bytes_over_wire=nb, latency_ms=ms
        )

    # -- buried fields: read the docs an agent would read --
    def _buried(self, field: Field) -> Answer:
        blob, src = self._doc_for(field)
        nb, ms = self._charge_docs(field)
        if not blob:
            return Answer(
                value=None,
                confidence=None,
                source="github:no-doc",
                bytes_over_wire=nb,
                latency_ms=ms,
            )
        if self.extractor == "llm":
            val, conf = self._llm_extract(field, blob)
        else:
            val, conf = self._heuristic_extract(field, blob)
        return Answer(
            value=val,
            confidence=conf,
            source=f"github:{src}:{self.extractor}",
            bytes_over_wire=nb,
            latency_ms=ms,
        )

    def _doc_for(self, field: Field):
        if field.id == "security_contact":
            return self._docs.get("security"), "SECURITY.md"
        if field.id == "test":
            return self._join_docs(
                "contributing", "makefile", "justfile", "package", "pyproject", "readme"
            ), "test-docs"
        if field.id == "min_toolchain":
            return self._join_docs(
                "cargo",
                "rust_toolchain_toml",
                "rust_toolchain",
                "pyproject",
                "package",
                "go_mod",
                "readme",
            ), "toolchain-docs"
        return (
            self._join_docs(
                "contributing",
                "makefile",
                "justfile",
                "package",
                "pyproject",
                "cargo",
                "go_mod",
                "readme",
            ),
            "build-docs",
        )

    def _join_docs(self, *labels: str) -> str:
        return "\n".join(
            f"\n--- {label} ---\n{self._docs[label]}" for label in labels if self._docs.get(label)
        )

    def _heuristic_extract(self, field: Field, blob: str):
        low = blob.lower()
        if field.id == "security_contact":
            m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", blob)
            if m:
                return m.group(0), "medium"
            m = re.search(r"https?://\S*security\S*", blob, re.I)
            return (m.group(0), "low") if m else (None, None)
        if field.id in ("build", "test"):
            key = "test" if field.id == "test" else "build|install|compile"
            # find a fenced block near a heading mentioning the key
            for m in re.finditer(
                rf"#{{1,4}}[^\n]*\b({key})\b[^\n]*\n(.*?)(?=\n#|\Z)", blob, re.S | re.I
            ):
                fb = _FENCE.search(m.group(2))
                if fb:
                    cmd = _first_cmd(fb.group(1), field.id)
                    if cmd:
                        return cmd, "medium"
            # fall back: any fenced command containing the keyword
            for fb in _FENCE.finditer(blob):
                cmd = _first_cmd(fb.group(1), field.id)
                if cmd and (
                    field.id in cmd
                    or (field.id == "build" and re.search(r"build|install|make|cargo b|npm i", cmd))
                ):
                    return cmd, "low"
            return None, None
        if field.id == "min_toolchain":
            m = re.search(r"rust-version\s*=\s*[\"'](\d+\.\d+(?:\.\d+)?)[\"']", blob, re.I)
            if m:
                return m.group(1), "high"
            m = re.search(r"channel\s*=\s*[\"'](\d+\.\d+(?:\.\d+)?)[\"']", blob, re.I)
            if m:
                return m.group(1), "medium"
            m = re.search(
                r"(?:requires-python|python)\s*=\s*[\"']>=\s*(\d+\.\d+(?:\.\d+)?)[\"']",
                blob,
                re.I,
            )
            if m:
                return m.group(1), "medium"
            m = re.search(r"[\"\']node[\"\']\s*:\s*[\"\']>=\s*(\d+(?:\.\d+)*)", blob, re.I)
            if m:
                return m.group(1), "medium"
            m = re.search(r"^go\s+(\d+\.\d+(?:\.\d+)?)\s*$", blob, re.I | re.M)
            if m:
                return m.group(1), "high"
            m = re.search(r"(rust|msrv)[^\n]{0,30}?(\d+\.\d+(?:\.\d+)?)", low)
            if m:
                return m.group(2), "low"
            m = re.search(r"(node|python)[^\n]{0,20}?(\d+\.\d+)", low)
            return (m.group(2), "low") if m else (None, None)
        return None, None

    def _llm_extract(self, field: Field, blob: str):
        """Opt-in model extraction. Returns (value|None, confidence)."""
        if os.environ.get("OPENROUTER_API_KEY"):
            return self._openrouter_extract(field, blob)
        if os.environ.get("ANTHROPIC_API_KEY"):
            return self._anthropic_extract(field, blob)
        raise RuntimeError(
            "LLM extractor requires OPENROUTER_API_KEY or ANTHROPIC_API_KEY; "
            "refusing to fall back to heuristics"
        )

    def _llm_prompt(self, field: Field, blob: str) -> str:
        return (
            f"From the document below, extract: {field.prompt}\n"
            f'Reply as JSON: {{"value": <string or null>, "confidence": '
            f'"high"|"medium"|"low"}}. null if the document does not state it. '
            f"No prose.\n\n---\n{blob[:12000]}"
        )

    def _openrouter_extract(self, field: Field, blob: str):
        import requests as rq

        api_key = os.environ["OPENROUTER_API_KEY"]
        model = (
            os.environ.get("OPENROUTER_MODEL")
            or os.environ.get("DOTREPO_ADJUDICATION_MODEL")
            or os.environ.get("DOTREPO_ADJUDICATION_API_MODEL")
        )
        if not model:
            raise RuntimeError(
                "LLM extractor using OpenRouter requires OPENROUTER_MODEL, "
                "DOTREPO_ADJUDICATION_MODEL, or DOTREPO_ADJUDICATION_API_MODEL"
            )
        prompt = self._llm_prompt(field, blob)
        cached = self._cached_llm_result("openrouter", model, prompt)
        if cached is not None:
            return cached
        r = rq.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "authorization": f"Bearer {api_key}",
                "content-type": "application/json",
                "http-referer": "https://github.com/maxwellsantoro/dotrepo",
                "x-title": "dotrepo-head-to-head-benchmark",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Return strict JSON only. Never wrap in markdown fences.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "max_tokens": 400,
                "response_format": {"type": "json_object"},
                "reasoning": {"enabled": False},
            },
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        choice = data["choices"][0]
        txt = choice["message"].get("content")
        if isinstance(txt, list):
            txt = "".join(part.get("text", "") for part in txt if isinstance(part, dict))
        if not txt:
            raise RuntimeError(
                "OpenRouter returned an empty LLM extraction response "
                f"for {field.id}; finish_reason={choice.get('finish_reason')!r}"
            )
        result = _parse_llm_json(field, txt)
        self._freeze_llm_result("openrouter", model, prompt, result)
        return result

    def _anthropic_extract(self, field: Field, blob: str):
        import requests as rq

        api_key = os.environ["ANTHROPIC_API_KEY"]
        model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
        prompt = self._llm_prompt(field, blob)
        cached = self._cached_llm_result("anthropic", model, prompt)
        if cached is not None:
            return cached
        r = rq.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "content-type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": model,
                "max_tokens": 400,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=40,
        )
        r.raise_for_status()
        data = r.json()
        txt = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        result = _parse_llm_json(field, txt)
        self._freeze_llm_result("anthropic", model, prompt, result)
        return result

    def _cached_llm_result(self, provider: str, model: str, prompt: str):
        if self.http.cache is None:
            return None
        key = self._llm_cache_key(provider, model, prompt)
        hit = self.http.cache.get(key)
        if hit is not None:
            payload = json.loads(hit["text"])
            return payload.get("value"), payload.get("confidence")
        if self.http.cache.mode == "replay":
            raise ReplayCacheMiss(f"replay cache miss: {key}")
        return None

    def _freeze_llm_result(
        self, provider: str, model: str, prompt: str, result: tuple[object, str]
    ) -> None:
        if self.http.cache is None:
            return
        key = self._llm_cache_key(provider, model, prompt)
        value, confidence = result
        self.http.cache.put(
            key,
            200,
            json.dumps({"value": value, "confidence": confidence}, sort_keys=True),
        )

    @staticmethod
    def _llm_cache_key(provider: str, model: str, prompt: str) -> str:
        digest = hashlib.sha256(prompt.encode()).hexdigest()
        return f"benchmark-llm://{provider}/{model}/{digest}"

    # -- byte/latency accounting: charge each underlying fetch exactly once --
    def _charge(self, key: str):
        nb, ms = self._cost.get(key, (0, 0.0))
        self._cost[key] = (0, 0.0)
        return nb, ms

    def _charge_docs(self, field: Field):
        keys = {"security_contact": ["__security__"]}
        if field.id == "test":
            return self._charge_many(
                [
                    "__contributing__",
                    "__makefile__",
                    "__justfile__",
                    "__package__",
                    "__pyproject__",
                    "__readme__",
                ]
            )
        if field.id == "min_toolchain":
            return self._charge_many(
                [
                    "__cargo__",
                    "__rust_toolchain_toml__",
                    "__rust_toolchain__",
                    "__pyproject__",
                    "__package__",
                    "__go_mod__",
                    "__readme__",
                ]
            )
        if field.id == "build":
            return self._charge_many(
                [
                    "__contributing__",
                    "__makefile__",
                    "__justfile__",
                    "__package__",
                    "__pyproject__",
                    "__cargo__",
                    "__go_mod__",
                    "__readme__",
                ]
            )
        return self._charge_many(keys.get(field.id, ["__readme__"]))

    def _charge_many(self, keys):
        total_bytes = 0
        total_ms = 0.0
        for key in keys:
            nb, ms = self._charge(key)
            total_bytes += nb
            total_ms += ms
        return total_bytes, total_ms


def _split(repo: str):
    parts = repo.replace("https://", "").strip("/").split("/")
    # accept "github.com/o/r" or "o/r"
    if parts[0].endswith(".com") or parts[0].endswith(".org"):
        return parts[1], parts[2]
    return parts[0], parts[1]


def _parse_llm_json(field: Field, txt: str):
    start = txt.find("{")
    end = txt.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise RuntimeError(f"LLM extractor returned non-JSON text for {field.id}: {txt!r}")
    obj = json.loads(txt[start : end + 1])
    conf = obj.get("confidence") or "medium"
    if conf not in ("high", "medium", "low"):
        conf = "medium"
    return obj.get("value"), conf


def _first_cmd(block: str, field_id: str) -> Optional[str]:
    for line in block.splitlines():
        line = line.strip().lstrip("$ ").strip()
        if not line or line.startswith("#"):
            continue
        if field_id == "test" and re.search(r"\btest\b", line):
            return line
        if field_id == "build" and re.search(
            r"build|install|make|cargo b|npm i|go build|pip install", line
        ):
            return line
    # otherwise first executable-looking line
    for line in block.splitlines():
        line = line.strip().lstrip("$ ").strip()
        if line and not line.startswith("#"):
            return line
    return None
