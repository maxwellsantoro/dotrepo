"""The baseline. Deliberately competent, not a strawman.

If dotrepo can't beat an honest GitHub-API-plus-README agent, it isn't earning
its existence -- and this arm is built to make that a fair fight. Structured
fields come straight from the REST API (high confidence). Buried fields are
extracted from README/SECURITY.md/CONTRIBUTING with either a regex heuristic
(default, zero API cost, low/medium confidence) or an LLM extractor (opt-in).
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

from ..model import Answer, Field, FieldClass
from .base import Arm, Http

API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"

_FENCE = re.compile(r"```(?:bash|sh|console|shell|text)?\n(.*?)```", re.S | re.I)


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

    def prefetch(self, repo: str):
        self._meta, self._docs, self._cost = {}, {}, {}
        owner, name = _split(repo)
        # 1) structured metadata (one call answers all github-native fields)
        st, text, nb, ms = self.http.get(f"{API}/repos/{owner}/{name}", self._headers())
        if st == 200:
            self._meta = json.loads(text)
        self._cost["__meta__"] = (nb, ms)
        # 2) docs for buried fields, fetched lazily-but-once per file
        for label, path in (("readme", "README.md"), ("security", "SECURITY.md"),
                            ("contributing", "CONTRIBUTING.md")):
            branch = self._meta.get("default_branch", "main")
            st, text, nb, ms = self.http.get(f"{RAW}/{owner}/{name}/{branch}/{path}")
            if st == 200:
                self._docs[label] = text
            self._cost[f"__{label}__"] = (nb if st == 200 else 0, ms)

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
        return Answer(value=val, confidence=conf, source="github:rest", bytes_over_wire=nb, latency_ms=ms)

    # -- buried fields: read the docs an agent would read --
    def _buried(self, field: Field) -> Answer:
        blob, src = self._doc_for(field)
        nb, ms = self._charge_docs(field)
        if not blob:
            return Answer(value=None, confidence=None, source="github:no-doc",
                          bytes_over_wire=nb, latency_ms=ms)
        if self.extractor == "llm":
            val, conf = self._llm_extract(field, blob)
        else:
            val, conf = self._heuristic_extract(field, blob)
        return Answer(value=val, confidence=conf, source=f"github:{src}:{self.extractor}",
                      bytes_over_wire=nb, latency_ms=ms)

    def _doc_for(self, field: Field):
        if field.id == "security_contact":
            return self._docs.get("security"), "SECURITY.md"
        if field.id == "test":
            return (self._docs.get("contributing") or self._docs.get("readme")), "docs"
        return self._docs.get("readme"), "README.md"

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
            for m in re.finditer(rf"#{{1,4}}[^\n]*\b({key})\b[^\n]*\n(.*?)(?=\n#|\Z)", blob, re.S | re.I):
                fb = _FENCE.search(m.group(2))
                if fb:
                    cmd = _first_cmd(fb.group(1), field.id)
                    if cmd:
                        return cmd, "medium"
            # fall back: any fenced command containing the keyword
            for fb in _FENCE.finditer(blob):
                cmd = _first_cmd(fb.group(1), field.id)
                if cmd and (field.id in cmd or (field.id == "build" and re.search(r"build|install|make|cargo b|npm i", cmd))):
                    return cmd, "low"
            return None, None
        if field.id == "min_toolchain":
            m = re.search(r"(rust|msrv)[^\n]{0,30}?(\d+\.\d+(?:\.\d+)?)", low)
            if m:
                return m.group(2), "low"
            m = re.search(r"(node|python)[^\n]{0,20}?(\d+\.\d+)", low)
            return (m.group(2), "low") if m else (None, None)
        return None, None

    def _llm_extract(self, field: Field, blob: str):
        """Opt-in Anthropic extraction. Returns (value|None, confidence)."""
        import requests as rq
        prompt = (
            f"From the document below, extract: {field.prompt}\n"
            f"Reply as JSON: {{\"value\": <string or null>, \"confidence\": "
            f"\"high\"|\"medium\"|\"low\"}}. null if the document does not state it. "
            f"No prose.\n\n---\n{blob[:12000]}"
        )
        try:
            r = rq.post("https://api.anthropic.com/v1/messages",
                        headers={"content-type": "application/json"},
                        json={"model": "claude-sonnet-4-6", "max_tokens": 400,
                              "messages": [{"role": "user", "content": prompt}]},
                        timeout=40)
            data = r.json()
            txt = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
            obj = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
            return obj.get("value"), (obj.get("confidence") or "medium")
        except Exception:
            return self._heuristic_extract(field, blob)

    # -- byte/latency accounting: charge each underlying fetch exactly once --
    def _charge(self, key: str):
        nb, ms = self._cost.get(key, (0, 0.0))
        self._cost[key] = (0, 0.0)
        return nb, ms

    def _charge_docs(self, field: Field):
        keys = {"security_contact": "__security__", "test": "__contributing__"}
        primary = keys.get(field.id, "__readme__")
        return self._charge(primary)


def _split(repo: str):
    parts = repo.replace("https://", "").strip("/").split("/")
    # accept "github.com/o/r" or "o/r"
    if parts[0].endswith(".com") or parts[0].endswith(".org"):
        return parts[1], parts[2]
    return parts[0], parts[1]


def _first_cmd(block: str, field_id: str) -> Optional[str]:
    for line in block.splitlines():
        line = line.strip().lstrip("$ ").strip()
        if not line or line.startswith("#"):
            continue
        if field_id == "test" and re.search(r"\btest\b", line):
            return line
        if field_id == "build" and re.search(r"build|install|make|cargo b|npm i|go build|pip install", line):
            return line
    # otherwise first executable-looking line
    for line in block.splitlines():
        line = line.strip().lstrip("$ ").strip()
        if line and not line.startswith("#"):
            return line
    return None
