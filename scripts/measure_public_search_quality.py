#!/usr/bin/env -S uv run python

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


SCHEMA = "dotrepo-public-search-quality/v0"
SEARCHABLE_TEXT_FIELDS = ("identity", "name", "purpose", "homepage", "license")
COMPLETENESS_SIGNALS = (
    "hasBuild",
    "hasTest",
    "hasDocs",
    "hasSecurityContact",
    "hasOwnershipSignal",
    "hasLicense",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Measure public profile search quality against a representative "
            "discovery workload."
        )
    )
    parser.add_argument(
        "--public-root",
        required=True,
        help="Public export root containing v0/repos/**/profile.json",
    )
    parser.add_argument(
        "--workload",
        required=True,
        help="JSON workload file listing search queries and expected repositories",
    )
    parser.add_argument("--output-json", help="Optional path for report JSON")
    parser.add_argument("--output-md", help="Optional path for markdown report")
    parser.add_argument(
        "--generated-at",
        help="Override report timestamp, primarily for deterministic tests",
    )
    parser.add_argument(
        "--min-success-rate",
        type=float,
        default=0.0,
        help="Fail when success rate is below this threshold",
    )
    parser.add_argument(
        "--min-mean-reciprocal-rank",
        type=float,
        default=0.0,
        help="Fail when mean reciprocal rank is below this threshold",
    )
    parser.add_argument(
        "--max-average-first-rank",
        type=float,
        default=None,
        help="Fail when average first expected rank exceeds this threshold",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"failed to parse JSON in {path}: {exc}") from exc


def generated_timestamp(override: Optional[str]) -> str:
    if override:
        return override
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize(value: str) -> str:
    return value.strip().lower()


def parse_repository(value: str) -> tuple[str, str, str]:
    parts = [part for part in value.strip("/").split("/") if part]
    if len(parts) != 3:
        raise SystemExit(f"repository must be host/owner/repo, got {value!r}")
    return parts[0], parts[1], parts[2]


def repository_key(identity: dict[str, Any]) -> str:
    return f"{identity.get('host')}/{identity.get('owner')}/{identity.get('repo')}"


def load_workload(path: Path) -> dict[str, Any]:
    workload = load_json(path)
    tasks = workload.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise SystemExit(f"workload must contain a non-empty tasks array: {path}")
    for task in tasks:
        if not isinstance(task, dict):
            raise SystemExit("each workload task must be an object")
        if not isinstance(task.get("id"), str) or not task["id"].strip():
            raise SystemExit("each workload task must have a non-empty id")
        if not isinstance(task.get("query"), str):
            raise SystemExit(f"task {task.get('id', '<unknown>')} is missing query")
        expected = task.get("expectedRepositories")
        if not isinstance(expected, list) or not expected:
            raise SystemExit(f"task {task['id']} must list expectedRepositories")
        for repository in expected:
            if not isinstance(repository, str):
                raise SystemExit(f"task {task['id']} has an invalid expected repository")
            parse_repository(repository)
        filters = task.get("filters", {})
        if not isinstance(filters, dict):
            raise SystemExit(f"task {task['id']} filters must be an object")
    return workload


def profile_paths(public_root: Path) -> list[Path]:
    root = public_root / "v0" / "repos"
    if not root.is_dir():
        raise SystemExit(f"missing public repo root: {root}")
    return sorted(root.glob("*/*/*/profile.json"))


def inventory_path(public_root: Path) -> Path:
    return public_root / "v0" / "repos" / "index.json"


def file_size(path: Path) -> int:
    return path.stat().st_size if path.is_file() else 0


def load_profiles(public_root: Path) -> list[dict[str, Any]]:
    profiles = []
    for path in profile_paths(public_root):
        profile = load_json(path)
        identity = profile.get("identity")
        if not isinstance(identity, dict):
            continue
        profiles.append(
            {
                "profile": profile,
                "path": path,
                "repository": repository_key(identity),
            }
        )
    return profiles


def requires_profile_fanout(filters: dict[str, Any]) -> bool:
    if not filters:
        return False
    profile_filter_keys = {
        "languages",
        "topics",
        "statuses",
        "confidences",
        "requireBuild",
        "requireTest",
        "requireDocs",
        "requireSecurityContact",
        "requireLicense",
    }
    for key in profile_filter_keys:
        value = filters.get(key)
        if isinstance(value, list) and value:
            return True
        if isinstance(value, bool) and value:
            return True
    return False


