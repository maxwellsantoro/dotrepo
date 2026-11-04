#!/usr/bin/env -S uv run python
"""Verify captured source/notice bytes; report separate redistribution holds."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "benchmarks/third-party-licenses"


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
    for capture in captures:
        for source in capture["files"]:
            path = root / source["path"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
                errors.append(source["path"])
    holds = json.loads((audit / "dispositions.json").read_text())["holds"]
    return {
        "sourceCaptureRoots": len(captures),
        "sourceFiles": sum(len(capture["files"]) for capture in captures),
        "licenseNoticeFiles": licenses,
        "byteErrors": errors,
        "redistributionHolds": holds,
        "meaning": "Byte/provenance check only. License texts and notices do not establish legal clearance; original captures remain unchanged.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-clearance", action="store_true")
    args = parser.parse_args()
    report = check()
    print(json.dumps(report, indent=2))
    if report["byteErrors"]:
        return 1
    return 2 if args.require_clearance and report["redistributionHolds"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
