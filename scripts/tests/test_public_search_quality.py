import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "measure_public_search_quality.py"
SPEC = importlib.util.spec_from_file_location("measure_public_search_quality", SCRIPT)
search_quality = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(search_quality)

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_ROOT = (
    ROOT
    / "crates/dotrepo-core/tests/fixtures/public-export/expected/public"
)
WORKLOAD = ROOT / "scripts/fixtures/public_search_workload.json"


def test_summarize_fixture_workload_reports_search_quality() -> None:
    report = search_quality.summarize(
        PUBLIC_ROOT,
        WORKLOAD,
        generated_at="2026-03-10T18:30:00Z",
    )

    assert report["schema"] == "dotrepo-public-search-quality/v0"
    assert report["summary"]["taskCount"] == 2
    assert report["summary"]["successCount"] == 2
    assert report["summary"]["successRate"] == 1.0
    assert report["summary"]["meanReciprocalRank"] == 1.0
    assert report["summary"]["averageFirstExpectedRank"] == 1.0
    assert report["summary"]["candidateProfileCount"] == 2
    assert report["summary"]["searchedProfileBytes"] > 0
    assert report["summary"]["freshness"]["snapshotCount"] == 1
    assert report["passed"] is True
    assert report["gates"]["minSuccessRate"] == {
        "threshold": 0.0,
        "actual": 1.0,
        "passed": True,
    }
    assert report["tasks"][0]["returnedRepositories"] == ["github.com/example/orbit"]
    assert report["tasks"][0]["topResults"][0]["ranking"] == {
        "score": 43,
        "matchedFieldCount": 4,
        "completenessSignalCount": 3,
        "basis": ["matchedFields", "profileCompleteness"],
    }
    assert "trust" not in report["tasks"][0]["topResults"][0]["ranking"]


def test_missing_expected_repository_is_not_success(tmp_path: Path) -> None:
    workload = tmp_path / "workload.json"
    workload.write_text(
        """
{
  "schema": "dotrepo-public-search-workload/v0",
  "tasks": [
    {
      "id": "missing-result",
      "query": "orbit",
      "expectedRepositories": ["github.com/example/nova"],
      "filters": {
        "requireDocs": true
      },
      "limit": 5
    }
  ]
}
""".strip()
        + "\n"
    )

    report = search_quality.summarize(
        PUBLIC_ROOT,
        workload,
        generated_at="2026-03-10T18:30:00Z",
    )

    assert report["summary"]["taskCount"] == 1
    assert report["summary"]["successCount"] == 0
    assert report["summary"]["successRate"] == 0.0
    assert report["summary"]["meanReciprocalRank"] == 0.0
    assert report["tasks"][0]["expectedRanks"] == {"github.com/example/nova": None}


def test_threshold_gates_mark_report_failed(tmp_path: Path) -> None:
    workload = tmp_path / "workload.json"
    workload.write_text(
        """
{
  "schema": "dotrepo-public-search-workload/v0",
  "tasks": [
    {
      "id": "rank-two",
      "query": "example",
      "expectedRepositories": ["github.com/example/nova"],
      "limit": 5
    }
  ]
}
""".strip()
        + "\n"
    )

    report = search_quality.summarize(
        PUBLIC_ROOT,
        workload,
        generated_at="2026-03-10T18:30:00Z",
        min_success_rate=1.0,
        min_mean_reciprocal_rank=0.75,
        max_average_first_rank=1.0,
    )

    assert report["passed"] is False
    assert report["summary"]["successRate"] == 1.0
    assert report["summary"]["meanReciprocalRank"] == 0.5
    assert report["summary"]["averageFirstExpectedRank"] == 2.0
    assert report["gates"]["minMeanReciprocalRank"] == {
        "threshold": 0.75,
        "actual": 0.5,
        "passed": False,
    }
    assert report["gates"]["maxAverageFirstRank"] == {
        "threshold": 1.0,
        "actual": 2.0,
        "passed": False,
    }


def test_render_markdown_includes_gates_and_task_table() -> None:
    report = search_quality.summarize(
        PUBLIC_ROOT,
        WORKLOAD,
        generated_at="2026-03-10T18:30:00Z",
    )

    markdown = search_quality.render_markdown(report)

    assert "# dotrepo public search quality benchmark" in markdown
    assert "| Tasks succeeded | 2 / 2 |" in markdown
    assert "## Gates" in markdown
    assert "| minSuccessRate | 1.0 | 0.0 | pass |" in markdown
    assert "| `orbit-docs-discovery` | `orbit` | true | 1 | `github.com/example/orbit` |" in markdown
