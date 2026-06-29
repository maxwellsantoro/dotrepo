from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts/check_release_gate.py"
SPEC = importlib.util.spec_from_file_location("check_release_gate", SCRIPT)
release_gate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(release_gate)


def test_release_gate_applies_versioned_profile_coverage_baseline(tmp_path: Path) -> None:
    public_dir = tmp_path / "public"
    output_root = tmp_path / "release-gate"

    command = release_gate.public_profile_coverage_command(
        REPO_ROOT, public_dir, output_root
    )

    assert command[1:4] == [
        "scripts/check_public_profile_coverage.py",
        "--public-root",
        str(public_dir),
    ]
    assert command[command.index("--min-profiles") + 1] == "181"
    assert command[command.index("--min-high-signal") + 1] == "121"
    assert command[command.index("--max-conflict-rate") + 1] == "0.0"
    assert command[command.index("--max-malformed-profiles") + 1] == "0"
    assert str(output_root / "public-profile-coverage.json") in command
    assert str(output_root / "public-profile-coverage.md") in command
    assert "hasBuild=132" in command
    assert "hasDocs=71" in command


def test_profile_coverage_baseline_is_well_formed() -> None:
    baseline = json.loads(
        (REPO_ROOT / "scripts/fixtures/public_profile_coverage_baseline.json").read_text()
    )

    assert baseline["schema"] == "dotrepo-public-profile-coverage-baseline/v0"
    assert baseline["minProfiles"] >= baseline["minHighSignal"] > 0
    assert 0 < baseline["minHighSignalRatio"] <= 1
    assert 0 <= baseline["maxConflictRate"] <= 1
    assert baseline["maxMalformedProfiles"] == 0
    assert all(
        0 < minimum <= baseline["minProfiles"]
        for minimum in baseline["minSignal"].values()
    )


def test_release_gate_applies_index_growth_tranche_baseline(tmp_path: Path) -> None:
    output_root = tmp_path / "release-gate"

    command = release_gate.index_growth_tranche_command(REPO_ROOT, output_root)

    assert "scripts/plan_index_growth_tranche.py" in command
    assert command[command.index("--candidate-file") + 1] == str(
        REPO_ROOT / "index/tranche-two-targets.txt"
    )
    assert command[command.index("--target-count") + 1] == "80"
    assert command[command.index("--min-selected") + 1] == "80"
    assert command[command.index("--current-high-signal") + 1] == "121"
    assert command[command.index("--milestone-high-signal-target") + 1] == "500"
    assert command[command.index("--min-planned-high-signal-capacity") + 1] == "201"
    assert str(output_root / "index-growth-targets.txt") in command
    assert str(output_root / "index-growth-plan.json") in command
    assert str(output_root / "index-growth-plan.md") in command


def test_index_growth_tranche_baseline_is_well_formed() -> None:
    baseline = json.loads(
        (REPO_ROOT / "scripts/fixtures/index_growth_tranche_baseline.json").read_text()
    )

    assert baseline == {
        "schema": "dotrepo-index-growth-tranche-baseline/v0",
        "candidateFile": "index/tranche-two-targets.txt",
        "milestoneHighSignalTarget": 500,
        "targetCount": 80,
        "minSelected": 80,
    }
    assert (REPO_ROOT / baseline["candidateFile"]).is_file()


def test_release_gate_builds_and_measures_research_lookup_workload(
    tmp_path: Path,
) -> None:
    public_dir = tmp_path / "public"
    output_root = tmp_path / "release-gate"

    build, measure = release_gate.public_lookup_benchmark_commands(
        REPO_ROOT,
        public_dir,
        output_root,
        "2026-06-28T00:00:00Z",
    )

    assert "scripts/build_public_lookup_workload.py" in build
    assert build[build.index("--mode") + 1] == "research"
    assert build[build.index("--limit") + 1] == "0"
    assert str(output_root / "public-lookup-workload.json") in build
    assert "scripts/measure_public_lookup_efficiency.py" in measure
    assert measure[measure.index("--min-tasks") + 1] == "724"
    assert measure[measure.index("--min-repositories") + 1] == "181"
    assert measure[measure.index("--min-task-hit-rate") + 1] == "0.64"
    assert measure[measure.index("--min-field-hit-rate") + 1] == "0.818"
    assert "overview=0.9" in measure
    assert "documentation=0.309" in measure
    assert "execution=0.685" in measure
    assert "security=0.657" in measure
    assert str(output_root / "public-lookup-efficiency.json") in measure
    assert str(output_root / "public-lookup-efficiency.md") in measure


def test_lookup_efficiency_baseline_is_well_formed() -> None:
    baseline = json.loads(
        (REPO_ROOT / "scripts/fixtures/public_lookup_efficiency_baseline.json").read_text()
    )

    assert baseline["schema"] == "dotrepo-public-lookup-efficiency-baseline/v0"
    assert baseline["mode"] == "research"
    assert baseline["limit"] == 0
    assert baseline["minTasks"] == baseline["minRepositories"] * 4
    assert 0 < baseline["minTaskHitRate"] <= baseline["minFieldHitRate"] <= 1
    assert set(baseline["minIntentHitRate"]) == {
        "overview",
        "execution",
        "documentation",
        "security",
    }
    assert all(0 < rate <= 1 for rate in baseline["minIntentHitRate"].values())


def test_release_gate_applies_cited_factual_accuracy_baseline(tmp_path: Path) -> None:
    public_dir = tmp_path / "public"
    output_root = tmp_path / "release-gate"

    command = release_gate.public_factual_accuracy_command(
        REPO_ROOT,
        public_dir,
        output_root,
        "2026-06-28T00:00:00Z",
    )

    assert "scripts/measure_public_factual_accuracy.py" in command
    assert "scripts/fixtures/public_factual_accuracy_workload.json" in command
    assert command[command.index("--min-assertions") + 1] == "20"
    assert command[command.index("--min-repositories") + 1] == "3"
    assert command[command.index("--min-accuracy-rate") + 1] == "1.0"
    assert command[command.index("--max-missing-rate") + 1] == "0.0"
    assert command[command.index("--max-mismatch-rate") + 1] == "0.0"
    assert str(output_root / "public-factual-accuracy.json") in command
    assert str(output_root / "public-factual-accuracy.md") in command


def test_factual_accuracy_baseline_and_workload_are_well_formed() -> None:
    baseline = json.loads(
        (REPO_ROOT / "scripts/fixtures/public_factual_accuracy_baseline.json").read_text()
    )
    workload = json.loads(
        (REPO_ROOT / "scripts/fixtures/public_factual_accuracy_workload.json").read_text()
    )

    assert baseline == {
        "schema": "dotrepo-public-factual-accuracy-baseline/v0",
        "minAssertions": 20,
        "minRepositories": 3,
        "minAccuracyRate": 1.0,
        "maxMissingRate": 0.0,
        "maxMismatchRate": 0.0,
    }
    assert workload["schema"] == "dotrepo-public-factual-accuracy-workload/v0"
    assert len(workload["assertions"]) == 20
    assert len({item["repository"] for item in workload["assertions"]}) == 3
