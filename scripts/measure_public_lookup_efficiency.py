#!/usr/bin/env -S uv run python

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


SCHEMA = "dotrepo-public-lookup-efficiency/v0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Measure how often a public dotrepo export answers a representative "
            "known-repository workload, and compare compact public payload bytes "
            "with checked-in source/evidence proxy bytes."
        )
    )
    parser.add_argument(
        "--public-root",
        required=True,
        help="Public export root containing v0/ and query-input/ directories",
    )
    parser.add_argument(
        "--index-root",
        required=True,
        help="Index root containing repos/<host>/<owner>/<repo>/ records",
    )
    parser.add_argument(
        "--workload",
        required=True,
        help="JSON workload file listing repositories and dot paths to resolve",
    )
    parser.add_argument("--output-json", help="Optional path for report JSON")
    parser.add_argument("--output-md", help="Optional path for markdown report")
    parser.add_argument(
        "--generated-at",
        help="Override report timestamp, primarily for deterministic tests",
    )
    parser.add_argument(
        "--min-task-hit-rate",
        type=float,
        default=0.0,
        help="Fail when task hit rate is below this threshold",
    )
    parser.add_argument(
        "--min-field-hit-rate",
        type=float,
        default=0.0,
        help="Fail when field hit rate is below this threshold",
    )
    parser.add_argument(
        "--max-dotrepo-to-scrape-proxy-ratio",
        type=float,
        default=None,
        help=(
            "Fail when dotrepoToScrapeProxyRatio exceeds this threshold. "
            "Unset by default because fixture-scale payloads can be larger than "
            "their normalized record/evidence proxy."
        ),
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"failed to parse JSON in {path}: {exc}") from exc


def parse_repository(value: str) -> tuple[str, str, str]:
    parts = [part for part in value.strip("/").split("/") if part]
    if len(parts) != 3:
        raise SystemExit(
            f"repository must be host/owner/repo, got {value!r}"
        )
    return parts[0], parts[1], parts[2]


def generated_timestamp(override: Optional[str]) -> str:
    if override:
        return override
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def file_size_from_manifest(public_root: Path) -> dict[str, int]:
    manifest_path = public_root / "v0" / "files.json"
    if not manifest_path.is_file():
        return {}
    document = load_json(manifest_path)
    sizes = {}
    for item in document.get("files", []):
        path = item.get("path")
        byte_count = item.get("bytes")
        if isinstance(path, str) and isinstance(byte_count, int):
            sizes[path] = byte_count
    return sizes


def relative_public_path(public_root: Path, path: Path) -> str:
    return path.relative_to(public_root).as_posix()


def measured_size(path: Path, manifest_sizes: dict[str, int], root: Path) -> int:
    if not path.is_file():
        return 0
    relative = relative_public_path(root, path)
    return manifest_sizes.get(relative, path.stat().st_size)


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
        if not isinstance(task.get("repository"), str):
            raise SystemExit(f"task {task.get('id', '<unknown>')} is missing repository")
        fields = task.get("fields")
        if not isinstance(fields, list) or not fields:
            raise SystemExit(f"task {task['id']} must contain a non-empty fields array")
        if any(not isinstance(field, str) or not field.strip() for field in fields):
            raise SystemExit(f"task {task['id']} has an invalid field")
    return workload


def resolve_dot_path(value: Any, dot_path: str) -> Any:
    current = value
    for segment in dot_path.split("."):
        if isinstance(current, dict):
            if segment not in current:
                return None
            current = current[segment]
        elif isinstance(current, list) and segment.isdigit():
            index = int(segment)
            if index >= len(current):
                return None
            current = current[index]
        else:
            return None
    return current


