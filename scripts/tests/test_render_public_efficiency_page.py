"""Protect the distinction between field presence, usable coverage, and modeled cost."""

import copy
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import render_public_efficiency_page as renderer
from measure_public_lookup_efficiency import summarize
from measure_public_policy_coverage import measure


ROOT = Path(__file__).resolve().parents[2]
PUBLIC_ROOT = ROOT / "crates/dotrepo-core/tests/fixtures/public-export/expected/public"
INDEX_ROOT = ROOT / "crates/dotrepo-core/tests/fixtures/public-export/fixture-index"
WORKLOAD = ROOT / "scripts/fixtures/public_lookup_workload.json"


@pytest.fixture
def policy_report():
    # Aggregate counts from the public 2026-10-03 export. No per-repository data is needed.
    counts = {
        "description": (613, 612),
        "documentation": (429, 429),
        "build": (402, 211),
        "test": (396, 219),
        "build-and-test": (356, 159),
    }
    return {
        "profileCount": 613,
        "evaluatedAt": "2026-10-03T20:37:11Z",
        "tasks": {
            task: {
                "presentCount": present,
                "acceptableCount": acceptable,
                "presenceRate": present / 613,
                "acceptableRate": acceptable / 613,
                "independentlyCorrectCount": None,
                "completedTaskCount": None,
            }
            for task, (present, acceptable) in counts.items()
        },
    }


@pytest.fixture
def lookup_report():
    return summarize(PUBLIC_ROOT, INDEX_ROOT, WORKLOAD, generated_at="2026-10-03T20:39:06Z")


class Elements(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.tags = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_coverage_chart_uses_report_values_and_common_scale(policy_report):
    rendered = renderer.render_policy_coverage(policy_report, "/prefix")
    tags = Elements(rendered).tags
    fills = [attrs for _, attrs in tags if "coverage-bar__fill " in attrs.get("class", "")]
    expected_tasks = [policy_report["tasks"][task] for task in renderer.POLICY_TASK_LABELS]

    assert len(fills) == 10
    for index, values in enumerate(expected_tasks):
        for offset, rate_key in enumerate(("presenceRate", "acceptableRate")):
            expected_width = f"width: {values[rate_key] * 100:.4f}%"
            assert fills[index * 2 + offset]["style"] == expected_width
    assert "58.1% <span>(356 / 613)</span>" in rendered
    assert "25.9% <span>(159 / 613)</span>" in rendered
    assert "454 of 613" in " ".join(rendered.split())
    assert "(74.1%) require upstream fallback" in rendered
    assert "same 0–100% scale" in rendered
    assert "evaluated 2026-10-03 20:37 UTC" in rendered
    assert rendered.index("<h3>Build and test</h3>") < rendered.index("Repository description")


def test_chart_labels_table_and_limitations_are_available_without_scripts(policy_report):
    rendered = renderer.render_policy_coverage(policy_report, "/prefix")
    tags = Elements(rendered).tags

    assert "<script" not in rendered
    assert rendered.count('class="coverage-bar__label">Fields present') == 5
    assert rendered.count('class="coverage-bar__label">Policy acceptable') == 5
    assert "<summary>View coverage as a data table</summary>" in rendered
    assert "<caption>Coverage out of 613 primary profiles</caption>" in rendered
    assert '<th scope="row">Build and test</th>' in rendered
    assert "356 (58.1%)" in rendered
    assert "159 (25.9%)" in rendered
    assert "Independent correctness and task completion: Not measured." in rendered
    assert "not permission to execute commands" in rendered
    assert "/prefix/benchmarks/policy-coverage.json" in rendered
    assert all(
        attrs.get("aria-hidden") == "true"
        for _, attrs in tags
        if attrs.get("class") == "coverage-bar__track"
    )


def test_page_leads_with_policy_coverage_before_modeled_reduction(lookup_report, policy_report):
    rendered = renderer.render_efficiency_page(lookup_report, "", policy_report)
    body = rendered.split("<body>", 1)[1]

    assert "<h1>What a lookup can answer</h1>" in body
    assert body.index('id="coverage-heading"') < body.index('id="presence-heading"')
    assert body.index('id="presence-heading"') < body.index('id="cost-heading"')
    assert body.index('id="cost-heading"') < body.index("75.0% modeled request reduction")
    assert 'class="metric"' not in body
    assert "not live GitHub traffic or measured batch-response bytes" in body
    assert "No measured end-to-end savings claim is made here" in body
    assert "measure_public_policy_coverage.py" in body


def test_payload_cost_uses_correct_binary_units_and_reports_larger_payload(lookup_report):
    lookup_report["summary"].update(dotrepoBytes=6_959_481, scrapeProxyBytes=2_961_078)
    rendered = renderer.render_efficiency_page(lookup_report, "")

    assert "6.6 MiB" in rendered
    assert "2.8 MiB" in rendered
    assert "2.35× the proxy size" in rendered
    assert "1 MiB = 1,048,576 bytes" in rendered
    assert "&nbsp;MB" not in rendered


@pytest.mark.parametrize("report", [None, {"profileCount": 0, "tasks": {}}])
def test_unavailable_policy_does_not_invent_a_zero_rate(report):
    rendered = renderer.render_policy_coverage(report, "")

    assert "coverage-heading" in rendered
    assert "coverage-chart" not in rendered
    assert "0.0%" not in rendered
    assert "fallback" in rendered or "No profiles evaluated" in rendered


def test_chart_handles_zero_and_full_coverage_and_escapes_labels(policy_report):
    policy_report = copy.deepcopy(policy_report)
    policy_report["tasks"] = {
        "<unexpected-task>": {
            "presentCount": 613,
            "acceptableCount": 0,
            "presenceRate": 1,
            "acceptableRate": 0,
        }
    }
    rendered = renderer.render_policy_coverage(policy_report, "")

    assert "<unexpected-task>" not in rendered
    assert "&lt;unexpected-task&gt;" in rendered
    assert "width: 100.0000%" in rendered
    assert "width: 0.0000%" in rendered
    assert "100.0% <span>(613 / 613)</span>" in rendered
    assert "0.0% <span>(0 / 613)</span>" in rendered
    assert "require upstream fallback" not in rendered  # No combined task to summarize.


def test_render_publishes_the_same_policy_report_and_sanitized_lookup(
    tmp_path, monkeypatch, lookup_report
):
    public_root = tmp_path / "public"
    shutil.copytree(PUBLIC_ROOT, public_root)
    benchmark = tmp_path / "lookup.json"
    benchmark.write_text(json.dumps(lookup_report))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "render_public_efficiency_page.py",
            "--input",
            str(public_root),
            "--benchmark",
            str(benchmark),
        ],
    )

    assert renderer.main() == 0
    policy = json.loads((public_root / "benchmarks/policy-coverage.json").read_text())
    published_lookup = json.loads((public_root / "benchmarks/lookup-efficiency.json").read_text())
    page = (public_root / "efficiency/index.html").read_text()

    assert policy == measure(public_root)
    assert published_lookup["summary"] == lookup_report["summary"]
    assert published_lookup["tasks"] == []
    assert "path" not in published_lookup["workload"]
    assert "All 2 primary profiles" in page
    for counts in policy["tasks"].values():
        assert f"({counts['acceptableCount']} / 2)" in page


def test_unmeasured_presence_rates_are_not_zero():
    rendered = renderer.render_intent_rows({"overview": {"taskCount": 1}})
    assert rendered.count("Not measured") == 3
    assert "0.0%" not in rendered
