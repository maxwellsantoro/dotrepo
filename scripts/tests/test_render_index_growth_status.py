import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "render_index_growth_status.py"
SPEC = importlib.util.spec_from_file_location("render_index_growth_status", SCRIPT)
growth_status = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(growth_status)


def write_record(
    root: Path,
    owner: str,
    repo: str,
    *,
    status: str,
    confidence: str,
    languages: list[str],
    build: str | None = "make build",
    test: str | None = "make test",
    security: str | None = "security@example.com",
    generated_at: str | None = "2026-03-10T00:00:00Z",
) -> None:
    record_dir = root / "repos" / "github.com" / owner / repo
    record_dir.mkdir(parents=True)
    lines = [
        'schema = "dotrepo/v0.1"',
        "",
        "[record]",
        'mode = "overlay"',
        f'status = "{status}"',
        f'source = "https://github.com/{owner}/{repo}"',
    ]
    if generated_at is not None:
        lines.append(f'generated_at = "{generated_at}"')
    lines.extend(
        [
            "",
            "[record.trust]",
            f'confidence = "{confidence}"',
            'provenance = ["imported"]',
            "",
            "[repo]",
            f'name = "{repo}"',
            f'description = "{repo} description"',
            f'homepage = "https://github.com/{owner}/{repo}"',
            "languages = [",
        ]
    )
    lines.extend(f'    "{language}",' for language in languages)
    lines.append("]")
    if build is not None:
        lines.append(f'build = "{build}"')
    if test is not None:
        lines.append(f'test = "{test}"')
    lines.extend(["", "[owners]"])
    if security is not None:
        lines.append(f'security_contact = "{security}"')
    (record_dir / "record.toml").write_text("\n".join(lines) + "\n")
    (record_dir / "evidence.md").write_text("# Evidence\n")


def test_summarize_reports_tranche_and_quality_queue(tmp_path: Path) -> None:
    index_root = tmp_path / "index"
    targets_file = tmp_path / "targets.txt"
    targets_file.write_text("# Rust\nowner/alpha\n# Go\nowner/beta\n")
    write_record(
        index_root,
        "owner",
        "alpha",
        status="verified",
        confidence="high",
        languages=["Rust"],
    )
    write_record(
        index_root,
        "owner",
        "beta",
        status="inferred",
        confidence="medium",
        languages=["Go"],
        build=None,
        test=None,
        security="unknown",
    )

    summary = growth_status.summarize(index_root, targets_file, max_items=5)

    assert summary["totalRecords"] == 2
    assert summary["passed"] is True
    assert summary["tranche"]["presentCount"] == 2
    assert summary["tranche"]["coverageRatio"] == 1.0
    assert summary["gates"]["minTrancheCoverageRatio"] == {
        "threshold": 0.0,
        "actual": 1.0,
        "passed": True,
    }
    assert summary["tranche"]["coverageByGroup"]["Rust"] == {"target": 1, "present": 1}
    assert summary["languageFamilyCounts"] == {"Rust": 1, "Go": 1}
    assert summary["qualitySignals"]["lowerConfidenceQueue"] == 1
    assert summary["milestoneProgress"] == {
        "recordLevelHighSignalCount": 1,
        "milestoneHighSignalTarget": 500,
        "recordLevelHighSignalRatio": 0.002,
        "activeTrancheMissingTargets": 0,
        "statusLiftCandidateCount": 0,
        "recordLevelPotentialAfterLift": 1,
        "recordLevelPotentialAfterLiftRatio": 0.002,
        "activeTrancheHighSignalCapacityUpperBound": 1,
        "activeTrancheCapacityRatio": 0.002,
        "remainingHighSignalGap": 499,
        "remainingHighSignalGapAfterStatusLift": 499,
        "remainingHighSignalGapAfterActiveTranche": 499,
    }
    assert summary["nextQualityTargets"][0]["identity"] == "github.com/owner/beta"


