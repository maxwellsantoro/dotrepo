from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "render_unit_cost_report.py"
SPEC = importlib.util.spec_from_file_location("render_unit_cost_report", SCRIPT)
unit_cost = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(unit_cost)


def synthetic_runs() -> list[dict]:
    return [
        {
            "generatedAt": "2026-03-17T12:00:00Z",
            "crawled": 2,
            "unchangedSkips": [
                {
                    "repository": "github.com/example/stale",
                    "category": "unchanged",
                    "reason": "already fresh",
                    "wallTimeMs": 0,
                    "networkRequests": 0,
                    "networkBytes": 0,
                    "adjudicationCalls": 0,
                    "tokensUsed": 0,
                }
            ],
            "crawls": [
                {
                    "repository": "github.com/example/orbit",
                    "status": "written",
                    "category": "improved",
                    "recordStatus": "verified",
                    "wallTimeMs": 800,
                    "totalWallTimeMs": 950,
                    "networkRequests": 12,
                    "networkBytes": 40000,
                    "tokensUsed": 1200,
                    "adjudicationCalls": 2,
                    "cpuTimeMs": 500,
                    "peakMemoryBytes": 120_000_000,
                },
                {
                    "repository": "github.com/example/nova",
                    "status": "written",
                    "category": "changed",
                    "recordStatus": "imported",
                    "wallTimeMs": 600,
                    "totalWallTimeMs": 700,
                    "networkRequests": 10,
                    "networkBytes": 30000,
                    "tokensUsed": 0,
                    "adjudicationCalls": 0,
                    "cpuTimeMs": 300,
                    "peakMemoryBytes": 80_000_000,
                },
            ],
        },
        {
            "generatedAt": "2026-03-18T12:00:00Z",
            "crawled": 1,
            "unchangedSkips": [],
            "crawls": [
                {
                    "repository": "github.com/example/comet",
                    "status": "failed",
                    "category": "changed",
                    "commandWallTimeMs": 400,
                    "error": "boom",
                }
            ],
        },
    ]


def write_ndjson(path: Path, runs: list[dict]) -> None:
    path.write_text("".join(json.dumps(run) + "\n" for run in runs))


def test_collect_entries_splits_unchanged_changed_improved() -> None:
    runs = synthetic_runs()
    by_category = unit_cost.collect_entries(runs)

    assert [entry["repository"] for entry in by_category["unchanged"]] == [
        "github.com/example/stale"
    ]
    assert [entry["repository"] for entry in by_category["changed"]] == [
        "github.com/example/nova",
        "github.com/example/comet",
    ]
    assert [entry["repository"] for entry in by_category["improved"]] == [
        "github.com/example/orbit"
    ]


def test_wall_time_ms_prefers_in_process_timer_then_falls_back() -> None:
    assert unit_cost.wall_time_ms({"wallTimeMs": 100, "totalWallTimeMs": 200}) == 100.0
    assert unit_cost.wall_time_ms({"totalWallTimeMs": 200}) == 200.0
    assert unit_cost.wall_time_ms({"commandWallTimeMs": 300}) == 300.0
    assert unit_cost.wall_time_ms({}) is None


def test_build_report_computes_per_category_means() -> None:
    report = unit_cost.build_report(synthetic_runs())

    assert report["schema"] == "dotrepo/unit-cost-report/v0.1"
    assert report["runCount"] == 2
    assert report["totalEntries"] == 4

    unchanged = report["categories"]["unchanged"]
    assert unchanged["count"] == 1
    assert unchanged["wallTimeMs"]["mean"] == 0.0
    assert unchanged["networkBytes"]["mean"] == 0.0

    improved = report["categories"]["improved"]
    assert improved["count"] == 1
    assert improved["wallTimeMs"]["mean"] == 800.0
    assert improved["networkBytes"]["mean"] == 40000.0
    assert improved["tokensUsed"]["mean"] == 1200.0
    assert improved["modelCalls"]["mean"] == 2.0

    changed = report["categories"]["changed"]
    assert changed["count"] == 2
    # nova reports wallTimeMs=600; comet only has commandWallTimeMs=400.
    assert changed["wallTimeMs"]["mean"] == 500.0
    assert changed["wallTimeMs"]["sampled"] == 2
    # comet never produced JSON output, so it contributes no network sample.
    assert changed["networkBytes"]["sampled"] == 1

    assert improved["cpuTimeMs"]["mean"] == 500.0
    assert improved["cpuTimeMs"]["sampled"] == 1
    assert improved["peakMemoryBytes"]["mean"] == 120_000_000.0
    # Legacy entry without CPU/RSS (comet) keeps sampled count honest.
    assert changed["cpuTimeMs"]["sampled"] == 1
    assert changed["peakMemoryBytes"]["sampled"] == 1


def test_load_runs_reads_ndjson_fixture(tmp_path: Path) -> None:
    runs_path = tmp_path / "autonomous-runs.ndjson"
    write_ndjson(runs_path, synthetic_runs())

    loaded = unit_cost.load_runs(runs_path)

    assert len(loaded) == 2
    assert loaded[0]["crawled"] == 2


def test_load_runs_missing_file_returns_empty_list(tmp_path: Path) -> None:
    assert unit_cost.load_runs(tmp_path / "missing.ndjson") == []


def test_render_markdown_includes_category_table_and_documented_gap() -> None:
    report = unit_cost.build_report(synthetic_runs())
    markdown = unit_cost.render_markdown(report)

    assert "| unchanged |" in markdown
    assert "| changed |" in markdown
    assert "| improved |" in markdown
    assert "RUSAGE" in markdown or "process-group" in markdown
    assert "mean CPU" in markdown


def test_main_writes_json_and_markdown_outputs(tmp_path: Path) -> None:
    runs_path = tmp_path / "autonomous-runs.ndjson"
    write_ndjson(runs_path, synthetic_runs())
    output_json = tmp_path / "unit-cost-report.json"
    output_md = tmp_path / "unit-cost-report.md"

    import sys

    argv = sys.argv
    try:
        sys.argv = [
            "render_unit_cost_report.py",
            "--runs",
            str(runs_path),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ]
        exit_code = unit_cost.main()
    finally:
        sys.argv = argv

    assert exit_code == 0
    payload = json.loads(output_json.read_text())
    assert payload["schema"] == "dotrepo/unit-cost-report/v0.1"
    assert output_md.read_text().startswith("# Autonomous Crawl Unit-Cost Report")
