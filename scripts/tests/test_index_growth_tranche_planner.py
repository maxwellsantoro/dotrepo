import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "plan_index_growth_tranche.py"
SPEC = importlib.util.spec_from_file_location("plan_index_growth_tranche", SCRIPT)
planner = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(planner)


def write_record(root: Path, owner: str, repo: str) -> None:
    record_dir = root / "repos" / "github.com" / owner / repo
    record_dir.mkdir(parents=True)
    (record_dir / "record.toml").write_text(
        "\n".join(
            [
                'schema = "dotrepo/v0.1"',
                "",
                "[record]",
                'mode = "overlay"',
                'status = "verified"',
                f'source = "https://github.com/{owner}/{repo}"',
                "",
                "[record.trust]",
                'confidence = "high"',
                'provenance = ["imported"]',
                "",
                "[repo]",
                f'name = "{repo}"',
            ]
        )
        + "\n"
    )


def test_build_plan_balances_groups_and_excludes_existing_records(tmp_path: Path) -> None:
    index_root = tmp_path / "index"
    write_record(index_root, "rust", "already")
    candidates = tmp_path / "candidates.txt"
    candidates.write_text(
        "\n".join(
            [
                "# Rust",
                "rust/already",
                "rust/one",
                "rust/two",
                "# Python",
                "python/one",
                "python/two",
                "# Go",
                "go/one",
            ]
        )
        + "\n"
    )

    plan = planner.build_plan(
        index_root=index_root,
        candidate_file=candidates,
        target_count=4,
        min_selected=4,
        current_high_signal=93,
        milestone_high_signal_target=500,
        min_planned_high_signal_capacity=97,
    )

    assert plan["schema"] == "dotrepo-index-growth-tranche-plan/v0"
    assert plan["passed"] is True
    assert plan["summary"]["existingRecordCount"] == 1
    assert plan["summary"]["candidateCount"] == 6
    assert plan["summary"]["eligibleCandidateCount"] == 5
    assert plan["summary"]["selectedCount"] == 4
    assert [target["target"] for target in plan["selectedTargets"]] == [
        "rust/one",
        "python/one",
        "go/one",
        "rust/two",
    ]
    assert plan["groups"]["Rust"] == {
        "candidates": 3,
        "eligible": 2,
        "selected": 2,
        "alreadyIndexed": 1,
    }
    assert plan["milestoneProgress"] == {
        "completedHighSignalProfiles": 93,
        "milestoneHighSignalTarget": 500,
        "selectedGrowthTargets": 4,
        "plannedHighSignalCapacityUpperBound": 97,
        "remainingHighSignalGap": 407,
        "remainingHighSignalGapAfterSelected": 403,
        "completedHighSignalRatio": 0.186,
        "plannedCapacityRatio": 0.194,
    }
    assert plan["gates"]["minPlannedHighSignalCapacity"] == {
        "threshold": 97,
        "actual": 97,
        "passed": True,
    }
    assert plan["alreadyIndexedCandidates"][0]["identity"] == "github.com/rust/already"


def test_duplicate_candidates_are_ignored_and_reported(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.txt"
    candidates.write_text("# Rust\nowner/repo\nowner/repo\ngithub.com/other/repo\n")

    plan = planner.build_plan(
        index_root=tmp_path / "index",
        candidate_file=candidates,
        target_count=10,
    )

    assert plan["summary"]["candidateCount"] == 2
    assert plan["summary"]["duplicateCandidateCount"] == 1
    assert [target["identity"] for target in plan["selectedTargets"]] == [
        "github.com/owner/repo",
        "github.com/other/repo",
    ]


def test_min_selected_gate_can_fail(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.txt"
    candidates.write_text("# Rust\nowner/repo\n")

    plan = planner.build_plan(
        index_root=tmp_path / "index",
        candidate_file=candidates,
        target_count=5,
        min_selected=2,
    )

    assert plan["passed"] is False
    assert plan["gates"]["minSelected"] == {
        "threshold": 2,
        "actual": 1,
        "passed": False,
    }


def test_min_planned_high_signal_capacity_gate_can_fail(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.txt"
    candidates.write_text("# Rust\nowner/repo\n")

    plan = planner.build_plan(
        index_root=tmp_path / "index",
        candidate_file=candidates,
        target_count=1,
        current_high_signal=93,
        milestone_high_signal_target=500,
        min_planned_high_signal_capacity=100,
    )

    assert plan["passed"] is False
    assert plan["gates"]["minPlannedHighSignalCapacity"] == {
        "threshold": 100,
        "actual": 94,
        "passed": False,
    }


def test_invalid_candidate_reports_file_and_line(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.txt"
    candidates.write_text("# Bad\nowner/../repo\n")

    with pytest.raises(SystemExit) as exc:
        planner.build_plan(
            index_root=tmp_path / "index",
            candidate_file=candidates,
            target_count=5,
        )

    assert f"{candidates}:2" in str(exc.value)
    assert "unsafe repository target" in str(exc.value)


def test_render_markdown_includes_selected_and_indexed_sections(tmp_path: Path) -> None:
    index_root = tmp_path / "index"
    write_record(index_root, "owner", "indexed")
    candidates = tmp_path / "candidates.txt"
    candidates.write_text("# Rust\nowner/indexed\nowner/new\n")
    plan = planner.build_plan(
        index_root=index_root,
        candidate_file=candidates,
        target_count=1,
    )

    markdown = planner.render_markdown(plan)

    assert "# Index Growth Tranche Plan" in markdown
    assert "- selected targets: 1/1" in markdown
    assert "## Milestone 2 Capacity" in markdown
    assert "- planned high-signal capacity upper bound: 1/500" in markdown
    assert "- `owner/new` (Rust)" in markdown
    assert "- `github.com/owner/indexed` (Rust)" in markdown