def test_summarize_reports_high_signal_lift_candidates(tmp_path: Path) -> None:
    index_root = tmp_path / "index"
    targets_file = tmp_path / "targets.txt"
    targets_file.write_text("# Rust\nowner/alpha\n")
    write_record(
        index_root,
        "owner",
        "alpha",
        status="imported",
        confidence="high",
        languages=["Rust"],
    )

    summary = growth_status.summarize(index_root, targets_file, max_items=5)

    assert summary["milestoneProgress"]["recordLevelHighSignalCount"] == 0
    assert summary["milestoneProgress"]["statusLiftCandidateCount"] == 1
    assert summary["milestoneProgress"]["recordLevelPotentialAfterLift"] == 1
    assert summary["milestoneProgress"]["remainingHighSignalGapAfterStatusLift"] == 499
    assert summary["nextHighSignalLiftTargets"] == [
        {
            "identity": "github.com/owner/alpha",
            "status": "imported",
            "confidence": "high",
            "primaryLanguage": "Rust",
            "languageFamily": "Rust",
        }
    ]


def test_summarize_operational_gates_fail_when_thresholds_are_not_met(tmp_path: Path) -> None:
    index_root = tmp_path / "index"
    targets_file = tmp_path / "targets.txt"
    targets_file.write_text("# Rust\nowner/alpha\n# Go\nowner/beta\n")
    write_record(
        index_root,
        "owner",
        "alpha",
        status="imported",
        confidence="medium",
        languages=["Rust"],
        build=None,
        test=None,
        security="unknown",
    )

    summary = growth_status.summarize(
        index_root,
        targets_file,
        max_items=5,
        min_tranche_coverage_ratio=0.75,
        max_lower_confidence_queue=0,
        max_missing_targets=0,
        milestone_high_signal_target=3,
        min_tranche_high_signal_capacity=2,
    )

    assert summary["passed"] is False
    assert summary["tranche"]["coverageRatio"] == 0.5
    assert summary["gates"] == {
        "minTrancheCoverageRatio": {
            "threshold": 0.75,
            "actual": 0.5,
            "passed": False,
        },
        "maxLowerConfidenceQueue": {
            "threshold": 0,
            "actual": 1,
            "passed": False,
        },
        "maxMissingTargets": {
            "threshold": 0,
            "actual": 1,
            "passed": False,
        },
        "minTrancheHighSignalCapacity": {
            "threshold": 2,
            "actual": 1,
            "passed": False,
        },
    }


def test_summarize_reports_freshness_queue_and_stale_gate(tmp_path: Path) -> None:
    index_root = tmp_path / "index"
    targets_file = tmp_path / "targets.txt"
    targets_file.write_text("# Rust\nowner/fresh\nowner/stale\nowner/missing\nowner/invalid\n")
    write_record(
        index_root,
        "owner",
        "fresh",
        status="verified",
        confidence="high",
        languages=["Rust"],
        generated_at="2026-03-28T00:00:00Z",
    )
    write_record(
        index_root,
        "owner",
        "stale",
        status="verified",
        confidence="high",
        languages=["Rust"],
        generated_at="2026-02-01T00:00:00Z",
    )
    write_record(
        index_root,
        "owner",
        "missing",
        status="verified",
        confidence="high",
        languages=["Rust"],
        generated_at=None,
    )
    write_record(
        index_root,
        "owner",
        "invalid",
        status="verified",
        confidence="high",
        languages=["Rust"],
        generated_at="not-a-date",
    )

    summary = growth_status.summarize(
        index_root,
        targets_file,
        max_items=5,
        stale_after_days=30,
        now=datetime(2026, 4, 1, tzinfo=timezone.utc),
        max_stale_or_missing_record_rate=0.5,
        max_refresh_overdue_days=20,
    )

    freshness = summary["freshnessSignals"]
    assert summary["passed"] is False
    assert freshness["recordCount"] == 4
    assert freshness["generatedAtKnown"] == 2
    assert freshness["staleRecords"] == 1
    assert freshness["missingGeneratedAt"] == 1
    assert freshness["invalidGeneratedAt"] == 1
    assert freshness["staleOrMissingRecords"] == 3
    assert freshness["staleRecordRate"] == 0.25
    assert freshness["staleOrMissingRecordRate"] == 0.75
    assert freshness["maxRecordAgeDays"] == 59.0
    assert freshness["maxRefreshOverdueDays"] == 29.0
    assert freshness["meanRefreshOverdueDays"] == 29.0
    assert freshness["totalRefreshOverdueDays"] == 29.0
    assert freshness["oldestGeneratedAt"] == "2026-02-01T00:00:00Z"
    assert freshness["newestGeneratedAt"] == "2026-03-28T00:00:00Z"
    assert freshness["staleRecordIdentities"] == ["github.com/owner/stale"]
    assert freshness["missingGeneratedAtIdentities"] == ["github.com/owner/missing"]
    assert freshness["invalidGeneratedAtIdentities"] == ["github.com/owner/invalid"]
    assert summary["gates"]["maxStaleOrMissingRecordRate"] == {
        "threshold": 0.5,
        "actual": 0.75,
        "passed": False,
    }
    assert summary["gates"]["maxRefreshOverdueDays"] == {
        "threshold": 20,
        "actual": 29.0,
        "passed": False,
    }

    markdown = growth_status.render_markdown(summary)

    assert "- stale/missing generated_at: 3/4 (0.75) as of 2026-04-01T00:00:00Z" in markdown
    assert "- refresh overdue latency: max=29.0 days, mean=29.0 days" in markdown
    assert "- `github.com/owner/stale`: stale generated_at" in markdown
    assert "- `github.com/owner/missing`: missing generated_at" in markdown
    assert "- `github.com/owner/invalid`: invalid generated_at" in markdown


