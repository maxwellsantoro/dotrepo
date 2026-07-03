#!/usr/bin/env -S uv run python

import argparse
import json
import shutil
import tempfile
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage a reviewed dotrepo public export for the Cloudflare Worker."
    )
    parser.add_argument("--input", required=True, help="Source public export directory")
    parser.add_argument("--output", required=True, help="Destination Worker snapshot directory")
    parser.add_argument(
        "--archive-dir",
        help="Optional local archive mirror root for immutable v0/snapshots payloads.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def snapshot_id(root: Path) -> str | None:
    value = load_json(root / "v0/meta.json").get("snapshotId")
    return value if isinstance(value, str) and value else None


def copy_snapshot(root: Path, snapshot: str, destination: Path) -> None:
    source = root / "v0/snapshots" / snapshot
    if not source.is_dir():
        return
    target = destination / "v0/snapshots" / snapshot
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)


def merge_snapshot_logs(input_dir: Path, previous_dir: Path | None, output_dir: Path) -> None:
    merged: dict[str, dict] = {}
    for root in [previous_dir, input_dir]:
        if root is None:
            continue
        log = load_json(root / "v0/snapshots/log.json")
        for entry in log.get("entries", []):
            digest = entry.get("snapshotDigest")
            if isinstance(digest, str) and digest:
                merged[digest] = entry
    entries = sorted(
        merged.values(),
        key=lambda entry: (entry.get("generatedAt", ""), entry.get("snapshotDigest", "")),
    )
    if not entries:
        return
    output_log = {
        "apiVersion": "v0",
        "snapshotCount": len(entries),
        "entries": entries,
    }
    path = output_dir / "v0/snapshots/log.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output_log, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    write_stats(output_dir, output_log)


def write_stats(output_dir: Path, log: dict) -> None:
    entries = log.get("entries", [])
    deltas = []
    for previous, current in zip(entries, entries[1:]):
        deltas.append(
            {
                "fromSnapshotId": previous.get("snapshotId"),
                "toSnapshotId": current.get("snapshotId"),
                "repositoryCountDelta": current.get("repositoryCount", 0)
                - previous.get("repositoryCount", 0),
                "fileCountDelta": current.get("fileCount", 0) - previous.get("fileCount", 0),
            }
        )
    stats = {
        "apiVersion": "v0",
        "latest": entries[-1] if entries else None,
        "snapshotCount": len(entries),
        "history": entries,
        "deltas": deltas,
    }
    path = output_dir / "v0/stats.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stats, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def mirror_archive(output_dir: Path, archive_dir: Path) -> None:
    snapshots = output_dir / "v0/snapshots"
    if not snapshots.exists():
        return
    target = archive_dir / "v0/snapshots"
    target.mkdir(parents=True, exist_ok=True)
    for child in snapshots.iterdir():
        destination = target / child.name
        if child.is_dir():
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(child, destination)
        elif child.is_file():
            shutil.copy2(child, destination)


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()

    if not input_dir.is_dir():
        raise SystemExit(f"input public export directory does not exist: {input_dir}")

    previous_snapshot = snapshot_id(output_dir)
    if output_dir.exists():
        with tempfile.TemporaryDirectory(prefix="dotrepo-public-previous-") as previous:
            previous_dir = Path(previous)
            if previous_snapshot:
                copy_snapshot(output_dir, previous_snapshot, previous_dir)
            previous_log = output_dir / "v0/snapshots/log.json"
            if previous_log.exists():
                target_log = previous_dir / "v0/snapshots/log.json"
                target_log.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(previous_log, target_log)
            shutil.rmtree(output_dir)
            output_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(input_dir, output_dir)
            if previous_snapshot and previous_snapshot != snapshot_id(input_dir):
                copy_snapshot(previous_dir, previous_snapshot, output_dir)
            merge_snapshot_logs(input_dir, previous_dir, output_dir)
    else:
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(input_dir, output_dir)
        merge_snapshot_logs(input_dir, None, output_dir)
    if args.archive_dir:
        mirror_archive(output_dir, Path(args.archive_dir).resolve())
    print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
