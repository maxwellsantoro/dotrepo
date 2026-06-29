#!/usr/bin/env -S uv run python

import argparse
import json
import tomllib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATUS_ORDER = {
    "draft": 0,
    "inferred": 1,
    "imported": 2,
    "reviewed": 3,
    "verified": 4,
    "canonical": 5,
}
CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}
HIGH_SIGNAL_STATUSES = {"reviewed", "verified", "canonical"}
HIGH_SIGNAL_CONFIDENCE = {"medium", "high"}
LANGUAGE_FAMILIES = ("Rust", "TypeScript / JavaScript", "Python", "Go", "Other")
GROWTH_BASELINE = Path("scripts/fixtures/index_growth_tranche_baseline.json")


def default_targets_file(repo_root: Path | None = None) -> str:
    root = repo_root or Path.cwd()
    baseline_path = root / GROWTH_BASELINE
    if not baseline_path.is_file():
        raise SystemExit(f"missing growth baseline: {baseline_path}")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    candidate = baseline.get("candidateFile")
    if isinstance(candidate, str) and candidate.strip():
        return candidate
    raise SystemExit(f"{baseline_path} is missing string candidateFile")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render the current seed-index growth status from checked-in records."
    )
    parser.add_argument(
        "--index-root",
        default="index",
        help="Index root to inspect (default: index)",
    )
    parser.add_argument(
        "--targets-file",
        default=None,
        help=(
            "Machine-readable candidate target list from the active growth catalog "
            "(default: index_growth_tranche_baseline.json candidateFile)"
        ),
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=10,
        help="Maximum low-confidence records or missing targets to list (default: 10)",
    )
    parser.add_argument(
        "--min-tranche-coverage-ratio",
        type=float,
        default=0.0,
        help="Fail when present candidate target ratio is below this threshold",
    )
    parser.add_argument(
        "--max-lower-confidence-queue",
        type=int,
        default=None,
        help="Fail when lower-confidence quality queue exceeds this threshold",
    )
    parser.add_argument(
        "--max-missing-targets",
        type=int,
        default=None,
        help="Fail when missing candidate target count exceeds this threshold",
    )
    parser.add_argument(
        "--milestone-high-signal-target",
        type=int,
        default=500,
        help="Milestone high-signal profile target for status reporting (default: 500)",
    )
    parser.add_argument(
        "--min-tranche-high-signal-capacity",
        type=int,
        default=None,
        help=(
            "Fail when current record-level high-signal count plus missing candidate "
            "targets is below this capacity threshold"
        ),
    )
    parser.add_argument(
        "--stale-after-days",
        type=int,
        default=30,
        help="Treat records generated more than this many days ago as stale (default: 30)",
    )
    parser.add_argument(
        "--now",
        help="Override current timestamp for deterministic freshness reports",
    )
    parser.add_argument(
        "--max-stale-or-missing-record-rate",
        type=float,
        default=None,
        help="Fail when stale, missing, or invalid generated_at records exceed this ratio",
    )
    parser.add_argument(
        "--max-refresh-overdue-days",
        type=float,
        default=None,
        help="Fail when any stale record is more than this many days past the stale threshold",
    )
    parser.add_argument("--output-json", help="Optional path for machine-readable JSON")
    parser.add_argument("--output-md", help="Optional path for markdown output")
    args = parser.parse_args()
    if args.targets_file is None:
        args.targets_file = default_targets_file()
    return args


