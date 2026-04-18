#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select one review batch and emit targets plus metadata."
    )
    parser.add_argument("--input", required=True, help="Path to seed-batches.json or refresh-batches.json")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--batch-id", help="Batch identifier such as seed-batch-01")
    selection.add_argument(
        "--first-batch",
        action="store_true",
        help="Select the first batch in the plan, optionally skipping failed ones",
    )
    parser.add_argument("--output-targets", required=True, help="Path for newline-delimited repository identities")
    parser.add_argument("--output-metadata", required=True, help="Path for selected batch metadata JSON")
    parser.add_argument(
        "--require-no-failed",
        action="store_true",
        help="Fail when the selected batch still contains repositories with status=failed",
    )
    parser.add_argument(
        "--skip-batches-with-failed",
        action="store_true",
        help="When selecting the first batch, skip any batch that still contains repositories with status=failed",
    )
    return parser.parse_args()


def load_plan(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"missing batch plan: {path}")
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise SystemExit(f"batch plan is malformed: {path}")
    return data


def main() -> int:
    args = parse_args()
    plan = load_plan(Path(args.input))
    batches = plan.get("batches", [])
    if not isinstance(batches, list):
        raise SystemExit("batch plan is malformed: missing batches array")

    selected = None
    if args.batch_id:
        for batch in batches:
            if isinstance(batch, dict) and batch.get("id") == args.batch_id:
                selected = batch
                break
        if selected is None:
            available = ", ".join(
                batch.get("id", "<unknown>") for batch in batches if isinstance(batch, dict)
            )
            raise SystemExit(f"batch `{args.batch_id}` not found; available: {available}")
    else:
        for batch in batches:
            if not isinstance(batch, dict):
                continue
            repositories = batch.get("repositories", [])
            if args.skip_batches_with_failed and any(
                repo.get("status") == "failed" for repo in repositories if isinstance(repo, dict)
            ):
                continue
            selected = batch
            break
        if selected is None:
            if args.skip_batches_with_failed:
                raise SystemExit("no eligible batch without failed repositories was found")
            raise SystemExit("batch plan contains no selectable batches")

    repositories = selected.get("repositories", [])
    if not isinstance(repositories, list) or not repositories:
        raise SystemExit(f"selected batch `{selected.get('id', '<unknown>')}` contains no repositories")
    if args.require_no_failed:
        failed = [repo.get("identity", "<unknown>") for repo in repositories if repo.get("status") == "failed"]
        if failed:
            rendered = ", ".join(failed)
            raise SystemExit(
                f"batch `{args.batch_id}` still contains failed crawl candidates: {rendered}"
            )

    targets_path = Path(args.output_targets)
    targets_path.parent.mkdir(parents=True, exist_ok=True)
    targets_path.write_text(
        "".join(f"{repo.get('identity', '').strip()}\n" for repo in repositories if repo.get("identity"))
    )

    metadata = {
        "source": plan.get("source", {}),
        "summary": plan.get("summary", {}),
        "batch": selected,
    }
    metadata_path = Path(args.output_metadata)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
