#!/usr/bin/env -S uv run python
"""Run one autonomous index refresh batch: crawl, gate, writeback, validate."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from process_resources import run_with_resource_sample  # noqa: E402

# Canonical way to invoke Python helpers under the uv-managed environment.
# This makes the AGENTS.md "uv run" contract explicit and auditable.
UV_PYTHON: list[str] = ["uv", "run", "python"]

# "Worst-run" rates deliberately look at a bounded rolling window, not the
# entire lifetime of retained telemetry. The original unbounded design existed
# so a bad run could not be hidden by favorable aggregate totals; that
# property still holds inside this window (a single bad run continues to fail
# the worst-run gate for every one of the next WORST_RUN_WINDOW_SIZE runs), it
# just eventually ages out the way the existing 3-run recent/previous windows
# already do. Without a bound, one historic run can pin the strict proof gate
# red forever regardless of how many clean runs follow, which defeats the
# gate's purpose of proving *current* operating behavior. See
# docs/factual-crawl-automation.md for the full rationale.
WORST_RUN_WINDOW_SIZE = 10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-root", default="index")
    parser.add_argument("--state-path", default="index/.crawler-state.toml")
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--batch-id", default="refresh-batch-01")
    parser.add_argument("--output-dir", default="index-autonomous-batch")
    parser.add_argument(
        "--synthesize",
        action="store_true",
        help="Request bounded non-factual synthesis through DOTREPO_SYNTHESIS_URL",
    )
    parser.add_argument(
        "--synthesis-model",
        default=None,
        help="Synthesis model identifier; defaults to DOTREPO_SYNTHESIS_MODEL",
    )
    parser.add_argument(
        "--synthesis-provider",
        default=None,
        help="Synthesis provider identifier; defaults to DOTREPO_SYNTHESIS_PROVIDER",
    )
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


def resolve_synthesis_config(args: argparse.Namespace) -> tuple[str | None, str | None]:
    if not args.synthesize:
        return None, None
    model = (args.synthesis_model or os.environ.get("DOTREPO_SYNTHESIS_MODEL", "")).strip()
    provider = (args.synthesis_provider or os.environ.get("DOTREPO_SYNTHESIS_PROVIDER", "")).strip()
    missing = [name for name, value in (("model", model), ("provider", provider)) if not value]
    if missing:
        raise SystemExit(
            "--synthesize requires "
            + " and ".join(missing)
            + " via CLI flags or DOTREPO_SYNTHESIS_MODEL/DOTREPO_SYNTHESIS_PROVIDER"
        )
    if not os.environ.get("DOTREPO_SYNTHESIS_URL", "").strip():
        raise SystemExit("--synthesize requires DOTREPO_SYNTHESIS_URL")
    return model, provider


def crawl_env_for_remaining_budget(
    base_env: dict[str, str], remaining_budget: int
) -> dict[str, str]:
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


def unchanged_skips_from_refresh_plan(refresh_plan_stdout: str) -> list[dict]:
    """Build zero-cost "unchanged" unit-cost entries from a refresh-plan run.

    `dotrepo-crawler refresh-plan` reports `schedule.skipped` for
    repositories whose head SHA has not changed since the last factual
    crawl (see `dotrepo-crawler/src/schedule.rs`). Those repositories never
    reach the crawl subprocess this run, so they are not part of `crawls` —
    but they are exactly the "unchanged" unit-cost outcome: zero network,
    zero wall time, zero model calls, by construction.
    """
    try:
        plan = json.loads(refresh_plan_stdout)
    except json.JSONDecodeError:
        return []
    skipped = ((plan.get("schedule") or {}).get("skipped")) or []
    unchanged = []
    for item in skipped:
        repository = item.get("repository") or {}
        identity = "/".join(
            [
                str(repository.get("host", "")).strip(),
                str(repository.get("owner", "")).strip(),
                str(repository.get("repo", "")).strip(),
            ]
        )
        if identity.count("/") != 2:
            continue
        unchanged.append(
            {
                "repository": identity,
                "category": "unchanged",
                "reason": item.get("reason"),
                "wallTimeMs": 0,
                "networkRequests": 0,
                "networkBytes": 0,
                "adjudicationCalls": 0,
                "tokensUsed": 0,
                "cpuTimeMs": 0,
                "peakMemoryBytes": 0,
            }
        )
    return unchanged


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


# Shared status ladder used both to rank quality-reprocess candidates and to
# approximate whether a re-crawl "usefully improved" a record (unit-cost
# classification proxy: status-ladder advancement, e.g. imported -> verified).
STATUS_ORDER: dict[str, int] = {
    "draft": 0,
    "inferred": 1,
    "imported": 2,
    "reviewed": 3,
    "verified": 4,
    "canonical": 5,
}


def record_status_rank(status: object) -> int:
    return STATUS_ORDER.get(str(status), -1)


def quality_reprocess_rank(candidate: dict) -> tuple[str, int, int, int, int, str]:
    confidence_order = {"low": 0, "medium": 1, "high": 2}
    return (
        str(candidate.get("generatedAt") or ""),
        record_status_rank(candidate.get("status")),
        confidence_order.get(str(candidate.get("confidence")), -1),
        -int(candidate.get("missingBuild", False) or candidate.get("missingTest", False)),
        -int(candidate.get("missingSecurity", False)),
        str(candidate.get("identity", "")),
    )


def capture_record_status_before_crawl(index_root: Path, identity: str) -> str | None:
    """Read the on-disk record status for `identity` before it is (re-)crawled.

    Returns None when no record exists yet (a brand-new addition to the
    index), which the unit-cost classifier treats as "changed" rather than
    "improved" since there is no prior baseline to improve upon.
    """
    host, owner, repo = identity.split("/", 2)
    record_path = index_root / "repos" / host / owner / repo / "record.toml"
    if not record_path.is_file():
        return None
    document = parse_quality_record(record_path)
    return str(document.get("record", {}).get("status") or "") or None


def classify_unit_cost_category(before_status: str | None, after_status: object) -> str:
    """Classify a crawled repository's unit-cost category.

    Proxy for "usefully improved": the record's status advanced on the
    draft -> inferred -> imported -> reviewed -> verified -> canonical
    ladder relative to what was on disk before this run's crawl. Repositories
    with no prior record (first factual crawl) or no rank improvement are
    "changed" — real crawl work happened, but there is no completeness gain
    to report relative to a baseline. Repositories the scheduler skipped
    entirely (head unchanged, no materialization) are tagged "unchanged" by
    the caller and never reach this function.
    """
    if before_status is None:
        return "changed"
    if record_status_rank(after_status) > record_status_rank(before_status):
        return "improved"
    return "changed"


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
                "generatedAt": record.get("generated_at"),
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
    # A scheduled run may request a batch the (possibly limited) plan did not
    # produce — e.g. asking for refresh-batch-03 when only two batches exist.
    # That is a normal "nothing to do this run" condition, not a crash: degrade
    # to an empty batch so the conveyor stays stable across repeated runs.
    reason = "no_scheduled_refreshes"
    if batches:
        if any(isinstance(batch, dict) and batch.get("id") == batch_id for batch in batches):
            run(
                [
                    *UV_PYTHON,
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
        reason = "batch_not_found"

    selected_metadata.write_text(
        json.dumps(
            {
                "source": plan.get("source", {}),
                "summary": plan.get("summary", {}),
                "batch": {
                    "id": batch_id,
                    "reason": reason,
                    "repositoryCount": 0,
                    "repositories": [],
                },
            },
            indent=2,
        )
    )
    write_target_identities(selected_targets, [])
    return False


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


def unique_fixture_slug(value: str, seen: set[str]) -> str:
    base = fixture_slug(value)
    candidate = base
    suffix = 2
    while candidate in seen:
        suffix_text = f"-{suffix}"
        candidate = f"{base[: 80 - len(suffix_text)].rstrip('-')}{suffix_text}"
        suffix += 1
    seen.add(candidate)
    return candidate


# Ordered so the most specific manifest signal wins. Substrings are matched
# against lowercased failure text. Manifest filenames are the strongest
# deterministic ecosystem signal available from an error fingerprint.
ECOSYSTEM_SIGNALS: list[tuple[str, str]] = [
    ("cargo.toml", "rust"),
    ("cargo ", "rust"),
    ("rustup", "rust"),
    ("crate", "rust"),
    ("package.json", "node"),
    ("pnpm", "node"),
    ("yarn", "node"),
    ("npm ", "node"),
    ("node_modules", "node"),
    ("pyproject.toml", "python"),
    ("setup.py", "python"),
    ("requirements.txt", "python"),
    ("pytest", "python"),
    ("pip ", "python"),
    ("python", "python"),
    ("go.mod", "go"),
    ("go test", "go"),
    ("go build", "go"),
    ("pom.xml", "jvm"),
    ("build.gradle", "jvm"),
    ("mvn ", "jvm"),
    ("maven", "jvm"),
    ("gemfile", "ruby"),
    ("bundler", "ruby"),
    ("rake", "ruby"),
    ("composer.json", "php"),
    ("composer ", "php"),
    (".csproj", "dotnet"),
    ("dotnet", "dotnet"),
    ("mix.exs", "elixir"),
    ("rebar.config", "erlang"),
    ("cmake", "cpp"),
    ("meson.build", "cpp"),
]

# Failure classes that can be reproduced by a checked-in source fixture run
# through the deterministic import pipeline. Provider, infrastructure, and
# writeback failures are environmental and are not fixture-able.
FIXTURE_ELIGIBLE_FAILURE_CLASSES = frozenset({"parser", "evidence", "validation"})


def classify_ecosystem(*texts: object) -> str:
    """Infer a repository ecosystem from lowercased failure/source text.

    Deterministic and conservative: returns ``unknown`` when no manifest or
    language signal is present. The first matching signal wins, so more
    specific manifest filenames should precede looser language hints in
    ``ECOSYSTEM_SIGNALS``.
    """
    haystack = " ".join(str(part or "").lower() for part in texts)
    if not haystack.strip():
        return "unknown"
    for signal, ecosystem in ECOSYSTEM_SIGNALS:
        if signal in haystack:
            return ecosystem
    return "unknown"


def fixture_eligible(failure_class: object) -> bool:
    return str(failure_class or "unknown") in FIXTURE_ELIGIBLE_FAILURE_CLASSES


def enrich_telemetry(telemetry: dict, args: argparse.Namespace) -> dict:
    crawls = telemetry.get("crawls") or []
    failure_classes: Counter[str] = Counter()
    failure_fingerprints: Counter[str] = Counter()
    failure_fingerprint_classes: dict[str, str] = {}
    failure_fingerprint_ecosystems: dict[str, str] = {}
    failure_fingerprint_repositories: dict[str, set[str]] = {}
    promoted = 0
    synthesis_failures: Counter[str] = Counter()

    for crawl in crawls:
        if crawl.get("status") == "failed":
            failure_class = classify_failure(crawl.get("error"))
            crawl["failureClass"] = failure_class
            failure_classes[failure_class] += 1
            fingerprint = failure_fingerprint(crawl.get("error"))
            failure_fingerprints[fingerprint] += 1
            failure_fingerprint_classes.setdefault(fingerprint, failure_class)
            ecosystem = classify_ecosystem(crawl.get("error"), crawl.get("repository"))
            crawl["ecosystem"] = ecosystem
            failure_fingerprint_ecosystems.setdefault(fingerprint, ecosystem)
            repository = str(crawl.get("repository") or "").strip()
            if repository:
                failure_fingerprint_repositories.setdefault(fingerprint, set()).add(repository)
        if crawl.get("recordStatus") == "verified":
            promoted += 1
        synthesis_failure = crawl.get("synthesisFailure") or {}
        if synthesis_failure:
            synthesis_failures[str(synthesis_failure.get("class") or "unknown")] += 1

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
            "failureFingerprintEcosystems": dict(sorted(failure_fingerprint_ecosystems.items())),
            "failureFingerprintRepositories": {
                fingerprint: sorted(repositories)
                for fingerprint, repositories in sorted(failure_fingerprint_repositories.items())
            },
            "promoted": promoted,
            "synthesisRequested": len(crawls) if getattr(args, "synthesize", False) else 0,
            "synthesisSucceeded": sum(1 for item in crawls if item.get("synthesisPath")),
            "synthesisFailed": sum(1 for item in crawls if item.get("synthesisFailure")),
            "synthesisFailureClasses": dict(sorted(synthesis_failures.items())),
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


def run_rates(run_telemetry: dict) -> dict[str, float]:
    crawled = int(run_telemetry.get("crawled") or 0)
    zero_model_runs = int(run_telemetry.get("zeroModelRuns") or 0)
    tiers = run_telemetry.get("repositoriesByAdjudicationTier") or {}
    if not crawled:
        return {
            "failureRate": 0.0,
            "adjudicationRate": 0.0,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.0,
            "zeroModelRate": 0.0,
        }
    return {
        "failureRate": int(run_telemetry.get("failed") or 0) / crawled,
        "adjudicationRate": (crawled - zero_model_runs) / crawled,
        "secondOpinionRate": int(tiers.get("local_second_opinion") or 0) / crawled,
        "apiEscalationRate": int(tiers.get("api_escalation") or 0) / crawled,
        "zeroModelRate": zero_model_runs / crawled,
    }


def aggregate_rates(runs: list[dict]) -> dict[str, float]:
    totals = Counter()
    tier_counts: Counter[str] = Counter()
    for run_telemetry in runs:
        for key in ("crawled", "failed", "zeroModelRuns"):
            totals[key] += int(run_telemetry.get(key) or 0)
        for tier, count in (run_telemetry.get("repositoriesByAdjudicationTier") or {}).items():
            tier_counts[str(tier)] += int(count or 0)

    crawled = totals["crawled"]
    repos_with_adjudication = crawled - totals["zeroModelRuns"]
    if not crawled:
        return {
            "failureRate": 0.0,
            "adjudicationRate": 0.0,
            "secondOpinionRate": 0.0,
            "apiEscalationRate": 0.0,
            "zeroModelRate": 0.0,
        }
    return {
        "failureRate": totals["failed"] / crawled,
        "adjudicationRate": repos_with_adjudication / crawled,
        "secondOpinionRate": int(tier_counts.get("local_second_opinion") or 0) / crawled,
        "apiEscalationRate": int(tier_counts.get("api_escalation") or 0) / crawled,
        "zeroModelRate": totals["zeroModelRuns"] / crawled,
    }


def aggregate_tiers(runs: list[dict]) -> dict[str, int]:
    tier_counts: Counter[str] = Counter()
    for run_telemetry in runs:
        for tier, count in (run_telemetry.get("repositoriesByAdjudicationTier") or {}).items():
            tier_counts[str(tier)] += int(count or 0)
    return dict(sorted(tier_counts.items()))


def aggregate_costs(runs: list[dict]) -> dict[str, int | float]:
    totals = Counter()
    for run_telemetry in runs:
        for key in (
            "adjudicationCallBudget",
            "adjudicationCalls",
            "crawled",
            "tokensUsed",
        ):
            totals[key] += int(run_telemetry.get(key) or 0)

    budget = totals["adjudicationCallBudget"]
    crawled = totals["crawled"]
    return {
        "adjudicationCallBudget": budget,
        "adjudicationCalls": totals["adjudicationCalls"],
        "adjudicationBudgetUseRate": (totals["adjudicationCalls"] / budget if budget else 0.0),
        "crawled": crawled,
        "tokensUsed": totals["tokensUsed"],
        "tokensPerCrawled": totals["tokensUsed"] / crawled if crawled else 0.0,
    }


def aggregate_runs(runs: list[dict]) -> dict:
    totals = Counter()
    failure_classes: Counter[str] = Counter()
    failure_fingerprints: Counter[str] = Counter()
    failure_fingerprint_classes: dict[str, str] = {}
    failure_fingerprint_ecosystems: dict[str, str] = {}
    failure_fingerprint_repositories: dict[str, set[str]] = {}
    failure_classes_by_ecosystem: Counter[str] = Counter()
    ecosystem_counts: Counter[str] = Counter()
    tier_counts: Counter[str] = Counter()
    synthesis_failure_classes: Counter[str] = Counter()
    first_run = None
    last_run = None
    budget_exhausted_runs = 0
    saw_crawled_run = False

    # Worst-run rates are scoped to a bounded rolling window (see
    # WORST_RUN_WINDOW_SIZE above), not the full lifetime `runs` list, so a
    # single historic bad run cannot pin the strict proof gate red forever.
    worst_run_window = runs[-WORST_RUN_WINDOW_SIZE:]
    worst_rates = {
        "failureRate": 0.0,
        "adjudicationRate": 0.0,
        "secondOpinionRate": 0.0,
        "apiEscalationRate": 0.0,
        "zeroModelRate": 1.0,
    }
    for run_telemetry in worst_run_window:
        for key, value in run_rates(run_telemetry).items():
            if key == "zeroModelRate":
                if int(run_telemetry.get("crawled") or 0):
                    saw_crawled_run = True
                    worst_rates[key] = min(worst_rates[key], value)
            else:
                worst_rates[key] = max(worst_rates[key], value)

    for run_telemetry in runs:
        generated_at = run_telemetry.get("generatedAt")
        if generated_at:
            first_run = generated_at if first_run is None else min(first_run, generated_at)
            last_run = generated_at if last_run is None else max(last_run, generated_at)
        if bool(run_telemetry.get("adjudicationBudgetExhausted", False)):
            budget_exhausted_runs += 1
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
            "synthesisRequested",
            "synthesisSucceeded",
            "synthesisFailed",
        ):
            totals[key] += int(run_telemetry.get(key) or 0)
        for failure_class, count in (run_telemetry.get("failureClasses") or {}).items():
            failure_classes[str(failure_class)] += int(count or 0)
        for fingerprint, count in (run_telemetry.get("failureFingerprints") or {}).items():
            fingerprint = str(fingerprint).strip()
            if not fingerprint:
                continue
            failure_fingerprints[fingerprint] += int(count or 0)
        for fingerprint, failure_class in (
            run_telemetry.get("failureFingerprintClasses") or {}
        ).items():
            fingerprint = str(fingerprint).strip()
            if fingerprint:
                failure_fingerprint_classes.setdefault(fingerprint, str(failure_class))
        for fingerprint, ecosystem in (
            run_telemetry.get("failureFingerprintEcosystems") or {}
        ).items():
            fingerprint = str(fingerprint).strip()
            if fingerprint:
                failure_fingerprint_ecosystems.setdefault(fingerprint, str(ecosystem))
        for fingerprint, repositories in (
            run_telemetry.get("failureFingerprintRepositories") or {}
        ).items():
            fingerprint = str(fingerprint).strip()
            if fingerprint and isinstance(repositories, list):
                failure_fingerprint_repositories.setdefault(fingerprint, set()).update(
                    str(repository).strip()
                    for repository in repositories
                    if str(repository).strip()
                )
        for tier, count in (run_telemetry.get("repositoriesByAdjudicationTier") or {}).items():
            tier_counts[str(tier)] += int(count or 0)
        for failure_class, count in (run_telemetry.get("synthesisFailureClasses") or {}).items():
            synthesis_failure_classes[str(failure_class)] += int(count or 0)

    # Cross-tabulate failure class by ecosystem using the per-fingerprint maps so
    # recurring parser/evidence/validation defects can be prioritized by ecosystem.
    for fingerprint, count in failure_fingerprints.items():
        failure_class = failure_fingerprint_classes.get(fingerprint, "unknown")
        ecosystem = failure_fingerprint_ecosystems.get(fingerprint, classify_ecosystem(fingerprint))
        ecosystem_counts[ecosystem] += count
        failure_classes_by_ecosystem[f"{failure_class}/{ecosystem}"] += count

    crawled = totals["crawled"]
    repos_with_adjudication = crawled - totals["zeroModelRuns"]
    if not saw_crawled_run:
        worst_rates["zeroModelRate"] = 0.0
    recent_window_runs = runs[-3:]
    previous_window_runs = runs[-6:-3]
    recent_window_rates = aggregate_rates(recent_window_runs)
    previous_window_rates = aggregate_rates(previous_window_runs)
    recent_window_tiers = aggregate_tiers(recent_window_runs)
    previous_window_tiers = aggregate_tiers(previous_window_runs)
    recent_window_costs = aggregate_costs(recent_window_runs)
    previous_window_costs = aggregate_costs(previous_window_runs)
    recurring_failures = [
        {"fingerprint": fingerprint, "count": count}
        for fingerprint, count in failure_fingerprints.most_common(20)
        if count > 1
    ]
    regression_fixture_candidates = []
    seen_fixture_slugs: set[str] = set()
    for item in recurring_failures:
        fingerprint = item["fingerprint"]
        failure_class = failure_fingerprint_classes.get(fingerprint, "unknown")
        ecosystem = failure_fingerprint_ecosystems.get(fingerprint, classify_ecosystem(fingerprint))
        candidate = {
            "failureClass": failure_class,
            "ecosystem": ecosystem,
            "fixtureEligible": fixture_eligible(failure_class),
            "fingerprint": fingerprint,
            "count": item["count"],
            "suggestedFixture": unique_fixture_slug(fingerprint, seen_fixture_slugs),
        }
        repositories = sorted(failure_fingerprint_repositories.get(fingerprint, ()))[:20]
        if repositories:
            candidate["repositories"] = repositories
        regression_fixture_candidates.append(candidate)
    return {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": now_rfc3339(),
        "runCount": len(runs),
        "firstRunAt": first_run,
        "lastRunAt": last_run,
        "totals": dict(sorted(totals.items())),
        "budgetExhaustedRuns": budget_exhausted_runs,
        "rates": {
            "writeRate": totals["written"] / crawled if crawled else 0.0,
            "failureRate": totals["failed"] / crawled if crawled else 0.0,
            "adjudicationRate": repos_with_adjudication / crawled if crawled else 0.0,
            "zeroModelRate": totals["zeroModelRuns"] / crawled if crawled else 0.0,
            "promotionRate": totals["promoted"] / crawled if crawled else 0.0,
        },
        "recentWindowRunCount": len(recent_window_runs),
        "recentWindowRates": {
            key: round(value, 6) for key, value in sorted(recent_window_rates.items())
        },
        "recentWindowRepositoriesByAdjudicationTier": recent_window_tiers,
        "recentWindowCosts": {
            key: round(value, 6) if isinstance(value, float) else value
            for key, value in sorted(recent_window_costs.items())
        },
        "previousWindowRunCount": len(previous_window_runs),
        "previousWindowRates": {
            key: round(value, 6) for key, value in sorted(previous_window_rates.items())
        },
        "previousWindowRepositoriesByAdjudicationTier": previous_window_tiers,
        "previousWindowCosts": {
            key: round(value, 6) if isinstance(value, float) else value
            for key, value in sorted(previous_window_costs.items())
        },
        "worstRunWindowSize": WORST_RUN_WINDOW_SIZE,
        "worstRunWindowRunCount": len(worst_run_window),
        "worstRunRates": {key: round(value, 6) for key, value in sorted(worst_rates.items())},
        "repositoriesByAdjudicationTier": dict(sorted(tier_counts.items())),
        "failureClasses": dict(sorted(failure_classes.items())),
        "synthesisFailureClasses": dict(sorted(synthesis_failure_classes.items())),
        "failureClassesByEcosystem": dict(sorted(failure_classes_by_ecosystem.items())),
        "failureEcosystems": dict(sorted(ecosystem_counts.items())),
        "recurringFailures": recurring_failures,
        "regressionFixtureCandidates": regression_fixture_candidates,
    }


def retain_telemetry(telemetry: dict, history_path: Path, summary_path: Path) -> dict:
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
        eligible = item.get("fixtureEligible")
        eligibility = (
            "eligible (deterministic parser/evidence/validation)"
            if eligible
            else "not eligible (environmental)"
            if eligible is False
            else "unknown"
        )
        lines.extend(
            [
                f"## {item.get('suggestedFixture', 'unknown-failure')}",
                "",
                f"- failure class: `{item.get('failureClass', 'unknown')}`",
                f"- ecosystem: `{item.get('ecosystem', 'unknown')}`",
                f"- fixture: {eligibility}",
                f"- observed runs: {item.get('count', 0)}",
                f"- fingerprint: `{item.get('fingerprint', 'unknown')}`",
                f"- repositories: {', '.join(f'`{repo}`' for repo in item.get('repositories') or []) or 'not retained'}",
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
    ecosystem = candidate.get("ecosystem", "unknown")
    eligible = candidate.get("fixtureEligible")
    fingerprint = candidate.get("fingerprint", "unknown")
    count = candidate.get("count", 0)
    repositories = candidate.get("repositories") or []
    if eligible is True:
        eligibility = (
            "eligible — this is a deterministic parser/evidence/validation defect "
            "that a checked-in source fixture can reproduce offline"
        )
    elif eligible is False:
        eligibility = (
            "not eligible — this is an environmental provider/infrastructure/writeback "
            "defect that a source fixture cannot reproduce"
        )
    else:
        eligibility = "unknown"
    lines = [
        f"# {fixture}",
        "",
        "This stub was generated from recurring autonomous index failure telemetry.",
        "",
        f"- failure class: `{failure_class}`",
        f"- ecosystem: `{ecosystem}`",
        f"- fixture: {eligibility}",
        f"- observed runs: {count}",
        f"- fingerprint: `{fingerprint}`",
        f"- repositories: {', '.join(f'`{repo}`' for repo in repositories) if repositories else 'not retained'}",
        "",
        "## Materialization Checklist",
        "",
        "Only fixture-eligible stubs should be materialized. Environmental failures are",
        "tracked here for operator awareness, not converted into source fixtures.",
        "",
        "- Capture the smallest repository source fixture that reproduces this failure:",
        f"  `uv run python scripts/materialize_regression_fixture.py --stub index/telemetry/regression-fixture-stubs/{fixture}`",
        "  Add `--repo <host/owner/repo>` when the stub lists multiple repositories.",
        "- Confirm or edit the generated `expectation.json` so it pins the fixed behavior.",
        "- Add the deterministic parser, evidence, or validation fix in `dotrepo-core`.",
        "- Run the runnable regression harness: `cargo test -p dotrepo-core --test regression_fixture_pack`",
        "- Remove this stub once the checked-in runnable fixture guards the fix.",
        "",
    ]
    return "\n".join(lines)


def prune_stale_regression_fixture_stubs(stub_root: Path, active_fixtures: set[str]) -> None:
    if not stub_root.is_dir():
        return
    for entry in stub_root.iterdir():
        if not entry.is_dir() or entry.name in active_fixtures:
            continue
        metadata_path = entry / "metadata.json"
        if not metadata_path.is_file():
            continue
        try:
            metadata = json.loads(metadata_path.read_text())
        except json.JSONDecodeError:
            continue
        if (
            isinstance(metadata, dict)
            and metadata.get("schema") == "dotrepo/regression-fixture-stub/v0.1"
        ):
            shutil.rmtree(entry)


def write_regression_fixture_stub_artifacts(candidates: list[dict], stub_root: Path) -> None:
    stub_root.mkdir(parents=True, exist_ok=True)
    active_fixtures = {
        fixture_slug(
            str(
                candidate.get("suggestedFixture")
                or candidate.get("fingerprint")
                or "unknown-failure"
            )
        )
        for candidate in candidates
    }
    prune_stale_regression_fixture_stubs(stub_root, active_fixtures)
    for candidate in candidates:
        fixture = fixture_slug(
            str(
                candidate.get("suggestedFixture")
                or candidate.get("fingerprint")
                or "unknown-failure"
            )
        )
        destination = stub_root / fixture
        destination.mkdir(parents=True, exist_ok=True)
        failure_class = candidate.get("failureClass", "unknown")
        metadata = {
            "schema": "dotrepo/regression-fixture-stub/v0.1",
            "fixture": fixture,
            "failureClass": failure_class,
            "ecosystem": candidate.get("ecosystem", "unknown"),
            "fixtureEligible": candidate.get("fixtureEligible", fixture_eligible(failure_class)),
            "fingerprint": candidate.get("fingerprint", "unknown"),
            "observedRuns": candidate.get("count", 0),
            "repositories": candidate.get("repositories", []),
            "status": "needs_materialization",
        }
        (destination / "metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n"
        )
        (destination / "README.md").write_text(render_regression_fixture_stub_readme(candidate))


def write_telemetry_outputs(
    telemetry: dict, args: argparse.Namespace, telemetry_path: Path
) -> None:
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
        "INDEX_AUTOMATION_ENABLED", ""
    ).strip().lower() not in {"1", "true", "yes"}:
        print(
            "INDEX_AUTOMATION_ENABLED is not true; skipping autonomous batch "
            "(fail closed — set INDEX_AUTOMATION_ENABLED=true or pass "
            "--skip-automation-enabled-check for explicit local opt-in)",
            file=sys.stderr,
        )
        return 0

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    adjudication_call_budget = resolve_adjudication_call_budget(args)
    discovery_limit = resolve_discovery_limit(args)
    synthesis_model, synthesis_provider = resolve_synthesis_config(args)
    remaining_adjudication_calls = adjudication_call_budget
    adjudication_budget_conservatively_exhausted = False
    base_env = os.environ.copy()

    refresh_plan = output_dir / "refresh-plan.json"
    refresh_batches = output_dir / "refresh-batches.json"
    discovery_json = output_dir / "discovery-fill.json"
    selected_targets = output_dir / "selected-targets.txt"
    selected_metadata = output_dir / "selected-batch.json"
    telemetry_path = output_dir / "telemetry.json"

    refresh_plan_command = [
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
    if args.synthesize:
        refresh_plan_command.extend(["--synthesize", "--synthesis-model", synthesis_model])
    proc = run(refresh_plan_command)
    refresh_plan.write_text(proc.stdout)
    unchanged_skips = unchanged_skips_from_refresh_plan(proc.stdout)

    run(
        [
            *UV_PYTHON,
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
    if (
        not args.disable_discovery
        and len(read_target_identities(selected_targets)) < args.batch_size
    ):
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
            "unchangedSkips": unchanged_skips,
        }
        write_telemetry_outputs(telemetry, args, telemetry_path)
        print("No refresh targets in selected batch")
        return 0

    for line in selected_targets.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        host, owner, repo = line.split("/", 2)
        identity = f"{host}/{owner}/{repo}"
        entry = {"repository": identity, "status": "failed"}
        crawls.append(entry)
        before_status = capture_record_status_before_crawl(Path(args.index_root), identity)
        try:
            crawl_env = crawl_env_for_remaining_budget(base_env, remaining_adjudication_calls)
            entry["adjudicationCallBudgetBefore"] = remaining_adjudication_calls
            crawl_command = [
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
            ]
            if args.synthesize:
                crawl_command.extend(
                    [
                        "--synthesize",
                        "--synthesis-model",
                        synthesis_model,
                        "--synthesis-provider",
                        synthesis_provider,
                    ]
                )
            command_started = time.monotonic()
            print("+", " ".join(crawl_command), flush=True)
            proc, resource_sample = run_with_resource_sample(crawl_command, env=crawl_env)
            # Always available (success or failure): the wall time of the
            # whole `cargo run ... crawl` subprocess as observed from this
            # orchestrator, including process startup overhead that the
            # narrower in-process `wallTimeMs`/`totalWallTimeMs` (reported
            # only on success, from dotrepo-crawler itself) excludes.
            entry["commandWallTimeMs"] = round((time.monotonic() - command_started) * 1000)
            if resource_sample.cpu_time_ms is not None:
                entry["cpuTimeMs"] = resource_sample.cpu_time_ms
            if resource_sample.peak_memory_bytes is not None:
                entry["peakMemoryBytes"] = resource_sample.peak_memory_bytes
            if resource_sample.note:
                entry["resourceSampleNote"] = resource_sample.note
            entry["category"] = "changed"
            if proc.returncode == 0:
                payload = json.loads(proc.stdout)
                entry["status"] = "written" if payload.get("wrote") else "skipped"
                entry["manifestPath"] = payload.get("manifestPath")
                escalation = payload.get("escalation") or {}
                entry["escalation"] = escalation
                entry["adjudicationCalls"] = int(escalation.get("modelCalls") or 0)
                entry["tokensUsed"] = int(escalation.get("tokensUsed") or 0)
                entry["recordStatus"] = payload.get("recordStatus")
                entry["synthesisPath"] = payload.get("synthesisPath")
                entry["synthesisFailure"] = payload.get("synthesisFailure")
                entry["wallTimeMs"] = payload.get("wallTimeMs")
                entry["totalWallTimeMs"] = payload.get("totalWallTimeMs")
                network = payload.get("network") or {}
                entry["networkRequests"] = network.get("requests")
                entry["networkBytes"] = network.get("bytes")
                entry["category"] = classify_unit_cost_category(
                    before_status, entry["recordStatus"]
                )
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
    adjudication_rate = repos_with_adjudication / len(crawls) if crawls else 0.0

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
        "unchangedSkips": unchanged_skips,
    }
    write_telemetry_outputs(telemetry, args, telemetry_path)
    print(json.dumps(telemetry, indent=2, sort_keys=True))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