def test_render_markdown_includes_operational_gates(tmp_path: Path) -> None:
    index_root = tmp_path / "index"
    targets_file = tmp_path / "targets.txt"
    targets_file.write_text("# Rust\nowner/alpha\n")
    write_record(
        index_root,
        "owner",
        "alpha",
        status="verified",
        confidence="high",
        languages=["Rust"],
    )

    markdown = growth_status.render_markdown(
        growth_status.summarize(
            index_root,
            targets_file,
            max_items=5,
            min_tranche_coverage_ratio=1.0,
            max_lower_confidence_queue=0,
        )
    )

    assert "- candidate coverage: 1/1 present (1.0)" in markdown
    assert "- record-level high-signal: 1/500 (0.002)" in markdown
    assert "- high-signal lift candidates: 0" in markdown
    assert "- record-level potential after lift: 1/500 (0.002)" in markdown
    assert "- active candidate high-signal capacity upper bound: 1/500 (0.002)" in markdown
    assert "## Gates" in markdown
    assert "- minTrancheCoverageRatio: 1.0 / 1.0 (pass)" in markdown
    assert "- maxLowerConfidenceQueue: 0 / 0 (pass)" in markdown


def test_malformed_toml_exits_with_path(tmp_path: Path) -> None:
    record_dir = tmp_path / "index" / "repos" / "github.com" / "owner" / "bad"
    record_dir.mkdir(parents=True)
    record_path = record_dir / "record.toml"
    record_path.write_text('schema = "dotrepo/v0.1"\n[record\n')

    with pytest.raises(SystemExit) as exc:
        growth_status.summarize(tmp_path / "index", tmp_path / "targets.txt", max_items=5)

    assert "failed to parse TOML" in str(exc.value)
    assert str(record_path) in str(exc.value)


def test_inferred_language_family_uses_dominant_language_not_any_occurrence() -> None:
    # Reproduces a real audit finding: docker/awesome-compose and
    # firecrawl/firecrawl were misclassified as "Rust" family purely because
    # Rust appeared somewhere in their (previously alphabetically-ordered,
    # now byte-count-ordered) languages list, even though Rust was not their
    # dominant language.
    record = {"repo": {"languages": ["Go", "Dockerfile", "Shell", "Rust"]}}
    assert growth_status.inferred_language_family(record) == "Go"

    record = {"repo": {"languages": ["Rust", "Go"]}}
    assert growth_status.inferred_language_family(record) == "Rust"

    record = {"repo": {"languages": []}}
    assert growth_status.inferred_language_family(record) == "Other"
