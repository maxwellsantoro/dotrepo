#!/usr/bin/env -S uv run python

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Optional


SCHEMA = "dotrepo-public-profile-coverage/v0"
HIGH_SIGNAL_STATUSES = {"reviewed", "verified", "canonical"}
HIGH_SIGNAL_CONFIDENCE = {"medium", "high"}
PROFILE_REQUIRED_KEYS = {
    "apiVersion",
    "freshness",
    "identity",
    "record",
    "purpose",
    "name",
    "execution",
    "docs",
    "ownership",
    "completeness",
    "trust",
    "conflicts",
    "links",
}
PROFILE_LINK_KEYS = {"self", "repository", "trust", "queryTemplate", "indexPath"}
COMPLETENESS_BOOL_KEYS = {
    "hasBuild",
    "hasTest",
    "hasDocs",
    "hasSecurityContact",
    "hasOwnershipSignal",
    "hasLicense",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure public profile coverage and optional Milestone 2 gates."
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
        help="Fail when profile count is below this threshold",
    )
    parser.add_argument(
        "--min-high-signal",
        type=int,
        default=0,
        help="Fail when high-signal profile count is below this threshold",
    )
    parser.add_argument(
        "--min-high-signal-ratio",
        type=float,
        default=0.0,
        help="Fail when the high-signal profile ratio is below this threshold",
    )
    parser.add_argument(
        "--max-missing-signal",
        action="append",
        default=[],
        metavar="SIGNAL=COUNT",
        help=(
            "Fail when a missing-signal count exceeds COUNT. May be repeated; "
            "signal names match report missingSignalCounts keys."
        ),
    )
    parser.add_argument(
        "--min-signal",
        action="append",
        default=[],
        metavar="SIGNAL=COUNT",
        help=(
            "Fail when fewer than COUNT profiles carry SIGNAL. May be repeated; "
            "signal names match report signalCounts keys."
        ),
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=10,
        help="Maximum lower-signal profiles to include in the report",
    )
    parser.add_argument(
        "--max-malformed-profiles",
        type=int,
        default=0,
        help="Fail when more than this many profile files violate the public contract",
    )
    parser.add_argument("--output-json", help="Optional path for JSON output")
    parser.add_argument("--output-md", help="Optional path for Markdown output")
    return parser.parse_args()


def profile_paths(public_root: Path) -> list[Path]:
    repos_root = public_root / "v0" / "repos"
    if not repos_root.is_dir():
        raise SystemExit(f"public root does not contain v0/repos/: {repos_root}")
    return sorted(repos_root.glob("*/*/*/profile.json"))


def ratio(numerator: int, denominator: int) -> Optional[float]:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def parse_signal_limits(values: list[str], flag: str) -> dict[str, int]:
    limits = {}
    for raw in values:
        if "=" not in raw:
            raise SystemExit(
                f"{flag} must use SIGNAL=COUNT, got {raw!r}"
            )
        signal, count_text = raw.split("=", 1)
        signal = signal.strip()
        if not signal:
            raise SystemExit(
                f"{flag} must include a signal name, got {raw!r}"
            )
        try:
            count = int(count_text)
        except ValueError as exc:
            raise SystemExit(
                f"{flag} count must be an integer, got {raw!r}"
            ) from exc
        if count < 0:
            raise SystemExit(
                f"{flag} count must be >= 0, got {raw!r}"
            )
        limits[signal] = count
    return limits


def parse_max_missing_signal(values: list[str]) -> dict[str, int]:
    return parse_signal_limits(values, "--max-missing-signal")


def parse_min_signal(values: list[str]) -> dict[str, int]:
    return parse_signal_limits(values, "--min-signal")


def profile_identity(profile: dict[str, Any], path: Path) -> str:
    identity = profile.get("identity") or {}
    try:
        return "/".join([identity["host"], identity["owner"], identity["repo"]])
    except (KeyError, TypeError):
        return path.as_posix()


def nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def profile_contract_errors(
    profile: object, path: Path, public_root: Path
) -> list[str]:
    if not isinstance(profile, dict):
        return ["profile must be a JSON object"]

    errors = []
    missing = sorted(PROFILE_REQUIRED_KEYS - profile.keys())
    if missing:
        errors.append(f"missing required top-level keys: {', '.join(missing)}")
    if profile.get("apiVersion") != "v0":
        errors.append("apiVersion must be v0")
    for key in ("purpose", "name"):
        if not nonempty_string(profile.get(key)):
            errors.append(f"{key} must be a nonempty string")

    object_fields = (
        "freshness",
        "identity",
        "record",
        "execution",
        "docs",
        "ownership",
        "completeness",
        "trust",
        "links",
    )
    for key in object_fields:
        if not isinstance(profile.get(key), dict):
            errors.append(f"{key} must be an object")
    if not isinstance(profile.get("conflicts"), list):
        errors.append("conflicts must be an array")

    freshness = profile.get("freshness")
    if isinstance(freshness, dict):
        for key in ("generatedAt", "snapshotDigest"):
            if not nonempty_string(freshness.get(key)):
                errors.append(f"freshness.{key} must be a nonempty string")

    identity = profile.get("identity")
    if isinstance(identity, dict):
        for key in ("host", "owner", "repo"):
            if not nonempty_string(identity.get(key)):
                errors.append(f"identity.{key} must be a nonempty string")
        relative = path.relative_to(public_root / "v0" / "repos")
        expected_parts = relative.parts[:3]
        actual_parts = tuple(identity.get(key) for key in ("host", "owner", "repo"))
        if len(relative.parts) != 4 or relative.name != "profile.json":
            errors.append("profile path must be v0/repos/<host>/<owner>/<repo>/profile.json")
        elif actual_parts != expected_parts:
            errors.append(
                "identity does not match profile path: "
                f"expected {'/'.join(expected_parts)}"
            )

    record = profile.get("record")
    if isinstance(record, dict):
        for key in ("manifestPath", "mode"):
            if not nonempty_string(record.get(key)):
                errors.append(f"record.{key} must be a nonempty string")

    completeness = profile.get("completeness")
    if isinstance(completeness, dict):
        for key in sorted(COMPLETENESS_BOOL_KEYS):
            if not isinstance(completeness.get(key), bool):
                errors.append(f"completeness.{key} must be a boolean")
        conflict_count = completeness.get("conflictCount")
        if (
            not isinstance(conflict_count, int)
            or isinstance(conflict_count, bool)
            or conflict_count < 0
        ):
            errors.append("completeness.conflictCount must be a nonnegative integer")

    trust = profile.get("trust")
    if isinstance(trust, dict):
        if not nonempty_string(trust.get("selectedStatus")):
            errors.append("trust.selectedStatus must be a nonempty string")
        if not nonempty_string(trust.get("selectionReason")):
            errors.append("trust.selectionReason must be a nonempty string")

    links = profile.get("links")
    if isinstance(links, dict):
        missing_links = sorted(PROFILE_LINK_KEYS - links.keys())
        if missing_links:
            errors.append(f"missing required link keys: {', '.join(missing_links)}")
        for key in sorted(PROFILE_LINK_KEYS & links.keys()):
            if not nonempty_string(links.get(key)):
                errors.append(f"links.{key} must be a nonempty string")
    return errors


def profile_quality(profile: dict[str, Any]) -> dict[str, Any]:
    completeness = profile.get("completeness") or {}
    trust = profile.get("trust") or {}
    purpose = str(profile.get("purpose") or "").strip()
    signal_flags = {
        "hasPurpose": bool(purpose),
        "hasBuild": bool(completeness.get("hasBuild")),
        "hasTest": bool(completeness.get("hasTest")),
        "hasDocs": bool(completeness.get("hasDocs")),
        "hasSecurityContact": bool(completeness.get("hasSecurityContact")),
        "hasOwnershipSignal": bool(completeness.get("hasOwnershipSignal")),
        "hasLicense": bool(completeness.get("hasLicense")),
        "hasNoConflicts": int(completeness.get("conflictCount") or 0) == 0,
    }
    selected_status = str(trust.get("selectedStatus") or "unknown")
    confidence = str(trust.get("confidence") or "unknown")
    is_high_signal = (
        signal_flags["hasPurpose"]
        and selected_status in HIGH_SIGNAL_STATUSES
        and confidence in HIGH_SIGNAL_CONFIDENCE
        and signal_flags["hasNoConflicts"]
    )
    return {
        "selectedStatus": selected_status,
        "confidence": confidence,
        "signalFlags": signal_flags,
        "signalCount": sum(1 for value in signal_flags.values() if value),
        "isHighSignal": is_high_signal,
        "missingSignals": [
            key for key, value in signal_flags.items() if not value
        ],
    }


