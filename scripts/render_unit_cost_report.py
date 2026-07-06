#!/usr/bin/env -S uv run python
"""Render a versioned unit-cost report from retained autonomous-run telemetry.

Reads the newline-delimited JSON history written by
`scripts/run_autonomous_index_batch.py` (one JSON object per run, appended to
`index/telemetry/autonomous-runs.ndjson`) and reports per-repository unit cost
— network, model calls, tokens, and wall time — broken out by outcome
category:

- ``unchanged``: the refresh scheduler found the repository's head SHA
  unchanged (see `dotrepo-crawler/src/schedule.rs`'s `ScheduleRefreshReport`)
  and skipped it entirely. Recorded under each run's ``unchangedSkips`` list
  with all costs pinned at zero by construction (no fetch, no import, no
  model call was ever attempted).
- ``changed``: the repository was re-crawled (fetched, imported, verified)
  but the resulting record did not advance on the draft -> inferred ->
  imported -> reviewed -> verified -> canonical status ladder relative to
  what was on disk before this run.
- ``improved``: the repository was re-crawled and its record status
  advanced on that ladder — a real completeness/quality gain, not just
  avoided or repeated work.

CPU time and peak memory are process-level (see ROADMAP Milestone 1 item 4)
and are not currently collected anywhere in the pipeline, so those columns
are reported as ``null``/"not collected" rather than fabricated; this is a
documented gap, not an oversight.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

SCHEMA = "dotrepo/unit-cost-report/v0.1"
CATEGORIES = ("unchanged", "changed", "improved")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs",
        default="index/telemetry/autonomous-runs.ndjson",
        help="Retained autonomous-run telemetry as newline-delimited JSON",
    )
    parser.add_argument("--output-json", help="Optional path for machine-readable JSON")
    parser.add_argument("--output-md", help="Optional path for markdown output")
    return parser.parse_args()


def load_runs(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    runs = []
    for line_number, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            runs.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"failed to parse {path}:{line_number}: {exc}") from exc
    return runs


def number_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def wall_time_ms(entry: dict) -> float | None:
    """Prefer dotrepo-crawler's in-process timer; fall back to the
    orchestrator's subprocess wall clock, which is the only signal available
    for failed crawls (the crawler never printed JSON) and for older
    telemetry recorded before in-process timing existed."""
    for key in ("wallTimeMs", "totalWallTimeMs", "commandWallTimeMs"):
        value = number_or_none(entry.get(key))
        if value is not None:
            return value
    return None


def collect_entries(runs: list[dict]) -> dict[str, list[dict]]:
    by_category: dict[str, list[dict]] = {category: [] for category in CATEGORIES}
    for run in runs:
        for entry in run.get("unchangedSkips") or []:
            by_category.setdefault("unchanged", []).append(entry)
        for entry in run.get("crawls") or []:
            category = str(entry.get("category") or "changed")
            by_category.setdefault(category, []).append(entry)
    return by_category


def mean_or_none(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 3) if values else None


def median_or_none(values: list[float]) -> float | None:
    return round(statistics.median(values), 3) if values else None


def summarize_category(category: str, entries: list[dict]) -> dict[str, Any]:
    wall_times = [
        value for value in (wall_time_ms(entry) for entry in entries) if value is not None
    ]
    network_bytes = [
        value
        for value in (number_or_none(entry.get("networkBytes")) for entry in entries)
        if value is not None
    ]
    network_requests = [
        value
        for value in (number_or_none(entry.get("networkRequests")) for entry in entries)
        if value is not None
    ]
    tokens = [
        value
        for value in (number_or_none(entry.get("tokensUsed")) for entry in entries)
        if value is not None
    ]
    model_calls = [
        value
        for value in (number_or_none(entry.get("adjudicationCalls")) for entry in entries)
        if value is not None
    ]
    # CPU time / peak memory are process-level (ROADMAP Milestone 1 item 4)
    # and are not collected by any layer of the pipeline today; report the
    # gap explicitly rather than defaulting to zero, which would look like a
    # real (and misleadingly cheap) measurement.
    return {
        "count": len(entries),
        "wallTimeMs": {
            "mean": mean_or_none(wall_times),
            "median": median_or_none(wall_times),
            "sampled": len(wall_times),
        },
        "networkBytes": {"mean": mean_or_none(network_bytes), "sampled": len(network_bytes)},
        "networkRequests": {
            "mean": mean_or_none(network_requests),
            "sampled": len(network_requests),
        },
        "tokensUsed": {"mean": mean_or_none(tokens), "sampled": len(tokens)},
        "modelCalls": {"mean": mean_or_none(model_calls), "sampled": len(model_calls)},
        "cpuTimeMs": {"mean": None, "sampled": 0, "note": "not collected"},
        "peakMemoryBytes": {"mean": None, "sampled": 0, "note": "not collected"},
    }


def build_report(runs: list[dict]) -> dict[str, Any]:
    by_category = collect_entries(runs)
    categories = {
        category: summarize_category(category, entries) for category, entries in by_category.items()
    }
    total_entries = sum(summary["count"] for summary in categories.values())
    return {
        "schema": SCHEMA,
        "runCount": len(runs),
        "totalEntries": total_entries,
        "categories": {
            category: categories[category] for category in CATEGORIES if category in categories
        },
    }


def format_number(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Autonomous Crawl Unit-Cost Report",
        "",
        f"- schema: `{report['schema']}`",
        f"- runs inspected: {report['runCount']}",
        f"- repository outcomes inspected: {report['totalEntries']}",
        "",
        "| category | count | mean wall (ms) | median wall (ms) | mean net bytes | mean net requests | mean tokens | mean model calls |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for category in CATEGORIES:
        summary = report["categories"].get(category)
        if summary is None:
            continue
        lines.append(
            "| {category} | {count} | {wall_mean} | {wall_median} | {net_bytes} | {net_requests} | {tokens} | {model_calls} |".format(
                category=category,
                count=summary["count"],
                wall_mean=format_number(summary["wallTimeMs"]["mean"]),
                wall_median=format_number(summary["wallTimeMs"]["median"]),
                net_bytes=format_number(summary["networkBytes"]["mean"], digits=0),
                net_requests=format_number(summary["networkRequests"]["mean"], digits=1),
                tokens=format_number(summary["tokensUsed"]["mean"], digits=0),
                model_calls=format_number(summary["modelCalls"]["mean"], digits=2),
            )
        )
    lines.append("")
    lines.append(
        "CPU time and peak memory are process-level and are not currently collected anywhere "
        "in the pipeline (documented gap; see ROADMAP Milestone 1 item 4), so those columns are "
        "omitted from this table rather than reported as zero."
    )
    lines.append("")
    return "\n".join(lines)


def write_text(path: str | None, text: str) -> None:
    if not path:
        return
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text)


def write_json(path: str | None, payload: dict[str, Any]) -> None:
    if not path:
        return
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main() -> int:
    args = parse_args()
    runs = load_runs(Path(args.runs))
    report = build_report(runs)
    markdown = render_markdown(report)
    write_json(args.output_json, report)
    write_text(args.output_md, markdown)
    if not args.output_md:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
