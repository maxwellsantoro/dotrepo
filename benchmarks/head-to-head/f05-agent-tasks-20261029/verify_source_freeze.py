#!/usr/bin/env -S uv run python
"""Verify the retained F-05 source packet without running upstream code."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


def read_json(path: Path):
    return json.loads(path.read_text())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify(root: Path) -> tuple[int, int]:
    freeze = read_json(root / "SOURCE_FREEZE.json")
    require(freeze["campaignExecuted"] is False, "source packet cannot report execution")
    retained = {
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file() and path.name != "SOURCE_FREEZE.json"
    }
    declared = {entry["path"] for entry in freeze["files"]}
    require(retained == declared, "retained file inventory differs from source freeze")
    for entry in freeze["files"]:
        path = root / entry["path"]
        require(not path.is_symlink(), f"unexpected link: {entry['path']}")
        raw = path.read_bytes()
        require(len(raw) == entry["bytes"], f"size changed: {entry['path']}")
        require(
            hashlib.sha256(raw).hexdigest() == entry["sha256"],
            f"content changed: {entry['path']}",
        )

    catalog = read_json(root / "source-catalog.json")
    for entry in catalog:
        raw = (root / entry["localPath"]).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == entry["sha256"], "source hash changed")
        if entry["kind"] == "source":
            blob = b"blob " + str(len(raw)).encode() + b"\0" + raw
            require(
                hashlib.sha1(blob, usedforsecurity=False).hexdigest() == entry["gitBlobSha"],
                f"upstream blob identity mismatch: {entry['localPath']}",
            )
            require(entry["ref"] in entry["url"], "source URL is not commit pinned")

    roster = read_json(root / "tasks.json")
    tasks = roster["tasks"]
    require(roster["indexConsulted"] is False, "evaluated index influenced curation")
    require(len(tasks) == 12, "expected twelve tasks")
    require(len({task["repository"].lower() for task in tasks}) == 12, "repeated repository")
    require(len({task["id"] for task in tasks}) == 12, "repeated task identity")
    require(
        Counter(task["ecosystem"] for task in tasks)
        == {"Rust": 3, "Python": 3, "JavaScript/TypeScript": 3, "Go": 3},
        "ecosystem quotas changed",
    )
    require(
        Counter(task["scope"] for task in tasks) == {"repository": 6, "component": 6},
        "scope quotas changed",
    )
    require(
        Counter(task["startingState"] for task in tasks) == {"pre-clone": 6, "local-checkout": 6},
        "starting-state quotas changed",
    )
    slots = {
        "Rust": [
            ("repository", "pre-clone"),
            ("component", "local-checkout"),
            ("repository", "local-checkout"),
        ],
        "Python": [
            ("repository", "pre-clone"),
            ("component", "local-checkout"),
            ("component", "pre-clone"),
        ],
        "TypeScript": [
            ("repository", "pre-clone"),
            ("component", "local-checkout"),
            ("repository", "local-checkout"),
        ],
        "Go": [
            ("repository", "pre-clone"),
            ("component", "local-checkout"),
            ("component", "pre-clone"),
        ],
    }
    reservations = read_json(root / "rules/screening-reservations.json")
    excluded = {row["repository"].lower() for row in reservations["excluded"]}
    queues = {queue["ecosystem"]: queue for queue in reservations["queues"]}
    screening = read_json(root / "screening.json")
    require(screening["indexConsulted"] is False, "index-influenced screening")
    by_id = {task["id"]: task for task in tasks}
    for ecosystem, queue in queues.items():
        rows = [row for row in screening["rows"] if row["ecosystem"] == ecosystem]
        require(
            [row["repository"] for row in rows] == queue["f05"][: len(rows)],
            f"screening skipped/reordered a {ecosystem} reservation",
        )
        enrolled = [row for row in rows if row["decision"] == "enrolled"]
        require([row["slot"] for row in enrolled] == [1, 2, 3], "incorrect slot enrollment")
        e1 = {identity.lower() for identity in queue["e1Qualification"]}
        for row, (scope, state) in zip(enrolled, slots[ecosystem], strict=True):
            task = by_id[row["taskId"]]
            require(task["repository"] == row["repository"], "screening identity differs")
            require(task["revision"] == row["revision"], "screening revision differs")
            require((task["scope"], task["startingState"]) == (scope, state), "slot changed")
            require(task["repository"].lower() not in excluded | e1, "prior-exposure overlap")

    for task in tasks:
        require(re.fullmatch(r"[0-9a-f]{40}", task["revision"]) is not None, "unfrozen revision")
        require(task["request"].startswith("requests/"), "request path leaks curator material")
        require(task["gold"].startswith("curator/gold/"), "gold outside curator boundary")
        require(task["oracle"].startswith("curator/oracles/"), "oracle outside curator boundary")
        prompt = (root / task["request"]).read_text()
        require(
            task["revision"] in prompt and task["repository"] in prompt, "request lost identity"
        )
        require(
            re.search(r"cargo test|uv run|npm run|npx hereby|go test|pytest|pnpm", prompt) is None,
            "request contains an instruction answer",
        )
        for relative in [task["gold"], task["oracle"]]:
            document = read_json(root / relative)
            require(document["taskId"] == task["id"], "scorer artifact identity differs")
            for locator in document["sourceLocators"]:
                source, span = locator.rsplit(":", 1)
                first, last = map(int, span.split("-"))
                length = len((root / source).read_text().splitlines())
                require(1 <= first <= last <= length, f"invalid source locator: {locator}")
        gold = read_json(root / task["gold"])
        require(gold["executionObserved"] is False, "source gold claims execution")
    return len(tasks), len(catalog)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    try:
        tasks, sources = verify(args.root)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"error: {exc}\n")
    print(
        f"source freeze verified: {tasks} tasks, {sources} source/metadata files; no campaign run"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