def summarize_profile(path: Path, public_root: Path) -> dict[str, Any]:
    try:
        profile = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return {
            "identity": path.relative_to(public_root).as_posix(),
            "path": path.relative_to(public_root).as_posix(),
            "contractErrors": [f"invalid JSON: {exc.msg}"],
            "valid": False,
        }
    errors = profile_contract_errors(profile, path, public_root)
    if not isinstance(profile, dict):
        return {
            "identity": path.relative_to(public_root).as_posix(),
            "path": path.relative_to(public_root).as_posix(),
            "contractErrors": errors,
            "valid": False,
        }
    quality = profile_quality(profile)
    return {
        "identity": profile_identity(profile, path),
        "path": path.relative_to(public_root).as_posix(),
        "purpose": profile.get("purpose"),
        "contractErrors": errors,
        "valid": not errors,
        **quality,
    }


def summarize(
    public_root: Path,
    min_profiles: int,
    min_high_signal: int,
    max_items: int,
    min_high_signal_ratio: float = 0.0,
    max_missing_signal: dict[str, int] | None = None,
    min_signal: dict[str, int] | None = None,
    max_malformed_profiles: int = 0,
) -> dict[str, Any]:
    discovered_profiles = [
        summarize_profile(path, public_root) for path in profile_paths(public_root)
    ]
    profiles = [profile for profile in discovered_profiles if profile["valid"]]
    malformed_profiles = [
        profile for profile in discovered_profiles if not profile["valid"]
    ]
    profile_count = len(profiles)
    high_signal_profiles = [profile for profile in profiles if profile["isHighSignal"]]
    lower_signal_profiles = [profile for profile in profiles if not profile["isHighSignal"]]
    status_counts = Counter(profile["selectedStatus"] for profile in profiles)
    confidence_counts = Counter(profile["confidence"] for profile in profiles)
    signal_counts: Counter[str] = Counter()
    missing_signal_counts: Counter[str] = Counter()
    for profile in profiles:
        signal_counts.update(
            key for key, value in profile["signalFlags"].items() if value
        )
        missing_signal_counts.update(profile["missingSignals"])

    high_signal_ratio = ratio(len(high_signal_profiles), profile_count)
    missing_limits = max_missing_signal or {}
    missing_signal_gates = {
        signal: {
            "threshold": threshold,
            "actual": int(missing_signal_counts.get(signal) or 0),
            "passed": int(missing_signal_counts.get(signal) or 0) <= threshold,
        }
        for signal, threshold in sorted(missing_limits.items())
    }
    signal_minimums = min_signal or {}
    min_signal_gates = {
        signal: {
            "threshold": threshold,
            "actual": int(signal_counts.get(signal) or 0),
            "passed": int(signal_counts.get(signal) or 0) >= threshold,
        }
        for signal, threshold in sorted(signal_minimums.items())
    }
    gates = {
        "minProfiles": {
            "threshold": min_profiles,
            "actual": profile_count,
            "passed": profile_count >= min_profiles,
        },
        "minHighSignal": {
            "threshold": min_high_signal,
            "actual": len(high_signal_profiles),
            "passed": len(high_signal_profiles) >= min_high_signal,
        },
        "minHighSignalRatio": {
            "threshold": min_high_signal_ratio,
            "actual": high_signal_ratio,
            "passed": (high_signal_ratio or 0.0) >= min_high_signal_ratio,
        },
        "minSignal": min_signal_gates,
        "maxMissingSignal": missing_signal_gates,
        "maxMalformedProfiles": {
            "threshold": max_malformed_profiles,
            "actual": len(malformed_profiles),
            "passed": len(malformed_profiles) <= max_malformed_profiles,
        },
    }
    passed = (
        gates["minProfiles"]["passed"]
        and gates["minHighSignal"]["passed"]
        and gates["minHighSignalRatio"]["passed"]
        and all(gate["passed"] for gate in min_signal_gates.values())
        and all(gate["passed"] for gate in missing_signal_gates.values())
        and gates["maxMalformedProfiles"]["passed"]
    )

    return {
        "schema": SCHEMA,
        "publicRoot": public_root.as_posix(),
        "summary": {
            "discoveredProfileCount": len(discovered_profiles),
            "profileCount": profile_count,
            "malformedProfileCount": len(malformed_profiles),
            "highSignalProfileCount": len(high_signal_profiles),
            "highSignalRatio": high_signal_ratio,
            "statusCounts": dict(sorted(status_counts.items())),
            "confidenceCounts": dict(sorted(confidence_counts.items())),
            "signalCounts": dict(sorted(signal_counts.items())),
            "missingSignalCounts": dict(sorted(missing_signal_counts.items())),
        },
        "gates": gates,
        "passed": passed,
        "lowerSignalProfiles": sorted(
            lower_signal_profiles,
            key=lambda profile: (profile["signalCount"], profile["identity"]),
        )[:max_items],
        "malformedProfiles": malformed_profiles[:max_items],
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    gates = report["gates"]
    lines = [
        "# dotrepo public profile coverage",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Profiles | {summary['profileCount']} |",
        f"| Discovered profile files | {summary['discoveredProfileCount']} |",
        f"| Malformed profiles | {summary['malformedProfileCount']} |",
        f"| High-signal profiles | {summary['highSignalProfileCount']} |",
        f"| High-signal ratio | {summary['highSignalRatio']} |",
        f"| Min profiles gate | {gates['minProfiles']['actual']} / {gates['minProfiles']['threshold']} |",
        f"| Min high-signal gate | {gates['minHighSignal']['actual']} / {gates['minHighSignal']['threshold']} |",
        f"| Min high-signal ratio gate | {gates['minHighSignalRatio']['actual']} / {gates['minHighSignalRatio']['threshold']} |",
        f"| Max malformed profiles gate | {gates['maxMalformedProfiles']['actual']} / {gates['maxMalformedProfiles']['threshold']} |",
        "",
    ]
    if gates["maxMissingSignal"]:
        lines.extend(["## Missing-Signal Gates", ""])
        for signal, gate in gates["maxMissingSignal"].items():
            result = "pass" if gate["passed"] else "fail"
            lines.append(
                f"- `{signal}`: {gate['actual']} / {gate['threshold']} ({result})"
            )
        lines.append("")
    if gates["minSignal"]:
        lines.extend(["## Signal Minimum Gates", ""])
        for signal, gate in gates["minSignal"].items():
            result = "pass" if gate["passed"] else "fail"
            lines.append(
                f"- `{signal}`: {gate['actual']} / {gate['threshold']} ({result})"
            )
        lines.append("")
    lines.extend(["## Lower-Signal Profiles", ""])
    if not report["lowerSignalProfiles"]:
        lines.append("- None in this report window.")
    else:
        for profile in report["lowerSignalProfiles"]:
            missing = ", ".join(profile["missingSignals"]) or "-"
            lines.append(
                f"- `{profile['identity']}`: status `{profile['selectedStatus']}`, "
                f"confidence `{profile['confidence']}`, missing {missing}"
            )
    lines.append("")
    lines.extend(["## Malformed Profiles", ""])
    if not report["malformedProfiles"]:
        lines.append("- None.")
    else:
        for profile in report["malformedProfiles"]:
            errors = "; ".join(profile["contractErrors"])
            lines.append(f"- `{profile['path']}`: {errors}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    report = summarize(
        Path(args.public_root),
        min_profiles=args.min_profiles,
        min_high_signal=args.min_high_signal,
        max_items=args.max_items,
        min_high_signal_ratio=args.min_high_signal_ratio,
        max_missing_signal=parse_max_missing_signal(args.max_missing_signal),
        min_signal=parse_min_signal(args.min_signal),
        max_malformed_profiles=args.max_malformed_profiles,
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
