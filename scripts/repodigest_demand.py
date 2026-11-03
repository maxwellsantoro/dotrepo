"""Operator-only bounded follow-up acquisition for an exact indexed component."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from repodigest_acquire import PublicHTTP, canonical, safe_path, sha

MAX_NEW_FILES = 8
MAX_FILE_BYTES = 262144
MAX_NEW_BYTES = 1048576
MAX_TOTAL_FILES = 96
MANIFESTS = {"Cargo.toml", "package.json", "pyproject.toml", "go.mod"}
DOCS = {
    "readme",
    "readme.md",
    "readme.rst",
    "contributing.md",
    "contributing.rst",
    "testing.md",
    "development.md",
    "makefile",
    "justfile",
    "tox.ini",
    "setup.cfg",
    "rust-toolchain.toml",
    ".python-version",
}


def plan(component, blobs, contents):
    """Heuristic file candidates, never a claim that the list is complete."""
    if component != ".":
        safe_path(component)
    prefix = "" if component == "." else component + "/"
    candidates = {}

    def add(path, priority, reason):
        entry = blobs.get(path)
        if entry and entry.get("mode") in {"100644", "100755"}:
            safe_path(path)
            candidates.setdefault(path, (priority, reason))

    for name in sorted(MANIFESTS):
        add(prefix + name, 0, "component-manifest")
    for path in sorted(blobs):
        parent, _, name = path.rpartition("/")
        if parent in {component if component != "." else "", ""} and name.lower() in DOCS:
            add(
                path,
                1 if parent else 2,
                "component-documentation" if parent else "repository-context",
            )
        if path.startswith(".github/workflows/") and re.search(
            r"(?:tests?|ci)\.(?:yml|yaml)$", name
        ):
            add(path, 3, "test-workflow-context")
    # One hop through retained relevant material. Only literal repository script
    # paths are followed; no URLs, shell expansion, imports, or execution.
    for path in list(candidates):
        for linked in re.findall(
            r"\b(scripts/[A-Za-z0-9_./-]+\.(?:sh|py))\b", contents.get(path, "")
        ):
            add(linked, 4, "literal-script-reference:" + path)
    return [
        {
            "path": path,
            "reason": reason,
            "inspection": "retained" if path in contents else "not-inspected",
        }
        for path, (_, reason) in sorted(candidates.items(), key=lambda item: (item[1][0], item[0]))
    ]


def follow_up(previous, output, http, *, component, revision, extra_paths=()):
    from repodigest_store import components, validate_snapshot

    old, blobs, contents = validate_snapshot(previous)
    if revision != old["revision"]:
        raise ValueError("follow-up requires the exact retained revision; refresh separately")
    if component not in components(blobs, contents):
        raise ValueError("component not indexed")
    candidates = plan(component, blobs, contents)
    known = {item["path"] for item in candidates}
    for path in extra_paths:
        safe_path(path)
        entry = blobs.get(path)
        if not entry or entry.get("mode") not in {"100644", "100755"}:
            raise ValueError("requested path not a regular pinned blob")
        if path not in known:
            candidates.append(
                {
                    "path": path,
                    "reason": "operator-requested-context",
                    "inspection": "retained" if path in contents else "not-inspected",
                }
            )
            known.add(path)
    missing = [item for item in candidates if item["inspection"] == "not-inspected"]
    selected = missing[:MAX_NEW_FILES]
    if len(contents) + len(selected) > MAX_TOTAL_FILES:
        raise ValueError("total inspected-file budget exceeded")
    output.mkdir(parents=True, exist_ok=False)
    snapshot = copy.deepcopy(old)
    for path in ("commit.json", "tree.json"):
        shutil.copyfile(previous / path, output / path)
    for path in contents:
        dest = output / "files" / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(previous / "files" / path, dest)
    downloaded = 0
    fetched = []
    try:
        for item in selected:
            path = item["path"]
            raw = http.get(
                f"https://raw.githubusercontent.com/{old['repository'].split('/', 1)[1]}/{revision}/{quote(path, safe='/')}",
                min(MAX_FILE_BYTES, MAX_NEW_BYTES - downloaded),
            )
            downloaded += len(raw)
            if len(raw) > MAX_FILE_BYTES or downloaded > MAX_NEW_BYTES:
                raise ValueError("follow-up byte budget exceeded")
            if (
                hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
                != blobs[path]["sha"]
            ):
                raise ValueError("follow-up response does not match pinned Git blob")
            raw.decode("utf-8")
            dest = output / "files" / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
            snapshot["files"][path] = {
                "sha256": sha(raw),
                "gitBlob": blobs[path]["sha"],
                "bytes": len(raw),
            }
            fetched.append(path)
        focus = sorted({item["path"] for item in candidates if item["path"] in snapshot["files"]})
        focus_changed = snapshot.get("demandFocus", {}).get(component) != focus
        if fetched or focus_changed:
            snapshot.setdefault("demandFocus", {})[component] = focus
            snapshot["coverage"]["inspectedFiles"] = len(snapshot["files"])
            snapshot["demand"] = {
                "component": component,
                "baseSnapshotSha256": sha(canonical(old)),
                "acquiredAt": datetime.now(timezone.utc).isoformat(),
                "fetchedFiles": fetched,
                "meaning": "Additional pinned file inspection; original HEAD check time is unchanged. No execution or instruction qualification.",
            }
        (output / "snapshot.json").write_bytes(canonical(snapshot) + b"\n")
        report = {
            "state": "extended" if fetched else "focused" if focus_changed else "cached",
            "repository": old["repository"],
            "revision": revision,
            "component": component,
            "fetchedFiles": fetched,
            "reusedFiles": sorted(contents),
            "deferredFiles": [item["path"] for item in missing[MAX_NEW_FILES:]],
            "newResponseBodyBytes": downloaded,
            "candidatePolicy": "Bounded heuristic, not exhaustive dependencies or complete procedure coverage.",
        }
        (output / "demand-report.json").write_text(json.dumps(report, indent=2) + "\n")
        return snapshot, report
    finally:
        (output / "traffic.json").write_text(json.dumps(http.events, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--component", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--path", action="append", default=[])
    args = parser.parse_args()
    http = PublicHTTP(requests=MAX_NEW_FILES, byte_limit=MAX_NEW_BYTES, seconds=60)
    _, report = follow_up(
        args.previous,
        args.output,
        http,
        component=args.component,
        revision=args.revision,
        extra_paths=args.path,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
