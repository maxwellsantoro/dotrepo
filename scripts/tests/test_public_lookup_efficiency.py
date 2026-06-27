import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "measure_public_lookup_efficiency.py"
SPEC = importlib.util.spec_from_file_location("measure_public_lookup_efficiency", SCRIPT)
lookup_efficiency = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(lookup_efficiency)

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_ROOT = (
    ROOT
    / "crates/dotrepo-core/tests/fixtures/public-export/expected/public"
)
INDEX_ROOT = (
    ROOT
    / "crates/dotrepo-core/tests/fixtures/public-export/fixture-index"
)
WORKLOAD = ROOT / "scripts/fixtures/public_lookup_workload.json"


def test_summarize_fixture_workload_reports_hit_rates_and_bytes() -> None:
    report = lookup_efficiency.summarize(
        PUBLIC_ROOT,
        INDEX_ROOT,
        WORKLOAD,
        generated_at="2026-03-10T18:30:00Z",
    )

    assert report["schema"] == "dotrepo-public-lookup-efficiency/v0"
    assert report["summary"]["taskCount"] == 2
    assert report["summary"]["hitCount"] == 1
    assert report["summary"]["hitRate"] == 0.5
    assert report["summary"]["fieldCount"] == 11
    assert report["summary"]["answeredFieldCount"] == 7
    assert report["summary"]["fieldHitRate"] == 0.6364
    assert report["summary"]["dotrepoBytes"] > 0
    assert report["summary"]["scrapeProxyBytes"] > 0
    assert report["passed"] is True
    assert report["gates"]["minTaskHitRate"] == {
        "threshold": 0.0,
        "actual": 0.5,
        "passed": True,
    }
    assert report["gates"]["minFieldHitRate"] == {
        "threshold": 0.0,
        "actual": 0.6364,
        "passed": True,
    }
    assert report["tasks"][0]["fieldValues"]["docs.root"] == "https://docs.example.com/orbit"
    assert "query-input/github.com/example/orbit.json" in report["tasks"][0]["inputs"]["publicFiles"]
    assert report["tasks"][1]["missingFields"] == [
        "repo.license",
        "repo.languages",
        "repo.build",
        "repo.test",
    ]


def test_missing_field_is_not_counted_as_hit(tmp_path: Path) -> None:
    workload = tmp_path / "workload.json"
    workload.write_text(
        """
{
  "schema": "dotrepo-public-lookup-workload/v0",
  "tasks": [
    {
      "id": "missing-topic",
      "repository": "github.com/example/orbit",
      "fields": ["repo.description", "repo.topics"]
    }
  ]
}
""".strip()
        + "\n"
    )

    report = lookup_efficiency.summarize(
        PUBLIC_ROOT,
        INDEX_ROOT,
        workload,
        generated_at="2026-03-10T18:30:00Z",
    )

    assert report["summary"]["taskCount"] == 1
    assert report["summary"]["hitCount"] == 0
    assert report["summary"]["fieldHitRate"] == 0.5
    assert report["tasks"][0]["answeredFields"] == ["repo.description"]
    assert report["tasks"][0]["missingFields"] == ["repo.topics"]


def test_threshold_gates_mark_report_failed() -> None:
    report = lookup_efficiency.summarize(
        PUBLIC_ROOT,
        INDEX_ROOT,
        WORKLOAD,
        generated_at="2026-03-10T18:30:00Z",
        min_task_hit_rate=0.75,
        min_field_hit_rate=0.75,
        max_dotrepo_to_scrape_proxy_ratio=1.0,
    )

    assert report["passed"] is False
    assert report["gates"]["minTaskHitRate"] == {
        "threshold": 0.75,
        "actual": 0.5,
        "passed": False,
    }
    assert report["gates"]["minFieldHitRate"] == {
        "threshold": 0.75,
        "actual": 0.6364,
        "passed": False,
    }
    assert report["gates"]["maxDotrepoToScrapeProxyRatio"] == {
        "threshold": 1.0,
        "actual": 6.4617,
        "passed": False,
    }


def test_render_markdown_includes_summary_table() -> None:
    report = lookup_efficiency.summarize(
        PUBLIC_ROOT,
        INDEX_ROOT,
        WORKLOAD,
        generated_at="2026-03-10T18:30:00Z",
    )

    markdown = lookup_efficiency.render_markdown(report)

    assert "# dotrepo public lookup efficiency benchmark" in markdown
    assert "| Tasks answered | 1 / 2 |" in markdown
    assert "## Gates" in markdown
    assert "| minTaskHitRate | 0.5 | 0.0 | pass |" in markdown
    assert "| `orbit-docs-and-owner` | `github.com/example/orbit` | true | - |" in markdown
