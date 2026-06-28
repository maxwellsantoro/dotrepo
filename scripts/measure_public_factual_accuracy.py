#!/usr/bin/env -S uv run python

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "dotrepo-public-factual-accuracy/v0"
WORKLOAD_SCHEMA = "dotrepo-public-factual-accuracy-workload/v0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure exact public facts against a cited curated workload."
    )
    parser.add_argument("--public-root", required=True)
    parser.add_argument("--workload", required=True)
    parser.add_argument("--min-assertions", type=int, default=0)
    parser.add_argument("--min-repositories", type=int, default=0)
    parser.add_argument("--min-accuracy-rate", type=float, default=0.0)
    parser.add_argument("--max-missing-rate", type=float, default=1.0)
    parser.add_argument("--max-mismatch-rate", type=float, default=1.0)
    parser.add_argument("--generated-at")
    parser.add_argument("--output-json")
    parser.add_argument("--output-md")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"failed to parse JSON in {path}: {exc}") from exc


def resolve_dot_path(value: Any, dot_path: str) -> Any:
    current = value
    for segment in dot_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current


def query_input_path(public_root: Path, repository: str) -> Path:
    parts = repository.strip("/").split("/")
    if len(parts) != 3 or any(not part for part in parts):
        raise SystemExit(f"repository must be host/owner/repo, got {repository!r}")
    host, owner, repo = parts
    return public_root / "query-input" / host / owner / f"{repo}.json"


def validate_workload(workload: Any, path: Path) -> list[dict[str, Any]]:
    if not isinstance(workload, dict) or workload.get("schema") != WORKLOAD_SCHEMA:
        raise SystemExit(f"accuracy workload has an invalid schema: {path}")
    assertions = workload.get("assertions")
    if not isinstance(assertions, list) or not assertions:
        raise SystemExit(f"accuracy workload must contain assertions: {path}")
    seen_ids = set()
    for assertion in assertions:
        if not isinstance(assertion, dict):
            raise SystemExit("accuracy assertions must be objects")
        assertion_id = assertion.get("id")
        if not isinstance(assertion_id, str) or not assertion_id.strip():
            raise SystemExit("accuracy assertion id must be nonempty")
        if assertion_id in seen_ids:
            raise SystemExit(f"duplicate accuracy assertion id: {assertion_id}")
        seen_ids.add(assertion_id)
        if not isinstance(assertion.get("repository"), str):
            raise SystemExit(f"accuracy assertion {assertion_id} is missing repository")
        if not isinstance(assertion.get("path"), str) or not assertion["path"].strip():
            raise SystemExit(f"accuracy assertion {assertion_id} is missing path")
        if "expected" not in assertion:
            raise SystemExit(f"accuracy assertion {assertion_id} is missing expected")
        source = assertion.get("source")
        if not isinstance(source, dict):
            raise SystemExit(f"accuracy assertion {assertion_id} is missing source")
        for key in ("url", "locator", "checkedAt"):
            if not isinstance(source.get(key), str) or not source[key].strip():
                raise SystemExit(
                    f"accuracy assertion {assertion_id} source.{key} must be nonempty"
                )
        if not source["url"].startswith(("https://", "http://")):
            raise SystemExit(f"accuracy assertion {assertion_id} source.url must be HTTP(S)")
    return assertions


def analyze_assertion(
    assertion: dict[str, Any], public_root: Path, manifests: dict[str, Any]
) -> dict[str, Any]:
    repository = assertion["repository"]
    if repository not in manifests:
        path = query_input_path(public_root, repository)
        document = load_json(path) if path.is_file() else {}
        manifests[repository] = resolve_dot_path(document, "selection.manifest")
    actual = resolve_dot_path(manifests[repository], assertion["path"])
    expected = assertion["expected"]
    passed = actual == expected
    if passed:
        outcome = "correct"
    elif actual is None:
        outcome = "missing"
    else:
        outcome = "mismatch"
    return {
        "id": assertion["id"],
        "repository": repository,
        "path": assertion["path"],
        "expected": expected,
        "actual": actual,
        "passed": passed,
        "outcome": outcome,
        "source": assertion["source"],
    }


