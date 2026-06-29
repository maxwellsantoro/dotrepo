#!/usr/bin/env -S uv run python
"""Plan balanced target files for public-index coverage growth."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any


SCHEMA = "dotrepo-index-growth-tranche-plan/v0"
DEFAULT_HOST = "github.com"
TARGET_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Select a balanced set of not-yet-indexed repositories from a grouped "
            "candidate file and emit crawler target files plus audit reports."
        )
    )
    parser.add_argument("--index-root", default="index", help="Index root to inspect")
    parser.add_argument(
        "--candidate-file",
        required=True,
        help="Grouped repository candidate list. Comments starting with # name groups.",
    )
    parser.add_argument(
        "--target-count",
        type=int,
        default=500,
        help="Desired number of not-yet-indexed targets to emit (default: 500)",
    )
    parser.add_argument(
        "--default-host",
        default=DEFAULT_HOST,
        help=f"Host to apply to owner/repo candidates (default: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=20,
        help="Maximum selected/skipped examples to include in reports (default: 20)",
    )
    parser.add_argument(
        "--min-selected",
        type=int,
        default=0,
        help="Fail when fewer than this many targets are selected",
    )
    parser.add_argument(
        "--current-high-signal",
        type=int,
        default=0,
        help="Current checked-in high-signal profile count for milestone capacity reporting",
    )
    parser.add_argument(
        "--milestone-high-signal-target",
        type=int,
        default=500,
        help="Milestone high-signal profile target for capacity reporting (default: 500)",
    )
    parser.add_argument(
        "--min-planned-high-signal-capacity",
        type=int,
        default=0,
        help=(
            "Fail when current high-signal profiles plus selected growth targets "
            "is below this planned-capacity threshold"
        ),
    )
    parser.add_argument(
        "--output-targets",
        help="Optional path for newline-delimited crawler targets",
    )
    parser.add_argument("--output-json", help="Optional path for machine-readable JSON")
    parser.add_argument("--output-md", help="Optional path for markdown output")
    return parser.parse_args()


def normalize_target(raw: str, default_host: str) -> str:
    value = raw.strip()
    if not value:
        raise ValueError("target is empty")
    if "\\" in value or ".." in value:
        raise ValueError(f"unsafe repository target: {value}")
    if not TARGET_RE.match(value):
        raise ValueError(f"invalid repository target: {value}")
    parts = value.split("/")
    if len(parts) == 2:
        owner, repo = parts
        return f"{default_host}/{owner}/{repo}"
    host, owner, repo = parts
    return f"{host}/{owner}/{repo}"


def owner_repo(identity: str, default_host: str) -> str:
    prefix = f"{default_host}/"
    if identity.startswith(prefix):
        return identity.removeprefix(prefix)
    return identity


def load_existing_identities(index_root: Path) -> set[str]:
    repos_root = index_root / "repos"
    if not repos_root.is_dir():
        return set()
    identities = set()
    for path in sorted(repos_root.glob("*/*/*/record.toml")):
        relative = path.relative_to(repos_root)
        host, owner, repo, _record = relative.parts
        identities.add(f"{host}/{owner}/{repo}")
    return identities


def load_candidates(path: Path, default_host: str) -> list[dict[str, Any]]:
    if not path.is_file():
        raise SystemExit(f"missing candidate file: {path}")
    candidates = []
    current_group = "Uncategorized"
    seen: set[str] = set()
    duplicates: Counter[str] = Counter()
    for line_number, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            current_group = line.lstrip("#").strip() or current_group
            continue
        try:
            identity = normalize_target(line, default_host)
        except ValueError as exc:
            raise SystemExit(f"{path}:{line_number}: {exc}") from exc
        if identity in seen:
            duplicates[identity] += 1
            continue
        seen.add(identity)
        candidates.append(
            {
                "identity": identity,
                "target": owner_repo(identity, default_host),
                "group": current_group,
                "line": line_number,
            }
        )
    for candidate in candidates:
        candidate["duplicateCount"] = duplicates.get(candidate["identity"], 0)
    return candidates


def select_balanced(candidates: list[dict[str, Any]], target_count: int) -> list[dict[str, Any]]:
    groups: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    group_names: list[str] = []
    for candidate in candidates:
        group = str(candidate["group"])
        if group not in groups:
            group_names.append(group)
        groups[group].append(candidate)

    selected: list[dict[str, Any]] = []
    while len(selected) < target_count:
        made_progress = False
        for group in group_names:
            if len(selected) >= target_count:
                break
            if groups[group]:
                selected.append(groups[group].popleft())
                made_progress = True
        if not made_progress:
            break
    return selected


def ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def build_plan(
    *,
    index_root: Path,
    candidate_file: Path,
    target_count: int,
    default_host: str = DEFAULT_HOST,
    max_items: int = 20,
    min_selected: int = 0,
    current_high_signal: int = 0,
    milestone_high_signal_target: int = 500,
    min_planned_high_signal_capacity: int = 0,
) -> dict[str, Any]:
    if target_count < 0:
        raise SystemExit("--target-count must not be negative")
    if max_items < 0:
        raise SystemExit("--max-items must not be negative")
    if min_selected < 0:
        raise SystemExit("--min-selected must not be negative")
    if current_high_signal < 0:
        raise SystemExit("--current-high-signal must not be negative")
    if milestone_high_signal_target < 0:
        raise SystemExit("--milestone-high-signal-target must not be negative")
    if min_planned_high_signal_capacity < 0:
        raise SystemExit("--min-planned-high-signal-capacity must not be negative")

    existing = load_existing_identities(index_root)
    candidates = load_candidates(candidate_file, default_host)
    candidate_counts = Counter(candidate["group"] for candidate in candidates)
    duplicate_count = sum(candidate.get("duplicateCount", 0) for candidate in candidates)
    indexed_candidates = [
        candidate for candidate in candidates if candidate["identity"] in existing
    ]
    eligible = [
        candidate for candidate in candidates if candidate["identity"] not in existing
    ]
    selected = select_balanced(eligible, target_count)
    selected_identities = {candidate["identity"] for candidate in selected}
    deferred = [
        candidate
        for candidate in eligible
        if candidate["identity"] not in selected_identities
    ]
    selected_counts = Counter(candidate["group"] for candidate in selected)
    eligible_counts = Counter(candidate["group"] for candidate in eligible)
    indexed_counts = Counter(candidate["group"] for candidate in indexed_candidates)
    planned_capacity = current_high_signal + len(selected)
    remaining_gap = max(milestone_high_signal_target - current_high_signal, 0)
    remaining_gap_after_selected = max(milestone_high_signal_target - planned_capacity, 0)
    gates = {
        "minSelected": {
            "threshold": min_selected,
            "actual": len(selected),
            "passed": len(selected) >= min_selected,
        },
        "minPlannedHighSignalCapacity": {
            "threshold": min_planned_high_signal_capacity,
            "actual": planned_capacity,
            "passed": planned_capacity >= min_planned_high_signal_capacity,
        }
    }
    return {
        "schema": SCHEMA,
        "indexRoot": str(index_root),
        "candidateFile": str(candidate_file),
        "targetCount": target_count,
        "passed": all(gate["passed"] for gate in gates.values()),
        "gates": gates,
        "summary": {
            "existingRecordCount": len(existing),
            "candidateCount": len(candidates),
            "eligibleCandidateCount": len(eligible),
            "selectedCount": len(selected),
            "indexedCandidateCount": len(indexed_candidates),
            "deferredCandidateCount": len(deferred),
            "duplicateCandidateCount": duplicate_count,
        },
        "milestoneProgress": {
            "completedHighSignalProfiles": current_high_signal,
            "milestoneHighSignalTarget": milestone_high_signal_target,
            "selectedGrowthTargets": len(selected),
            "plannedHighSignalCapacityUpperBound": planned_capacity,
            "remainingHighSignalGap": remaining_gap,
            "remainingHighSignalGapAfterSelected": remaining_gap_after_selected,
            "completedHighSignalRatio": ratio(
                current_high_signal, milestone_high_signal_target
            ),
            "plannedCapacityRatio": ratio(
                planned_capacity, milestone_high_signal_target
            ),
        },
        "groups": {
            group: {
                "candidates": candidate_counts[group],
                "eligible": eligible_counts[group],
                "selected": selected_counts[group],
                "alreadyIndexed": indexed_counts[group],
            }
            for group in sorted(candidate_counts)
        },
        "selectedTargets": selected,
        "alreadyIndexedCandidates": indexed_candidates[:max_items],
        "deferredTargets": deferred[:max_items],
    }


def render_markdown(plan: dict[str, Any]) -> str:
    summary = plan["summary"]
    progress = plan["milestoneProgress"]
    lines = [
        "# Index Growth Plan",
        "",
        f"- candidate file: `{plan['candidateFile']}`",
        f"- existing records: {summary['existingRecordCount']}",
        f"- candidates: {summary['candidateCount']}",
        f"- eligible candidates: {summary['eligibleCandidateCount']}",
        f"- selected targets: {summary['selectedCount']}/{plan['targetCount']}",
        f"- already indexed candidates: {summary['indexedCandidateCount']}",
        f"- deferred eligible candidates: {summary['deferredCandidateCount']}",
        f"- duplicate candidate lines ignored: {summary['duplicateCandidateCount']}",
        "",
        "## Milestone 2 Capacity",
        "",
        f"- completed high-signal profiles: {progress['completedHighSignalProfiles']}/{progress['milestoneHighSignalTarget']}",
        f"- selected growth targets: {progress['selectedGrowthTargets']}",
        f"- planned high-signal capacity upper bound: {progress['plannedHighSignalCapacityUpperBound']}/{progress['milestoneHighSignalTarget']}",
        f"- remaining high-signal gap after selected targets: {progress['remainingHighSignalGapAfterSelected']}",
        "",
        "## Gates",
        "",
    ]
    for name, gate in plan.get("gates", {}).items():
        lines.append(
            f"- {name}: {gate['actual']} / {gate['threshold']} ({'pass' if gate['passed'] else 'fail'})"
        )
    lines.extend(["", "## Groups", ""])
    for group, counts in plan["groups"].items():
        lines.append(
            f"- {group}: selected={counts['selected']}, eligible={counts['eligible']}, alreadyIndexed={counts['alreadyIndexed']}, candidates={counts['candidates']}"
        )

    selected = plan.get("selectedTargets") or []
    if selected:
        lines.extend(["", "## Selected Targets", ""])
        for target in selected[:20]:
            lines.append(f"- `{target['target']}` ({target['group']})")

    indexed = plan.get("alreadyIndexedCandidates") or []
    if indexed:
        lines.extend(["", "## Already Indexed Candidates", ""])
        for target in indexed:
            lines.append(f"- `{target['identity']}` ({target['group']})")
    return "\n".join(lines).rstrip()


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
    destination.write_text(json.dumps(payload, indent=2) + "\n")


def main() -> int:
    args = parse_args()
    plan = build_plan(
        index_root=Path(args.index_root),
        candidate_file=Path(args.candidate_file),
        target_count=args.target_count,
        default_host=args.default_host,
        max_items=args.max_items,
        min_selected=args.min_selected,
        current_high_signal=args.current_high_signal,
        milestone_high_signal_target=args.milestone_high_signal_target,
        min_planned_high_signal_capacity=args.min_planned_high_signal_capacity,
    )
    write_json(args.output_json, plan)
    markdown = render_markdown(plan)
    write_text(args.output_md, markdown + "\n")
    write_text(
        args.output_targets,
        "".join(f"{target['target']}\n" for target in plan["selectedTargets"]),
    )
    if not args.output_md:
        print(markdown)
    return 0 if plan["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
