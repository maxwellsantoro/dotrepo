#!/usr/bin/env -S uv run python
"""Reconstruct published snapshot payloads from frozen Git indexes and export inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
from pathlib import Path

from archive_public_snapshot_r2 import validated_snapshot_files
from sync_cloudflare_public_snapshot import merge_log_documents


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def immutable_commit(repository: Path, commit: str) -> str:
    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError("source and exporter revisions must be full immutable Git commits")
    resolved = subprocess.run(
        ["git", "rev-parse", "--verify", f"{commit}^{{commit}}"],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if resolved != commit:
        raise ValueError("Git source does not resolve to the frozen commit")
    return resolved


def extract_index(repository: Path, commit: str, destination: Path) -> str:
    immutable_commit(repository, commit)
    archive = destination / "index.tar"
    with archive.open("wb") as output:
        subprocess.run(
            ["git", "archive", "--format=tar", commit, "index"],
            cwd=repository,
            stdout=output,
            check=True,
        )
    with tarfile.open(archive) as tree:
        for member in tree.getmembers():
            if (
                not (member.isfile() or member.isdir())
                or not (member.name.startswith("index/") or member.name == "index")
                or any(part in {".", ".."} for part in Path(member.name).parts)
            ):
                raise ValueError("immutable index archive contains an unsupported entry")
        tree.extractall(destination, filter="data")
    return sha256(archive)


def exporter_version(repository: Path, commit: str) -> str:
    manifest = subprocess.run(
        ["git", "show", f"{commit}:Cargo.toml"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return tomllib.loads(manifest)["workspace"]["package"]["version"]


def recover_history(
    log_path: Path,
    source_map_path: Path,
    binary: Path | None,
    output: Path,
    repository: Path,
    *,
    exporter_root: Path | None = None,
) -> dict:
    if output.exists():
        raise ValueError("recovery output already exists; use a fresh output directory")
    log_bytes = log_path.read_bytes()
    plan_bytes = source_map_path.read_bytes()
    plan = json.loads(plan_bytes)
    if hashlib.sha256(log_bytes).hexdigest() != plan.get("publishedLogSha256"):
        raise ValueError("published log bytes do not match the frozen recovery plan")
    published = json.loads(log_bytes)
    log = merge_log_documents(published)
    if published != log or not log["entries"]:
        raise ValueError("published log must be a complete canonical nonempty history")
    selected = {}
    if exporter_root is not None and binary is not None:
        raise ValueError("choose per-entry exporter root or one exporter binary")
    for entry in log["entries"]:
        snapshot = entry["snapshotId"]
        exporter = (
            plan.get("entryExporters", {}).get(snapshot, {})
            if exporter_root is not None
            else plan.get("exporter", {})
        )
        immutable_commit(repository, exporter.get("commit"))
        executable = (
            exporter_root / exporter["commit"] / "target/debug/dotrepo"
            if exporter_root is not None
            else binary
        )
        if executable is None:
            raise ValueError("recovery requires a frozen exporter binary")
        binary_digest = sha256(executable)
        if binary_digest != exporter.get("binarySha256"):
            raise ValueError("exporter binary does not match the frozen recovery plan")
        # The CLI has no --version flag. Version belongs to the pinned Cargo
        # source; the frozen binary hash binds the executable used for recovery.
        if exporter_version(repository, exporter["commit"]) != exporter.get("version"):
            raise ValueError("exporter version does not match the frozen recovery plan")
        selected[snapshot] = (exporter, executable, binary_digest)
    hours = plan.get("staleAfterHours")
    if not isinstance(hours, int) or isinstance(hours, bool) or hours < 1:
        raise ValueError("staleAfterHours must be frozen as a positive integer")
    sources = plan.get("sources", {})
    for entry in log["entries"]:
        immutable_commit(repository, sources.get(entry.get("snapshotDigest")))

    output.parent.mkdir(parents=True, exist_ok=True)
    records = []
    with tempfile.TemporaryDirectory(prefix="dotrepo-history-recovery-", dir=output.parent) as temp:
        temporary = Path(temp)
        recovered = temporary / "public"
        recovered.mkdir()
        for number, entry in enumerate(log["entries"]):
            exporter, executable, binary_digest = selected[entry["snapshotId"]]
            source = sources[entry["snapshotDigest"]]
            workspace = temporary / str(number)
            workspace.mkdir()
            archive_digest = extract_index(repository, source, workspace)
            export = workspace / "export"
            command = [
                str(executable),
                "public",
                "export",
                "--index-root",
                str(workspace / "index"),
                "--out-dir",
                str(export),
                "--generated-at",
                entry["generatedAt"],
                "--stale-after-hours",
                str(hours),
                "--base-path",
                "/",
            ]
            subprocess.run(command, check=True, capture_output=True, text=True)
            metadata = json.loads((export / "v0/meta.json").read_bytes())
            if any(
                metadata.get(field) != entry.get(field)
                for field in ["snapshotId", "snapshotDigest", "generatedAt"]
            ):
                raise ValueError(f"reconstructed snapshot identity mismatch: {entry['snapshotId']}")
            produced_log = json.loads((export / "v0/snapshots/log.json").read_bytes())
            if produced_log.get("entries") != [entry]:
                raise ValueError(
                    f"reconstructed snapshot counts/log mismatch: {entry['snapshotId']}"
                )
            files = validated_snapshot_files(export, entry)
            destination = recovered / "v0/snapshots" / entry["snapshotId"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(export / "v0/snapshots" / entry["snapshotId"], destination)
            records.append(
                {
                    "snapshotId": entry["snapshotId"],
                    "snapshotDigest": entry["snapshotDigest"],
                    "sourceCommit": source,
                    "exporter": exporter,
                    "versionSource": f"{exporter['commit']}:Cargo.toml workspace.package.version",
                    "indexArchiveSha256": archive_digest,
                    "manifestSha256": sha256(destination / "files.json"),
                    "validatedObjects": len(files),
                    "command": command,
                }
            )
        matches = []
        for known in plan.get("knownBodies", []):
            path = known.get("path")
            snapshot = known.get("snapshotId")
            if (
                not isinstance(path, str)
                or not isinstance(snapshot, str)
                or not path.startswith(f"v0/snapshots/{snapshot}/")
                or "\\" in path
                or any(part in {"", ".", ".."} for part in path.split("/"))
            ):
                raise ValueError("retained-body comparison has an unsafe snapshot path")
            actual = sha256(recovered / path)
            if actual != known.get("sha256"):
                raise ValueError(
                    f"reconstructed payload differs from retained published body: {path}"
                )
            matches.append({"path": path, "sha256": actual})
        for _exporter, executable, binary_digest in selected.values():
            if sha256(executable) != binary_digest:
                raise ValueError("exporter binary changed during recovery")
        (recovered / "v0/snapshots/log.json").write_bytes(log_bytes)
        receipt = {
            "schema": "dotrepo-public-history-recovery/v0",
            "kind": "deterministic_reconstruction",
            "publishedLogSha256": hashlib.sha256(log_bytes).hexdigest(),
            "sourceMapSha256": hashlib.sha256(plan_bytes).hexdigest(),
            "exporterMode": "original_per_entry"
            if exporter_root is not None
            else "single_exporter",
            "exporter": plan.get("exporter"),
            "snapshots": records,
            "retainedPublishedBodyMatches": matches,
            "limits": [
                "Identity and reconstructed manifest hashes do not independently prove every historical byte.",
                "Exporter commit is a declared source pin; binary hash binds the executable actually used.",
                "Only retainedPublishedBodyMatches independently corroborate original published payload bytes.",
            ],
        }
        (recovered / "recovery-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        # All entries and independent known bodies must pass before exposing the
        # bootstrap root. Failure leaves the requested output absent.
        recovered.replace(output)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--source-map", required=True, type=Path)
    exporters = parser.add_mutually_exclusive_group(required=True)
    exporters.add_argument("--dotrepo-bin", type=Path)
    exporters.add_argument("--exporter-root", type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    receipt = recover_history(
        args.log.resolve(),
        args.source_map.resolve(),
        args.dotrepo_bin.resolve() if args.dotrepo_bin else None,
        args.out_dir.resolve(),
        args.repository.resolve(),
        exporter_root=args.exporter_root.resolve() if args.exporter_root else None,
    )
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"reconstructed {len(receipt['snapshots'])} published snapshots in {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