def parse_rfc3339(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def resolve_now(value: str | None) -> datetime:
    if value:
        parsed = parse_rfc3339(value)
        if parsed is None:
            raise SystemExit(f"--now must be an RFC3339 timestamp, got {value!r}")
        return parsed
    return datetime.now(timezone.utc).replace(microsecond=0)


def load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise SystemExit(f"failed to parse TOML in {path}: {exc}") from exc


def record_paths(index_root: Path) -> list[Path]:
    repos_root = index_root / "repos"
    if not repos_root.is_dir():
        raise SystemExit(f"index root does not contain repos/: {repos_root}")
    return sorted(repos_root.glob("*/*/*/record.toml"))


def identity_from_record_path(index_root: Path, path: Path) -> str:
    relative = path.relative_to(index_root / "repos")
    host, owner, repo, _record = relative.parts
    return f"{host}/{owner}/{repo}"


def primary_language(record: dict[str, Any]) -> str:
    languages = record.get("repo", {}).get("languages") or []
    if not isinstance(languages, list) or not languages:
        return "unknown"
    first = str(languages[0]).strip()
    return first if first else "unknown"


def inferred_language_family(record: dict[str, Any]) -> str:
    languages = [str(language).lower() for language in record.get("repo", {}).get("languages") or []]
    if any(language == "rust" for language in languages):
        return "Rust"
    if any(language == "go" for language in languages):
        return "Go"
    if any(language == "python" or language == "cython" for language in languages):
        return "Python"
    if any(
        language in {"typescript", "javascript", "tsx", "jsx", "vue", "svelte"}
        for language in languages
    ):
        return "TypeScript / JavaScript"
    return "Other"


def claim_state_counts(record_dir: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    claims_dir = record_dir / "claims"
    if not claims_dir.is_dir():
        return counts
    for claim_path in sorted(claims_dir.glob("*/claim.toml")):
        claim = load_toml(claim_path)
        state = claim.get("claim", {}).get("state")
        counts[str(state or "unknown")] += 1
    return counts


def load_records(index_root: Path) -> list[dict[str, Any]]:
    records = []
    for path in record_paths(index_root):
        document = load_toml(path)
        record = document.get("record", {})
        repo = document.get("repo", {})
        trust = record.get("trust") or {}
        owners = document.get("owners", {})
        identity = identity_from_record_path(index_root, path)
        records.append(
            {
                "identity": identity,
                "path": str(path),
                "mode": record.get("mode", "unknown"),
                "status": record.get("status", "unknown"),
                "confidence": trust.get("confidence", "unknown"),
                "generatedAt": record.get("generated_at"),
                "primaryLanguage": primary_language(document),
                "languageFamily": inferred_language_family(document),
                "languages": repo.get("languages") or [],
                "buildPresent": bool(repo.get("build")),
                "testPresent": bool(repo.get("test")),
                "securityContact": owners.get("security_contact"),
                "claimStates": dict(claim_state_counts(path.parent)),
            }
        )
    return records


def load_targets(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    targets = []
    current_group = "Uncategorized"
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            current_group = line.lstrip("#").strip() or current_group
            continue
        if "/" not in line:
            continue
        owner, repo = line.split("/", 1)
        targets.append(
            {
                "identity": f"github.com/{owner}/{repo}",
                "group": current_group,
                "ownerRepo": line,
            }
        )
    return targets


def quality_rank(record: dict[str, Any]) -> tuple[int, int, int, int, str]:
    status = str(record.get("status", "unknown"))
    confidence = str(record.get("confidence", "unknown"))
    missing_execution = int(
        not record.get("buildPresent") or not record.get("testPresent")
    )
    missing_security = int(
        not record.get("securityContact") or record.get("securityContact") == "unknown"
    )
    return (
        STATUS_ORDER.get(status, -1),
        CONFIDENCE_ORDER.get(confidence, -1),
        -missing_execution,
        -missing_security,
        str(record.get("identity", "")),
    )


def lower_confidence_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = [
        record
        for record in records
        if str(record.get("status")) in {"draft", "inferred", "imported"}
        or str(record.get("confidence")) in {"low", "medium", "unknown"}
        or not record.get("buildPresent")
        or not record.get("testPresent")
        or not record.get("securityContact")
        or record.get("securityContact") == "unknown"
    ]
    return sorted(items, key=quality_rank)


def is_record_level_high_signal(record: dict[str, Any]) -> bool:
    return (
        str(record.get("status")) in HIGH_SIGNAL_STATUSES
        and str(record.get("confidence")) in HIGH_SIGNAL_CONFIDENCE
    )


def status_lift_rank(record: dict[str, Any]) -> tuple[int, int, str]:
    status = str(record.get("status", "unknown"))
    confidence = str(record.get("confidence", "unknown"))
    return (
        CONFIDENCE_ORDER.get(confidence, -1),
        STATUS_ORDER.get(status, -1),
        str(record.get("identity", "")),
    )


def high_signal_lift_candidates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = [
        record
        for record in records
        if not is_record_level_high_signal(record)
        and str(record.get("confidence")) in HIGH_SIGNAL_CONFIDENCE
        and bool(record.get("buildPresent"))
        and bool(record.get("testPresent"))
        and bool(record.get("securityContact"))
        and record.get("securityContact") != "unknown"
    ]
    return sorted(items, key=status_lift_rank, reverse=True)


def ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def build_gates(
    *,
    target_count: int,
    present_count: int,
    missing_count: int,
    lower_confidence_queue: int,
    tranche_high_signal_capacity: int,
    stale_or_missing_record_rate: float | None,
    max_refresh_overdue_days_actual: float,
    min_tranche_coverage_ratio: float = 0.0,
    max_lower_confidence_queue: int | None = None,
    max_missing_targets: int | None = None,
    min_tranche_high_signal_capacity: int | None = None,
    max_stale_or_missing_record_rate: float | None = None,
    max_refresh_overdue_days: float | None = None,
) -> dict[str, Any]:
    coverage_ratio = ratio(present_count, target_count)
    gates: dict[str, Any] = {
        "minTrancheCoverageRatio": {
            "threshold": min_tranche_coverage_ratio,
            "actual": coverage_ratio,
            "passed": (coverage_ratio or 0.0) >= min_tranche_coverage_ratio,
        }
    }
    if max_lower_confidence_queue is not None:
        gates["maxLowerConfidenceQueue"] = {
            "threshold": max_lower_confidence_queue,
            "actual": lower_confidence_queue,
            "passed": lower_confidence_queue <= max_lower_confidence_queue,
        }
    if max_missing_targets is not None:
        gates["maxMissingTargets"] = {
            "threshold": max_missing_targets,
            "actual": missing_count,
            "passed": missing_count <= max_missing_targets,
        }
    if min_tranche_high_signal_capacity is not None:
        gates["minTrancheHighSignalCapacity"] = {
            "threshold": min_tranche_high_signal_capacity,
            "actual": tranche_high_signal_capacity,
            "passed": tranche_high_signal_capacity >= min_tranche_high_signal_capacity,
        }
    if max_stale_or_missing_record_rate is not None:
        gates["maxStaleOrMissingRecordRate"] = {
            "threshold": max_stale_or_missing_record_rate,
            "actual": stale_or_missing_record_rate,
            "passed": stale_or_missing_record_rate is not None
            and stale_or_missing_record_rate <= max_stale_or_missing_record_rate,
        }
    if max_refresh_overdue_days is not None:
        gates["maxRefreshOverdueDays"] = {
            "threshold": max_refresh_overdue_days,
            "actual": max_refresh_overdue_days_actual,
            "passed": max_refresh_overdue_days_actual <= max_refresh_overdue_days,
        }
    return gates


def freshness_signals(
    records: list[dict[str, Any]],
    *,
    now: datetime,
    stale_after_days: int,
) -> dict[str, Any]:
    stale = []
    missing = []
    invalid = []
    ages = []
    overdue_days = []
    parsed_timestamps = []
    for record in records:
        identity = record["identity"]
        generated_at = record.get("generatedAt")
        if not isinstance(generated_at, str) or not generated_at.strip():
            missing.append(identity)
            continue
        parsed = parse_rfc3339(generated_at)
        if parsed is None:
            invalid.append(identity)
            continue
        age_days = max((now - parsed).total_seconds() / 86400, 0.0)
        ages.append((identity, age_days))
        parsed_timestamps.append(parsed)
        if age_days > stale_after_days:
            stale.append(identity)
            overdue_days.append(age_days - stale_after_days)

    total = len(records)
    stale_or_missing_count = len(stale) + len(missing) + len(invalid)
    total_overdue_days = sum(overdue_days)
    return {
        "asOf": now.isoformat().replace("+00:00", "Z"),
        "staleAfterDays": stale_after_days,
        "recordCount": total,
        "generatedAtKnown": len(ages),
        "missingGeneratedAt": len(missing),
        "invalidGeneratedAt": len(invalid),
        "staleRecords": len(stale),
        "staleOrMissingRecords": stale_or_missing_count,
        "staleRecordRate": ratio(len(stale), total),
        "staleOrMissingRecordRate": ratio(stale_or_missing_count, total),
        "maxRecordAgeDays": round(max((age for _identity, age in ages), default=0.0), 2),
        "maxRefreshOverdueDays": round(max(overdue_days, default=0.0), 2),
        "meanRefreshOverdueDays": (
            round(total_overdue_days / len(overdue_days), 2) if overdue_days else 0.0
        ),
        "totalRefreshOverdueDays": round(total_overdue_days, 2),
        "oldestGeneratedAt": (
            min(parsed_timestamps).isoformat().replace("+00:00", "Z")
            if parsed_timestamps
            else None
        ),
        "newestGeneratedAt": (
            max(parsed_timestamps).isoformat().replace("+00:00", "Z")
            if parsed_timestamps
            else None
        ),
        "staleRecordIdentities": stale,
        "missingGeneratedAtIdentities": missing,
        "invalidGeneratedAtIdentities": invalid,
    }


def summarize(
    index_root: Path,
    targets_file: Path,
    max_items: int,
    min_tranche_coverage_ratio: float = 0.0,
    max_lower_confidence_queue: int | None = None,
    max_missing_targets: int | None = None,
    milestone_high_signal_target: int = 500,
    min_tranche_high_signal_capacity: int | None = None,
    stale_after_days: int = 30,
    now: datetime | None = None,
    max_stale_or_missing_record_rate: float | None = None,
    max_refresh_overdue_days: float | None = None,
) -> dict[str, Any]:
    if milestone_high_signal_target < 0:
        raise SystemExit("--milestone-high-signal-target must not be negative")
    if stale_after_days < 0:
        raise SystemExit("--stale-after-days must not be negative")
    records = load_records(index_root)
    by_identity = {record["identity"]: record for record in records}
    targets = load_targets(targets_file)
    target_groups = {target["identity"]: target["group"] for target in targets}
    for record in records:
        record["languageFamily"] = target_groups.get(
            record["identity"], record["languageFamily"]
        )
    target_identities = [target["identity"] for target in targets]
    present_targets = [identity for identity in target_identities if identity in by_identity]
    missing_targets = [target for target in targets if target["identity"] not in by_identity]

    target_group_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"target": 0, "present": 0})
    for target in targets:
        target_group_counts[target["group"]]["target"] += 1
        if target["identity"] in by_identity:
            target_group_counts[target["group"]]["present"] += 1

    claim_states: Counter[str] = Counter()
    for record in records:
        claim_states.update(record.get("claimStates", {}))

    missing_build = [record["identity"] for record in records if not record["buildPresent"]]
    missing_test = [record["identity"] for record in records if not record["testPresent"]]
    unknown_security = [
        record["identity"]
        for record in records
        if not record.get("securityContact") or record.get("securityContact") == "unknown"
    ]
    quality_queue = lower_confidence_records(records)
    tranche_coverage_ratio = ratio(len(present_targets), len(targets))
    high_signal_record_count = sum(
        1 for record in records if is_record_level_high_signal(record)
    )
    lift_candidates = high_signal_lift_candidates(records)
    record_lift_capacity = high_signal_record_count + len(lift_candidates)
    tranche_high_signal_capacity = high_signal_record_count + len(missing_targets)
    freshness = freshness_signals(
        records,
        now=now or datetime.now(timezone.utc).replace(microsecond=0),
        stale_after_days=stale_after_days,
    )
    gates = build_gates(
        target_count=len(targets),
        present_count=len(present_targets),
        missing_count=len(missing_targets),
        lower_confidence_queue=len(quality_queue),
        tranche_high_signal_capacity=tranche_high_signal_capacity,
        stale_or_missing_record_rate=freshness["staleOrMissingRecordRate"],
        max_refresh_overdue_days_actual=freshness["maxRefreshOverdueDays"],
        min_tranche_coverage_ratio=min_tranche_coverage_ratio,
        max_lower_confidence_queue=max_lower_confidence_queue,
        max_missing_targets=max_missing_targets,
        min_tranche_high_signal_capacity=min_tranche_high_signal_capacity,
        max_stale_or_missing_record_rate=max_stale_or_missing_record_rate,
        max_refresh_overdue_days=max_refresh_overdue_days,
    )

    return {
        "indexRoot": str(index_root),
        "targetsFile": str(targets_file),
        "totalRecords": len(records),
        "passed": all(gate["passed"] for gate in gates.values()),
        "gates": gates,
        "recordStatusCounts": dict(Counter(record["status"] for record in records)),
        "recordModeCounts": dict(Counter(record["mode"] for record in records)),
        "trustConfidenceCounts": dict(Counter(record["confidence"] for record in records)),
        "languageFamilyCounts": {
            family: count
            for family, count in sorted(
                Counter(record["languageFamily"] for record in records).items(),
                key=lambda item: (
                    LANGUAGE_FAMILIES.index(item[0])
                    if item[0] in LANGUAGE_FAMILIES
                    else len(LANGUAGE_FAMILIES),
                    item[0],
                ),
            )
        },
        "claimStateCounts": dict(claim_states),
        "qualitySignals": {
            "missingBuild": len(missing_build),
            "missingTest": len(missing_test),
            "unknownSecurityContact": len(unknown_security),
            "lowerConfidenceQueue": len(quality_queue),
        },
        "freshnessSignals": freshness,
        "milestoneProgress": {
            "recordLevelHighSignalCount": high_signal_record_count,
            "milestoneHighSignalTarget": milestone_high_signal_target,
            "recordLevelHighSignalRatio": ratio(
                high_signal_record_count, milestone_high_signal_target
            ),
            "activeTrancheMissingTargets": len(missing_targets),
            "statusLiftCandidateCount": len(lift_candidates),
            "recordLevelPotentialAfterLift": record_lift_capacity,
            "recordLevelPotentialAfterLiftRatio": ratio(
                record_lift_capacity, milestone_high_signal_target
            ),
            "activeTrancheHighSignalCapacityUpperBound": tranche_high_signal_capacity,
            "activeTrancheCapacityRatio": ratio(
                tranche_high_signal_capacity, milestone_high_signal_target
            ),
            "remainingHighSignalGap": max(
                milestone_high_signal_target - high_signal_record_count, 0
            ),
            "remainingHighSignalGapAfterStatusLift": max(
                milestone_high_signal_target - record_lift_capacity, 0
            ),
            "remainingHighSignalGapAfterActiveTranche": max(
                milestone_high_signal_target - tranche_high_signal_capacity, 0
            ),
        },
        "tranche": {
            "targetCount": len(targets),
            "presentCount": len(present_targets),
            "missingCount": len(missing_targets),
            "coverageRatio": tranche_coverage_ratio,
            "coverageByGroup": dict(sorted(target_group_counts.items())),
            "missingTargets": missing_targets[:max_items],
        },
        "nextQualityTargets": [
            {
                "identity": record["identity"],
                "status": record["status"],
                "confidence": record["confidence"],
                "primaryLanguage": record["primaryLanguage"],
                "languageFamily": record["languageFamily"],
                "missingBuild": not record["buildPresent"],
                "missingTest": not record["testPresent"],
                "securityContact": record.get("securityContact") or "missing",
            }
            for record in quality_queue[:max_items]
        ],
        "nextHighSignalLiftTargets": [
            {
                "identity": record["identity"],
                "status": record["status"],
                "confidence": record["confidence"],
                "primaryLanguage": record["primaryLanguage"],
                "languageFamily": record["languageFamily"],
            }
            for record in lift_candidates[:max_items]
        ],
    }


def format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={counts[key]}" for key in sorted(counts))


def render_markdown(summary: dict[str, Any]) -> str:
    tranche = summary["tranche"]
    quality = summary["qualitySignals"]
    freshness = summary["freshnessSignals"]
    progress = summary["milestoneProgress"]
    lines = [
        "# Index Growth Status",
        "",
        f"- records: {summary['totalRecords']}",
        f"- record.status: {format_counts(summary['recordStatusCounts'])}",
        f"- record.mode: {format_counts(summary['recordModeCounts'])}",
        f"- trust confidence: {format_counts(summary['trustConfidenceCounts'])}",
        f"- language families: {format_counts(summary['languageFamilyCounts'])}",
        f"- maintainer claims: {format_counts(summary['claimStateCounts'])}",
        f"- record-level high-signal: {progress['recordLevelHighSignalCount']}/{progress['milestoneHighSignalTarget']} ({progress['recordLevelHighSignalRatio']})",
        f"- high-signal lift candidates: {progress['statusLiftCandidateCount']}",
        f"- record-level potential after lift: {progress['recordLevelPotentialAfterLift']}/{progress['milestoneHighSignalTarget']} ({progress['recordLevelPotentialAfterLiftRatio']})",
        f"- candidate coverage: {tranche['presentCount']}/{tranche['targetCount']} present ({tranche['coverageRatio']})",
        f"- active candidate high-signal capacity upper bound: {progress['activeTrancheHighSignalCapacityUpperBound']}/{progress['milestoneHighSignalTarget']} ({progress['activeTrancheCapacityRatio']})",
        f"- remaining high-signal gap after active candidates: {progress['remainingHighSignalGapAfterActiveTranche']}",
        f"- quality queue: {quality['lowerConfidenceQueue']} records need review hardening signals",
        f"- missing build/test/security: build={quality['missingBuild']}, test={quality['missingTest']}, security={quality['unknownSecurityContact']}",
        f"- stale/missing generated_at: {freshness['staleOrMissingRecords']}/{freshness['recordCount']} ({freshness['staleOrMissingRecordRate']}) as of {freshness['asOf']}",
        f"- max record age: {freshness['maxRecordAgeDays']} days; stale threshold: {freshness['staleAfterDays']} days",
        f"- refresh overdue latency: max={freshness['maxRefreshOverdueDays']} days, mean={freshness['meanRefreshOverdueDays']} days",
        "",
        "## Gates",
        "",
    ]
    for name, gate in summary.get("gates", {}).items():
        lines.append(
            f"- {name}: {gate['actual']} / {gate['threshold']} ({'pass' if gate['passed'] else 'fail'})"
        )
    lines.extend([
        "",
        "## Candidate Coverage (active targets file)",
        "",
    ])
    for group, counts in tranche["coverageByGroup"].items():
        lines.append(f"- {group}: {counts['present']}/{counts['target']} present")
    lines.append("")

    missing_targets = tranche.get("missingTargets") or []
    if missing_targets:
        lines.extend(["## Missing Candidate Targets", ""])
        for target in missing_targets:
            lines.append(f"- `{target['identity']}` ({target['group']})")
        lines.append("")

    next_quality_targets = summary.get("nextQualityTargets") or []
    if next_quality_targets:
        lines.extend(["## Next Quality Targets", ""])
        for record in next_quality_targets:
            blockers = []
            if record["missingBuild"]:
                blockers.append("missing build")
            if record["missingTest"]:
                blockers.append("missing test")
            if record["securityContact"] in {"missing", "unknown"}:
                blockers.append(f"security {record['securityContact']}")
            detail = ", ".join(blockers) if blockers else "review provenance"
            lines.append(
                f"- `{record['identity']}`: {record['languageFamily']}; status `{record['status']}`, confidence `{record['confidence']}`, {detail}"
            )
        lines.append("")

    next_lift_targets = summary.get("nextHighSignalLiftTargets") or []
    if next_lift_targets:
        lines.extend(["## Next High-Signal Lift Targets", ""])
        for record in next_lift_targets:
            lines.append(
                f"- `{record['identity']}`: {record['languageFamily']}; status `{record['status']}`, confidence `{record['confidence']}`"
            )
        lines.append("")

    stale = freshness.get("staleRecordIdentities") or []
    missing = freshness.get("missingGeneratedAtIdentities") or []
    invalid = freshness.get("invalidGeneratedAtIdentities") or []
    if stale or missing or invalid:
        lines.extend(["## Freshness Queue", ""])
        for identity in stale[:10]:
            lines.append(f"- `{identity}`: stale generated_at")
        for identity in missing[:10]:
            lines.append(f"- `{identity}`: missing generated_at")
        for identity in invalid[:10]:
            lines.append(f"- `{identity}`: invalid generated_at")
        lines.append("")

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
    if args.max_items < 0:
        raise SystemExit("--max-items must not be negative")
    if args.max_lower_confidence_queue is not None and args.max_lower_confidence_queue < 0:
        raise SystemExit("--max-lower-confidence-queue must not be negative")
    if args.max_missing_targets is not None and args.max_missing_targets < 0:
        raise SystemExit("--max-missing-targets must not be negative")
    if args.milestone_high_signal_target < 0:
        raise SystemExit("--milestone-high-signal-target must not be negative")
    if (
        args.min_tranche_high_signal_capacity is not None
        and args.min_tranche_high_signal_capacity < 0
    ):
        raise SystemExit("--min-tranche-high-signal-capacity must not be negative")
    if args.stale_after_days < 0:
        raise SystemExit("--stale-after-days must not be negative")
    if (
        args.max_stale_or_missing_record_rate is not None
        and not 0 <= args.max_stale_or_missing_record_rate <= 1
    ):
        raise SystemExit("--max-stale-or-missing-record-rate must be between 0 and 1")
    if args.max_refresh_overdue_days is not None and args.max_refresh_overdue_days < 0:
        raise SystemExit("--max-refresh-overdue-days must not be negative")
    summary = summarize(
        Path(args.index_root),
        Path(args.targets_file),
        args.max_items,
        min_tranche_coverage_ratio=args.min_tranche_coverage_ratio,
        max_lower_confidence_queue=args.max_lower_confidence_queue,
        max_missing_targets=args.max_missing_targets,
        milestone_high_signal_target=args.milestone_high_signal_target,
        min_tranche_high_signal_capacity=args.min_tranche_high_signal_capacity,
        stale_after_days=args.stale_after_days,
        now=resolve_now(args.now),
        max_stale_or_missing_record_rate=args.max_stale_or_missing_record_rate,
        max_refresh_overdue_days=args.max_refresh_overdue_days,
    )
    markdown = render_markdown(summary)
    write_json(args.output_json, summary)
    write_text(args.output_md, markdown + "\n")
    if not args.output_md:
        print(markdown)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
