#!/usr/bin/env -S uv run python
"""Aggregate hosted lookup-miss telemetry lines into a demand-signal report.

The Cloudflare hosted-query Worker emits one structured log line per
repository-not-found response:

    DOTREPO_LOOKUP_MISS {"host":"...","owner":"...","repo":"...","route":"...","ts":"..."}

Operators can export Worker logs (Logpush, `wrangler tail`, dashboard) and
pipe matching lines into this script to build the lookup-miss demand list that
Milestone 4 cohort selection depends on.

The script also accepts a pre-parsed newline-delimited JSON file of miss
objects (one JSON object per line, without the log prefix).
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "dotrepo/lookup-miss-report/v0.1"
PREFIX = "DOTREPO_LOOKUP_MISS"
LINE_RE = re.compile(rf"{re.escape(PREFIX)}\s+(\{{.*\}})\s*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        help="Log file or NDJSON file to read; may be repeated. Reads stdin when omitted.",
    )
    parser.add_argument("--output-json")
    parser.add_argument("--output-md")
    parser.add_argument("--top", type=int, default=50, help="Top-N misses to list (default 50)")
    return parser.parse_args()


def parse_line(line: str) -> dict[str, Any] | None:
    stripped = line.strip()
    if not stripped:
        return None
    match = LINE_RE.search(stripped)
    payload = match.group(1) if match else stripped
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    host = str(data.get("host") or "").strip()
    owner = str(data.get("owner") or "").strip()
    repo = str(data.get("repo") or "").strip()
    if not host or not owner or not repo:
        return None
    return {
        "host": host,
        "owner": owner,
        "repo": repo,
        "identity": f"{host}/{owner}/{repo}",
        "route": data.get("route"),
        "ts": data.get("ts"),
        "source": data.get("source") or "log",
    }


def load_misses(paths: list[str]) -> list[dict[str, Any]]:
    misses: list[dict[str, Any]] = []
    if not paths:
        import sys

        for line in sys.stdin:
            parsed = parse_line(line)
            if parsed is not None:
                misses.append(parsed)
        return misses

    for path_text in paths:
        path = Path(path_text)
        text = path.read_text()
        for line in text.splitlines():
            parsed = parse_line(line)
            if parsed is not None:
                misses.append(parsed)
    return misses


def build_report(misses: list[dict[str, Any]], *, top: int) -> dict[str, Any]:
    identity_counts: Counter[str] = Counter()
    host_counts: Counter[str] = Counter()
    route_counts: Counter[str] = Counter()
    for miss in misses:
        identity_counts[miss["identity"]] += 1
        host_counts[miss["host"]] += 1
        route_counts[str(miss.get("route") or "unknown")] += 1

    top_misses = [
        {"identity": identity, "count": count}
        for identity, count in identity_counts.most_common(top)
    ]
    return {
        "schema": SCHEMA,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "missCount": len(misses),
        "uniqueIdentities": len(identity_counts),
        "byHost": dict(host_counts.most_common()),
        "byRoute": dict(route_counts.most_common()),
        "topMisses": top_misses,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Lookup miss demand report",
        "",
        f"- schema: `{report['schema']}`",
        f"- generated at: `{report['generatedAt']}`",
        f"- miss events: {report['missCount']}",
        f"- unique identities: {report['uniqueIdentities']}",
        "",
        "## Top misses",
        "",
        "| identity | count |",
        "| --- | ---: |",
    ]
    for item in report["topMisses"]:
        lines.append(f"| `{item['identity']}` | {item['count']} |")
    if not report["topMisses"]:
        lines.append("| _(none)_ | 0 |")
    lines.extend(
        [
            "",
            "Use repeated misses as Milestone 4 cohort candidates after ecosystem-gap "
            "balancing. Empty reports mean either perfect coverage or no exported Worker "
            "logs yet — confirm `DOTREPO_LOOKUP_MISS` lines appear in `wrangler tail`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    misses = load_misses(args.input)
    report = build_report(misses, top=args.top)
    markdown = render_markdown(report)
    if args.output_json:
        path = Path(args.output_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.output_md:
        path = Path(args.output_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown)
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