def is_answered(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def repository_paths(public_root: Path, index_root: Path, repository: str) -> dict[str, Path]:
    host, owner, repo = parse_repository(repository)
    repo_path = Path(host) / owner / repo
    return {
        "profile": public_root / "v0" / "repos" / repo_path / "profile.json",
        "queryInput": public_root / "query-input" / host / owner / f"{repo}.json",
        "record": index_root / "repos" / repo_path / "record.toml",
        "evidence": index_root / "repos" / repo_path / "evidence.md",
    }


def size_existing(paths: list[Path]) -> int:
    return sum(path.stat().st_size for path in paths if path.is_file())


def analyze_task(
    task: dict[str, Any],
    public_root: Path,
    index_root: Path,
    manifest_sizes: dict[str, int],
) -> dict[str, Any]:
    repository = task["repository"]
    paths = repository_paths(public_root, index_root, repository)
    public_files = [paths["profile"], paths["queryInput"]]
    scrape_proxy_files = [paths["record"], paths["evidence"]]

    missing_inputs = [
        name
        for name in ("profile", "queryInput")
        if not paths[name].is_file()
    ]
    manifest = None
    if paths["queryInput"].is_file():
        query_input = load_json(paths["queryInput"])
        manifest = query_input.get("selection", {}).get("manifest")

    answered_fields = []
    missing_fields = []
    field_values = {}
    for field in task["fields"]:
        value = resolve_dot_path(manifest, field) if manifest is not None else None
        if is_answered(value):
            answered_fields.append(field)
            field_values[field] = value
        else:
            missing_fields.append(field)

    return {
        "id": task["id"],
        "repository": repository,
        "fields": list(task["fields"]),
        "answeredFields": answered_fields,
        "missingFields": missing_fields,
        "fieldValues": field_values,
        "hit": not missing_inputs and not missing_fields,
        "missingInputs": missing_inputs,
        "dotrepoBytes": sum(
            measured_size(path, manifest_sizes, public_root) for path in public_files
        ),
        "scrapeProxyBytes": size_existing(scrape_proxy_files),
        "inputs": {
            "publicFiles": [
                relative_public_path(public_root, path)
                for path in public_files
                if path.is_file()
            ],
            "scrapeProxyFiles": [
                path.as_posix()
                for path in scrape_proxy_files
                if path.is_file()
            ],
        },
    }


def unique_file_bytes(
    tasks: list[dict[str, Any]],
    public_root: Path,
    index_root: Path,
    manifest_sizes: dict[str, int],
) -> tuple[int, int]:
    public_paths = set()
    scrape_paths = set()
    for task in tasks:
        paths = repository_paths(public_root, index_root, task["repository"])
        public_paths.update([paths["profile"], paths["queryInput"]])
        scrape_paths.update([paths["record"], paths["evidence"]])
    public_bytes = sum(
        measured_size(path, manifest_sizes, public_root)
        for path in public_paths
        if path.is_file()
    )
    scrape_bytes = size_existing(sorted(scrape_paths))
    return public_bytes, scrape_bytes


def safe_ratio(numerator: int, denominator: int) -> Optional[float]:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def build_gates(
    summary: dict[str, Any],
    *,
    min_task_hit_rate: float = 0.0,
    min_field_hit_rate: float = 0.0,
    max_dotrepo_to_scrape_proxy_ratio: Optional[float] = None,
) -> dict[str, Any]:
    gates: dict[str, Any] = {
        "minTaskHitRate": {
            "threshold": min_task_hit_rate,
            "actual": summary["hitRate"],
            "passed": (summary["hitRate"] or 0.0) >= min_task_hit_rate,
        },
        "minFieldHitRate": {
            "threshold": min_field_hit_rate,
            "actual": summary["fieldHitRate"],
            "passed": (summary["fieldHitRate"] or 0.0) >= min_field_hit_rate,
        },
    }
    if max_dotrepo_to_scrape_proxy_ratio is not None:
        ratio_value = summary["dotrepoToScrapeProxyRatio"]
        gates["maxDotrepoToScrapeProxyRatio"] = {
            "threshold": max_dotrepo_to_scrape_proxy_ratio,
            "actual": ratio_value,
            "passed": ratio_value is not None
            and ratio_value <= max_dotrepo_to_scrape_proxy_ratio,
        }
    return gates


def summarize(
    public_root: Path,
    index_root: Path,
    workload_path: Path,
    generated_at: Optional[str] = None,
    min_task_hit_rate: float = 0.0,
    min_field_hit_rate: float = 0.0,
    max_dotrepo_to_scrape_proxy_ratio: Optional[float] = None,
) -> dict[str, Any]:
    workload = load_workload(workload_path)
    manifest_sizes = file_size_from_manifest(public_root)
    tasks = [
        analyze_task(task, public_root, index_root, manifest_sizes)
        for task in workload["tasks"]
    ]
    task_count = len(tasks)
    hit_count = sum(1 for task in tasks if task["hit"])
    field_count = sum(len(task["fields"]) for task in tasks)
    answered_field_count = sum(len(task["answeredFields"]) for task in tasks)
    dotrepo_bytes, scrape_proxy_bytes = unique_file_bytes(
        workload["tasks"],
        public_root,
        index_root,
        manifest_sizes,
    )
    bytes_saved = max(scrape_proxy_bytes - dotrepo_bytes, 0)

    summary = {
        "taskCount": task_count,
        "hitCount": hit_count,
        "hitRate": safe_ratio(hit_count, task_count),
        "fieldCount": field_count,
        "answeredFieldCount": answered_field_count,
        "fieldHitRate": safe_ratio(answered_field_count, field_count),
        "dotrepoBytes": dotrepo_bytes,
        "scrapeProxyBytes": scrape_proxy_bytes,
        "bytesSaved": bytes_saved,
        "bytesSavedRatio": safe_ratio(bytes_saved, scrape_proxy_bytes),
        "dotrepoToScrapeProxyRatio": safe_ratio(dotrepo_bytes, scrape_proxy_bytes),
    }
    gates = build_gates(
        summary,
        min_task_hit_rate=min_task_hit_rate,
        min_field_hit_rate=min_field_hit_rate,
        max_dotrepo_to_scrape_proxy_ratio=max_dotrepo_to_scrape_proxy_ratio,
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
            "scrapeProxyBytes uses checked-in record.toml and evidence.md as a deterministic local proxy, not live network scrape bytes",
            "dotrepoBytes counts unique public profile.json and query-input payloads needed by the workload",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# dotrepo public lookup efficiency benchmark",
        "",
        f"Generated at: `{report['generatedAt']}`",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Tasks answered | {summary['hitCount']} / {summary['taskCount']} |",
        f"| Task hit rate | {summary['hitRate']} |",
        f"| Fields answered | {summary['answeredFieldCount']} / {summary['fieldCount']} |",
        f"| Field hit rate | {summary['fieldHitRate']} |",
        f"| dotrepo bytes | {summary['dotrepoBytes']} |",
        f"| scrape proxy bytes | {summary['scrapeProxyBytes']} |",
        f"| bytes saved | {summary['bytesSaved']} |",
        f"| bytes saved ratio | {summary['bytesSavedRatio']} |",
        f"| dotrepo to scrape proxy ratio | {summary['dotrepoToScrapeProxyRatio']} |",
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
        "| Task | Repository | Hit | Missing fields |",
        "| --- | --- | --- | --- |",
    ])
    for task in report["tasks"]:
        missing = ", ".join(task["missingFields"]) or "-"
        lines.append(
            f"| `{task['id']}` | `{task['repository']}` | {str(task['hit']).lower()} | {missing} |"
        )
    lines.extend(
        [
            "",
            "Notes:",
            "",
        ]
    )
    for note in report["notes"]:
        lines.append(f"- {note}.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    report = summarize(
        Path(args.public_root),
        Path(args.index_root),
        Path(args.workload),
        generated_at=args.generated_at,
        min_task_hit_rate=args.min_task_hit_rate,
        min_field_hit_rate=args.min_field_hit_rate,
        max_dotrepo_to_scrape_proxy_ratio=args.max_dotrepo_to_scrape_proxy_ratio,
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
