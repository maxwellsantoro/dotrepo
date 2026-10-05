#!/usr/bin/env -S uv run python
"""Reproduce installed command checks using the immutable v1.0.2 source fixtures.

Supply the downloaded or cargo-installed CLI via --bin and a v1.0.2 checkout via
--source. Version identity comes from the package/bundle receipt; stable CLI has
no --version option. This performs controlled imports, not upstream execution.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path
from datetime import datetime, timezone

p = argparse.ArgumentParser()
p.add_argument("--bin", type=Path, required=True)
p.add_argument("--source", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
binary = a.bin.resolve()
root = a.source.resolve()
expected = tomllib.loads((root / "Cargo.toml").read_text())["workspace"]["package"]["version"]
assert expected == "1.0.2", "use the immutable v1.0.2 source fixture pack"
version = f"dotrepo {expected}"
manifest = binary.parent.parent / "README.txt"
if manifest.exists():
    assert expected in manifest.read_text()
subprocess.run([str(binary), "--help"], check=True, capture_output=True)
receipts = []
fixtures = root / "crates/dotrepo-core/tests/fixtures/import"
names = {
    "make-diagnostic",
    "make-comment",
    "make-uppercase",
    "make-prerequisite",
    "make-expressions",
    "just-required-argument",
    "just-wrapper",
    "go-compile-only",
    "go-compile-then-runner",
}
rows = [
    row
    for row in json.loads((fixtures / "expectations.json").read_text())
    if row["fixture"] in names
]
assert {row["fixture"] for row in rows} == names
for row in rows:
    with tempfile.TemporaryDirectory() as d:
        local = Path(d)
        shutil.copytree(fixtures / row["fixture"], local, dirs_exist_ok=True)
        result = subprocess.run(
            [
                str(binary),
                "--root",
                str(local),
                "import",
                "--mode",
                "overlay",
                "--source",
                "https://github.com/example/command-semantics",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        m = tomllib.loads((local / "record.toml").read_text())
        assert m["repo"].get("build") == row["repo_build"]
        assert m["repo"].get("test") == row["repo_test"]
        receipts.append(
            {
                "fixture": row["fixture"],
                "build": m["repo"].get("build"),
                "test": m["repo"].get("test"),
                "result": "passed",
            }
        )
with tempfile.TemporaryDirectory() as d:
    local = Path(d)
    index = local / "index"
    item = index / "repos/github.com/example/sentinel"
    item.mkdir(parents=True)
    (item / "record.toml").write_text("sentinel record")
    (item / "evidence.md").write_text("sentinel evidence")
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in item.iterdir()}
    result = subprocess.run(
        [str(binary), "promotion-report", "--index-root", str(index), "--apply"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in item.iterdir()}
    receipts.append(
        {"fixture": "promotion-no-write", "result": "passed", "diagnostic": result.stderr}
    )
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(
    json.dumps(
        {
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "binary": str(binary),
            "binarySha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            "version": version,
            "versionSource": "Source package version; correlate binary hash with the install receipt",
            "results": receipts,
        },
        indent=2,
    )
    + "\n"
)
print("Ten installed CLI safety controls passed; correlate version with the install receipt.")
