#!/usr/bin/env -S uv run python
"""Re-extract retained Make/Just commands at pinned revisions without executing them."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import tomllib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

TASK_SOURCES = {"Makefile", "makefile", "GNUmakefile", "justfile", "Justfile"}
MAX_SOURCE_BYTES = 1024 * 1024


def audit_record(path: Path, cli: Path, output: Path) -> dict | None:
    record = tomllib.loads(path.read_text())
    assessments = record.get("x", {}).get("dotrepo", {}).get("field_evidence", {})
    fields = {
        field: evidence.get("source")
        for field, evidence in assessments.items()
        if field in {"repo.build", "repo.test"}
        and (
            evidence.get("source") in TASK_SOURCES
            or (
                field == "repo.test"
                and "go test" in record["repo"].get("test", "")
                and any(
                    token in {"-c", "-list"}
                    or (
                        token.startswith("-c=")
                        and token[3:] not in {"false", "False", "FALSE", "0"}
                    )
                    or token.startswith("-list=")
                    for token in record["repo"]["test"].split()
                )
            )
        )
    }
    if not fields:
        return None
    host, owner, repo = path.parent.parts[-3:]
    identity = f"{host}/{owner}/{repo}"
    sha = record.get("x", {}).get("github", {}).get("head_sha", "")
    result = {"identity": identity, "revision": sha, "sources": [], "fields": []}
    try:
        if host != "github.com" or re.fullmatch(r"[0-9a-f]{40}", sha) is None:
            raise ValueError("audit requires a pinned GitHub revision")
        with tempfile.TemporaryDirectory(prefix="dotrepo-command-audit-") as temporary:
            root = Path(temporary)
            (root / "README.md").write_text("# Command Audit\n\nPinned command-source audit.\n")
            actual_sources = {}
            for source in sorted(set(fields.values())):
                if source not in TASK_SOURCES | {"CONTRIBUTING.md", ".github/CONTRIBUTING.md"}:
                    raise ValueError(f"unsupported source: {source}")
                alternatives = [source]
                if source in {"Makefile", "makefile", "GNUmakefile"}:
                    alternatives += sorted({"Makefile", "makefile", "GNUmakefile"} - {source})
                for actual_source in alternatives:
                    url = f"https://raw.githubusercontent.com/{quote(owner)}/{quote(repo)}/{sha}/{actual_source}"
                    try:
                        with urlopen(
                            Request(url, headers={"User-Agent": "dotrepo-command-audit/1.0"}),
                            timeout=30,
                        ) as response:
                            body = response.read(MAX_SOURCE_BYTES + 1)
                        break
                    except HTTPError as exc:
                        if exc.code != 404 or actual_source == alternatives[-1]:
                            raise
                actual_sources[source] = actual_source
                if len(body) > MAX_SOURCE_BYTES:
                    raise ValueError("source exceeds byte limit")
                captured = output / "sources" / host / owner / repo / actual_source
                captured.parent.mkdir(parents=True, exist_ok=True)
                captured.write_bytes(body)
                local = root / actual_source
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_bytes(body)
                result["sources"].append(
                    {
                        "path": str(captured.relative_to(output)),
                        "url": url,
                        "sha256": hashlib.sha256(body).hexdigest(),
                    }
                )
            subprocess.run(
                [
                    str(cli),
                    "--root",
                    str(root),
                    "import",
                    "--mode",
                    "overlay",
                    "--source",
                    f"https://github.com/{owner}/{repo}",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            imported = tomllib.loads((root / "record.toml").read_text())
            for field, source in fields.items():
                key = field.split(".")[1]
                previous = record["repo"].get(key)
                candidate = imported["repo"].get(key)
                result["fields"].append(
                    {
                        "field": field,
                        "source": source,
                        "inspectedSource": actual_sources[source],
                        "previous": previous,
                        "candidate": candidate,
                        "disposition": "preserve-existing-abstention"
                        if previous is None
                        else "unchanged"
                        if previous == candidate
                        else "withhold"
                        if candidate is None
                        else "replace-wrapper",
                    }
                )
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        result["error"] = str(exc)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-root", type=Path, default=Path("index"))
    parser.add_argument("--cli", type=Path, default=Path("target/debug/dotrepo"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    paths = sorted(args.index_root.glob("repos/*/*/*/record.toml"))
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        results = [
            row
            for row in executor.map(
                lambda path: audit_record(path, args.cli.resolve(), args.output), paths
            )
            if row is not None
        ]
    report = {
        "checkedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "policy": "static-source-preservation; no upstream execution; no task-correctness claim",
        "records": results,
    }
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "records": len(results),
                "fields": sum(len(row["fields"]) for row in results),
                "errors": sum("error" in row for row in results),
            }
        )
    )
    return int(any("error" in row for row in results))


if __name__ == "__main__":
    raise SystemExit(main())