def contains_normalized(values: list[str], expected: str) -> bool:
    expected = normalize(expected)
    return any(normalize(value) == expected for value in values)


def option_matches(actual: Optional[str], filters: list[str]) -> bool:
    return not filters or (
        actual is not None
        and any(normalize(actual) == normalize(filter_value) for filter_value in filters)
    )


def matches_filters(profile: dict[str, Any], filters: dict[str, Any]) -> bool:
    languages = profile.get("languages", [])
    topics = profile.get("topics", [])
    trust = profile.get("trust", {})
    completeness = profile.get("completeness", {})
    for language in filters.get("languages", []):
        if not contains_normalized(languages, language):
            return False
    for topic in filters.get("topics", []):
        if not contains_normalized(topics, topic):
            return False
    if not option_matches(trust.get("selectedStatus"), filters.get("statuses", [])):
        return False
    if not option_matches(trust.get("confidence"), filters.get("confidences", [])):
        return False
    required_flags = {
        "requireBuild": "hasBuild",
        "requireTest": "hasTest",
        "requireDocs": "hasDocs",
        "requireSecurityContact": "hasSecurityContact",
        "requireLicense": "hasLicense",
    }
    return all(
        not filters.get(flag) or bool(completeness.get(signal))
        for flag, signal in required_flags.items()
    )


def matched_fields(profile: dict[str, Any], query: str) -> list[str]:
    query = normalize(query)
    if not query:
        return ["all"]
    identity = profile.get("identity", {})
    text_values = {
        "identity": repository_key(identity),
        "name": profile.get("name", ""),
        "purpose": profile.get("purpose", ""),
        "homepage": profile.get("homepage", ""),
        "license": profile.get("license", ""),
    }
    matched = [
        field
        for field in SEARCHABLE_TEXT_FIELDS
        if query in normalize(str(text_values.get(field, "")))
    ]
    if any(query in normalize(str(language)) for language in profile.get("languages", [])):
        matched.append("languages")
    if any(query in normalize(str(topic)) for topic in profile.get("topics", [])):
        matched.append("topics")
    return matched


def completeness_signal_count(profile: dict[str, Any]) -> int:
    completeness = profile.get("completeness", {})
    return sum(1 for signal in COMPLETENESS_SIGNALS if completeness.get(signal))


