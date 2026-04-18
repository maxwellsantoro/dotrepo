#!/usr/bin/env python3

import argparse
import json
from collections import Counter
from pathlib import Path


PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
STATUS_ORDER = {"failed": 0, "planned": 1, "applied": 2, "skipped_existing": 3}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Group seed-review items into small reviewer-facing batches."
    )
    parser.add_argument("--input", required=True, help="Path to seed-report.json")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=3,
        help="Maximum repositories per review batch (default: 3)",
    )
    parser.add_argument(
        "--max-preview-batches",
        type=int,
        default=3,
        help="Maximum batches to preview in stdout markdown (default: 3)",
    )
    parser.add_argument("--output-json", help="Optional path for machine-readable batch JSON")
    parser.add_argument("--output-md", help="Optional path for reviewer-facing markdown")
    return parser.parse_args()


def load_report(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"missing seed report: {path}")
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise SystemExit(f"seed report is malformed: {path}")
    return data


def identity(item: dict) -> str:
    repository = item.get("repository", {})
    host = repository.get("host", "?")
    owner = repository.get("owner", "?")
    repo = repository.get("repo", "?")
    return f"{host}/{owner}/{repo}"


def item_sort_key(item: dict) -> tuple[int, int, str]:
    status = str(item.get("status", "planned"))
    reasons = item.get("reasons") or []
    return (
        STATUS_ORDER.get(status, 99),
        -len(reasons),
        identity(item),
    )


def compact_item(item: dict) -> dict:
    return {
        "identity": identity(item),
        "status": item.get("status"),
        "priority": item.get("priority"),
        "reasons": item.get("reasons", []),
        "manifestPath": item.get("manifestPath"),
        "evidencePath": item.get("evidencePath"),
        "recordStatus": item.get("recordStatus"),
        "build": item.get("build"),
        "test": item.get("test"),
        "securityContact": item.get("securityContact"),
        "inferredFields": item.get("inferredFields", []),
        "warningCodes": item.get("warningCodes", []),
    }


def top_reason_counts(items: list[dict], limit: int = 3) -> list[dict]:
    counts = Counter()
    for item in items:
        for reason in item.get("reasons", []):
            counts[reason] += 1
    return [
        {"reason": reason, "count": count}
        for reason, count in counts.most_common(limit)
    ]


def summarize_signals(items: list[dict]) -> dict:
    signal_counts = Counter()
    for item in items:
        failed = item.get("status") == "failed"
        security_contact = item.get("securityContact")
        if failed:
            signal_counts["failed"] += 1
            continue
        if not security_contact or security_contact == "unknown":
            signal_counts["missingSecurityContact"] += 1
        if not item.get("build") or not item.get("test"):
            signal_counts["missingExecutionFields"] += 1
        if item.get("inferredFields"):
            signal_counts["inferredFields"] += 1
        if item.get("warningCodes"):
            signal_counts["warningCodes"] += 1
    return dict(signal_counts)


def suggested_pr_title(batch_id: str, items: list[dict]) -> str:
    repo_names = [identity(item).split("/")[-1] for item in items[:3]]
    suffix = ", ".join(repo_names)
    if len(items) > 3:
        suffix = f"{suffix}, +{len(items) - 3} more"
    return f"{batch_id}: {suffix}"


def build_batches(review_items: list[dict], batch_size: int) -> list[dict]:
    batches = []
    next_id = 1
    for priority in ("high", "medium", "low"):
        items = [item for item in review_items if item.get("priority") == priority]
        items.sort(key=item_sort_key)
        for offset in range(0, len(items), batch_size):
            chunk = items[offset : offset + batch_size]
            status_counts = Counter(str(item.get("status", "unknown")) for item in chunk)
            batch_id = f"seed-batch-{next_id:02d}"
            batches.append(
                {
                    "id": batch_id,
                    "priority": priority,
                    "repositoryCount": len(chunk),
                    "statusCounts": dict(status_counts),
                    "signalCounts": summarize_signals(chunk),
                    "topReasons": top_reason_counts(chunk),
                    "suggestedPrTitle": suggested_pr_title(batch_id, chunk),
                    "repositories": [compact_item(item) for item in chunk],
                }
            )
            next_id += 1
    return batches


def build_plan(report: dict, batch_size: int) -> dict:
    review = report.get("review", {})
    items = review.get("items", [])
    if not isinstance(items, list):
        raise SystemExit("seed report review.items is malformed")
    batches = build_batches(items, batch_size)
    summary = review.get("summary", {})
    return {
        "source": {
            "dryRun": report.get("dryRun"),
            "requestedLimit": report.get("discovery", {}).get("requestedLimit"),
        },
        "summary": {
            "actionable": summary.get("actionable", 0),
            "batchCount": len(batches),
            "batchSize": batch_size,
            "high": summary.get("high", 0),
            "medium": summary.get("medium", 0),
            "low": summary.get("low", 0),
            "failed": summary.get("failed", 0),
        },
        "batches": batches,
    }


def render_markdown(plan: dict, max_preview_batches: int | None = None) -> str:
    summary = plan.get("summary", {})
    batches = plan.get("batches", [])
    visible_batches = batches if max_preview_batches is None else batches[:max_preview_batches]
    lines = [
        "# Seed Review Batches",
        "",
        f"- actionable repositories: {summary.get('actionable', 0)}",
        f"- batches: {summary.get('batchCount', 0)}",
        f"- max repositories per batch: {summary.get('batchSize', 0)}",
        f"- priority mix: high={summary.get('high', 0)}, medium={summary.get('medium', 0)}, low={summary.get('low', 0)}, failed={summary.get('failed', 0)}",
        "",
    ]

    for batch in visible_batches:
        lines.append(f"## {batch['id']} ({batch['priority']})")
        lines.append("")
        lines.append(f"- repositories: {batch['repositoryCount']}")
        lines.append(f"- suggested PR title: `{batch['suggestedPrTitle']}`")
        if batch.get("statusCounts"):
            rendered = ", ".join(
                f"{name}={count}" for name, count in sorted(batch["statusCounts"].items())
            )
            lines.append(f"- statuses: {rendered}")
        if batch.get("signalCounts"):
            rendered = ", ".join(
                f"{name}={count}" for name, count in sorted(batch["signalCounts"].items())
            )
            lines.append(f"- signals: {rendered}")
        if batch.get("topReasons"):
            rendered = ", ".join(
                f"{item['count']}x {item['reason']}" for item in batch["topReasons"]
            )
            lines.append(f"- dominant review reasons: {rendered}")
        lines.append("")
        for repository in batch.get("repositories", []):
            reasons = repository.get("reasons") or ["needs review"]
            details = []
            if repository.get("recordStatus"):
                details.append(f"record `{repository['recordStatus']}`")
            if repository.get("build"):
                details.append(f"build `{repository['build']}`")
            if repository.get("test"):
                details.append(f"test `{repository['test']}`")
            if repository.get("securityContact"):
                details.append(f"security `{repository['securityContact']}`")
            if repository.get("warningCodes"):
                details.append(f"warnings {', '.join(repository['warningCodes'])}")
            if repository.get("manifestPath"):
                details.append(f"manifest `{repository['manifestPath']}`")
            lines.append(f"- `{repository['identity']}`: {reasons[0]}")
            if len(reasons) > 1:
                lines.append(f"  additional reasons: {'; '.join(reasons[1:])}")
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
