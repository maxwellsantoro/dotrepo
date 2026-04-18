#!/usr/bin/env python3

import argparse
import json
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a GitHub-friendly markdown summary from a seed review report."
    )
    parser.add_argument("--input", required=True, help="Path to seed-report.json")
    parser.add_argument(
        "--batches",
        help="Optional path to seed-batches.json for batch planning context",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=5,
        help="Maximum repositories to list per priority bucket (default: 5)",
    )
    return parser.parse_args()


def load_report(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"missing seed report: {path}")
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise SystemExit(f"seed report is malformed: {path}")
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


def format_priority_section(title: str, items: list[dict], max_items: int) -> str:
    if not items:
        return ""
    lines = [f"## {title}", ""]
    for item in items[:max_items]:
        reasons = item.get("reasons") or []
        detail = reasons[0] if reasons else "needs review"
        lines.append(f"- `{identity(item)}`: {detail}")
    remaining = len(items) - min(len(items), max_items)
    if remaining > 0:
        lines.append(f"- plus {remaining} more")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    report = load_report(Path(args.input))
    discovery = report.get("discovery", {})
    review = report.get("review", {})
    summary = review.get("summary", {})
    results = report.get("results", [])
    items = review.get("items", [])
    statuses = Counter(item.get("status", "unknown") for item in results if isinstance(item, dict))

    high = [item for item in items if item.get("priority") == "high"]
    medium = [item for item in items if item.get("priority") == "medium"]
    low = [item for item in items if item.get("priority") == "low"]

    lines = [
        "# Index Seed Review",
        "",
        f"- mode: {'dry-run' if report.get('dryRun') else 'writeback'}",
        f"- requested limit: {discovery.get('requestedLimit', 'unknown')}",
        f"- discovered candidates: {len(discovery.get('discovered', []))}",
        f"- actionable repositories: {summary.get('actionable', 0)}",
        f"- result statuses: planned={statuses.get('planned', 0)}, skipped_existing={statuses.get('skipped_existing', 0)}, failed={statuses.get('failed', 0)}",
        f"- review priorities: high={summary.get('high', 0)}, medium={summary.get('medium', 0)}, low={summary.get('low', 0)}",
        f"- review signals: missing security={summary.get('missingSecurityContact', 0)}, inferred build/test={summary.get('inferredExecutionFields', 0)}, missing build/test={summary.get('missingExecutionFields', 0)}, missing maintainer/team={summary.get('missingOwnerSignal', 0)}, warnings={summary.get('warnings', 0)}",
        "",
    ]

    batch_plan = load_optional_json(args.batches)
    if batch_plan is not None:
        batch_summary = batch_plan.get("summary", {})
        batches = batch_plan.get("batches", [])
        lines.extend(
            [
                f"- review batches: {batch_summary.get('batchCount', 0)} at {batch_summary.get('batchSize', 'unknown')} repositories max",
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
                    f"- `{batch.get('id', 'seed-batch')}`: {batch.get('priority', 'unknown')} priority, {batch.get('repositoryCount', 0)} repositories"
                )
            if len(batches) > 3:
                lines.append(f"- plus {len(batches) - 3} more batches")
            lines.append("")

    for section in (
        format_priority_section("High Priority", high, args.max_items),
        format_priority_section("Medium Priority", medium, args.max_items),
        format_priority_section("Low Priority", low, args.max_items),
    ):
        if section:
            lines.append(section)

    print("\n".join(lines).rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
