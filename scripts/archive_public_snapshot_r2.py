#!/usr/bin/env -S uv run python
"""Upload immutable public snapshot payloads to a Cloudflare R2 archive bucket."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

from sync_cloudflare_public_snapshot import load_json, merge_log_documents


IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
MUTABLE_CACHE_CONTROL = "no-cache"


def validated_snapshot_files(public_root: Path, entry: dict) -> list[Path]:
    """Require every public leaf before advertising a snapshot in the archive log."""
    snapshot = entry.get("snapshotId")
    if not isinstance(snapshot, str) or re.fullmatch(r"[A-Za-z0-9_-]+", snapshot) is None:
        raise ValueError("snapshot log has an invalid snapshotId")
    root = f"v0/snapshots/{snapshot}"
    manifest_path = public_root / root / "files.json"
    if not manifest_path.is_file():
        raise ValueError(
            f"snapshot {snapshot} is not archived and has no local manifest; backfill it"
        )
    if manifest_path.is_symlink() or not manifest_path.resolve().is_relative_to(public_root):
        raise ValueError(f"snapshot {snapshot} manifest is not a contained file")
    manifest = load_json(manifest_path)
    if any(
        manifest.get("freshness", {}).get(field) != entry.get(field)
        for field in ["snapshotDigest", "generatedAt"]
    ):
        raise ValueError(f"snapshot {snapshot} manifest does not match its published log entry")
    leaves = manifest.get("files")
    if (
        not isinstance(leaves, list)
        or manifest.get("fileCount") != len(leaves)
        or entry.get("fileCount") != len(leaves)
    ):
        raise ValueError(f"snapshot {snapshot} manifest has an inconsistent file count")
    files = []
    seen = set()
    for leaf in leaves:
        if not isinstance(leaf, dict):
            raise ValueError("snapshot file manifest entries must be objects")
        path = leaf.get("path")
        if (
            not isinstance(path, str)
            or not path.startswith(f"{root}/")
            or any(part in {"", ".", ".."} for part in path.split("/"))
            or "\\" in path
            or path in seen
        ):
            raise ValueError(
                f"snapshot {snapshot} manifest has an unsafe or duplicate path: {path}"
            )
        seen.add(path)
        if (
            not isinstance(leaf.get("bytes"), int)
            or isinstance(leaf["bytes"], bool)
            or leaf["bytes"] < 0
            or not isinstance(leaf.get("sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", leaf["sha256"]) is None
        ):
            raise ValueError(f"snapshot {snapshot} manifest has invalid validators: {path}")
        local = public_root / path
        # Restoration intentionally omits private runtime inputs. They are not
        # part of the publicly retrievable archive guarantee.
        private = PurePosixPath(path).relative_to(root).parts[0] == "query-input"
        if private and not local.exists():
            continue
        if (
            not local.is_file()
            or local.is_symlink()
            or not local.resolve().is_relative_to(public_root)
        ):
            raise ValueError(f"snapshot {snapshot} is missing a contained payload: {path}")
        body = local.read_bytes()
        if len(body) != leaf["bytes"] or hashlib.sha256(body).hexdigest() != leaf["sha256"]:
            raise ValueError(f"snapshot {snapshot} payload fails manifest validation: {path}")
        files.append(local)
    # Manifest itself is uploaded only after all its leaves validate.
    return [*files, manifest_path]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--public-root",
        required=True,
        help="Reviewed exported public tree containing v0/snapshots/",
    )
    parser.add_argument(
        "--bucket",
        required=True,
        help="R2 bucket name that stores archived public snapshots",
    )
    parser.add_argument(
        "--wrangler-cwd",
        default="cloudflare/hosted-query",
        help="Directory from which to run npx wrangler (default: cloudflare/hosted-query)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the upload plan without invoking Wrangler",
    )
    parser.add_argument(
        "--require-complete-history",
        action="store_true",
        help="Fail if the reviewed local log omits an existing archive entry",
    )
    parser.add_argument(
        "--upload-concurrency", type=int, default=8, help="Bounded bulk upload workers (1-20)"
    )
    return parser.parse_args()


def snapshot_files(public_root: Path) -> list[Path]:
    snapshot_root = public_root / "v0" / "snapshots"
    if not snapshot_root.is_dir():
        raise SystemExit(f"snapshot root does not exist: {snapshot_root}")
    files = sorted(
        path
        for path in snapshot_root.rglob("*")
        if path.is_file() and "query-input" not in path.relative_to(snapshot_root).parts
    )
    if not files:
        raise SystemExit(f"snapshot root contains no files: {snapshot_root}")
    return files


def content_type(path: Path) -> str:
    if path.suffix == ".json":
        return "application/json; charset=utf-8"
    if path.suffix in {".html", ".htm"}:
        return "text/html; charset=utf-8"
    if path.suffix == ".txt":
        return "text/plain; charset=utf-8"
    return "application/octet-stream"


def cache_control(relative_path: str) -> str:
    return (
        MUTABLE_CACHE_CONTROL
        if relative_path == "v0/snapshots/log.json"
        else IMMUTABLE_CACHE_CONTROL
    )


def upload_command(bucket: str, public_root: Path, path: Path) -> list[str]:
    relative_path = path.relative_to(public_root).as_posix()
    return [
        "npx",
        "wrangler",
        "r2",
        "object",
        "put",
        f"{bucket}/{relative_path}",
        "--remote",
        "--file",
        str(path),
        "--content-type",
        content_type(path),
        "--cache-control",
        cache_control(relative_path),
    ]


def read_archive_log(bucket: str, wrangler_cwd: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="dotrepo-archive-log-") as temporary:
        path = Path(temporary) / "log.json"
        command = [
            "npx",
            "wrangler",
            "r2",
            "object",
            "get",
            f"{bucket}/v0/snapshots/log.json",
            "--remote",
            "--file",
            str(path),
        ]
        result = subprocess.run(command, cwd=wrangler_cwd, capture_output=True, text=True)
        if result.returncode != 0:
            # Wrangler distinguishes a missing object from authentication,
            # bucket and transport failures. Only an empty archive is optional.
            if "The specified key does not exist." in result.stderr:
                return {}
            raise RuntimeError(f"failed to read archived snapshot log: {result.stderr.strip()}")
        log = load_json(path)
        merge_log_documents(log)
        return log


def archive_snapshots(
    public_root: Path,
    bucket: str,
    wrangler_cwd: Path,
    *,
    require_complete_history: bool = False,
    upload_concurrency: int = 8,
) -> int:
    if not 1 <= upload_concurrency <= 20:
        raise ValueError("upload concurrency must be between 1 and 20")
    local_log = load_json(public_root / "v0/snapshots/log.json")
    if not local_log.get("entries"):
        raise ValueError("public snapshot log is missing or empty")
    archived_log = read_archive_log(bucket, wrangler_cwd)
    merged_log = merge_log_documents(archived_log, local_log)
    if require_complete_history and merged_log != merge_log_documents(local_log):
        raise ValueError("reviewed snapshot log omits archive history; restore it before export")

    # Existing archive entries were committed only after payload uploads. Do not
    # rewrite immutable objects on every deploy. New entries must all validate
    # before any upload, including history that is no longer at the static edge.
    archived_ids = {entry["snapshotId"] for entry in archived_log.get("entries", [])}
    payloads = [
        path
        for entry in merged_log["entries"]
        if entry["snapshotId"] not in archived_ids
        for path in validated_snapshot_files(public_root, entry)
        if "query-input" not in path.relative_to(public_root).parts
    ]
    with tempfile.TemporaryDirectory(prefix="dotrepo-archive-merged-") as temporary:
        merged_root = Path(temporary)
        # Wrangler is lockfile-pinned. Its bulk implementation has bounded
        # concurrency and API rate limiting; one process avoids thousands of
        # separate Node startup/authentication cycles. Any failure stops before
        # the public log is committed. Private runtime inputs are never uploaded.
        groups: dict[str, list[dict]] = {}
        for path in payloads:
            groups.setdefault(content_type(path), []).append(
                {"key": path.relative_to(public_root).as_posix(), "file": str(path)}
            )
        for number, (mime, entries) in enumerate(groups.items()):
            batch = merged_root / f"upload-{number}.json"
            batch.write_text(json.dumps(entries), encoding="utf-8")
            subprocess.run(
                [
                    "npx",
                    "wrangler",
                    "r2",
                    "bulk",
                    "put",
                    bucket,
                    "--filename",
                    str(batch),
                    "--remote",
                    "--force",
                    "--concurrency",
                    str(upload_concurrency),
                    "--content-type",
                    mime,
                    "--cache-control",
                    IMMUTABLE_CACHE_CONTROL,
                ],
                cwd=wrangler_cwd,
                check=True,
            )
        path = merged_root / "v0/snapshots/log.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(merged_log, indent=2) + "\n", encoding="utf-8")
        subprocess.run(upload_command(bucket, merged_root, path), cwd=wrangler_cwd, check=True)
    return len(payloads) + 1


def main() -> int:
    args = parse_args()
    public_root = Path(args.public_root).resolve()
    wrangler_cwd = Path(args.wrangler_cwd).resolve()

    if not public_root.is_dir():
        raise SystemExit(f"public root does not exist: {public_root}")
    if not wrangler_cwd.is_dir():
        raise SystemExit(f"wrangler cwd does not exist: {wrangler_cwd}")

    if args.dry_run:
        files = snapshot_files(public_root)
        for path in files:
            print(shlex.join(upload_command(args.bucket, public_root, path)))
        print(
            "Real uploads skip existing archive entries, validate every new public payload, "
            "use bounded bulk batches, and commit the merged log last."
        )
        return 0
    count = archive_snapshots(
        public_root,
        args.bucket,
        wrangler_cwd,
        require_complete_history=args.require_complete_history,
        upload_concurrency=args.upload_concurrency,
    )
    print(f"archived {count} snapshot object(s) to R2 bucket {args.bucket}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
