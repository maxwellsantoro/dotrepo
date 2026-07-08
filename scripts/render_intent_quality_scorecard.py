#!/usr/bin/env -S uv run python
"""Render intent- and ecosystem-level quality scorecards with error budgets.

Maps each overlay record into the intent classes named by ROADMAP cohort gates
(overview, execution, documentation, security, ownership, discovery) and reports
field presence, honest abstention (candidates without a single primary command),
and ecosystem breakdowns. Optional factual-accuracy JSON can be merged so
incorrect-fact rates from the curated workload appear on the same scorecard.

This is an operator scorecard, not a release hard-fail gate. Defaults encode
soft error budgets; pass stricter thresholds to fail CI when desired.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from language_family import LANGUAGE_FAMILIES, inferred_language_family  # noqa: E402

SCHEMA = "dotrepo/intent-quality-scorecard/v0.1"

INTENTS = (
    "overview",
    "execution",
    "documentation",
    "security",
    "ownership",
    "discovery",
)

# Soft budgets (missing-rate ceilings) for scorecard defaults. Calibrated above
# the 2026-07 checked-in index so the scorecard acts as a *regression*
# detector rather than a permanent red light; tighten with --max-missing-rate
# when a cohort improves. Release gates remain separate.
DEFAULT_MAX_MISSING_RATE = {
    "overview": 0.15,
    "execution": 0.50,
    "documentation": 0.85,  # multi-slot docs fields are often sparse
    "security": 0.75,  # honest absence is common; still tracked
    "ownership": 0.92,  # CODEOWNERS-derived owners are sparse by design
    "discovery": 0.25,
}
DEFAULT_MAX_INCORRECT_RATE = 0.05
DEFAULT_MIN_CORRECT_ABSTENTION_SHARE = 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-root", default="index")
    parser.add_argument(
        "--factual-accuracy-json",
        help="Optional output from measure_public_factual_accuracy.py to merge incorrect-fact rates",
    )
    parser.add_argument("--generated-at")
    parser.add_argument("--output-json")
    parser.add_argument("--output-md")
    parser.add_argument(
        "--max-missing-rate",
        action="append",
        default=[],
        metavar="INTENT=RATE",
        help="Override missing-rate budget; may be repeated",
    )
    parser.add_argument(
        "--max-incorrect-rate",
        type=float,
        default=DEFAULT_MAX_INCORRECT_RATE,
        help="Incorrect-fact rate ceiling when factual-accuracy JSON is provided",
    )
    parser.add_argument(
        "--fail-on-budget",
        action="store_true",
        help="Exit non-zero when any intent or ecosystem budget is exceeded",
    )
    return parser.parse_args()


def parse_rate_overrides(values: list[str]) -> dict[str, float]:
    rates: dict[str, float] = {}
    for raw in values:
        if "=" not in raw:
            raise SystemExit(f"--max-missing-rate must use INTENT=RATE, got {raw!r}")
        intent, rate_text = raw.split("=", 1)
        intent = intent.strip()
        if intent not in INTENTS:
            raise SystemExit(f"unknown intent {intent!r}; expected one of {INTENTS}")
        rates[intent] = float(rate_text)
    return rates


def present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() != "unknown"
    if isinstance(value, list):
        return len(value) > 0
    return True


def intent_field_status(document: dict[str, Any], intent: str) -> dict[str, Any]:
    repo = document.get("repo") or {}
    owners = document.get("owners") or {}
    docs = document.get("docs") or {}
    relations = document.get("relations") or {}

    if intent == "overview":
        fields = {
            "repo.name": present(repo.get("name")),
            "repo.description": present(repo.get("description")),
            "repo.homepage": present(repo.get("homepage")),
            "repo.license": present(repo.get("license")),
        }
        abstained = False
    elif intent == "execution":
        build = present(repo.get("build"))
        test = present(repo.get("test"))
        build_candidates = present(repo.get("build_candidates"))
        test_candidates = present(repo.get("test_candidates"))
        fields = {
            "repo.build": build,
            "repo.test": test,
        }
        # Honest multi-ecosystem tie: primary unset but candidates preserved.
        abstained = (not build and build_candidates) or (not test and test_candidates)
        if abstained:
            fields["repo.build_or_test_candidates"] = True
    elif intent == "documentation":
        fields = {
            "docs.root": present(docs.get("root")),
            "docs.getting_started": present(docs.get("getting_started")),
            "docs.architecture": present(docs.get("architecture")),
            "docs.api": present(docs.get("api")),
        }
        abstained = False
    elif intent == "security":
        fields = {"owners.security_contact": present(owners.get("security_contact"))}
        abstained = False
    elif intent == "ownership":
        fields = {
            "owners.maintainers": present(owners.get("maintainers")),
            "owners.team": present(owners.get("team")),
        }
        abstained = False
    elif intent == "discovery":
        fields = {
            "repo.languages": present(repo.get("languages")),
            "repo.topics": present(repo.get("topics")),
            "relations": present(relations),
        }
        abstained = False
    else:
        raise ValueError(f"unknown intent: {intent}")

    present_count = sum(1 for ok in fields.values() if ok)
    total = len(fields)
    missing = total - present_count
    if intent == "execution":
        complete = (missing == 0) or (abstained and present_count > 0)
    elif intent == "documentation":
        # Useful docs surface: root or getting-started is enough for "complete";
        # missingRate still counts all slots so sparse secondary fields remain visible.
        complete = bool(fields.get("docs.root") or fields.get("docs.getting_started"))
    elif intent == "ownership":
        complete = bool(fields.get("owners.maintainers") or fields.get("owners.team"))
    else:
        complete = missing == 0
    return {
        "fields": fields,
        "presentCount": present_count,
        "fieldCount": total,
        "missingCount": missing,
        "complete": complete,
        "correctAbstention": abstained
        and not (present(repo.get("build")) and present(repo.get("test"))),
    }


def load_index_records(index_root: Path) -> list[dict[str, Any]]:
    repos_root = index_root / "repos"
    if not repos_root.is_dir():
        raise SystemExit(f"index root does not contain repos/: {repos_root}")
    records = []
    for path in sorted(repos_root.glob("*/*/*/record.toml")):
        relative = path.relative_to(repos_root)
        host, owner, repo, _ = relative.parts
        document = tomllib.loads(path.read_text())
        records.append(
            {
                "identity": f"{host}/{owner}/{repo}",
                "path": str(path),
                "document": document,
                "family": inferred_language_family(document),
                "status": (document.get("record") or {}).get("status"),
            }
        )
    return records


def empty_intent_bucket() -> dict[str, Any]:
    return {
        "recordCount": 0,
        "completeCount": 0,
        "missingFactCount": 0,
        "fieldSlotCount": 0,
        "correctAbstentionCount": 0,
    }


def accumulate(bucket: dict[str, Any], status: dict[str, Any]) -> None:
    bucket["recordCount"] += 1
    if status["complete"]:
        bucket["completeCount"] += 1
    bucket["missingFactCount"] += status["missingCount"]
    bucket["fieldSlotCount"] += status["fieldCount"]
    if status["correctAbstention"]:
        bucket["correctAbstentionCount"] += 1


def finalize_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    records = bucket["recordCount"] or 0
    slots = bucket["fieldSlotCount"] or 0
    missing = bucket["missingFactCount"]
    complete = bucket["completeCount"]
    abstention = bucket["correctAbstentionCount"]
    return {
        **bucket,
        "completenessRate": round(complete / records, 4) if records else None,
        "missingRate": round(missing / slots, 4) if slots else None,
        "correctAbstentionRate": round(abstention / records, 4) if records else None,
    }


def load_factual_accuracy(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.is_file():
        raise SystemExit(f"factual accuracy JSON not found: {path}")
    return json.loads(path.read_text())


def build_scorecard(
    records: list[dict[str, Any]],
    *,
    missing_budgets: dict[str, float],
    incorrect_budget: float,
    factual: dict[str, Any] | None,
    generated_at: str,
) -> dict[str, Any]:
    by_intent: dict[str, dict[str, Any]] = {intent: empty_intent_bucket() for intent in INTENTS}
    by_intent_ecosystem: dict[str, dict[str, dict[str, Any]]] = {
        intent: {family: empty_intent_bucket() for family in LANGUAGE_FAMILIES} for intent in INTENTS
    }
    status_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()

    for entry in records:
        status_counts[str(entry.get("status") or "unknown")] += 1
        family_counts[entry["family"]] += 1
        document = entry["document"]
        family = entry["family"]
        for intent in INTENTS:
            status = intent_field_status(document, intent)
            accumulate(by_intent[intent], status)
            accumulate(by_intent_ecosystem[intent][family], status)

    intents_out = {}
    budget_failures: list[dict[str, Any]] = []
    for intent in INTENTS:
        summary = finalize_bucket(by_intent[intent])
        budget = missing_budgets.get(intent, DEFAULT_MAX_MISSING_RATE[intent])
        summary["maxMissingRateBudget"] = budget
        missing_rate = summary["missingRate"]
        within = missing_rate is None or missing_rate <= budget
        summary["withinMissingBudget"] = within
        if not within:
            budget_failures.append(
                {
                    "scope": "intent",
                    "intent": intent,
                    "metric": "missingRate",
                    "value": missing_rate,
                    "budget": budget,
                }
            )
        ecosystems = {
            family: finalize_bucket(by_intent_ecosystem[intent][family])
            for family in LANGUAGE_FAMILIES
        }
        summary["ecosystems"] = ecosystems
        intents_out[intent] = summary

    factual_block: dict[str, Any] | None = None
    if factual is not None:
        summary = factual.get("summary") or {}
        incorrect_rate = summary.get("mismatchRate")
        if incorrect_rate is None and summary.get("assertionCount"):
            incorrect_rate = (summary.get("mismatchCount") or 0) / summary["assertionCount"]
        within_incorrect = incorrect_rate is None or float(incorrect_rate) <= incorrect_budget
        factual_block = {
            "schema": factual.get("schema"),
            "assertionCount": summary.get("assertionCount"),
            "accuracyRate": summary.get("accuracyRate"),
            "missingRate": summary.get("missingRate"),
            "mismatchRate": incorrect_rate,
            "correctAbstentionCount": summary.get("correctAbstentionCount"),
            "correctAbstentionRate": summary.get("correctAbstentionRate"),
            "maxIncorrectRateBudget": incorrect_budget,
            "withinIncorrectBudget": within_incorrect,
            "ecosystemSummaries": summary.get("ecosystemSummaries"),
        }
        if not within_incorrect:
            budget_failures.append(
                {
                    "scope": "factual-accuracy",
                    "metric": "mismatchRate",
                    "value": incorrect_rate,
                    "budget": incorrect_budget,
                }
            )

    return {
        "schema": SCHEMA,
        "generatedAt": generated_at,
        "recordCount": len(records),
        "statusCounts": dict(status_counts),
        "familyCounts": dict(family_counts),
        "intents": intents_out,
        "factualAccuracy": factual_block,
        "budgetFailures": budget_failures,
        "withinBudgets": len(budget_failures) == 0,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Intent quality scorecard",
        "",
        f"- schema: `{report['schema']}`",
        f"- generated at: `{report['generatedAt']}`",
        f"- records: {report['recordCount']}",
        f"- within budgets: {'yes' if report['withinBudgets'] else 'no'}",
        "",
        "## Intent completeness",
        "",
        "| intent | records | complete | completeness | missing rate | missing budget | abstentions | within budget |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for intent in INTENTS:
        summary = report["intents"][intent]
        lines.append(
            "| {intent} | {records} | {complete} | {completeness} | {missing} | {budget} | {abstention} | {within} |".format(
                intent=intent,
                records=summary["recordCount"],
                complete=summary["completeCount"],
                completeness=_pct(summary["completenessRate"]),
                missing=_pct(summary["missingRate"]),
                budget=_pct(summary["maxMissingRateBudget"]),
                abstention=summary["correctAbstentionCount"],
                within="yes" if summary["withinMissingBudget"] else "no",
            )
        )
    lines.append("")
    lines.append("## Status and ecosystem mix")
    lines.append("")
    lines.append(f"- status: `{json.dumps(report['statusCounts'], sort_keys=True)}`")
    lines.append(f"- families: `{json.dumps(report['familyCounts'], sort_keys=True)}`")
    lines.append("")
    if report.get("factualAccuracy"):
        fa = report["factualAccuracy"]
        lines.extend(
            [
                "## Factual accuracy (curated workload)",
                "",
                f"- assertions: {fa.get('assertionCount')}",
                f"- accuracy: {_pct(fa.get('accuracyRate'))}",
                f"- missing: {_pct(fa.get('missingRate'))}",
                f"- incorrect (mismatch): {_pct(fa.get('mismatchRate'))} "
                f"(budget {_pct(fa.get('maxIncorrectRateBudget'))})",
                f"- correct abstention: {_pct(fa.get('correctAbstentionRate'))}",
                f"- within incorrect budget: "
                f"{'yes' if fa.get('withinIncorrectBudget') else 'no'}",
                "",
            ]
        )
    if report["budgetFailures"]:
        lines.append("## Budget failures")
        lines.append("")
        for failure in report["budgetFailures"]:
            lines.append(f"- `{json.dumps(failure, sort_keys=True)}`")
        lines.append("")
    lines.append(
        "Soft budgets make honest absence and multi-ecosystem abstention visible without "
        "forcing fabricated completeness. Tighten with `--max-missing-rate` / "
        "`--fail-on-budget` when a cohort is ready for hard gates."
    )
    lines.append("")
    return "\n".join(lines)


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


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
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main() -> int:
    args = parse_args()
    overrides = parse_rate_overrides(args.max_missing_rate)
    budgets = {**DEFAULT_MAX_MISSING_RATE, **overrides}
    generated_at = args.generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    records = load_index_records(Path(args.index_root))
    factual = load_factual_accuracy(Path(args.factual_accuracy_json) if args.factual_accuracy_json else None)
    report = build_scorecard(
        records,
        missing_budgets=budgets,
        incorrect_budget=args.max_incorrect_rate,
        factual=factual,
        generated_at=generated_at,
    )
    markdown = render_markdown(report)
    write_json(args.output_json, report)
    write_text(args.output_md, markdown)
    if not args.output_md:
        print(markdown)
    if args.fail_on_budget and not report["withinBudgets"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
