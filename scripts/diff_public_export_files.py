#!/usr/bin/env -S uv run python

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "dotrepo-public-file-delta/v0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare two dotrepo public v0/files.json manifests."
    )
    parser.add_argument(
        "--old-files",
        required=True,
        help="Previous public export file manifest, usually old/public/v0/files.json",
    )
    parser.add_argument(
        "--new-files",
        required=True,
        help="New public export file manifest, usually new/public/v0/files.json",
    )
    parser.add_argument("--output-json", help="Optional path for JSON delta output")
    parser.add_argument("--output-md", help="Optional path for Markdown delta output")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"failed to parse JSON in {path}: {exc}") from exc


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = load_json(path)
    if manifest.get("apiVersion") != "v0":
        raise SystemExit(
            f"unsupported file manifest apiVersion in {path}: {manifest.get('apiVersion')}"
        )
    files = manifest.get("files")
    if not isinstance(files, list):
        raise SystemExit(f"file manifest must contain a files array: {path}")

    by_path = {}
    for item in files:
        if not isinstance(item, dict):
            raise SystemExit(f"file manifest entry must be an object: {path}")
        file_path = item.get("path")
        sha256 = item.get("sha256")
        byte_count = item.get("bytes")
        if not isinstance(file_path, str) or not file_path:
            raise SystemExit(f"file manifest entry has invalid path: {path}")
        if not isinstance(sha256, str) or not sha256:
            raise SystemExit(f"file manifest entry has invalid sha256 for {file_path}: {path}")
        if not isinstance(byte_count, int) or byte_count < 0:
            raise SystemExit(f"file manifest entry has invalid bytes for {file_path}: {path}")
        if file_path in by_path:
            raise SystemExit(f"duplicate file manifest path {file_path}: {path}")
        by_path[file_path] = {
            "path": file_path,
            "bytes": byte_count,
            "sha256": sha256,
        }

    return {
        "path": path.as_posix(),
        "freshness": manifest.get("freshness", {}),
        "files": by_path,
    }


def classify_delta(old_file: dict[str, Any], new_file: dict[str, Any]) -> str:
    if old_file["sha256"] != new_file["sha256"]:
        return "content"
    if old_file["bytes"] != new_file["bytes"]:
        return "metadata"
    return "unchanged"


def compare_manifests(old_manifest_path: Path, new_manifest_path: Path) -> dict[str, Any]:
    old_manifest = load_manifest(old_manifest_path)
    new_manifest = load_manifest(new_manifest_path)
    old_files = old_manifest["files"]
    new_files = new_manifest["files"]

    added = []
    removed = []
    changed = []
    unchanged = []

    for path in sorted(new_files):
        if path not in old_files:
            added.append(new_files[path])
            continue
        delta_kind = classify_delta(old_files[path], new_files[path])
        if delta_kind == "unchanged":
            unchanged.append(new_files[path])
        else:
            changed.append(
                {
                    "path": path,
                    "change": delta_kind,
                    "old": old_files[path],
                    "new": new_files[path],
                    "byteDelta": new_files[path]["bytes"] - old_files[path]["bytes"],
                }
            )

    for path in sorted(old_files):
        if path not in new_files:
            removed.append(old_files[path])

    refetch = sorted(item["path"] for item in added) + sorted(item["path"] for item in changed)
    old_bytes = sum(item["bytes"] for item in old_files.values())
    new_bytes = sum(item["bytes"] for item in new_files.values())
    refetch_bytes = sum(new_files[path]["bytes"] for path in refetch)

    return {
        "schema": SCHEMA,
        "old": {
            "path": old_manifest["path"],
            "freshness": old_manifest["freshness"],
            "fileCount": len(old_files),
            "bytes": old_bytes,
        },
        "new": {
            "path": new_manifest["path"],
            "freshness": new_manifest["freshness"],
            "fileCount": len(new_files),
            "bytes": new_bytes,
        },
        "summary": {
            "addedCount": len(added),
            "changedCount": len(changed),
            "removedCount": len(removed),
            "unchangedCount": len(unchanged),
            "oldBytes": old_bytes,
            "newBytes": new_bytes,
            "refetchBytes": refetch_bytes,
            "refetchFileCount": len(refetch),
            "refetchByteRatio": round(refetch_bytes / new_bytes, 4) if new_bytes else None,
        },
        "added": added,
        "changed": changed,
        "removed": removed,
        "unchanged": [item["path"] for item in unchanged],
        "refetch": refetch,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# dotrepo public file delta",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Added files | {summary['addedCount']} |",
        f"| Changed files | {summary['changedCount']} |",
        f"| Removed files | {summary['removedCount']} |",
        f"| Unchanged files | {summary['unchangedCount']} |",
        f"| Refetch files | {summary['refetchFileCount']} |",
        f"| Refetch bytes | {summary['refetchBytes']} |",
        f"| Refetch byte ratio | {summary['refetchByteRatio']} |",
        "",
        "## Refetch",
        "",
    ]
    if report["refetch"]:
        for path in report["refetch"]:
            lines.append(f"- `{path}`")
    else:
        lines.append("- No files need refetching.")
    if report["removed"]:
        lines.extend(["", "## Removed", ""])
        for item in report["removed"]:
            lines.append(f"- `{item['path']}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    report = compare_manifests(Path(args.old_files), Path(args.new_files))
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output_json:
        Path(args.output_json).write_text(rendered)
    else:
        print(rendered, end="")
    if args.output_md:
        Path(args.output_md).write_text(render_markdown(report))


if __name__ == "__main__":
    main()
