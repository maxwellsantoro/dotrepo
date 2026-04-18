#!/usr/bin/env python3

import argparse
import json
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a GitHub-friendly markdown summary from a refresh plan report."
    )
    parser.add_argument("--input", required=True, help="Path to refresh-plan.json")
    parser.add_argument(
        "--batches",
        help="Optional path to refresh-batches.json for batch planning context",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=8,
        help="Maximum scheduled or skipped repositories to list per section (default: 8)",
    )
    return parser.parse_args()


def load_report(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"missing refresh plan report: {path}")
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise SystemExit(f"refresh plan report is malformed: {path}")
    return data


def load_optional_json(path: str | None) -> dict | None:
    if not path:
        return None
    target = Path(path)
    if not target.is_file():
        return None
    data = json.loads(target.read_text())
    if not isinstance(data, dict):
        return None
    return data


def identity(item: dict) -> str:
    repository = item.get("repository", {})
    host = repository.get("host", "?")
    owner = repository.get("owner", "?")
    repo = repository.get("repo", "?")
    return f"{host}/{owner}/{repo}"


def render_item_list(title: str, items: list[dict], max_items: int, *, field: str) -> str:
    if not items:
        return ""
    lines = [f"## {title}", ""]
    for item in items[:max_items]:
        value = item.get(field, "unknown")
        lines.append(f"- `{identity(item)}`: {value}")
    remaining = len(items) - min(len(items), max_items)
    if remaining > 0:
        lines.append(f"- plus {remaining} more")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    report = load_report(Path(args.input))
    schedule = report.get("schedule", {})
    scheduled = schedule.get("scheduled", [])
    skipped = schedule.get("skipped", [])
    reason_counts = Counter(
        item.get("reason", "unknown") for item in scheduled if isinstance(item, dict)
    )

    lines = [
        "# Index Refresh Review",
        "",
        f"- state path: `{report.get('statePath', 'unknown')}`",
        f"- tracked repositories: {report.get('trackedRepositories', 0)}",
        f"- fetched candidates: {report.get('candidateCount', 0)}",
        f"- scheduled refreshes: {len(scheduled)}",
        f"- skipped repositories: {len(skipped)}",
    ]

    if reason_counts:
        rendered = ", ".join(
            f"{reason}={count}" for reason, count in sorted(reason_counts.items())
        )
        lines.append(f"- scheduled reasons: {rendered}")
    lines.append("")

    batch_plan = load_optional_json(args.batches)
    if batch_plan is not None:
        batch_summary = batch_plan.get("summary", {})
        batches = batch_plan.get("batches", [])
        lines.extend(
            [
                f"- refresh batches: {batch_summary.get('batchCount', 0)} at {batch_summary.get('batchSize', 'unknown')} repositories max",
                "",
            ]
        )
        if isinstance(batches, list) and batches:
            lines.extend(
                [
                    "## Batch Preview",
                    "",
                ]
            )
            for batch in batches[:3]:
                lines.append(
                    f"- `{batch.get('id', 'refresh-batch')}`: {batch.get('reason', 'unknown')}, {batch.get('repositoryCount', 0)} repositories"
                )
            if len(batches) > 3:
                lines.append(f"- plus {len(batches) - 3} more batches")
            lines.append("")

    for section in (
        render_item_list("Scheduled", scheduled, args.max_items, field="reason"),
        render_item_list("Skipped", skipped, args.max_items, field="reason"),
    ):
        if section:
            lines.append(section)

    print("\n".join(lines).rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
