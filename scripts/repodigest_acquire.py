"""Bounded public GitHub snapshot acquisition. Never imports repository code."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(value):
    value = value.removeprefix("https://").rstrip("/")
    if not re.fullmatch(r"github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        raise ValueError("expected github.com/owner/repository")
    if any(part in {".", ".."} for part in value.split("/")):
        raise ValueError("invalid identity path")
    return value.lower()


def safe_path(path):
    if (
        not isinstance(path, str)
        or not path
        or path.startswith("/")
        or "\\" in path
        or any(ord(c) < 32 or ord(c) == 127 for c in path)
        or any(part in {"", ".", ".."} for part in path.split("/"))
    ):
        raise ValueError("unsafe repository path")
    return path


class PublicHTTP:
    def __init__(self, *, requests=180, byte_limit=33554432, seconds=300):
        self.remaining = requests
        self.byte_limit = byte_limit
        self.bytes = 0
        self.deadline = time.monotonic() + seconds
        self.events = []
        self.opener = urllib.request.build_opener(NoRedirect)

    def get(self, url, limit=1048576):
        if not url.startswith(
            ("https://api.github.com/repos/", "https://raw.githubusercontent.com/")
        ):
            raise ValueError("origin not admitted")
        if (
            self.remaining <= 0
            or self.bytes >= self.byte_limit
            or time.monotonic() >= self.deadline
        ):
            raise ValueError("acquisition budget exhausted")
        self.remaining -= 1
        start = time.monotonic()
        event = {"url": url, "responseBodyBytes": 0, "status": None}
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "repodigest-experimental/0.1",
                    "Accept": "application/vnd.github+json",
                },
            )
            with self.opener.open(
                request, timeout=min(20, max(0.1, self.deadline - time.monotonic()))
            ) as response:
                event["status"] = response.status
                raw = response.read(min(limit, self.byte_limit - self.bytes) + 1)
                event["responseBodyBytes"] = len(raw)
                self.bytes += len(raw)
                if len(raw) > limit or self.bytes > self.byte_limit:
                    raise ValueError("response exceeds admitted budget")
                return raw
        except urllib.error.HTTPError as exc:
            event["status"] = exc.code
            raise
        finally:
            event["wallSeconds"] = time.monotonic() - start
            self.events.append(event)


def selected_paths(tree, maximum=36):
    paths = [x["path"] for x in tree if x["type"] == "blob" and x.get("mode") == "100644"]
    root_names = {
        "readme.md",
        "readme.rst",
        "readme",
        "contributing.md",
        "contributing.rst",
        "contributing",
        "pyproject.toml",
        "package.json",
        "cargo.toml",
        "go.mod",
        "tox.ini",
        "setup.cfg",
        "setup.py",
        "makefile",
        "justfile",
        "uv.lock",
        ".python-version",
        "rust-toolchain.toml",
    }
    selected = {p for p in paths if "/" not in p and p.lower() in root_names}
    selected |= {
        p for p in paths if p.lower() in {".github/contributing.md", ".github/contributing.rst"}
    }
    others = [
        p
        for p in paths
        if (
            p.count("/") <= 2
            and p.rsplit("/", 1)[-1] in {"Cargo.toml", "package.json", "pyproject.toml", "go.mod"}
        )
        or (
            p.count("/") <= 2
            and any(s in p.lower() for s in ("contribut", "development", "devguide", "testing"))
            and p.endswith((".md", ".rst"))
        )
        or (p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml")))
    ]
    return (
        sorted(selected)
        + [p for p in sorted(others) if p not in selected][: max(0, maximum - len(selected))]
    )


def acquire(repo, output, http, *, revision=None, maximum=36, previous=None):
    repo = identity(repo)
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    full = repo.split("/", 1)[1]
    commit_raw = http.get(
        f"https://api.github.com/repos/{full}/commits/{revision or 'HEAD'}", 4194304
    )
    commit = json.loads(commit_raw)
    revision = commit["sha"]
    if not re.fullmatch("[0-9a-f]{40}", revision):
        raise ValueError("invalid revision")
    tree_sha = commit["commit"]["tree"]["sha"]
    old = json.loads((previous / "snapshot.json").read_text()) if previous else None
    if old and old["repository"] != repo:
        raise ValueError("refresh identity mismatch")
    if old and old["tree"] == tree_sha:
        tree_raw = (previous / "tree.json").read_bytes()
        if sha(tree_raw) != old["treeSha256"]:
            raise ValueError("cached tree corrupted")
    else:
        tree_raw = http.get(
            f"https://api.github.com/repos/{full}/git/trees/{tree_sha}?recursive=1", 8388608
        )
    tree = json.loads(tree_raw)
    if tree.get("truncated") or tree["sha"] != tree_sha:
        raise ValueError("incomplete or mismatched source tree")
    (output / "commit.json").write_bytes(commit_raw)
    (output / "tree.json").write_bytes(tree_raw)
    entries = {e["path"]: e for e in tree["tree"] if e["type"] == "blob"}
    selected = selected_paths(tree["tree"], maximum)
    # Preserve demand-selected coverage across normal refresh. Every reused or
    # changed file is still verified against the new tree; deleted paths drop.
    if old:
        selected += [
            p
            for p in sorted(old["files"])
            if p not in selected and p in entries and entries[p].get("mode") in {"100644", "100755"}
        ]
    if len(selected) > 96:
        raise ValueError("total inspected-file budget exceeded")
    inventory = {}
    reused = []
    fetched = []
    for path in selected:
        safe_path(path)
        binding = old["files"].get(path) if old else None
        if binding and binding["gitBlob"] == entries[path]["sha"]:
            raw = (previous / "files" / path).read_bytes()
            if sha(raw) != binding["sha256"]:
                raise ValueError("cached source corrupted:" + path)
            reused.append(path)
        else:
            raw = http.get(f"https://raw.githubusercontent.com/{full}/{revision}/{path}")
            fetched.append(path)
        if (
            hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            != entries[path]["sha"]
        ):
            raise ValueError("content does not match Git tree")
        raw.decode("utf-8")
        file = output / "files" / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(raw)
        inventory[path] = {"sha256": sha(raw), "gitBlob": entries[path]["sha"], "bytes": len(raw)}
    snapshot = {
        "repository": repo,
        "revision": revision,
        "tree": tree_sha,
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "treeSha256": sha(tree_raw),
        "files": inventory,
        "coverage": {
            "treeComplete": True,
            "trackedBlobs": len(entries),
            "inspectedFiles": len(inventory),
            "meaning": "Bounded docs/config acquisition. Unread files and linked external docs remain unknown.",
        },
    }
    if old and "demandFocus" in old:
        snapshot["demandFocus"] = {
            component: [p for p in paths if p in inventory]
            for component, paths in old["demandFocus"].items()
        }
    kept_provenance = {}
    invalidated_provenance = []
    if old and "sourceReuse" in old:
        from repodigest_reuse import lineage

        for path, receipt in lineage(old).items():
            binding = inventory.get(path)
            if binding and (binding["gitBlob"], binding["sha256"]) == (
                receipt["gitBlob"],
                receipt["sha256"],
            ):
                kept_provenance[path] = receipt
            else:
                invalidated_provenance.append(path)
        if kept_provenance:
            snapshot["sourceReuse"] = kept_provenance
    (output / "snapshot.json").write_bytes(canonical(snapshot) + b"\n")
    (output / "refresh.json").write_text(
        json.dumps(
            {
                "previousRevision": old["revision"] if old else None,
                "currentRevision": revision,
                "fetchedFiles": fetched,
                "reusedFiles": reused,
                "removedFiles": sorted(set(old["files"]) - set(inventory)) if old else [],
                "retainedSourceReuseProvenance": sorted(kept_provenance),
                "invalidatedSourceReuseProvenance": sorted(invalidated_provenance),
            },
            indent=2,
        )
        + "\n"
    )
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--revision")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    http = PublicHTTP()
    results = []
    try:
        for repo in args.repository:
            snapshot = acquire(
                repo,
                args.output / identity(repo).split("/", 1)[1].replace("/", "__"),
                http,
                previous=args.previous,
                revision=args.revision,
            )
            results.append(
                {
                    "repository": snapshot["repository"],
                    "revision": snapshot["revision"],
                    "files": len(snapshot["files"]),
                }
            )
    finally:
        (args.output / "traffic.json").write_text(json.dumps(http.events, indent=2) + "\n")
        (args.output / "report.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
