#!/usr/bin/env python3
"""Run one autonomous index refresh batch: crawl, gate, writeback, validate."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-root", default="index")
    parser.add_argument("--state-path", default="index/.crawler-state.toml")
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--batch-id", default="refresh-batch-01")
    parser.add_argument("--output-dir", default="index-autonomous-batch")
    parser.add_argument(
        "--disable-quality-reprocess",
        action="store_true",
        help="Do not fill empty batch slots with lower-confidence index records",
    )
    parser.add_argument(
        "--disable-discovery",
        action="store_true",
        help="Do not fill empty batch slots with newly discovered repositories",
    )
    parser.add_argument(
        "--discovery-limit",
        type=int,
        default=None,
        help=(
            "Maximum repositories to request from discovery when filling open slots. "
            "Defaults to INDEX_DISCOVERY_LIMIT, then the batch size."
        ),
    )
    parser.add_argument(
        "--discovery-star-band",
        action="append",
        default=[],
        help="Star-band filter such as 1000..10000 or 10000+ for discovery fills",
    )
    parser.add_argument(
        "--adjudication-call-budget",
        type=int,
        default=None,
        help=(
            "Hard batch-wide model-call budget. Defaults to "
            "INDEX_MAX_BATCH_ADJUDICATION_CALLS, then INDEX_MAX_ADJUDICATION_CALLS, then 0."
        ),
    )
    parser.add_argument(
        "--telemetry-history",
        default="index/telemetry/autonomous-runs.ndjson",
        help="Append retained per-run telemetry as newline-delimited JSON",
    )
    parser.add_argument(
        "--telemetry-summary",
        default="index/telemetry/autonomous-summary.json",
        help="Write aggregate telemetry derived from the retained run history",
    )
    parser.add_argument(
        "--regression-fixture-candidates-json",
        default="index/telemetry/regression-fixture-candidates.json",
        help="Write recurring-failure regression fixture candidates as JSON",
    )
    parser.add_argument(
        "--regression-fixture-candidates-md",
        default="index/telemetry/regression-fixture-candidates.md",
        help="Write recurring-failure regression fixture candidates as markdown",
    )
    parser.add_argument(
        "--regression-fixture-stub-dir",
        default="index/telemetry/regression-fixture-stubs",
        help="Write checked-in regression fixture stub directories for recurring failures",
    )
    parser.add_argument(
        "--skip-automation-enabled-check",
        action="store_true",
        help="Allow local runs without INDEX_AUTOMATION_ENABLED=true",
    )
    return parser.parse_args()


def run(
    command: list[str],
    *,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(command), flush=True)
    return subprocess.run(command, check=check, text=True, capture_output=True, env=env)


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text())


def env_int(name: str) -> int | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer, got {raw!r}") from exc


def resolve_adjudication_call_budget(args: argparse.Namespace) -> int:
    values = [
        args.adjudication_call_budget,
        env_int("INDEX_MAX_BATCH_ADJUDICATION_CALLS"),
        env_int("INDEX_MAX_ADJUDICATION_CALLS"),
        0,
    ]
    budget = next(value for value in values if value is not None)
    if budget < 0:
        raise SystemExit("--adjudication-call-budget must be >= 0")
    return budget


def resolve_discovery_limit(args: argparse.Namespace) -> int:
    values = [args.discovery_limit, env_int("INDEX_DISCOVERY_LIMIT"), args.batch_size]
    limit = next(value for value in values if value is not None)
    if limit < 0:
        raise SystemExit("--discovery-limit must be >= 0")
    return limit


def crawl_env_for_remaining_budget(base_env: dict[str, str], remaining_budget: int) -> dict[str, str]:
    env = base_env.copy()
    if remaining_budget <= 0:
        env["INDEX_MAX_ADJUDICATION_CALLS"] = "0"
        env.pop("DOTREPO_ADJUDICATION_URL", None)
        env.pop("DOTREPO_ADJUDICATION_SECOND_OPINION_URL", None)
        env.pop("DOTREPO_ADJUDICATION_API_URL", None)
        return env

    configured_per_repo = env.get("INDEX_MAX_ADJUDICATION_CALLS", "").strip()
    if configured_per_repo:
        try:
            per_repo_limit = int(configured_per_repo)
        except ValueError as exc:
            raise SystemExit(
                f"INDEX_MAX_ADJUDICATION_CALLS must be an integer, got {configured_per_repo!r}"
            ) from exc
        per_repo_limit = max(0, per_repo_limit)
    else:
        per_repo_limit = remaining_budget
    env["INDEX_MAX_ADJUDICATION_CALLS"] = str(min(per_repo_limit, remaining_budget))
    return env


def adjudication_enabled(env: dict[str, str]) -> bool:
    if int(env.get("INDEX_MAX_ADJUDICATION_CALLS") or 0) <= 0:
        return False
    return any(
        env.get(name, "").strip()
        for name in (
            "DOTREPO_ADJUDICATION_URL",
            "DOTREPO_ADJUDICATION_SECOND_OPINION_URL",
            "DOTREPO_ADJUDICATION_API_URL",
        )
    )


def adjudication_tier_counts(crawls: list[dict]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for crawl in crawls:
        escalation = crawl.get("escalation") or {}
        for tier in escalation.get("adjudicationTiersUsed") or []:
            counts[str(tier)] += 1
    return dict(sorted(counts.items()))


def parse_quality_record(path: Path) -> dict:
    document: dict[str, dict[str, str]] = {"record": {}, "trust": {}, "repo": {}, "owners": {}}
    section = ""
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line.strip("[]")
            continue
        match = re.match(r"([A-Za-z0-9_.-]+)\s*=\s*(.+)", line)
        if not match:
            continue
        key, value = match.groups()
        value = value.strip().strip('"')
        if section == "record":
            document["record"][key] = value
        elif section == "record.trust":
            document["trust"][key] = value
        elif section == "repo":
            document["repo"][key] = value
        elif section == "owners":
            document["owners"][key] = value
    return document


def identity_from_record_path(index_root: Path, record_path: Path) -> str:
    relative = record_path.relative_to(index_root / "repos")
    host, owner, repo, _record = relative.parts
    return f"{host}/{owner}/{repo}"


def quality_reprocess_rank(candidate: dict) -> tuple[int, int, int, int, str]:
    status_order = {
        "draft": 0,
        "inferred": 1,
        "imported": 2,
        "reviewed": 3,
        "verified": 4,
        "canonical": 5,
    }
    confidence_order = {"low": 0, "medium": 1, "high": 2}
    return (
        status_order.get(str(candidate.get("status")), -1),
        confidence_order.get(str(candidate.get("confidence")), -1),
        -int(candidate.get("missingBuild", False) or candidate.get("missingTest", False)),
        -int(candidate.get("missingSecurity", False)),
        str(candidate.get("identity", "")),
    )


def quality_reprocess_candidates(index_root: Path) -> list[dict]:
    repos_root = index_root / "repos"
    if not repos_root.is_dir():
        return []

    candidates = []
    for record_path in sorted(repos_root.glob("*/*/*/record.toml")):
        document = parse_quality_record(record_path)
        record = document.get("record", {})
        repo = document.get("repo", {})
        trust = document.get("trust") or {}
        owners = document.get("owners") or {}
        status = str(record.get("status", "unknown"))
        confidence = str(trust.get("confidence", "unknown"))
        missing_build = not bool(repo.get("build"))
        missing_test = not bool(repo.get("test"))
        security_contact = owners.get("security_contact")
        missing_security = not security_contact or security_contact == "unknown"
        needs_reprocess = (
            status in {"draft", "inferred", "imported"}
            or confidence in {"low", "medium", "unknown"}
            or missing_build
            or missing_test
            or missing_security
        )
        if not needs_reprocess:
            continue
        candidates.append(
            {
                "identity": identity_from_record_path(index_root, record_path),
                "status": status,
                "confidence": confidence,
                "missingBuild": missing_build,
                "missingTest": missing_test,
                "missingSecurity": missing_security,
            }
        )

    return sorted(candidates, key=quality_reprocess_rank)


def read_target_identities(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def write_target_identities(path: Path, identities: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{identity}\n" for identity in identities))


def existing_index_identities(index_root: Path) -> set[str]:
    repos_root = index_root / "repos"
    if not repos_root.is_dir():
        return set()
    return {
        identity_from_record_path(index_root, record_path)
        for record_path in repos_root.glob("*/*/*/record.toml")
    }


def select_refresh_batch_or_empty(
    refresh_batches: Path,
    batch_id: str,
    selected_targets: Path,
    selected_metadata: Path,
) -> bool:
    plan = load_json(refresh_batches)
    batches = plan.get("batches") or []
    if not batches:
        selected_metadata.write_text(
            json.dumps(
                {
                    "source": plan.get("source", {}),
                    "summary": plan.get("summary", {}),
                    "batch": {
                        "id": batch_id,
                        "reason": "no_scheduled_refreshes",
                        "repositoryCount": 0,
                        "repositories": [],
                    },
                },
                indent=2,
            )
        )
        write_target_identities(selected_targets, [])
        return False

    run(
        [
            "python3",
            "scripts/select_review_batch.py",
            "--input",
            str(refresh_batches),
            "--batch-id",
            batch_id,
            "--output-targets",
            str(selected_targets),
            "--output-metadata",
            str(selected_metadata),
        ]
    )
    return True


def fill_quality_reprocess_targets(
    *,
    index_root: Path,
    selected_targets: Path,
    selected_metadata: Path,
    batch_size: int,
) -> list[dict]:
    identities = read_target_identities(selected_targets)
    if len(identities) >= batch_size:
        return []

    seen = set(identities)
    additions = []
    for candidate in quality_reprocess_candidates(index_root):
        identity = candidate["identity"]
        if identity in seen:
            continue
        additions.append(candidate)
        identities.append(identity)
        seen.add(identity)
        if len(identities) >= batch_size:
            break

    if not additions:
        return []

    write_target_identities(selected_targets, identities)
    metadata = load_json(selected_metadata)
    metadata["qualityReprocessSupplement"] = {
        "reason": "lower_confidence_record",
        "repositoryCount": len(additions),
        "repositories": additions,
    }
    selected_metadata.write_text(json.dumps(metadata, indent=2) + "\n")
    return additions


def run_discovery_fill(
    *,
    discovery_json: Path,
    discovery_limit: int,
    discovery_star_bands: list[str],
) -> dict:
    command = [
        "cargo",
        "run",
        "-q",
        "-p",
        "dotrepo-crawler",
        "--",
        "discover",
        "--limit",
        str(discovery_limit),
        "--json",
    ]
    for star_band in discovery_star_bands:
        command.extend(["--star-band", star_band])
    proc = run(command)
    discovery_json.write_text(proc.stdout)
    return json.loads(proc.stdout)


def fill_discovery_targets(
    *,
    index_root: Path,
    selected_targets: Path,
    selected_metadata: Path,
    batch_size: int,
    discovery_report: dict,
) -> list[dict]:
    identities = read_target_identities(selected_targets)
    if len(identities) >= batch_size:
        return []

    seen = set(identities)
    existing = existing_index_identities(index_root)
    additions = []
    for entry in discovery_report.get("discovered") or []:
        repository = entry.get("repository") or {}
        identity = "/".join(
            [
                str(repository.get("host", "")).strip(),
                str(repository.get("owner", "")).strip(),
                str(repository.get("repo", "")).strip(),
            ]
        )
        if identity.count("/") != 2 or identity in seen or identity in existing:
            continue
        addition = {
            "identity": identity,
            "stars": entry.get("stars", 0),
            "defaultBranch": entry.get("defaultBranch"),
            "archived": bool(entry.get("archived", False)),
            "fork": bool(entry.get("fork", False)),
        }
        additions.append(addition)
        identities.append(identity)
        seen.add(identity)
        if len(identities) >= batch_size:
            break

    if not additions:
        return []

    write_target_identities(selected_targets, identities)
    metadata = load_json(selected_metadata)
    metadata["discoverySupplement"] = {
        "reason": "new_discovered_repository",
        "repositoryCount": len(additions),
        "repositories": additions,
    }
    selected_metadata.write_text(json.dumps(metadata, indent=2) + "\n")
    return additions


def now_rfc3339() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def classify_failure(message: str | None) -> str:
    text = (message or "").lower()
    if not text:
        return "unknown"
    if "toml" in text or "parse" in text or "schema" in text:
        return "parser"
    if "repo.description is required" in text or "missing" in text or "not found" in text:
        return "evidence"
    if "openrouter" in text or "model" in text or "adjudication" in text:
        return "provider"
    if "rate limit" in text or "timeout" in text or "http" in text or "network" in text:
        return "infrastructure"
    if "validate" in text or "verification" in text or "gate failed" in text:
        return "validation"
    if "write" in text or "rename" in text or "permission" in text:
        return "writeback"
    return "unknown"


def failure_fingerprint(message: str | None) -> str:
    text = " ".join((message or "unknown").split())
    if len(text) > 120:
        return text[:117] + "..."
    return text or "unknown"


def fixture_slug(value: str) -> str:
    slug = []
    previous_dash = False
    for char in value.lower():
        if char.isalnum():
            slug.append(char)
            previous_dash = False
        elif not previous_dash:
            slug.append("-")
            previous_dash = True
        if len(slug) >= 80:
            break
    return "".join(slug).strip("-") or "unknown-failure"


def enrich_telemetry(telemetry: dict, args: argparse.Namespace) -> dict:
    crawls = telemetry.get("crawls") or []
    failure_classes: Counter[str] = Counter()
    failure_fingerprints: Counter[str] = Counter()
    failure_fingerprint_classes: dict[str, str] = {}
    promoted = 0

    for crawl in crawls:
        if crawl.get("status") == "failed":
            failure_class = classify_failure(crawl.get("error"))
            crawl["failureClass"] = failure_class
            failure_classes[failure_class] += 1
            fingerprint = failure_fingerprint(crawl.get("error"))
            failure_fingerprints[fingerprint] += 1
            failure_fingerprint_classes.setdefault(fingerprint, failure_class)
        if crawl.get("recordStatus") == "verified":
            promoted += 1

    telemetry.update(
        {
            "schema": "dotrepo/autonomous-telemetry/v0.1",
            "generatedAt": now_rfc3339(),
            "indexRoot": args.index_root,
            "statePath": args.state_path,
            "batchSize": args.batch_size,
            "refreshLimit": args.limit,
            "adjudicationCallBudget": telemetry.get("adjudicationCallBudget", 0),
            "adjudicationBudgetExhausted": telemetry.get("adjudicationBudgetExhausted", False),
            "repositoriesByAdjudicationTier": adjudication_tier_counts(crawls),
            "failureClasses": dict(sorted(failure_classes.items())),
            "failureFingerprints": dict(sorted(failure_fingerprints.items())),
            "failureFingerprintClasses": dict(sorted(failure_fingerprint_classes.items())),
            "promoted": promoted,
            "zeroModelRuns": sum(
                1 for item in crawls if int(item.get("adjudicationCalls") or 0) == 0
            ),
        }
    )
    return telemetry


def load_retained_runs(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    runs = []
    for line_number, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            runs.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(
                f"failed to parse retained telemetry {path}:{line_number}: {exc}"
            ) from exc
    return runs


def aggregate_runs(runs: list[dict]) -> dict:
    totals = Counter()
    failure_classes: Counter[str] = Counter()
    failure_fingerprints: Counter[str] = Counter()
    failure_fingerprint_classes: dict[str, str] = {}
    tier_counts: Counter[str] = Counter()
    first_run = None
    last_run = None

    for run_telemetry in runs:
        generated_at = run_telemetry.get("generatedAt")
        if generated_at:
            first_run = generated_at if first_run is None else min(first_run, generated_at)
            last_run = generated_at if last_run is None else max(last_run, generated_at)
        for key in (
            "crawled",
            "written",
            "failed",
            "skipped",
            "qualityReprocessQueued",
            "discoveryQueued",
            "adjudicationCallBudget",
            "adjudicationCalls",
            "tokensUsed",
            "promoted",
            "zeroModelRuns",
        ):
            totals[key] += int(run_telemetry.get(key) or 0)
        for failure_class, count in (run_telemetry.get("failureClasses") or {}).items():
            failure_classes[str(failure_class)] += int(count or 0)
        for fingerprint, count in (run_telemetry.get("failureFingerprints") or {}).items():
            failure_fingerprints[str(fingerprint)] += int(count or 0)
        for fingerprint, failure_class in (
            run_telemetry.get("failureFingerprintClasses") or {}
        ).items():
            failure_fingerprint_classes.setdefault(str(fingerprint), str(failure_class))
        for tier, count in (run_telemetry.get("repositoriesByAdjudicationTier") or {}).items():
            tier_counts[str(tier)] += int(count or 0)

    crawled = totals["crawled"]
    repos_with_adjudication = crawled - totals["zeroModelRuns"]
    recurring_failures = [
        {"fingerprint": fingerprint, "count": count}
        for fingerprint, count in failure_fingerprints.most_common(20)
        if count > 1
    ]
    return {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": now_rfc3339(),
        "runCount": len(runs),
        "firstRunAt": first_run,
        "lastRunAt": last_run,
        "totals": dict(sorted(totals.items())),
        "rates": {
            "writeRate": totals["written"] / crawled if crawled else 0.0,
            "failureRate": totals["failed"] / crawled if crawled else 0.0,
            "adjudicationRate": repos_with_adjudication / crawled if crawled else 0.0,
            "zeroModelRate": totals["zeroModelRuns"] / crawled if crawled else 0.0,
            "promotionRate": totals["promoted"] / crawled if crawled else 0.0,
        },
        "repositoriesByAdjudicationTier": dict(sorted(tier_counts.items())),
        "failureClasses": dict(sorted(failure_classes.items())),
        "recurringFailures": recurring_failures,
        "regressionFixtureCandidates": [
            {
                "failureClass": failure_fingerprint_classes.get(
                    item["fingerprint"], "unknown"
                ),
                "fingerprint": item["fingerprint"],
                "count": item["count"],
                "suggestedFixture": fixture_slug(item["fingerprint"]),
            }
            for item in recurring_failures
        ],
    }


def retain_telemetry(
    telemetry: dict, history_path: Path, summary_path: Path
) -> dict:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(telemetry, sort_keys=True, separators=(",", ":")) + "\n")

    runs = load_retained_runs(history_path)
    summary = aggregate_runs(runs)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def render_regression_fixture_candidates_markdown(candidates: list[dict]) -> str:
    lines = [
        "# Regression Fixture Candidates",
        "",
        "Recurring autonomous crawl failures that should become deterministic fixes or regression fixtures.",
        "",
    ]
    if not candidates:
        lines.append("No recurring failure fingerprints have been observed yet.")
        return "\n".join(lines).rstrip() + "\n"

    for item in candidates:
        lines.extend(
            [
                f"## {item.get('suggestedFixture', 'unknown-failure')}",
                "",
                f"- failure class: `{item.get('failureClass', 'unknown')}`",
                f"- observed runs: {item.get('count', 0)}",
                f"- fingerprint: `{item.get('fingerprint', 'unknown')}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_regression_fixture_candidate_artifacts(
    summary: dict,
    json_path: Path,
    md_path: Path,
) -> None:
    candidates = summary.get("regressionFixtureCandidates") or []
    payload = {
        "schema": "dotrepo/regression-fixture-candidates/v0.1",
        "generatedAt": summary.get("generatedAt"),
        "sourceSummary": summary.get("schema"),
        "candidateCount": len(candidates),
        "candidates": candidates,
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_regression_fixture_candidates_markdown(candidates))


def render_regression_fixture_stub_readme(candidate: dict) -> str:
    fixture = candidate.get("suggestedFixture", "unknown-failure")
    failure_class = candidate.get("failureClass", "unknown")
    fingerprint = candidate.get("fingerprint", "unknown")
    count = candidate.get("count", 0)
    lines = [
        f"# {fixture}",
        "",
        "This stub was generated from recurring autonomous index failure telemetry.",
        "",
        f"- failure class: `{failure_class}`",
        f"- observed runs: {count}",
        f"- fingerprint: `{fingerprint}`",
        "",
        "## Materialization Checklist",
        "",
        "- Add the smallest repository source fixture that reproduces this failure.",
        "- Add or update the matching quality-gate expectation.",
        "- Add the deterministic parser, evidence, provider, infrastructure, or validation fix.",
        "- Run the relevant focused regression test before removing this stub.",
        "",
    ]
    return "\n".join(lines)


def write_regression_fixture_stub_artifacts(candidates: list[dict], stub_root: Path) -> None:
    stub_root.mkdir(parents=True, exist_ok=True)
    for candidate in candidates:
        fixture = fixture_slug(str(candidate.get("suggestedFixture") or candidate.get("fingerprint") or "unknown-failure"))
        destination = stub_root / fixture
        destination.mkdir(parents=True, exist_ok=True)
        metadata = {
            "schema": "dotrepo/regression-fixture-stub/v0.1",
            "fixture": fixture,
            "failureClass": candidate.get("failureClass", "unknown"),
            "fingerprint": candidate.get("fingerprint", "unknown"),
            "observedRuns": candidate.get("count", 0),
            "status": "needs_materialization",
        }
        (destination / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
        (destination / "README.md").write_text(render_regression_fixture_stub_readme(candidate))


def write_telemetry_outputs(telemetry: dict, args: argparse.Namespace, telemetry_path: Path) -> None:
    telemetry = enrich_telemetry(telemetry, args)
    telemetry_path.write_text(json.dumps(telemetry, indent=2, sort_keys=True) + "\n")
    summary = retain_telemetry(
        telemetry,
        Path(args.telemetry_history),
        Path(args.telemetry_summary),
    )
    write_regression_fixture_candidate_artifacts(
        summary,
        Path(args.regression_fixture_candidates_json),
        Path(args.regression_fixture_candidates_md),
    )
    write_regression_fixture_stub_artifacts(
        summary.get("regressionFixtureCandidates") or [],
        Path(args.regression_fixture_stub_dir),
    )


def main() -> int:
    args = parse_args()
    if not args.skip_automation_enabled_check and os.environ.get(
        "INDEX_AUTOMATION_ENABLED", "true"
    ).lower() not in {"1", "true", "yes"}:
        print("INDEX_AUTOMATION_ENABLED is not true; skipping autonomous batch", file=sys.stderr)
        return 0

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    adjudication_call_budget = resolve_adjudication_call_budget(args)
    discovery_limit = resolve_discovery_limit(args)
    remaining_adjudication_calls = adjudication_call_budget
    adjudication_budget_conservatively_exhausted = False
    base_env = os.environ.copy()

    refresh_plan = output_dir / "refresh-plan.json"
    refresh_batches = output_dir / "refresh-batches.json"
    discovery_json = output_dir / "discovery-fill.json"
    selected_targets = output_dir / "selected-targets.txt"
    selected_metadata = output_dir / "selected-batch.json"
    telemetry_path = output_dir / "telemetry.json"

    proc = run(
        [
            "cargo",
            "run",
            "-q",
            "-p",
            "dotrepo-crawler",
            "--",
            "refresh-plan",
            "--state-path",
            args.state_path,
            "--limit",
            str(args.limit),
            "--json",
        ]
    )
    refresh_plan.write_text(proc.stdout)

    run(
        [
            "python3",
            "scripts/plan_refresh_review_batches.py",
            "--input",
            str(refresh_plan),
            "--batch-size",
            str(args.batch_size),
            "--output-json",
            str(refresh_batches),
            "--output-md",
            str(output_dir / "refresh-batches.md"),
        ]
    )

    selected_refresh_batch = select_refresh_batch_or_empty(
        refresh_batches,
        args.batch_id,
        selected_targets,
        selected_metadata,
    )
    quality_reprocess_additions = []
    if not args.disable_quality_reprocess:
        quality_reprocess_additions = fill_quality_reprocess_targets(
            index_root=Path(args.index_root),
            selected_targets=selected_targets,
            selected_metadata=selected_metadata,
            batch_size=args.batch_size,
        )
    discovery_additions = []
    if not args.disable_discovery and len(read_target_identities(selected_targets)) < args.batch_size:
        discovery_report = run_discovery_fill(
            discovery_json=discovery_json,
            discovery_limit=discovery_limit,
            discovery_star_bands=args.discovery_star_band,
        )
        discovery_additions = fill_discovery_targets(
            index_root=Path(args.index_root),
            selected_targets=selected_targets,
            selected_metadata=selected_metadata,
            batch_size=args.batch_size,
            discovery_report=discovery_report,
        )

    crawls: list[dict] = []
    if not selected_targets.is_file() or selected_targets.stat().st_size == 0:
        telemetry = {
            "batchId": args.batch_id,
            "crawled": 0,
            "written": 0,
            "failed": 0,
            "skipped": 0,
            "adjudicationCalls": 0,
            "tokensUsed": 0,
            "adjudicationRate": 0.0,
            "adjudicationCallBudget": adjudication_call_budget,
            "adjudicationBudgetExhausted": False,
            "selectedRefreshBatch": selected_refresh_batch,
            "qualityReprocessQueued": len(quality_reprocess_additions),
            "discoveryQueued": len(discovery_additions),
            "crawls": crawls,
        }
        write_telemetry_outputs(telemetry, args, telemetry_path)
        print("No refresh targets in selected batch")
        return 0

    for line in selected_targets.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        host, owner, repo = line.split("/", 2)
        entry = {"repository": f"{host}/{owner}/{repo}", "status": "failed"}
        crawls.append(entry)
        try:
            crawl_env = crawl_env_for_remaining_budget(
                base_env, remaining_adjudication_calls
            )
            entry["adjudicationCallBudgetBefore"] = remaining_adjudication_calls
            proc = run(
                [
                    "cargo",
                    "run",
                    "-q",
                    "-p",
                    "dotrepo-crawler",
                    "--",
                    "crawl",
                    "--index-root",
                    args.index_root,
                    "--state-path",
                    args.state_path,
                    "--host",
                    host,
                    "--owner",
                    owner,
                    "--repo",
                    repo,
                    "--write",
                    "--json",
                ],
                check=False,
                env=crawl_env,
            )
            if proc.returncode == 0:
                payload = json.loads(proc.stdout)
                entry["status"] = "written" if payload.get("wrote") else "skipped"
                entry["manifestPath"] = payload.get("manifestPath")
                escalation = payload.get("escalation") or {}
                entry["escalation"] = escalation
                entry["adjudicationCalls"] = int(escalation.get("modelCalls") or 0)
                entry["tokensUsed"] = int(escalation.get("tokensUsed") or 0)
                entry["recordStatus"] = payload.get("recordStatus")
                remaining_adjudication_calls = max(
                    0,
                    remaining_adjudication_calls - entry["adjudicationCalls"],
                )
                entry["adjudicationCallBudgetAfter"] = remaining_adjudication_calls
            else:
                entry["status"] = "failed"
                entry["error"] = (proc.stderr or proc.stdout).strip()[-500:]
                if adjudication_enabled(crawl_env):
                    remaining_adjudication_calls = 0
                    adjudication_budget_conservatively_exhausted = True
                    entry["adjudicationBudgetConservativelyExhausted"] = True
                    entry["adjudicationCallBudgetAfter"] = remaining_adjudication_calls
        except Exception as exc:  # noqa: BLE001 - batch telemetry should continue
            entry["status"] = "failed"
            entry["error"] = str(exc)

    written = sum(1 for item in crawls if item["status"] == "written")
    failed = sum(1 for item in crawls if item["status"] == "failed")
    skipped = sum(1 for item in crawls if item["status"] == "skipped")
    adjudication_calls = sum(int(item.get("adjudicationCalls") or 0) for item in crawls)
    tokens_used = sum(int(item.get("tokensUsed") or 0) for item in crawls)
    repos_with_adjudication = sum(
        1 for item in crawls if int(item.get("adjudicationCalls") or 0) > 0
    )
    adjudication_rate = (
        repos_with_adjudication / len(crawls) if crawls else 0.0
    )

    if written > 0:
        run(["cargo", "run", "-q", "-p", "dotrepo-cli", "--", "validate-index"])

    telemetry = {
        "batchId": args.batch_id,
        "crawled": len(crawls),
        "written": written,
        "failed": failed,
        "skipped": skipped,
        "adjudicationCalls": adjudication_calls,
        "tokensUsed": tokens_used,
        "adjudicationRate": adjudication_rate,
        "adjudicationCallBudget": adjudication_call_budget,
        "adjudicationBudgetExhausted": (
            adjudication_budget_conservatively_exhausted
            or (
                adjudication_call_budget > 0
                and remaining_adjudication_calls == 0
                and adjudication_calls >= adjudication_call_budget
            )
        ),
        "selectedRefreshBatch": selected_refresh_batch,
        "qualityReprocessQueued": len(quality_reprocess_additions),
        "discoveryQueued": len(discovery_additions),
        "crawls": crawls,
    }
    write_telemetry_outputs(telemetry, args, telemetry_path)
    print(json.dumps(telemetry, indent=2, sort_keys=True))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
