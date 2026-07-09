#!/usr/bin/env -S uv run python
"""Execute the active ROADMAP.md batch loop: grow, refresh, telemetry, validate."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

UV_PYTHON = ["uv", "run", "python"]
GROWTH_BASELINE = Path(
    "scripts/fixtures/index_growth_tranche_baseline.json"
)  # baseline supplies candidateFile (may be exhausted tranche or arbitrary)


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def default_targets_file(repo_root: Path | None = None) -> str:
    root = repo_root or Path.cwd()
    baseline_path = root / GROWTH_BASELINE
    baseline = load_json(baseline_path)
    candidate = baseline.get("candidateFile")
    if isinstance(candidate, str) and candidate.strip():
        return candidate
    raise SystemExit(f"{baseline_path} is missing string candidateFile")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("seed", "refresh", "all"),
        default="all",
        help="Run candidate seed growth, overdue refresh, or both (default: all)",
    )
    parser.add_argument("--index-root", default="index")
    parser.add_argument(
        "--targets-file",
        default=None,
        help="Grouped candidate list for seed growth (default: index growth baseline candidateFile)",
    )
    parser.add_argument(
        "--seed-batch-size",
        type=int,
        default=8,
        help="Repositories to crawl in one seed batch (default: 8)",
    )
    parser.add_argument(
        "--refresh-batch-size",
        type=int,
        default=5,
        help="Repositories to refresh in one autonomous batch (default: 5)",
    )
    parser.add_argument(
        "--output-dir",
        default="roadmap-execution",
        help="Artifact directory for plans, reports, and telemetry",
    )
    parser.add_argument(
        "--skip-automation-enabled-check",
        action="store_true",
        help="Allow local runs without INDEX_AUTOMATION_ENABLED=true",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan seed targets and render status without writing index changes",
    )
    args = parser.parse_args()
    if args.targets_file is None:
        args.targets_file = default_targets_file()
    return args


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(command), flush=True)
    proc = subprocess.run(command, check=False, text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout, end="", flush=True)
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr, flush=True)
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, command, proc.stdout, proc.stderr)
    return proc


def baseline_int(path: Path, key: str) -> int:
    data = load_json(path)
    value = data.get(key)
    if not isinstance(value, int):
        raise SystemExit(f"{path} is missing integer {key!r}")
    return value


def render_growth_status(index_root: Path, targets_file: Path, output_md: Path) -> None:
    proc = run(
        [
            *UV_PYTHON,
            "scripts/render_index_growth_status.py",
            "--index-root",
            str(index_root),
            "--targets-file",
            str(targets_file),
        ]
    )
    output_md.write_text(proc.stdout, encoding="utf-8")


def plan_seed_targets(
    args: argparse.Namespace,
    output_dir: Path,
    current_high_signal: int,
    milestone_target: int,
    *,
    min_selected: int,
    min_planned_high_signal_capacity: int,
) -> Path | None:
    planned_targets = output_dir / "planned-targets.txt"
    run(
        [
            *UV_PYTHON,
            "scripts/plan_index_growth_tranche.py",
            "--index-root",
            args.index_root,
            "--candidate-file",
            args.targets_file,
            "--target-count",
            str(args.seed_batch_size),
            "--min-selected",
            str(min_selected),
            "--current-high-signal",
            str(current_high_signal),
            "--milestone-high-signal-target",
            str(milestone_target),
            "--min-planned-high-signal-capacity",
            str(min_planned_high_signal_capacity),
            "--output-targets",
            str(planned_targets),
            "--output-json",
            str(output_dir / "growth-plan.json"),
            "--output-md",
            str(output_dir / "growth-plan.md"),
        ]
    )
    if not planned_targets.is_file() or not planned_targets.read_text(encoding="utf-8").strip():
        print(
            "candidate catalog has no missing targets; skipping seed crawl",
            file=sys.stderr,
        )
        return None
    return planned_targets


def apply_seed_batch(args: argparse.Namespace, planned_targets: Path, output_dir: Path) -> None:
    seed_command = [
        "cargo",
        "run",
        "-q",
        "-p",
        "dotrepo-crawler",
        "--",
        "seed",
        "--index-root",
        args.index_root,
        "--targets-file",
        str(planned_targets),
        "--limit",
        str(args.seed_batch_size),
        "--review-report-md",
        str(output_dir / "seed-review.md"),
        "--json",
    ]
    if args.dry_run:
        seed_command.insert(len(seed_command) - 1, "--dry-run")
    proc = run(seed_command)
    (output_dir / "seed-report.json").write_text(proc.stdout, encoding="utf-8")


def plan_refresh_batch(args: argparse.Namespace, output_dir: Path) -> None:
    refresh_dir = output_dir / "refresh"
    refresh_dir.mkdir(parents=True, exist_ok=True)
    refresh_plan = refresh_dir / "refresh-plan.json"
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
            str(Path(args.index_root) / ".crawler-state.toml"),
            "--limit",
            str(max(args.refresh_batch_size * 4, 20)),
            "--json",
        ]
    )
    refresh_plan.write_text(proc.stdout, encoding="utf-8")
    run(
        [
            *UV_PYTHON,
            "scripts/plan_refresh_review_batches.py",
            "--input",
            str(refresh_plan),
            "--batch-size",
            str(args.refresh_batch_size),
            "--output-json",
            str(refresh_dir / "refresh-batches.json"),
            "--output-md",
            str(refresh_dir / "refresh-batches.md"),
        ]
    )


def apply_refresh_batch(args: argparse.Namespace, output_dir: Path) -> None:
    refresh_command = [
        *UV_PYTHON,
        "scripts/run_autonomous_index_batch.py",
        "--index-root",
        args.index_root,
        "--output-dir",
        str(output_dir / "refresh"),
        "--batch-size",
        str(args.refresh_batch_size),
        "--limit",
        str(max(args.refresh_batch_size * 4, 20)),
        "--batch-id",
        "roadmap-refresh-batch",
        "--telemetry-history",
        str(Path(args.index_root) / "telemetry" / "autonomous-runs.ndjson"),
        "--telemetry-summary",
        str(Path(args.index_root) / "telemetry" / "autonomous-summary.json"),
    ]
    if args.skip_automation_enabled_check:
        refresh_command.append("--skip-automation-enabled-check")
    run(refresh_command)


def validate_index() -> None:
    run(["cargo", "run", "-q", "-p", "dotrepo-cli", "--", "validate-index"])


def main() -> int:
    args = parse_args()
    if not args.skip_automation_enabled_check and os.environ.get(
        "INDEX_AUTOMATION_ENABLED", ""
    ).strip().lower() not in {"1", "true", "yes"}:
        print(
            "INDEX_AUTOMATION_ENABLED is not true; skipping roadmap batch "
            "(fail closed — set INDEX_AUTOMATION_ENABLED=true or pass "
            "--skip-automation-enabled-check for explicit local opt-in)",
            file=sys.stderr,
        )
        return 0

    repo_root = Path.cwd()
    output_dir = repo_root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    index_root = repo_root / args.index_root
    targets_file = repo_root / args.targets_file

    current_high_signal = baseline_int(
        repo_root / "scripts/fixtures/public_profile_coverage_baseline.json",
        "minHighSignal",
    )
    growth_baseline_path = repo_root / GROWTH_BASELINE
    growth_baseline = load_json(growth_baseline_path)
    milestone_target = baseline_int(growth_baseline_path, "milestoneHighSignalTarget")
    min_selected = int(growth_baseline.get("minSelected", 0))
    min_planned_capacity = current_high_signal + min_selected

    print(f"== roadmap batch: active candidate catalog: {args.targets_file} ==")
    print("== roadmap batch: pre-flight growth status ==")
    render_growth_status(index_root, targets_file, output_dir / "growth-status-before.md")
    print((output_dir / "growth-status-before.md").read_text(encoding="utf-8"))

    if args.mode in {"seed", "all"}:
        print("== roadmap batch: candidate seed growth ==")
        planned_targets = plan_seed_targets(
            args,
            output_dir,
            current_high_signal,
            milestone_target,
            min_selected=min_selected,
            min_planned_high_signal_capacity=min_planned_capacity,
        )
        seed_targets = planned_targets
        if seed_targets is None and args.dry_run:
            print(
                "candidate catalog exhausted; running seed dry-run audit against catalog",
                file=sys.stderr,
            )
            seed_targets = targets_file
        if seed_targets is not None:
            apply_seed_batch(args, seed_targets, output_dir)

    if args.mode in {"refresh", "all"}:
        if args.dry_run:
            print("== roadmap batch: refresh planning ==")
            plan_refresh_batch(args, output_dir)
        else:
            print("== roadmap batch: overdue refresh ==")
            apply_refresh_batch(args, output_dir)

    if not args.dry_run:
        print("== roadmap batch: validate-index ==")
        validate_index()

    print("== roadmap batch: post-flight growth status ==")
    render_growth_status(index_root, targets_file, output_dir / "growth-status-after.md")
    print((output_dir / "growth-status-after.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
