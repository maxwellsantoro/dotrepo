from pathlib import Path


WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def test_public_edge_canary_is_fail_closed_and_daily() -> None:
    workflow = (WORKFLOWS / "public-edge-canary.yml").read_text()

    assert 'cron: "0 14 * * *"' in workflow
    assert 'cron: "17,47 * * * *"' not in workflow
    assert "vars.DOTREPO_PUBLIC_EDGE_CANARY_ENABLED == 'true'" in workflow
    assert "github.event_name == 'workflow_dispatch'" in workflow
    assert "group: public-edge-canary" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "uv sync --dev --locked" in workflow
    assert "Skipping duplicate failure comment" in workflow


def test_index_seed_review_schedule_is_fail_closed() -> None:
    workflow = (WORKFLOWS / "index-seed-review.yml").read_text()

    assert "vars.DOTREPO_INDEX_SEED_REVIEW_ENABLED == 'true'" in workflow
    assert "github.event_name == 'workflow_dispatch'" in workflow


def test_index_refresh_review_schedule_is_fail_closed() -> None:
    workflow = (WORKFLOWS / "index-refresh-review.yml").read_text()

    assert "vars.DOTREPO_INDEX_REFRESH_REVIEW_ENABLED == 'true'" in workflow
    assert "github.event_name == 'workflow_dispatch'" in workflow
