#!/usr/bin/env -S uv run python
"""Draw a randomized, risk-weighted audit sample from the checked-in index.

Roadmap context: Milestone 1's active execution order item 7 calls for
"randomized and risk-weighted system audits" that convert every actionable
finding into a fixture, deterministic fix, calibration change, or policy
update (see `ROADMAP.md`'s "Audit strategy" section and
`docs/factual-crawl-automation.md`). This script is the *sampling* half of
that loop only: it reads the existing overlay records under
`index/repos/<host>/<owner>/<repo>/record.toml` (and their `evidence.md`),
computes a heuristic risk weight per record, and draws a reproducible random
sample sized for a human (or a future automated pass) to actually inspect
against `index/review-checklist.md`. It does not touch the network, call any
model or adjudication provider, write to `index/repos/*`, or act on findings
itself — that conversion step is deliberately out of scope for this first
slice.

## Risk-weighting heuristic (read this before trusting the numbers)

This is a heuristic, not a calibrated model. There is no historical
ground-truth of "audits that actually found something" to fit against yet
(that data will only exist once this script has been run and its findings
acted upon), so the formula below encodes plain, inspectable reasoning
rather than any statistically fitted precision. Every real `record.toml`
inspected while building this script has exactly one `record.trust.confidence`
value per `record.status` (`inferred` -> low/medium, `imported` -> medium,
`verified` -> high) -- there is no separately recorded model tier or
adjudication tier inside `record.toml` itself (that lives only in run-level
telemetry, not the per-record artifact), so "model tier" from the roadmap's
audit-strategy prose is approximated here by `record.status` /
`record.trust.confidence` and by ecosystem/language family instead of an
unavailable field. If model-tier provenance is ever recorded on the record
itself, this weighting should be extended to use it directly.

Per-record risk weight is the sum of:

- **Confidence signal** (`low`/`unknown` = 3.0, `medium` = 1.5, `high` = 0.5):
  lower-confidence records are cheaper to be wrong about silently and are
  the most obviously worth checking.
- **Missing high-value fields** (`build`, `test`, `security_contact`: +1.5
  each; `license`, `docs.root`: +0.5 each): a missing field is either a
  legitimate absence or a gap worth fixing, and an audit is the cheapest way
  to tell the difference. Build/test/security are weighted higher because
  they gate promotion and downstream utility; license/docs are lower-stakes.
- **Near-promotion-threshold bonus** (+2.0): a record whose status is not
  yet `verified` but which already has `build`, `test`, and a non-`unknown`
  `security_contact` present would plausibly flip to `verified` on the next
  honest-resolution pass. These are exactly the records where an audit
  either confirms the promotion is safe or catches something that should
  not have looked "one field away."
- **Surprising completeness** (+1.5): a record whose simple field-presence
  count (build, test, security_contact, license, docs.root, topics) differs
  from its language-family peers' average by 2 or more fields, in either
  direction. Unusually complete records among sparse peers, or unusually
  sparse records among complete peers, are the "surprising cost or
  completeness" the roadmap's audit-strategy language calls out.
- **Ecosystem dampening** (divide the running total by
  `sqrt(family_population)`): without this, the largest language family in
  the index would supply most of the sample just because it has the most
  records, not because its records are riskier. Dividing by the square root
  of that family's population size tempers (but does not eliminate) that
  effect, so a sample of size N still tends to spread across ecosystems
  rather than being dominated by whichever family happens to be largest.
  This is a deliberately mild, easy-to-explain correction, not a
  proportional-allocation quota system.

Given these weights, the sample is drawn via weighted random sampling
without replacement (repeatedly drawing one record with probability
proportional to remaining weight, then removing it) using a seedable RNG, so
the same `--seed` always reproduces the same sample from the same index
state. The default seed is derived from the current UTC date, so a run
today and a run tomorrow (with an unchanged index) draw different samples,
while re-running the *same* audit today is reproducible.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import tomllib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from language_family import inferred_language_family  # noqa: E402

SCHEMA = "dotrepo/audit-sample/v0.1"

STATUS_ORDER = {
    "draft": 0,
    "inferred": 1,
    "imported": 2,
    "reviewed": 3,
    "verified": 4,
    "canonical": 5,
}
CONFIDENCE_WEIGHT = {"low": 3.0, "unknown": 3.0, "medium": 1.5, "high": 0.5}
MISSING_FIELD_WEIGHT = {
    "build": 1.5,
    "test": 1.5,
    "security_contact": 1.5,
    "license": 0.5,
    "docs": 0.5,
}
NEAR_PROMOTION_BONUS = 2.0
SURPRISING_COMPLETENESS_BONUS = 1.5
SURPRISING_COMPLETENESS_DELTA = 2.0
COMPLETENESS_FIELDS = ("build", "test", "security_contact", "license", "docs", "topics")
DEFAULT_SAMPLE_SIZE = 20


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Draw a randomized, risk-weighted audit sample from checked-in index records.")
    )
    parser.add_argument(
        "--index-root",
        default="index",
        help="Index root to inspect (default: index)",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=DEFAULT_SAMPLE_SIZE,
        help=f"Number of records to sample (default: {DEFAULT_SAMPLE_SIZE}; capped at population size)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help=(
            "Seed for the sampling RNG (default: derived from the current UTC date, "
            "so runs are reproducible per day but vary day to day)"
        ),
    )
    parser.add_argument(
        "--now",
        help="Override current timestamp for deterministic default-seed derivation and reports",
    )
    parser.add_argument("--output-json", help="Optional path for machine-readable JSON")
    parser.add_argument("--output-md", help="Optional path for markdown output")
    return parser.parse_args()


def resolve_now(value: str | None) -> datetime:
    if value:
        parsed = parse_rfc3339(value)
        if parsed is None:
            raise SystemExit(f"--now must be an RFC3339 timestamp, got {value!r}")
        return parsed
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_rfc3339(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def default_seed(now: datetime) -> int:
    return int(now.strftime("%Y%m%d"))


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


def load_records(index_root: Path) -> list[dict[str, Any]]:
    records = []
    for path in record_paths(index_root):
        document = load_toml(path)
        record = document.get("record", {})
        repo = document.get("repo", {})
        trust = record.get("trust") or {}
        owners = document.get("owners", {})
        docs = document.get("docs", {})
        identity = identity_from_record_path(index_root, path)
        security_contact = owners.get("security_contact")
        record_dir = path.parent
        evidence_path = record_dir / "evidence.md"
        entry = {
            "identity": identity,
            "recordPath": str(path),
            "evidencePath": str(evidence_path) if evidence_path.is_file() else None,
            "status": str(record.get("status", "unknown")),
            "confidence": str(trust.get("confidence", "unknown")),
            "provenance": list(trust.get("provenance") or []),
            "languages": repo.get("languages") or [],
            "languageFamily": inferred_language_family(document),
            "buildPresent": bool(repo.get("build")),
            "testPresent": bool(repo.get("test")),
            "securityContactPresent": bool(security_contact) and security_contact != "unknown",
            "licensePresent": bool(repo.get("license")),
            "docsPresent": bool(docs.get("root")),
            "topicsPresent": bool(repo.get("topics")),
        }
        entry["completenessCount"] = sum(
            1
            for _field, present in (
                ("build", entry["buildPresent"]),
                ("test", entry["testPresent"]),
                ("security_contact", entry["securityContactPresent"]),
                ("license", entry["licensePresent"]),
                ("docs", entry["docsPresent"]),
                ("topics", entry["topicsPresent"]),
            )
            if present
        )
        records.append(entry)
    return records


def family_completeness_averages(records: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, list[int]] = defaultdict(list)
    for record in records:
        totals[record["languageFamily"]].append(record["completenessCount"])
    return {
        family: (sum(values) / len(values) if values else 0.0) for family, values in totals.items()
    }


def family_populations(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        counts[record["languageFamily"]] += 1
    return dict(counts)


def risk_factors_and_weight(
    record: dict[str, Any],
    *,
    family_average_completeness: float,
    family_population: int,
) -> tuple[float, list[str]]:
    factors: list[str] = []
    weight = 0.0

    confidence = record["confidence"]
    confidence_weight = CONFIDENCE_WEIGHT.get(confidence, CONFIDENCE_WEIGHT["unknown"])
    weight += confidence_weight
    if confidence in {"low", "unknown"}:
        factors.append(f"confidence:{confidence}")
    elif confidence == "medium":
        factors.append("confidence:medium")

    missing_present_map = {
        "build": record["buildPresent"],
        "test": record["testPresent"],
        "security_contact": record["securityContactPresent"],
        "license": record["licensePresent"],
        "docs": record["docsPresent"],
    }
    for field, present in missing_present_map.items():
        if not present:
            weight += MISSING_FIELD_WEIGHT[field]
            factors.append(f"missing:{field}")

    near_promotion = (
        record["status"] != "verified"
        and record["buildPresent"]
        and record["testPresent"]
        and record["securityContactPresent"]
    )
    if near_promotion:
        weight += NEAR_PROMOTION_BONUS
        factors.append("near-promotion-threshold")

    delta = record["completenessCount"] - family_average_completeness
    if abs(delta) >= SURPRISING_COMPLETENESS_DELTA:
        weight += SURPRISING_COMPLETENESS_BONUS
        direction = "high" if delta > 0 else "low"
        factors.append(f"surprising-completeness:{direction}")

    if family_population > 0:
        weight = weight / math.sqrt(family_population)

    # A floor keeps every record eligible for the sample (weight 0 would
    # never be drawn); this is a small constant, not a meaningful signal.
    weight = max(weight, 0.01)
    return weight, factors


def compute_risk(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    averages = family_completeness_averages(records)
    populations = family_populations(records)
    enriched = []
    for record in records:
        weight, factors = risk_factors_and_weight(
            record,
            family_average_completeness=averages.get(record["languageFamily"], 0.0),
            family_population=populations.get(record["languageFamily"], 0),
        )
        enriched.append({**record, "riskWeight": round(weight, 4), "riskFactors": factors})
    return enriched


def weighted_sample_without_replacement(
    records: list[dict[str, Any]], sample_size: int, rng: random.Random
) -> list[dict[str, Any]]:
    pool = list(records)
    chosen: list[dict[str, Any]] = []
    for _ in range(min(sample_size, len(pool))):
        weights = [record["riskWeight"] for record in pool]
        picked = rng.choices(pool, weights=weights, k=1)[0]
        chosen.append(picked)
        pool.remove(picked)
    return chosen


def build_report(
    index_root: Path,
    sample_size: int,
    seed: int,
    now: datetime,
) -> dict[str, Any]:
    records = load_records(index_root)
    enriched = compute_risk(records)
    rng = random.Random(seed)
    sample = weighted_sample_without_replacement(enriched, sample_size, rng)
    sample_sorted = sorted(sample, key=lambda record: (-record["riskWeight"], record["identity"]))

    return {
        "schema": SCHEMA,
        "generatedAt": now.isoformat().replace("+00:00", "Z"),
        "indexRoot": str(index_root),
        "seed": seed,
        "populationSize": len(records),
        "sampleSize": len(sample_sorted),
        "requestedSampleSize": sample_size,
        "sample": [
            {
                "identity": record["identity"],
                "languageFamily": record["languageFamily"],
                "status": record["status"],
                "confidence": record["confidence"],
                "riskWeight": record["riskWeight"],
                "riskFactors": record["riskFactors"],
                "recordPath": record["recordPath"],
                "evidencePath": record["evidencePath"],
            }
            for record in sample_sorted
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Index Audit Sample",
        "",
        f"- schema: {report['schema']}",
        f"- generated at: {report['generatedAt']}",
        f"- index root: {report['indexRoot']}",
        f"- seed: {report['seed']}",
        f"- population size: {report['populationSize']}",
        f"- sample size: {report['sampleSize']} (requested {report['requestedSampleSize']})",
        "",
        "## Sample",
        "",
        "| Identity | Family | Status | Confidence | Risk weight | Risk factors |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for record in report["sample"]:
        factors = ", ".join(record["riskFactors"]) if record["riskFactors"] else "none"
        lines.append(
            f"| `{record['identity']}` | {record['languageFamily']} | {record['status']} "
            f"| {record['confidence']} | {record['riskWeight']} | {factors} |"
        )
    lines.append("")
    lines.append("## Inspection pointers")
    lines.append("")
    for record in report["sample"]:
        lines.append(
            f"- `{record['identity']}`: `{record['recordPath']}`"
            + (
                f", `{record['evidencePath']}`"
                if record["evidencePath"]
                else " (no evidence.md found)"
            )
        )
    return "\n".join(lines).rstrip() + "\n"


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
    if args.sample_size < 0:
        raise SystemExit("--sample-size must not be negative")
    now = resolve_now(args.now)
    seed = args.seed if args.seed is not None else default_seed(now)
    report = build_report(Path(args.index_root), args.sample_size, seed, now)
    markdown = render_markdown(report)
    write_json(args.output_json, report)
    write_text(args.output_md, markdown)
    if not args.output_md:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
