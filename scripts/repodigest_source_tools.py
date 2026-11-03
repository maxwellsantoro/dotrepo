"""Bounded, metered public-source tools for the equal-task consumer study."""

from __future__ import annotations

import fnmatch
import json
import hashlib
from pathlib import Path
from urllib.parse import quote

from repodigest_acquire import PublicHTTP, canonical, identity, safe_path, sha

MAX_LIST_LIMIT = 100
MAX_PATTERN_LENGTH = 200
MAX_READ_LINES = 120
MAX_RESPONSE_BYTES = 32768


def bounded_payload(value):
    """Bound the source JSON payload, excluding its transport envelope."""
    if len(canonical(value)) > MAX_RESPONSE_BYTES:
        raise ValueError("source payload exceeds32KiB; request a narrower range or pattern")
    return value


class Sources:
    def __init__(self, catalog, traffic_log):
        self.catalog = json.loads(catalog.read_text())
        self.blobs = {}
        for repo, item in self.catalog.items():
            raw = Path(item["treePath"]).read_bytes()
            if sha(raw) != item["treeSha256"]:
                raise ValueError("catalog tree changed")
            self.blobs[repo] = {
                e["path"]: e for e in json.loads(raw)["tree"] if e["type"] == "blob"
            }
        self.traffic_log = traffic_log
        self.http = PublicHTTP(requests=24, byte_limit=8388608, seconds=300)
        self.cache = {}
        self.calls = []
        self.flush()

    def flush(self):
        self.traffic_log.write_text(
            json.dumps({"http": self.http.events, "toolCalls": self.calls}, indent=2) + "\n"
        )

    def target(self, repository, revision):
        repo = identity(repository)
        item = self.catalog.get(repo)
        if not item or item["revision"] != revision:
            raise ValueError("source target outside admitted study catalog")
        return repo, item

    def list(self, repository, revision, pattern="*", offset=0, limit=60):
        repo, item = self.target(repository, revision)
        if not isinstance(pattern, str) or len(pattern) > MAX_PATTERN_LENGTH:
            raise ValueError(f"pattern must be a string of at most {MAX_PATTERN_LENGTH} characters")
        if type(offset) is not int or offset < 0:
            raise ValueError("offset must be an integer >=0")
        if type(limit) is not int or not 1 <= limit <= MAX_LIST_LIMIT:
            raise ValueError(
                f"limit must be an integer in 1..{MAX_LIST_LIMIT}; use nextOffset to continue"
            )
        key = (repo, "tree", item["tree"])
        try:
            if key not in self.cache:
                raw = self.http.get(
                    f"https://api.github.com/repos/{repo.split('/', 1)[1]}/git/trees/{item['tree']}?recursive=1",
                    8388608,
                )
                tree = json.loads(raw)
                if tree.get("truncated") or tree["sha"] != item["tree"]:
                    raise ValueError("tree incomplete")
                self.cache[key] = tree
            paths = sorted(
                e["path"]
                for e in self.cache[key]["tree"]
                if e["type"] == "blob" and fnmatch.fnmatchcase(e["path"], pattern)
            )
            out = {
                "paths": paths[offset : offset + limit],
                "totalPaths": len(paths),
                "nextOffset": offset + limit if len(paths) > offset + limit else None,
            }
            return bounded_payload(out)
        finally:
            self.calls.append(
                {
                    "tool": "source.list",
                    "repository": repo,
                    "revision": revision,
                    "pattern": pattern,
                }
            )
            self.flush()

    def read(self, repository, revision, path, start=1, end=None):
        repo, item = self.target(repository, revision)
        safe_path(path)
        if end is None and type(start) is int:
            end = start + 99
        if (
            type(start) is not int
            or type(end) is not int
            or start < 1
            or not start <= end < start + MAX_READ_LINES
        ):
            raise ValueError("read at most 120 numbered lines")
        entry = self.blobs[repo].get(path)
        if not entry or entry.get("mode") not in {"100644", "100755"}:
            raise ValueError("path not a regular blob in pinned tree")
        key = (repo, "blob", revision, path)
        try:
            if key not in self.cache:
                raw = self.http.get(
                    f"https://raw.githubusercontent.com/{repo.split('/', 1)[1]}/{revision}/{quote(path, safe='/')}"
                )
                if (
                    hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
                    != entry["sha"]
                ):
                    raise ValueError("source response does not match pinned Git blob")
                # Retain exact response for independent scoring.
                self.cache[key] = raw
                directory = self.traffic_log.parent / "source-responses" / repo.split("/", 1)[1]
                file = directory / path
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(raw)
            raw = self.cache[key]
            lines = raw.decode("utf-8").splitlines()
            return bounded_payload(
                {
                    "repository": repo,
                    "revision": revision,
                    "path": path,
                    "sha256": sha(raw),
                    "startLine": start,
                    "endLine": min(end, len(lines)),
                    "totalLines": len(lines),
                    "lines": "\n".join(
                        f"{n + 1}: {line}"
                        for n, line in enumerate(lines[start - 1 : end], start - 1)
                    ),
                }
            )
        finally:
            self.calls.append(
                {
                    "tool": "source.read",
                    "repository": repo,
                    "revision": revision,
                    "path": path,
                    "start": start,
                    "end": end,
                }
            )
            self.flush()