def safe_ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def summarize(
    public_root: Path,
    workload_path: Path,
    *,
    generated_at: str | None = None,
    min_assertions: int = 0,
    min_repositories: int = 0,
    min_accuracy_rate: float = 0.0,
    max_missing_rate: float = 1.0,
    max_mismatch_rate: float = 1.0,
) -> dict[str, Any]:
    assertions = validate_workload(load_json(workload_path), workload_path)
    manifests: dict[str, Any] = {}
    results = [
        analyze_assertion(assertion, public_root, manifests) for assertion in assertions
    ]
    assertion_count = len(results)
    repository_count = len({result["repository"] for result in results})
    correct_count = sum(1 for result in results if result["passed"])
    missing_count = sum(1 for result in results if result["outcome"] == "missing")
    mismatch_count = sum(1 for result in results if result["outcome"] == "mismatch")
    accuracy_rate = safe_ratio(correct_count, assertion_count)
    missing_rate = safe_ratio(missing_count, assertion_count)
    mismatch_rate = safe_ratio(mismatch_count, assertion_count)
    summary = {
        "assertionCount": assertion_count,
        "repositoryCount": repository_count,
        "correctCount": correct_count,
        "missingCount": missing_count,
        "mismatchCount": mismatch_count,
        "accuracyRate": accuracy_rate,
        "missingRate": missing_rate,
        "mismatchRate": mismatch_rate,
    }
    gates = {
        "minAssertions": {
            "threshold": min_assertions,
            "actual": assertion_count,
            "passed": assertion_count >= min_assertions,
        },
        "minRepositories": {
            "threshold": min_repositories,
            "actual": repository_count,
            "passed": repository_count >= min_repositories,
        },
        "minAccuracyRate": {
            "threshold": min_accuracy_rate,
            "actual": accuracy_rate,
            "passed": accuracy_rate is not None and accuracy_rate >= min_accuracy_rate,
        },
        "maxMissingRate": {
            "threshold": max_missing_rate,
            "actual": missing_rate,
            "passed": missing_rate is not None and missing_rate <= max_missing_rate,
        },
        "maxMismatchRate": {
            "threshold": max_mismatch_rate,
            "actual": mismatch_rate,
            "passed": mismatch_rate is not None and mismatch_rate <= max_mismatch_rate,
        },
    }
    return {
        "schema": SCHEMA,
        "generatedAt": generated_at
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "workload": {
            "path": workload_path.as_posix(),
            "schema": WORKLOAD_SCHEMA,
        },
        "summary": summary,
        "gates": gates,
        "passed": all(gate["passed"] for gate in gates.values()),
        "assertions": results,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# dotrepo public factual accuracy",
        "",
        f"Generated at: `{report['generatedAt']}`",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Correct assertions | {summary['correctCount']} / {summary['assertionCount']} |",
        f"| Repositories sampled | {summary['repositoryCount']} |",
        f"| Accuracy rate | {summary['accuracyRate']} |",
        f"| Missing values | {summary['missingCount']} |",
        f"| Missing rate | {summary['missingRate']} |",
        f"| Mismatched values | {summary['mismatchCount']} |",
        f"| Mismatch rate | {summary['mismatchRate']} |",
        "",
        "| Gate | Actual | Threshold | Result |",
        "| --- | ---: | ---: | --- |",
    ]
    for name, gate in report["gates"].items():
        lines.append(
            f"| {name} | {gate['actual']} | {gate['threshold']} | "
            f"{'pass' if gate['passed'] else 'fail'} |"
        )
    lines.extend(
        [
            "",
            "| Assertion | Repository | Path | Result | Source |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for result in report["assertions"]:
        source = result["source"]
        lines.append(
            f"| `{result['id']}` | `{result['repository']}` | `{result['path']}` | "
            f"{result['outcome']} | [{source['locator']}]({source['url']}) |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    report = summarize(
        Path(args.public_root),
        Path(args.workload),
        generated_at=args.generated_at,
        min_assertions=args.min_assertions,
        min_repositories=args.min_repositories,
        min_accuracy_rate=args.min_accuracy_rate,
        max_missing_rate=args.max_missing_rate,
        max_mismatch_rate=args.max_mismatch_rate,
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
