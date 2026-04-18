#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a draft pull-request body for a selected review batch."
    )
    parser.add_argument("--input", required=True, help="Path to selected batch metadata JSON")
    parser.add_argument(
        "--kind",
        required=True,
        choices=("seed", "refresh"),
        help="Batch kind: seed or refresh",
    )
    parser.add_argument("--output", help="Optional output markdown path")
    return parser.parse_args()


def load_metadata(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"missing batch metadata: {path}")
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise SystemExit(f"batch metadata is malformed: {path}")
    return data


def render_seed(metadata: dict) -> str:
    batch = metadata.get("batch", {})
    repositories = batch.get("repositories", [])
    top_reasons = batch.get("topReasons", [])
    lines = [
        "## Why this PR exists",
        "",
        f"This draft applies `{batch.get('id', 'seed-batch')}` from the scheduled seed-review pipeline.",
        f"The batch priority is `{batch.get('priority', 'unknown')}` and it contains {batch.get('repositoryCount', 0)} repositories.",
        "",
    ]
    if top_reasons:
        lines.extend(
            [
                "## Dominant review reasons",
                "",
            ]
        )
        for reason in top_reasons:
            lines.append(f"- {reason.get('count', 0)}x {reason.get('reason', 'needs review')}")
        lines.append("")

    lines.extend(
        [
            "## Included repositories",
            "",
        ]
    )
    for repository in repositories:
        reasons = repository.get("reasons") or ["needs review"]
        lines.append(f"- `{repository.get('identity', '<unknown>')}`: {reasons[0]}")
    lines.append("")
    lines.extend(
        [
            "## Review focus",
            "",
            "- confirm the factual overlay is grounded in upstream evidence",
            "- confirm security, build, test, and ownership signals are acceptable for merge",
            "- decide whether any repo should be split out of the batch before merge",
        ]
    )
    return "\n".join(lines)


def render_refresh(metadata: dict) -> str:
    batch = metadata.get("batch", {})
    repositories = batch.get("repositories", [])
    lines = [
        "## Why this PR exists",
        "",
        f"This draft applies `{batch.get('id', 'refresh-batch')}` from the scheduled refresh-review pipeline.",
        f"The batch reason is `{batch.get('reason', 'unknown')}` and it contains {batch.get('repositoryCount', 0)} repositories.",
        "",
        "## Included repositories",
        "",
    ]
    for repository in repositories:
        detail = repository.get("headSha") or "head unknown"
        lines.append(
            f"- `{repository.get('identity', '<unknown>')}`: {repository.get('reason', 'unknown')} (`{detail}`)"
        )
    lines.append("")
    lines.extend(
        [
            "## Review focus",
            "",
            "- confirm the factual refresh still matches upstream state",
            "- confirm any regenerated fields remain conservative and evidence-backed",
            "- decide whether any repo should be split out of the batch before merge",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    metadata = load_metadata(Path(args.input))
    markdown = render_seed(metadata) if args.kind == "seed" else render_refresh(metadata)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown)
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
