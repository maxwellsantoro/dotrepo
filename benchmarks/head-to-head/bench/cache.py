from __future__ import annotations

import hashlib
import json
import os
from typing import Optional


class ResponseCache:
    """Content-addressed cache of raw HTTP responses.

    Run once with --freeze to capture every response into a directory, then re-run
    with --replay to score the exact same bytes offline. This makes a benchmark
    result a falsifiable artifact you can commit, diff, and re-audit -- and lets a
    regression be frozen as a fixture the way a failing pipeline record should be.
    """

    def __init__(self, root: str, mode: str = "off"):
        self.root = root
        self.mode = mode  # "off" | "freeze" | "replay"
        if mode in ("freeze", "replay"):
            os.makedirs(root, exist_ok=True)

    def _path(self, url: str) -> str:
        h = hashlib.sha256(url.encode()).hexdigest()[:24]
        return os.path.join(self.root, f"{h}.json")

    def get(self, url: str) -> Optional[dict]:
        if self.mode != "replay":
            return None
        p = self._path(url)
        if not os.path.exists(p):
            return None
        with open(p) as f:
            return json.load(f)

    def put(self, url: str, status: int, text: str) -> None:
        if self.mode != "freeze":
            return
        with open(self._path(url), "w") as f:
            json.dump({"url": url, "status": status, "text": text}, f)
