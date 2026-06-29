from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts/execute_roadmap_batch.py"
SPEC = importlib.util.spec_from_file_location("execute_roadmap_batch", SCRIPT)
roadmap_batch = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(roadmap_batch)


def test_baseline_int_reads_fixture_keys() -> None:
    assert roadmap_batch.baseline_int(
        REPO_ROOT / "scripts/fixtures/public_profile_coverage_baseline.json",
        "minHighSignal",
    ) == 239
    assert roadmap_batch.baseline_int(
        REPO_ROOT / "scripts/fixtures/index_growth_tranche_baseline.json",
        "milestoneHighSignalTarget",
    ) == 500


def test_plan_seed_targets_uses_growth_baselines(tmp_path: Path) -> None:
    index_root = tmp_path / "index"
    index_root.mkdir()
    targets_file = tmp_path / "targets.txt"
    targets_file.write_text("rust/one\n")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    args = argparse.Namespace(
        index_root=str(index_root),
        targets_file=str(targets_file),
        seed_batch_size=1,
    )

    planned = roadmap_batch.plan_seed_targets(
        args,
        output_dir,
        239,
        500,
        min_selected=0,
        min_planned_high_signal_capacity=239,
    )

    assert planned is None or planned.is_file()
    plan = json.loads((output_dir / "growth-plan.json").read_text())
    assert plan["gates"]["minPlannedHighSignalCapacity"]["threshold"] == 239
    assert plan["milestoneProgress"]["milestoneHighSignalTarget"] == 500


def test_dry_run_runs_planning_without_writeback_or_validate(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], *, check: bool = True):
        calls.append(command)
        class Result:
            stdout = "# Index Growth Status\n"
            stderr = ""
            returncode = 0

        return Result()

    def fake_plan_seed_targets(
        args,
        output_dir,
        current_high_signal,
        milestone_target,
        *,
        min_selected,
        min_planned_high_signal_capacity,
    ):
        planned = output_dir / "planned-targets.txt"
        planned.parent.mkdir(parents=True, exist_ok=True)
        planned.write_text("rust/one\n")
        return planned

    monkeypatch.setattr(roadmap_batch, "run", fake_run)
    monkeypatch.setattr(roadmap_batch, "plan_seed_targets", fake_plan_seed_targets)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "scripts/fixtures").mkdir(parents=True)
    (tmp_path / "scripts/fixtures/public_profile_coverage_baseline.json").write_text(
        json.dumps({"minHighSignal": 1})
    )
    (tmp_path / "scripts/fixtures/index_growth_tranche_baseline.json").write_text(
        json.dumps({"milestoneHighSignalTarget": 500, "minSelected": 0})
    )
    (tmp_path / "index").mkdir()
    targets_path = "index/candidate-targets.txt"
    (tmp_path / targets_path).write_text("rust/one\n")
    (tmp_path / "scripts/fixtures/index_growth_tranche_baseline.json").write_text(
        json.dumps(
            {
                "candidateFile": targets_path,
                "milestoneHighSignalTarget": 500,
                "minSelected": 0,
            }
        )
    )

    monkeypatch.setattr(
        roadmap_batch,
        "parse_args",
        lambda: argparse.Namespace(
            mode="all",
            index_root="index",
            targets_file=targets_path,
            seed_batch_size=8,
            refresh_batch_size=5,
            output_dir="roadmap-execution",
            skip_automation_enabled_check=True,
            dry_run=True,
        ),
    )

    assert roadmap_batch.main() == 0

    joined = [" ".join(command) for command in calls]
    assert any("render_index_growth_status.py" in command for command in joined)
    assert any("dotrepo-crawler" in command and "--dry-run" in command for command in joined)
    assert any("refresh-plan" in command for command in joined)
    assert any("plan_refresh_review_batches.py" in command for command in joined)
    assert not any("run_autonomous_index_batch.py" in command for command in joined)
    assert not any("validate-index" in command for command in joined)


def test_default_targets_file_reads_growth_baseline() -> None:
    baseline = json.loads(
        (REPO_ROOT / "scripts/fixtures/index_growth_tranche_baseline.json").read_text()
    )
    assert roadmap_batch.default_targets_file(REPO_ROOT) == baseline["candidateFile"]