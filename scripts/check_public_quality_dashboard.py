#!/usr/bin/env -S uv run python

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCHEMA = "dotrepo-public-quality-dashboard/v0"

GENERIC_NAMES = {
    "discussion",
    "discussions",
    "documentation",
    "docs",
    "download",
    "downloads",
    "home",
    "issue",
    "issues",
    "project",
    "readme",
    "readme.md",
    "repository",
    "sponsor",
    "sponsors",
    "wiki",
}

GENERIC_TEXT_PATTERNS = [
    re.compile(r"\bdownload the latest release\b", re.IGNORECASE),
    re.compile(r"\bissues? (are|is) for bug reports\b", re.IGNORECASE),
    re.compile(r"\bplease go to (our )?(discussion|forum)\b", re.IGNORECASE),
    re.compile(r"\buse at your own risk\b", re.IGNORECASE),
    re.compile(r"\bdisclaimer\b", re.IGNORECASE),
    re.compile(r"\bsponsors?\b", re.IGNORECASE),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a public export quality dashboard for duplicated, generic, "
            "and low-confidence repository records."
        )
    )
    parser.add_argument(
        "--public-root",
        default="public",
        help="Public export root containing v0/repos/**/profile.json (default: public)",
    )
    parser.add_argument(
        "--min-profiles",
        type=int,
        default=0,
        help="Fail when analyzed profile count is below this threshold",
    )
    parser.add_argument(
        "--max-generic-field-hits",
        type=int,
        default=1_000_000,
        help="Fail when generic name/purpose hits exceed this threshold",
    )
    parser.add_argument(
        "--max-duplicated-description-values",
        type=int,
        default=1_000_000,
        help="Fail when duplicated public descriptions exceed this threshold",
    )
    parser.add_argument(
        "--max-duplicate-description-records",
        type=int,
        default=1_000_000,
        help="Fail when records participating in duplicated descriptions exceed this threshold",
    )
    parser.add_argument(
        "--max-bad-looking-records",
        type=int,
        default=1_000_000,
        help="Fail when bad-looking record count exceeds this threshold",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=20,
        help="Maximum example items per section",
    )
    parser.add_argument("--output-json", help="Optional path for JSON output")
    parser.add_argument("--output-md", help="Optional path for Markdown output")
    return parser.parse_args()


def profile_paths(public_root: Path) -> list[Path]:
    repos_root = public_root / "v0" / "repos"
    if not repos_root.is_dir():
        raise SystemExit(f"public root does not contain v0/repos/: {repos_root}")
    return sorted(repos_root.glob("*/*/*/profile.json"))


def normalize_text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def display_text(value: object, limit: int = 180) -> str:
    cleaned = " ".join(str(value or "").strip().split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 1].rstrip()}…"


def is_generic_name(value: object) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return True
    return normalized in GENERIC_NAMES


def generic_text_reasons(value: object) -> list[str]:
    text = str(value or "")
    return [pattern.pattern for pattern in GENERIC_TEXT_PATTERNS if pattern.search(text)]


def profile_identity(profile: dict[str, Any], path: Path) -> str:
    identity = profile.get("identity") or {}
    try:
        return "/".join([identity["host"], identity["owner"], identity["repo"]])
    except (KeyError, TypeError):
        return path.as_posix()


def read_profile(path: Path, public_root: Path) -> dict[str, Any]:
    try:
        profile = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return {
            "identity": path.relative_to(public_root).as_posix(),
            "path": path.relative_to(public_root).as_posix(),
            "valid": False,
            "errors": [f"invalid JSON: {exc.msg}"],
        }
    if not isinstance(profile, dict):
        return {
            "identity": path.relative_to(public_root).as_posix(),
            "path": path.relative_to(public_root).as_posix(),
            "valid": False,
            "errors": ["profile must be a JSON object"],
        }
    trust = profile.get("trust") or {}
    completeness = profile.get("completeness") or {}
    name = str(profile.get("name") or "")
    purpose = str(profile.get("purpose") or "")
    generic_findings: list[dict[str, str]] = []
    if is_generic_name(name):
        generic_findings.append({"field": "name", "reason": "generic-name"})
    for reason in generic_text_reasons(purpose):
        generic_findings.append({"field": "purpose", "reason": reason})
    return {
        "identity": profile_identity(profile, path),
        "path": path.relative_to(public_root).as_posix(),
        "valid": True,
        "name": name,
        "purpose": purpose,
        "purposeKey": normalize_text(purpose),
        "selectedStatus": str(trust.get("selectedStatus") or "unknown"),
        "confidence": str(trust.get("confidence") or "unknown"),
        "conflictCount": int(completeness.get("conflictCount") or 0),
        "hasBuild": bool(completeness.get("hasBuild")),
        "hasTest": bool(completeness.get("hasTest")),
        "hasDocs": bool(completeness.get("hasDocs")),
        "hasSecurityContact": bool(completeness.get("hasSecurityContact")),
        "hasOwnershipSignal": bool(completeness.get("hasOwnershipSignal")),
        "hasLicense": bool(completeness.get("hasLicense")),
        "genericFindings": generic_findings,
    }


