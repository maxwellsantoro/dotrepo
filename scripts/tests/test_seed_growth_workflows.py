from pathlib import Path


WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
SEED_REVIEW = WORKFLOWS / "index-seed-review.yml"
SEED_BATCH_PR = WORKFLOWS / "index-seed-batch-pr.yml"


def test_seed_review_defaults_to_second_growth_tranche_and_plans_before_crawl() -> None:
    workflow = SEED_REVIEW.read_text()

    plan = workflow.index("scripts/plan_index_growth_tranche.py")
    crawl = workflow.index("cargo run -p dotrepo-crawler -- seed")
    batches = workflow.index("scripts/plan_seed_review_batches.py")
    summary = workflow.index("cat index-seed-review/growth-plan.md")
    status = workflow.index("scripts/render_index_growth_status.py")

    assert "default: index/tranche-two-targets.txt" in workflow
    assert 'targets_file="index/tranche-two-targets.txt"' in workflow
    assert "public_profile_coverage_baseline.json" in workflow[:plan]
    assert "index_growth_tranche_baseline.json" in workflow[:plan]
    assert "min_planned_capacity=$((current_high_signal + 1))" in workflow[:plan]
    assert plan < crawl < batches < summary
    assert "--min-selected 1" in workflow[plan:crawl]
    assert "--current-high-signal" in workflow[plan:crawl]
    assert "--milestone-high-signal-target" in workflow[plan:crawl]
    assert "--min-planned-high-signal-capacity" in workflow[plan:crawl]
    assert "--output-targets index-seed-review/planned-targets.txt" in workflow[plan:crawl]
    assert "--targets-file index-seed-review/planned-targets.txt" in workflow[crawl:batches]
    assert "--milestone-high-signal-target" in workflow[status:summary]
    assert "--targets-file \"${{ steps.inputs.outputs.targets_file }}\"" in workflow[
        batches:summary
    ]


def test_seed_batch_pr_defaults_to_second_growth_tranche_and_uses_planned_targets() -> None:
    workflow = SEED_BATCH_PR.read_text()

    plan = workflow.index("scripts/plan_index_growth_tranche.py")
    crawl = workflow.index("cargo run -p dotrepo-crawler -- seed")
    batches = workflow.index("scripts/plan_seed_review_batches.py")

    assert "default: index/tranche-two-targets.txt" in workflow
    assert 'targets_file="index/tranche-two-targets.txt"' in workflow
    assert "public_profile_coverage_baseline.json" in workflow[:plan]
    assert "index_growth_tranche_baseline.json" in workflow[:plan]
    assert "min_planned_capacity=$((current_high_signal + 1))" in workflow[:plan]
    assert plan < crawl < batches
    assert "--min-selected 1" in workflow[plan:crawl]
    assert "--current-high-signal" in workflow[plan:crawl]
    assert "--milestone-high-signal-target" in workflow[plan:crawl]
    assert "--min-planned-high-signal-capacity" in workflow[plan:crawl]
    assert "--output-targets index-seed-batch/planned-targets.txt" in workflow[plan:crawl]
    assert "--targets-file index-seed-batch/planned-targets.txt" in workflow[crawl:batches]
