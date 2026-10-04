#!/usr/bin/env -S uv run python
"""Gate factual record age independently of snapshot publication time."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from public_product_content import freshness_summary, profiles


def evaluation_time(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("--now must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def evaluate_freshness(
    public_root: Path,
    inventory: dict,
    now: str,
    max_stale_or_unknown_rate: float = 0.1,
    max_refresh_overdue_days: float = 7,
) -> dict:
    result = freshness_summary(public_root, inventory, now)
    evaluated_at = datetime.fromisoformat(now.replace("Z", "+00:00"))
    overdue = []
    for profile in profiles(public_root, inventory):
        try:
            checked_at = datetime.fromisoformat(
                profile["record"]["generatedAt"].replace("Z", "+00:00")
            )
            if checked_at.tzinfo is None or checked_at > evaluated_at:
                continue
            overdue_days = max(
                0.0, (evaluated_at - checked_at).total_seconds() / 86400 - result["staleAfterDays"]
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        overdue.append((overdue_days, profile.get("identity")))
    total = result["fresh"] + result["stale"] + result["unknown"]
    result["staleOrUnknownRate"] = (result["stale"] + result["unknown"]) / total if total else 1.0
    result["maxStaleOrUnknownRate"] = max_stale_or_unknown_rate
    result["maxRefreshOverdueDays"] = max_refresh_overdue_days
    result["oldestRefreshOverdueDays"] = max((days for days, _ in overdue), default=None)
    result["overdueRepositories"] = [
        {"identity": identity, "refreshOverdueDays": days}
        for days, identity in overdue
        if days > max_refresh_overdue_days
    ]
    result["passed"] = (
        total > 0
        and result["staleOrUnknownRate"] <= max_stale_or_unknown_rate
        and not result["overdueRepositories"]
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-root", type=Path, required=True)
    parser.add_argument("--max-stale-or-unknown-rate", type=float, default=0.1)
    parser.add_argument("--max-refresh-overdue-days", type=float, default=7)
    parser.add_argument("--now", help="Evaluation time with timezone (default: current UTC time)")
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    if not 0 <= args.max_stale_or_unknown_rate <= 1:
        parser.error("rate must be between 0 and 1")
    if not 0 <= args.max_refresh_overdue_days < float("inf"):
        parser.error("overdue days must be finite and nonnegative")
    try:
        now = evaluation_time(args.now)
    except (ValueError, TypeError) as err:
        parser.error(str(err))
    meta = json.loads((args.public_root / "v0/meta.json").read_text())
    inventory = json.loads((args.public_root / "v0/repos/index.json").read_text())
    result = evaluate_freshness(
        args.public_root,
        inventory,
        now,
        args.max_stale_or_unknown_rate,
        args.max_refresh_overdue_days,
    )
    result["exportGeneratedAt"] = meta["generatedAt"]
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return int(not result["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