def duplicate_description_groups(
    profiles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_description: dict[str, list[dict[str, Any]]] = defaultdict(list)
    display_by_description: dict[str, str] = {}
    for profile in profiles:
        key = profile["purposeKey"]
        if len(key) < 20:
            continue
        by_description[key].append(profile)
        display_by_description.setdefault(key, display_text(profile["purpose"]))
    groups = []
    for key, records in by_description.items():
        if len(records) < 2:
            continue
        groups.append(
            {
                "description": display_by_description[key],
                "count": len(records),
                "repositories": [record["identity"] for record in records],
            }
        )
    return sorted(groups, key=lambda item: (-item["count"], item["description"]))


def summarize(public_root: Path, max_items: int, thresholds: dict[str, int]) -> dict[str, Any]:
    discovered = [read_profile(path, public_root) for path in profile_paths(public_root)]
    malformed = [profile for profile in discovered if not profile["valid"]]
    profiles = [profile for profile in discovered if profile["valid"]]
    status_counts = Counter(profile["selectedStatus"] for profile in profiles)
    confidence_counts = Counter(profile["confidence"] for profile in profiles)
    duplicate_groups = duplicate_description_groups(profiles)
    duplicated_identities = {
        identity for group in duplicate_groups for identity in group["repositories"]
    }
    generic_examples = [
        {
            "identity": profile["identity"],
            "name": profile["name"],
            "purpose": display_text(profile["purpose"]),
            "findings": profile["genericFindings"],
        }
        for profile in profiles
        if profile["genericFindings"]
    ]
    bad_records = []
    for profile in profiles:
        reasons = []
        if profile["genericFindings"]:
            reasons.append("generic-field")
        if profile["identity"] in duplicated_identities:
            reasons.append("duplicated-description")
        if profile["confidence"] in {"low", "unknown", "suspect"}:
            reasons.append(f"{profile['confidence']}-confidence")
        if profile["conflictCount"] > 0:
            reasons.append("selected-record-conflict")
        if reasons:
            bad_records.append(
                {
                    "identity": profile["identity"],
                    "name": profile["name"],
                    "purpose": display_text(profile["purpose"]),
                    "selectedStatus": profile["selectedStatus"],
                    "confidence": profile["confidence"],
                    "reasons": sorted(reasons),
                }
            )
    bad_records.sort(key=lambda item: (len(item["reasons"]) * -1, item["identity"]))
    signal_counts = Counter()
    for profile in profiles:
        for signal in (
            "hasBuild",
            "hasTest",
            "hasDocs",
            "hasSecurityContact",
            "hasOwnershipSignal",
            "hasLicense",
        ):
            if profile[signal]:
                signal_counts[signal] += 1
    summary = {
        "discoveredProfileCount": len(discovered),
        "profileCount": len(profiles),
        "malformedProfileCount": len(malformed),
        "statusCounts": dict(sorted(status_counts.items())),
        "confidenceCounts": dict(sorted(confidence_counts.items())),
        "signalCounts": dict(sorted(signal_counts.items())),
        "genericFieldHitCount": sum(len(profile["genericFindings"]) for profile in profiles),
        "genericRecordCount": len(generic_examples),
        "duplicatedDescriptionValueCount": len(duplicate_groups),
        "duplicateDescriptionRecordCount": len(duplicated_identities),
        "badLookingRecordCount": len(bad_records),
    }
    gates = {
        "minProfiles": {
            "threshold": thresholds["minProfiles"],
            "actual": summary["profileCount"],
            "passed": summary["profileCount"] >= thresholds["minProfiles"],
        },
        "maxGenericFieldHits": {
            "threshold": thresholds["maxGenericFieldHits"],
            "actual": summary["genericFieldHitCount"],
            "passed": summary["genericFieldHitCount"] <= thresholds["maxGenericFieldHits"],
        },
        "maxDuplicatedDescriptionValues": {
            "threshold": thresholds["maxDuplicatedDescriptionValues"],
            "actual": summary["duplicatedDescriptionValueCount"],
            "passed": summary["duplicatedDescriptionValueCount"]
            <= thresholds["maxDuplicatedDescriptionValues"],
        },
        "maxDuplicateDescriptionRecords": {
            "threshold": thresholds["maxDuplicateDescriptionRecords"],
            "actual": summary["duplicateDescriptionRecordCount"],
            "passed": summary["duplicateDescriptionRecordCount"]
            <= thresholds["maxDuplicateDescriptionRecords"],
        },
        "maxBadLookingRecords": {
            "threshold": thresholds["maxBadLookingRecords"],
            "actual": summary["badLookingRecordCount"],
            "passed": summary["badLookingRecordCount"] <= thresholds["maxBadLookingRecords"],
        },
    }
    return {
        "schema": SCHEMA,
        "publicRoot": public_root.as_posix(),
        "summary": summary,
        "gates": gates,
        "passed": all(gate["passed"] for gate in gates.values()),
        "genericFieldExamples": generic_examples[:max_items],
        "duplicatedDescriptions": [
            {
                **group,
                "repositories": group["repositories"][:max_items],
            }
            for group in duplicate_groups[:max_items]
        ],
        "badLookingRecords": bad_records[:max_items],
        "malformedProfiles": malformed[:max_items],
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    gates = report["gates"]
    lines = [
        "# dotrepo public quality dashboard",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Profiles | {summary['profileCount']} |",
        f"| Malformed profiles | {summary['malformedProfileCount']} |",
        f"| Generic field hits | {summary['genericFieldHitCount']} |",
        f"| Generic records | {summary['genericRecordCount']} |",
        f"| Duplicated description values | {summary['duplicatedDescriptionValueCount']} |",
        f"| Records with duplicated descriptions | {summary['duplicateDescriptionRecordCount']} |",
        f"| Bad-looking records | {summary['badLookingRecordCount']} |",
        "",
        "## Gates",
        "",
    ]
    for name, gate in gates.items():
        result = "pass" if gate["passed"] else "fail"
        lines.append(f"- `{name}`: {gate['actual']} / {gate['threshold']} ({result})")
    lines.extend(["", "## Generic field examples", ""])
    if not report["genericFieldExamples"]:
        lines.append("- None.")
    else:
        for item in report["genericFieldExamples"]:
            fields = ", ".join(f"{f['field']}:{f['reason']}" for f in item["findings"])
            lines.append(f"- `{item['identity']}` — name `{item['name']}`; findings {fields}")
    lines.extend(["", "## Duplicated descriptions", ""])
    if not report["duplicatedDescriptions"]:
        lines.append("- None.")
    else:
        for item in report["duplicatedDescriptions"]:
            repos = ", ".join(f"`{repo}`" for repo in item["repositories"])
            lines.append(f"- {item['count']} records: “{item['description']}” — {repos}")
    lines.extend(["", "## Bad-looking records", ""])
    if not report["badLookingRecords"]:
        lines.append("- None.")
    else:
        for item in report["badLookingRecords"]:
            reasons = ", ".join(item["reasons"])
            lines.append(
                f"- `{item['identity']}` — confidence `{item['confidence']}`, "
                f"reasons {reasons}; purpose “{item['purpose']}”"
            )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    thresholds = {
        "minProfiles": args.min_profiles,
        "maxGenericFieldHits": args.max_generic_field_hits,
        "maxDuplicatedDescriptionValues": args.max_duplicated_description_values,
        "maxDuplicateDescriptionRecords": args.max_duplicate_description_records,
        "maxBadLookingRecords": args.max_bad_looking_records,
    }
    report = summarize(Path(args.public_root), args.max_items, thresholds)
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
