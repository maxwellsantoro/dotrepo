#!/usr/bin/env -S uv run python
"""Verify captured source/notice bytes; report separate redistribution holds."""

import argparse
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "benchmarks/third-party-licenses"


def check_capture_bytes(root, captures, quarantine):
    captured = {f["path"]: f for c in captures for f in c["files"]}
    removed = {f["path"]: f for f in quarantine.get("files", [])}
    errors = []
    if len(removed) != len(quarantine.get("files", [])):
        errors.append("duplicate-quarantine-path")
    for path, record in removed.items():
        if record != captured.get(path):
            errors.append("quarantine-record-mismatch:" + path)
    for path, record in captured.items():
        source = root / path
        if path in removed:
            if source.exists() or source.is_symlink():
                errors.append("quarantined-source-reintroduced:" + path)
        elif (
            not source.is_file()
            or hashlib.sha256(source.read_bytes()).hexdigest() != record["sha256"]
        ):
            errors.append(path)
    return errors, len(captured) - len(removed), len(removed)


def verify_archive(path, quarantine):
    """Verify the external preservation archive without extracting any files."""
    if (
        path.stat().st_size != quarantine["archiveBytes"]
        or hashlib.sha256(path.read_bytes()).hexdigest() != quarantine["archiveSha256"]
    ):
        raise ValueError("quarantine archive identity mismatch")
    records = {f["path"]: f for f in quarantine["files"]}
    with tarfile.open(path, "r:gz") as archive:
        if set(archive.getnames()) != set(records):
            raise ValueError("quarantine archive inventory mismatch")
        for name, record in records.items():
            member = archive.getmember(name)
            if not member.isfile() or member.size != record["bytes"]:
                raise ValueError("quarantine archive member mismatch:" + name)
            body = archive.extractfile(member).read(record["bytes"] + 1)
            if hashlib.sha256(body).hexdigest() != record["sha256"]:
                raise ValueError("quarantine archive body mismatch:" + name)


def check(root=ROOT):
    audit = root / "benchmarks/third-party-licenses"
    upstream = json.loads((audit / "inventory.json").read_text())
    packages = json.loads((audit / "npm/inventory.json").read_text())
    captures = json.loads((audit / "captures.json").read_text())["captures"]
    errors = []
    licenses = 0
    for item in upstream:
        for notice in item["licenseFiles"]:
            path = audit / item["repository"] / item["revision"] / notice["path"]
            body = path.read_bytes()
            blob = hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()
            if blob != notice["gitBlobSha"] or hashlib.sha256(body).hexdigest() != notice["sha256"]:
                errors.append(str(path.relative_to(root)))
            licenses += 1
    for package in packages:
        for notice in package["licenseFiles"]:
            path = root / notice["path"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != notice["sha256"]:
                errors.append(str(path.relative_to(root)))
            licenses += 1
    for notice in json.loads((audit / "standard-texts.json").read_text()):
        path = root / notice["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != notice["sha256"]:
            errors.append(notice["path"])
        licenses += 1
    for item in upstream:
        declaration = item.get("declaredLicense")
        if (
            declaration
            and hashlib.sha256((root / declaration["sourcePath"]).read_bytes()).hexdigest()
            != declaration["sourceSha256"]
        ):
            errors.append(declaration["sourcePath"])
    quarantine = json.loads((audit / "quarantine.json").read_text())
    capture_errors, present, removed = check_capture_bytes(root, captures, quarantine)
    errors.extend(capture_errors)
    dispositions = json.loads((audit / "dispositions.json").read_text())
    return {
        "sourceCaptureRoots": len(captures),
        "sourceFiles": sum(len(capture["files"]) for capture in captures),
        "sourceFilesPresent": present,
        "sourceFilesQuarantined": removed,
        "licenseNoticeFiles": licenses,
        "byteErrors": errors,
        "redistributionHolds": dispositions["holds"],
        "historicalRedistributionHolds": dispositions["quarantinedHolds"],
        "archiveVerification": "not-requested; pass --archive for the separate private preservation check",
        "meaning": "Current-tree byte/provenance check only. Quarantined sources must stay absent; their original inventory and Git history remain. Notices or source absence do not establish legal clearance for historical/private copies.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-clearance", action="store_true")
    parser.add_argument(
        "--archive", type=Path, help="Verify the external private preservation archive"
    )
    args = parser.parse_args()
    report = check()
    if args.archive:
        try:
            verify_archive(args.archive, json.loads((AUDIT / "quarantine.json").read_text()))
            report["archiveVerification"] = "verified"
        except (OSError, ValueError, tarfile.TarError) as error:
            report["byteErrors"].append(str(error))
    print(json.dumps(report, indent=2))
    if report["byteErrors"]:
        return 1
    return 2 if args.require_clearance and report["redistributionHolds"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
