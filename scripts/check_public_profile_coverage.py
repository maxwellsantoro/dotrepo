#!/usr/bin/env -S uv run python

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Optional


SCHEMA = "dotrepo-public-profile-coverage/v0"
HIGH_SIGNAL_STATUSES = {"reviewed", "verified", "canonical"}
HIGH_SIGNAL_CONFIDENCE = {"medium", "high"}


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
        "--max-items",
        type=int,
        default=10,
        help="Maximum lower-signal profiles to include in the report",
    )
    parser.add_argument("--output-json", help="Optional path for JSON output")
    parser.add_argument("--output-md", help="Optional path for Markdown output")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"failed to parse JSON in {path}: {exc}") from exc


def profile_paths(public_root: Path) -> list[Path]:
    repos_root = public_root / "v0" / "repos"
    if not repos_root.is_dir():
        raise SystemExit(f"public root does not contain v0/repos/: {repos_root}")
    return sorted(repos_root.glob("*/*/*/profile.json"))


def ratio(numerator: int, denominator: int) -> Optional[float]:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def parse_max_missing_signal(values: list[str]) -> dict[str, int]:
    limits = {}
    for raw in values:
        if "=" not in raw:
            raise SystemExit(
                f"--max-missing-signal must use SIGNAL=COUNT, got {raw!r}"
            )
        signal, count_text = raw.split("=", 1)
        signal = signal.strip()
        if not signal:
            raise SystemExit(
                f"--max-missing-signal must include a signal name, got {raw!r}"
            )
        try:
            count = int(count_text)
        except ValueError as exc:
            raise SystemExit(
                f"--max-missing-signal count must be an integer, got {raw!r}"
            ) from exc
        if count < 0:
            raise SystemExit(
                f"--max-missing-signal count must be >= 0, got {raw!r}"
            )
        limits[signal] = count
    return limits


def profile_identity(profile: dict[str, Any], path: Path) -> str:
    identity = profile.get("identity") or {}
    try:
        return "/".join([identity["host"], identity["owner"], identity["repo"]])
    except KeyError:
        return path.as_posix()


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
    profile = load_json(path)
    quality = profile_quality(profile)
    return {
        "identity": profile_identity(profile, path),
        "path": path.relative_to(public_root).as_posix(),
        "purpose": profile.get("purpose"),
        **quality,
    }


def summarize(
    public_root: Path,
    min_profiles: int,
    min_high_signal: int,
    max_items: int,
    min_high_signal_ratio: float = 0.0,
    max_missing_signal: dict[str, int] | None = None,
) -> dict[str, Any]:
    profiles = [summarize_profile(path, public_root) for path in profile_paths(public_root)]
    profile_count = len(profiles)
    high_signal_profiles = [profile for profile in profiles if profile["isHighSignal"]]
    lower_signal_profiles = [profile for profile in profiles if not profile["isHighSignal"]]
    status_counts = Counter(profile["selectedStatus"] for profile in profiles)
    confidence_counts = Counter(profile["confidence"] for profile in profiles)
    missing_signal_counts: Counter[str] = Counter()
    for profile in profiles:
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
        "maxMissingSignal": missing_signal_gates,
    }
    passed = (
        gates["minProfiles"]["passed"]
        and gates["minHighSignal"]["passed"]
        and gates["minHighSignalRatio"]["passed"]
        and all(gate["passed"] for gate in missing_signal_gates.values())
    )

    return {
        "schema": SCHEMA,
        "publicRoot": public_root.as_posix(),
        "summary": {
            "profileCount": profile_count,
            "highSignalProfileCount": len(high_signal_profiles),
            "highSignalRatio": high_signal_ratio,
            "statusCounts": dict(sorted(status_counts.items())),
            "confidenceCounts": dict(sorted(confidence_counts.items())),
            "missingSignalCounts": dict(sorted(missing_signal_counts.items())),
        },
        "gates": gates,
        "passed": passed,
        "lowerSignalProfiles": sorted(
            lower_signal_profiles,
            key=lambda profile: (profile["signalCount"], profile["identity"]),
        )[:max_items],
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
        f"| High-signal profiles | {summary['highSignalProfileCount']} |",
        f"| High-signal ratio | {summary['highSignalRatio']} |",
        f"| Min profiles gate | {gates['minProfiles']['actual']} / {gates['minProfiles']['threshold']} |",
        f"| Min high-signal gate | {gates['minHighSignal']['actual']} / {gates['minHighSignal']['threshold']} |",
        f"| Min high-signal ratio gate | {gates['minHighSignalRatio']['actual']} / {gates['minHighSignalRatio']['threshold']} |",
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
