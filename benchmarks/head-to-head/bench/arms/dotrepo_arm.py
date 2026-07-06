"""The dotrepo arm.

One batched call per repo hits /v0/batch/query with every dot-path, then each
field reads its result out of the envelope. dotrepo's public docs guarantee
per-result confidence + provenance but don't pin the exact JSON keys, so the
resolver tries a priority list rather than hardcoding one shape. If your deployed
envelope differs, adjust VALUE_KEYS / CONF_KEYS below in one place -- verified
against a single live curl, this arm needs no other change.
"""

from __future__ import annotations

import json
from urllib.parse import quote

from ..model import Answer, Field
from .base import Arm, Http

# Candidate locations for the resolved value inside one query result, best-first.
VALUE_KEYS = ["value", "resolved", "result", "answer", ["query", "value"], ["field", "value"]]
# Candidate locations for confidence.
CONF_KEYS = [
    "confidence",
    ["trust", "confidence"],
    ["value", "confidence"],
    "selectedConfidence",
    ["query", "selection", "record", "record", "trust", "confidence"],
]
# Candidate locations for provenance/source (audit trail).
PROV_KEYS = [
    "provenance",
    "source",
    ["trust", "provenance"],
    "origin",
    ["query", "selection", "record", "record", "trust", "provenance"],
]


class DotrepoArm(Arm):
    name = "dotrepo"

    def __init__(self, http: Http, base_url: str = "https://dotrepo.org"):
        self.http = http
        self.base = base_url.rstrip("/")
        self._results: dict = {}  # path -> result dict (or error)
        self._cost = (0, 0.0)

    def configuration(self) -> dict:
        return {"base_url": self.base}

    def prefetch(self, repo: str):
        from ..fields import FIELDS

        self._results, self._cost = {}, (0, 0.0)
        paths = [f.dotrepo_path for f in FIELDS if f.dotrepo_path]
        q = "&".join([f"repo={quote(repo)}"] + [f"path={quote(p)}" for p in paths])
        url = f"{self.base}/v0/batch/query?{q}"
        st, text, nb, ms = self.http.get(url, {"Accept": "application/json"})
        self._cost = (nb, ms)
        if st != 200:
            return
        try:
            self._results = _index_by_path(json.loads(text))
        except Exception:
            self._results = {}

    def answer(self, repo: str, field: Field) -> Answer:
        nb, ms = self._cost
        self._cost = (0, 0.0)  # charge the batch call once, to the first field
        if not field.dotrepo_path:
            return Answer(None, None, "dotrepo:no-path", nb, ms)
        res = self._results.get(field.dotrepo_path)
        if res is None or "error" in (res or {}):
            return Answer(None, None, "dotrepo:missing", nb, ms, raw=res)
        val = _dig_first(res, VALUE_KEYS)
        if isinstance(val, (dict, list)):
            val = json.dumps(val)
        conf = _dig_first(res, CONF_KEYS)
        prov = _dig_first(res, PROV_KEYS)
        return Answer(
            value=(str(val) if val is not None else None),
            confidence=(str(conf).lower() if conf else None),
            source=f"dotrepo:{prov or 'query'}",
            bytes_over_wire=nb,
            latency_ms=ms,
            raw=res,
        )


def _index_by_path(payload) -> dict:
    """Normalize the batch envelope into {dot_path: result}. Tolerant of a few
    plausible shapes: {"results":[{"path":..,...}]}, {"paths":{path:..}}, or a
    bare list."""
    out = {}
    items = None
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            items = payload["results"]
        elif isinstance(payload.get("queries"), list):
            items = payload["queries"]
        elif isinstance(payload.get("paths"), dict):
            return {k: v for k, v in payload["paths"].items()}
    elif isinstance(payload, list):
        items = payload
    if items:
        for it in items:
            if isinstance(it, dict):
                p = it.get("path") or it.get("query") or _dig(it, ["query", "path"])
                if p:
                    out[p] = it
    return out


def _dig(obj, keypath):
    cur = obj
    for k in keypath if isinstance(keypath, list) else [keypath]:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _dig_first(obj, candidates):
    for c in candidates:
        v = _dig(obj, c)
        if v is not None:
            return v
    return None
