import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from public_product_content import freshness_summary, record_status
from check_public_record_freshness import evaluate_freshness, evaluation_time, main
import pytest


def test_new_export_does_not_reset_record_age():
    assert record_status({"generatedAt": "2026-07-06T00:00:00Z"}, "2026-09-16T00:00:00Z") == (
        "stale",
        72,
    )
    assert record_status({"generatedAt": "2026-09-17T00:00:00Z"}, "2026-09-16T00:00:00Z") == (
        "unknown",
        None,
    )
    assert record_status({"generatedAt": "2026-09-16"}, "2026-09-16T00:00:00Z") == ("unknown", None)


def test_missing_profile_counts_as_unknown_and_export_dates_are_not_substituted(tmp_path):
    inventory = {
        "repositoryCount": 2,
        "repositories": [
            {"identity": {"host": "github.com", "owner": "example", "repo": repo}}
            for repo in ["old", "missing"]
        ],
    }
    root = tmp_path / "v0/repos/github.com/example/old"
    root.mkdir(parents=True)
    (root / "profile.json").write_text(
        json.dumps(
            {
                "record": {"generatedAt": "2026-07-06T00:00:00Z"},
                "freshness": {"generatedAt": "2026-09-16T00:00:00Z"},
            }
        )
    )
    summary = freshness_summary(tmp_path, inventory, "2026-09-16T00:00:00Z")
    assert (summary["fresh"], summary["stale"], summary["unknown"]) == (0, 1, 1)


def test_lookup_example_uses_record_command_source_and_age(tmp_path):
    from public_product_content import render_lookup_example

    inventory = {
        "repositoryCount": 1,
        "repositories": [{"identity": {"host": "github.com", "owner": "example", "repo": "tool"}}],
    }
    root = tmp_path / "v0/repos/github.com/example/tool"
    root.mkdir(parents=True)
    profile = {
        "identity": inventory["repositories"][0]["identity"],
        "record": {
            "generatedAt": "2026-07-06T00:00:00Z",
            "evidencePath": "repos/github.com/example/tool/evidence.md",
        },
        "execution": {"test": "run-tests --target '<example>'"},
    }
    (root / "profile.json").write_text(json.dumps(profile))
    rendered = render_lookup_example(tmp_path, inventory, "/preview", "2026-09-16T00:00:00Z")
    assert "72 days at export" in rendered
    assert "stale" in rendered
    assert "run-tests --target &#x27;&lt;example&gt;&#x27;" in rendered
    assert "Source evidence" in rendered
    assert "/preview/v0/repos/github.com/example/tool/profile.json" in rendered
    assert "read the upstream instructions" in rendered
    assert "<example>" not in rendered


def test_lookup_example_handles_absent_profiles_and_commands(tmp_path):
    from public_product_content import render_lookup_example

    assert "No profile is available" in render_lookup_example(tmp_path, {}, "", "unknown")
    inventory = {"repositories": [{"identity": {"host": "github.com", "owner": "x", "repo": "y"}}]}
    root = tmp_path / "v0/repos/github.com/x/y"
    root.mkdir(parents=True)
    (root / "profile.json").write_text(
        json.dumps({"identity": inventory["repositories"][0]["identity"]})
    )
    rendered = render_lookup_example(tmp_path, inventory, "", "unknown")
    assert "Unknown — inspect upstream test instructions" in rendered
    assert "Source evidence unavailable" in rendered
    assert "at an unknown time" in rendered


def freshness_fixture(tmp_path, dates):
    entries = []
    for index, date in enumerate(dates):
        identity = {"host": "github.com", "owner": "example", "repo": f"repo-{index}"}
        entries.append({"identity": identity})
        if date is None:
            continue
        root = tmp_path / "v0/repos/github.com/example" / identity["repo"]
        root.mkdir(parents=True)
        (root / "profile.json").write_text(
            json.dumps({"identity": identity, "record": {"generatedAt": date}})
        )
    return {"repositoryCount": len(entries), "repositories": entries}


def test_small_stale_population_still_fails_overdue_budget(tmp_path):
    inventory = freshness_fixture(
        tmp_path, ["2026-10-04T00:00:00Z"] * 19 + ["2026-08-01T00:00:00Z"]
    )
    result = evaluate_freshness(tmp_path, inventory, "2026-10-04T00:00:00Z")
    assert result["staleOrUnknownRate"] == 0.05
    assert result["oldestRefreshOverdueDays"] == 34
    assert result["overdueRepositories"][0]["identity"]["repo"] == "repo-19"
    assert not result["passed"]


def test_overdue_boundary_uses_fractional_days(tmp_path):
    inventory = freshness_fixture(tmp_path, ["2026-10-04T00:00:00Z"] * 9 + ["2026-08-28T00:00:00Z"])
    assert evaluate_freshness(tmp_path, inventory, "2026-10-04T00:00:00Z")["passed"]
    assert not evaluate_freshness(tmp_path, inventory, "2026-10-04T00:00:01Z")["passed"]


def test_freshness_cli_evaluates_at_check_time_not_export_time(tmp_path, monkeypatch):
    inventory = freshness_fixture(tmp_path, ["2026-08-01T00:00:00Z"])
    (tmp_path / "v0/repos/index.json").write_text(json.dumps(inventory))
    (tmp_path / "v0/meta.json").write_text(json.dumps({"generatedAt": "2026-08-02T00:00:00Z"}))
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freshness",
            "--public-root",
            str(tmp_path),
            "--now",
            "2026-10-04T00:00:00Z",
            "--output-json",
            str(output),
        ],
    )
    assert main() == 1
    report = json.loads(output.read_text())
    assert report["evaluatedAt"] == "2026-10-04T00:00:00Z"
    assert report["exportGeneratedAt"] == "2026-08-02T00:00:00Z"


def test_unknown_future_and_missing_records_fail_closed(tmp_path):
    inventory = freshness_fixture(tmp_path, ["2026-10-05T00:00:00Z", "2026-10-01", "invalid", None])
    result = evaluate_freshness(tmp_path, inventory, "2026-10-04T00:00:00Z")
    assert result["unknown"] == 4
    assert result["oldestRefreshOverdueDays"] is None
    assert not result["passed"]
    assert not evaluate_freshness(tmp_path, {"repositories": []}, "2026-10-04T00:00:00Z")["passed"]


def test_evaluation_time_requires_timezone_and_normalizes_offsets():
    assert evaluation_time("2026-10-04T08:00:00-04:00") == "2026-10-04T12:00:00Z"
    with pytest.raises(ValueError, match="timezone"):
        evaluation_time("2026-10-04T00:00:00")
    assert datetime_with_timezone(evaluation_time(None)).utcoffset().total_seconds() == 0


def datetime_with_timezone(value):
    from datetime import datetime

    return datetime.fromisoformat(value.replace("Z", "+00:00"))
