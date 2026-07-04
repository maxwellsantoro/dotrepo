from __future__ import annotations

import time
from typing import Optional

import requests

from ..model import Answer, Field


class Arm:
    """An arm answers (repo, field) -> Answer, tracking bytes + latency.

    Arms may prefetch per-repo (one API call answering many fields). Byte cost is
    attributed to the first field that triggers the fetch, so total-bytes-per-arm
    reflects real wire cost, not per-question cost. That is deliberate: dotrepo's
    pitch is *amortized* cheapness, and the report should credit it fairly.
    """

    name = "base"

    def prefetch(self, repo: str) -> None:  # optional
        return None

    def answer(self, repo: str, field: Field) -> Answer:
        raise NotImplementedError


class Http:
    """Thin requests wrapper that counts response bytes and latency, with an
    optional on-disk cache so a benchmark run is replayable as a frozen fixture
    (freeze once, re-score deterministically forever)."""

    def __init__(self, cache: Optional["ResponseCache"] = None, timeout: float = 20.0):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "dotrepo-bench/0.1 (+falsifiable head-to-head)"
        self.cache = cache
        self.timeout = timeout

    def get(self, url: str, headers: Optional[dict] = None):
        if self.cache is not None:
            hit = self.cache.get(url)
            if hit is not None:
                return hit["status"], hit["text"], len(hit["text"].encode()), 0.0
        t0 = time.perf_counter()
        r = self.s.get(url, headers=headers or {}, timeout=self.timeout)
        dt = (time.perf_counter() - t0) * 1000.0
        text = r.text
        nbytes = len(r.content)
        if self.cache is not None:
            self.cache.put(url, r.status_code, text)
        return r.status_code, text, nbytes, dt