def rank_profiles(
    profiles: list[dict[str, Any]],
    query: str,
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    results = []
    for item in profiles:
        profile = item["profile"]
        if not matches_filters(profile, filters):
            continue
        matched = matched_fields(profile, query)
        if not matched:
            continue
        completeness_count = completeness_signal_count(profile)
        score = len(matched) * 10 + completeness_count
        basis = []
        if matched:
            basis.append("matchedFields")
        if completeness_count:
            basis.append("profileCompleteness")
        results.append(
            {
                "repository": item["repository"],
                "matched": matched,
                "ranking": {
                    "score": score,
                    "matchedFieldCount": len(matched),
                    "completenessSignalCount": completeness_count,
                    "basis": basis,
                },
                "profilePath": item["path"],
            }
        )
    return sorted(
        results,
        key=lambda item: (
            -item["ranking"]["score"],
            -item["ranking"]["matchedFieldCount"],
            item["repository"],
        ),
    )


def relative_public_path(public_root: Path, path: Path) -> str:
    return path.relative_to(public_root).as_posix()


def analyze_task(
    task: dict[str, Any],
    profiles: list[dict[str, Any]],
    public_root: Path,
) -> dict[str, Any]:
    limit = int(task.get("limit", 10))
    if limit <= 0:
        raise SystemExit(f"task {task['id']} limit must be positive")
    ranked = rank_profiles(profiles, task["query"], task.get("filters", {}))
    limited = ranked[:limit]
    expected = list(task["expectedRepositories"])
    rank_by_repository = {
        item["repository"]: index + 1
        for index, item in enumerate(limited)
    }
    expected_ranks = {
        repository: rank_by_repository.get(repository)
        for repository in expected
    }
    found_ranks = [
        rank
        for rank in expected_ranks.values()
        if isinstance(rank, int)
    ]
    first_expected_rank = min(found_ranks) if found_ranks else None
    reciprocal_rank = round(1 / first_expected_rank, 4) if first_expected_rank else 0.0
    success = all(isinstance(rank, int) for rank in expected_ranks.values())
    public_paths = [
        result["profilePath"]
        for result in ranked
    ]
    return {
        "id": task["id"],
        "query": task["query"],
        "filters": task.get("filters", {}),
        "costMode": (
            "profile_fanout"
            if requires_profile_fanout(task.get("filters", {}))
            else "inventory_only"
        ),
        "limit": limit,
        "expectedRepositories": expected,
        "returnedRepositories": [item["repository"] for item in limited],
        "expectedRanks": expected_ranks,
        "firstExpectedRank": first_expected_rank,
        "reciprocalRank": reciprocal_rank,
        "success": success,
        "resultCount": len(ranked),
        "topResults": [
            {
                "repository": item["repository"],
                "matched": item["matched"],
                "ranking": item["ranking"],
            }
            for item in limited
        ],
        "inputs": {
            "profileFiles": [
                relative_public_path(public_root, path)
                for path in public_paths
            ],
        },
    }


def safe_ratio(numerator: int, denominator: int) -> Optional[float]:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def average(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def build_gates(
    summary: dict[str, Any],
    *,
    min_success_rate: float = 0.0,
    min_mean_reciprocal_rank: float = 0.0,
    max_average_first_rank: Optional[float] = None,
) -> dict[str, Any]:
    gates: dict[str, Any] = {
        "minSuccessRate": {
            "threshold": min_success_rate,
            "actual": summary["successRate"],
            "passed": (summary["successRate"] or 0.0) >= min_success_rate,
        },
        "minMeanReciprocalRank": {
            "threshold": min_mean_reciprocal_rank,
            "actual": summary["meanReciprocalRank"],
            "passed": (summary["meanReciprocalRank"] or 0.0)
            >= min_mean_reciprocal_rank,
        },
    }
    if max_average_first_rank is not None:
        average_first_rank = summary["averageFirstExpectedRank"]
        gates["maxAverageFirstRank"] = {
            "threshold": max_average_first_rank,
            "actual": average_first_rank,
            "passed": average_first_rank is not None
            and average_first_rank <= max_average_first_rank,
        }
    return gates


def unique_profile_bytes(tasks: list[dict[str, Any]], public_root: Path) -> int:
    paths = {
        public_root / profile_path
        for task in tasks
        for profile_path in task["inputs"]["profileFiles"]
    }
    return sum(path.stat().st_size for path in paths if path.is_file())


def cost_summary(tasks: list[dict[str, Any]], public_root: Path) -> dict[str, Any]:
    inventory_only_count = sum(1 for task in tasks if task["costMode"] == "inventory_only")
    profile_fanout_count = sum(1 for task in tasks if task["costMode"] == "profile_fanout")
    task_count = len(tasks)
    searched_profile_bytes = unique_profile_bytes(tasks, public_root)
    inventory_bytes = file_size(inventory_path(public_root))
    return {
        "inventoryOnlyTaskCount": inventory_only_count,
        "profileFanoutTaskCount": profile_fanout_count,
        "inventoryOnlyTaskRate": safe_ratio(inventory_only_count, task_count),
        "profileFanoutTaskRate": safe_ratio(profile_fanout_count, task_count),
        "inventoryBytes": inventory_bytes,
        "searchedProfileBytes": searched_profile_bytes,
        "profileBytesPerTask": safe_ratio(searched_profile_bytes, task_count),
        "profileBytesPerProfileFanoutTask": safe_ratio(
            searched_profile_bytes, profile_fanout_count
        ),
    }


def freshness_summary(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    generated_at = sorted(
        {
            profile["profile"].get("freshness", {}).get("generatedAt")
            for profile in profiles
            if profile["profile"].get("freshness", {}).get("generatedAt")
        }
    )
    stale_after = sorted(
        {
            profile["profile"].get("freshness", {}).get("staleAfter")
            for profile in profiles
            if profile["profile"].get("freshness", {}).get("staleAfter")
        }
    )
    snapshots = sorted(
        {
            profile["profile"].get("freshness", {}).get("snapshotDigest")
            for profile in profiles
            if profile["profile"].get("freshness", {}).get("snapshotDigest")
        }
    )
    return {
        "generatedAt": generated_at,
        "staleAfter": stale_after,
        "snapshotCount": len(snapshots),
    }


def summarize(
    public_root: Path,
    workload_path: Path,
    generated_at: Optional[str] = None,
    min_success_rate: float = 0.0,
    min_mean_reciprocal_rank: float = 0.0,
    max_average_first_rank: Optional[float] = None,
) -> dict[str, Any]:
    workload = load_workload(workload_path)
    profiles = load_profiles(public_root)
    tasks = [
        analyze_task(task, profiles, public_root)
        for task in workload["tasks"]
    ]
    task_count = len(tasks)
    success_count = sum(1 for task in tasks if task["success"])
    first_ranks = [
        float(task["firstExpectedRank"])
        for task in tasks
        if task["firstExpectedRank"] is not None
    ]
    costs = cost_summary(tasks, public_root)
    summary = {
        "taskCount": task_count,
        "successCount": success_count,
        "successRate": safe_ratio(success_count, task_count),
        "meanReciprocalRank": average([task["reciprocalRank"] for task in tasks]),
        "averageFirstExpectedRank": average(first_ranks),
        "candidateProfileCount": len(profiles),
        "searchedProfileBytes": costs["searchedProfileBytes"],
        "cost": costs,
        "freshness": freshness_summary(profiles),
    }
    gates = build_gates(
        summary,
        min_success_rate=min_success_rate,
        min_mean_reciprocal_rank=min_mean_reciprocal_rank,
        max_average_first_rank=max_average_first_rank,
    )
    return {
        "schema": SCHEMA,
        "generatedAt": generated_timestamp(generated_at),
        "workload": {
            "path": workload_path.as_posix(),
            "schema": workload.get("schema"),
            "taskCount": task_count,
        },
        "summary": summary,
        "gates": gates,
        "passed": all(gate["passed"] for gate in gates.values()),
        "tasks": tasks,
        "notes": [
            "search quality is measured against exported profile.json payloads without repository scraping",
            "ranking score uses matched public fields and completeness signals, not trust status or confidence",
            "inventoryOnlyTaskRate estimates tasks that can use inventory-only hosted search without loading full profile snapshots",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# dotrepo public search quality benchmark",
        "",
        f"Generated at: `{report['generatedAt']}`",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Tasks succeeded | {summary['successCount']} / {summary['taskCount']} |",
        f"| Success rate | {summary['successRate']} |",
        f"| Mean reciprocal rank | {summary['meanReciprocalRank']} |",
        f"| Average first expected rank | {summary['averageFirstExpectedRank']} |",
        f"| Candidate profiles | {summary['candidateProfileCount']} |",
        f"| Searched profile bytes | {summary['searchedProfileBytes']} |",
        f"| Inventory bytes | {summary['cost']['inventoryBytes']} |",
        f"| Inventory-only task rate | {summary['cost']['inventoryOnlyTaskRate']} |",
        f"| Profile fan-out task rate | {summary['cost']['profileFanoutTaskRate']} |",
        f"| Profile bytes per fan-out task | {summary['cost']['profileBytesPerProfileFanoutTask']} |",
        f"| Snapshot count | {summary['freshness']['snapshotCount']} |",
        "",
        "## Gates",
        "",
        "| Gate | Actual | Threshold | Result |",
        "| --- | ---: | ---: | --- |",
    ]
    for name, gate in report.get("gates", {}).items():
        lines.append(
            f"| {name} | {gate['actual']} | {gate['threshold']} | {'pass' if gate['passed'] else 'fail'} |"
        )
    lines.extend([
        "",
        "| Task | Query | Success | First expected rank | Returned repositories |",
        "| --- | --- | --- | ---: | --- |",
    ])
    for task in report["tasks"]:
        returned = ", ".join(f"`{repo}`" for repo in task["returnedRepositories"]) or "-"
        lines.append(
            f"| `{task['id']}` | `{task['query']}` | {str(task['success']).lower()} | {task['firstExpectedRank']} | {returned} |"
        )
    lines.extend(["", "Notes:", ""])
    for note in report["notes"]:
        lines.append(f"- {note}.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    report = summarize(
        Path(args.public_root),
        Path(args.workload),
        generated_at=args.generated_at,
        min_success_rate=args.min_success_rate,
        min_mean_reciprocal_rank=args.min_mean_reciprocal_rank,
        max_average_first_rank=args.max_average_first_rank,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output_json:
        Path(args.output_json).write_text(rendered)
    else:
        print(rendered, end="")
    if args.output_md:
        Path(args.output_md).write_text(render_markdown(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
