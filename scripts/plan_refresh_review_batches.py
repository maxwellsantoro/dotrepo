#!/usr/bin/env python3

import argparse
import json
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Group refresh-plan entries into small reviewer-facing batches."
    )
    parser.add_argument("--input", required=True, help="Path to refresh-plan.json")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Maximum repositories per refresh batch (default: 5)",
    )
    parser.add_argument(
        "--max-preview-batches",
        type=int,
        default=3,
        help="Maximum batches to preview when printing markdown (default: 3)",
    )
    parser.add_argument("--output-json", help="Optional path for machine-readable batch JSON")
    parser.add_argument("--output-md", help="Optional path for reviewer-facing markdown")
    return parser.parse_args()


def load_report(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"missing refresh plan report: {path}")
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise SystemExit(f"refresh plan report is malformed: {path}")
    return data


def identity(item: dict) -> str:
    repository = item.get("repository", {})
    host = repository.get("host", "?")
    owner = repository.get("owner", "?")
    repo = repository.get("repo", "?")
    return f"{host}/{owner}/{repo}"


def compact_item(item: dict) -> dict:
    return {
        "identity": identity(item),
        "reason": item.get("reason"),
        "defaultBranch": item.get("defaultBranch"),
        "headSha": item.get("headSha"),
        "scheduledAt": item.get("scheduledAt"),
        "synthesize": item.get("synthesize"),
        "synthesisModel": item.get("synthesisModel"),
    }


def build_batches(scheduled: list[dict], batch_size: int) -> list[dict]:
    batches = []
    next_id = 1
    reason_order = sorted(
        Counter(str(item.get("reason", "unknown")) for item in scheduled).items(),
        key=lambda item: (-item[1], item[0]),
    )
    for reason, _count in reason_order:
        items = [item for item in scheduled if item.get("reason") == reason]
        items.sort(key=identity)
        for offset in range(0, len(items), batch_size):
            chunk = items[offset : offset + batch_size]
            batch_id = f"refresh-batch-{next_id:02d}"
            batches.append(
                {
                    "id": batch_id,
                    "reason": reason,
                    "repositoryCount": len(chunk),
                    "suggestedPrTitle": f"{batch_id}: {reason}",
                    "repositories": [compact_item(item) for item in chunk],
                }
            )
            next_id += 1
    return batches


def build_plan(report: dict, batch_size: int) -> dict:
    schedule = report.get("schedule", {})
    scheduled = schedule.get("scheduled", [])
    skipped = schedule.get("skipped", [])
    if not isinstance(scheduled, list) or not isinstance(skipped, list):
        raise SystemExit("refresh plan schedule is malformed")
    reason_counts = Counter(str(item.get("reason", "unknown")) for item in scheduled)
    batches = build_batches(scheduled, batch_size)
    return {
        "source": {
            "statePath": report.get("statePath"),
            "trackedRepositories": report.get("trackedRepositories", 0),
            "candidateCount": report.get("candidateCount", 0),
        },
        "summary": {
            "scheduledCount": len(scheduled),
            "skippedCount": len(skipped),
            "batchCount": len(batches),
            "batchSize": batch_size,
            "reasonCounts": dict(reason_counts),
        },
        "batches": batches,
    }


def render_markdown(plan: dict, max_preview_batches: int | None = None) -> str:
    summary = plan.get("summary", {})
    batches = plan.get("batches", [])
    visible_batches = batches if max_preview_batches is None else batches[:max_preview_batches]
    reason_counts = summary.get("reasonCounts", {})
    rendered_reasons = ", ".join(
        f"{reason}={count}" for reason, count in sorted(reason_counts.items())
    )
    lines = [
        "# Refresh Review Batches",
        "",
        f"- scheduled refreshes: {summary.get('scheduledCount', 0)}",
        f"- skipped repositories: {summary.get('skippedCount', 0)}",
        f"- batches: {summary.get('batchCount', 0)}",
        f"- max repositories per batch: {summary.get('batchSize', 0)}",
    ]
    if rendered_reasons:
        lines.append(f"- scheduled reasons: {rendered_reasons}")
    lines.append("")

    for batch in visible_batches:
        lines.append(f"## {batch['id']} ({batch['reason']})")
        lines.append("")
        lines.append(f"- repositories: {batch['repositoryCount']}")
        lines.append(f"- suggested PR title: `{batch['suggestedPrTitle']}`")
        lines.append("")
        for repository in batch.get("repositories", []):
            details = []
            if repository.get("defaultBranch"):
                details.append(f"branch `{repository['defaultBranch']}`")
            if repository.get("headSha"):
                details.append(f"head `{repository['headSha']}`")
            if repository.get("scheduledAt"):
                details.append(f"scheduled `{repository['scheduledAt']}`")
            if repository.get("synthesize"):
                details.append("synthesize enabled")
            if repository.get("synthesisModel"):
                details.append(f"model `{repository['synthesisModel']}`")
            lines.append(f"- `{repository['identity']}`: {repository.get('reason', 'unknown')}")
            if details:
                lines.append(f"  details: {'; '.join(details)}")
        lines.append("")

    remaining = len(batches) - len(visible_batches)
    if remaining > 0:
        lines.append(f"- plus {remaining} more batches in the JSON and markdown artifacts")
        lines.append("")

    return "\n".join(lines).rstrip()


def write_text(path: str | None, text: str) -> None:
    if not path:
        return
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text)


def write_json(path: str | None, payload: dict) -> None:
    if not path:
        return
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2))


def main() -> int:
    args = parse_args()
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be positive")

    report = load_report(Path(args.input))
    plan = build_plan(report, args.batch_size)
    markdown = render_markdown(plan, max_preview_batches=None if args.output_md else args.max_preview_batches)

    write_json(args.output_json, plan)
    write_text(args.output_md, markdown)

    if not args.output_md:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
