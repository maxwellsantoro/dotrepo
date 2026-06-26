from __future__ import annotations

import importlib.util
from argparse import Namespace
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "run_autonomous_index_batch.py"
SPEC = importlib.util.spec_from_file_location("run_autonomous_index_batch", SCRIPT)
autonomous_batch = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(autonomous_batch)


def test_aggregate_runs_calculates_retained_rates_and_recurring_failures() -> None:
    runs = [
        {
            "generatedAt": "2026-03-17T12:00:00Z",
            "crawled": 2,
            "written": 1,
            "failed": 1,
            "skipped": 0,
            "discoveryQueued": 1,
            "adjudicationCalls": 2,
            "tokensUsed": 50,
            "promoted": 1,
            "zeroModelRuns": 1,
            "repositoriesByAdjudicationTier": {"local_primary": 1},
            "failureClasses": {"parser": 1},
            "failureFingerprints": {"failed to parse TOML": 1},
            "failureFingerprintClasses": {"failed to parse TOML": "parser"},
        },
        {
            "generatedAt": "2026-03-18T12:00:00Z",
            "crawled": 2,
            "written": 2,
            "failed": 0,
            "skipped": 0,
            "discoveryQueued": 0,
            "adjudicationCalls": 0,
            "tokensUsed": 0,
            "promoted": 0,
            "zeroModelRuns": 2,
            "repositoriesByAdjudicationTier": {"local_primary": 1, "api_escalation": 1},
            "failureClasses": {},
            "failureFingerprints": {"failed to parse TOML": 1},
            "failureFingerprintClasses": {"failed to parse TOML": "parser"},
        },
    ]

    summary = autonomous_batch.aggregate_runs(runs)

    assert summary["runCount"] == 2
    assert summary["firstRunAt"] == "2026-03-17T12:00:00Z"
    assert summary["lastRunAt"] == "2026-03-18T12:00:00Z"
    assert summary["totals"]["crawled"] == 4
    assert summary["totals"]["written"] == 3
    assert summary["totals"]["discoveryQueued"] == 1
    assert summary["rates"]["writeRate"] == 0.75
    assert summary["rates"]["failureRate"] == 0.25
    assert summary["rates"]["adjudicationRate"] == 0.25
    assert summary["repositoriesByAdjudicationTier"] == {
        "api_escalation": 1,
        "local_primary": 2,
    }
    assert summary["failureClasses"] == {"parser": 1}
    assert summary["recurringFailures"] == [
        {"fingerprint": "failed to parse TOML", "count": 2}
    ]
    assert summary["regressionFixtureCandidates"] == [
        {
            "failureClass": "parser",
            "fingerprint": "failed to parse TOML",
            "count": 2,
            "suggestedFixture": "failed-to-parse-toml",
        }
    ]


def test_retain_telemetry_appends_history_and_writes_summary(tmp_path: Path) -> None:
    history = tmp_path / "index" / "telemetry" / "autonomous-runs.ndjson"
    summary_path = tmp_path / "index" / "telemetry" / "autonomous-summary.json"

    autonomous_batch.retain_telemetry(
        {
            "generatedAt": "2026-03-17T12:00:00Z",
            "crawled": 1,
            "written": 1,
            "failed": 0,
            "skipped": 0,
            "discoveryQueued": 0,
            "adjudicationCalls": 0,
            "tokensUsed": 0,
            "promoted": 0,
            "zeroModelRuns": 1,
            "repositoriesByAdjudicationTier": {},
            "failureClasses": {},
            "failureFingerprints": {},
            "failureFingerprintClasses": {},
        },
        history,
        summary_path,
    )
    autonomous_batch.retain_telemetry(
        {
            "generatedAt": "2026-03-18T12:00:00Z",
            "crawled": 1,
            "written": 0,
            "failed": 1,
            "skipped": 0,
            "discoveryQueued": 1,
            "adjudicationCalls": 1,
            "tokensUsed": 20,
            "promoted": 0,
            "zeroModelRuns": 0,
            "repositoriesByAdjudicationTier": {"local_primary": 1},
            "failureClasses": {"provider": 1},
            "failureFingerprints": {"model provider timeout": 1},
            "failureFingerprintClasses": {"model provider timeout": "provider"},
        },
        history,
        summary_path,
    )

    assert len(history.read_text().splitlines()) == 2
    summary = autonomous_batch.json.loads(summary_path.read_text())
    assert summary["runCount"] == 2
    assert summary["totals"]["failed"] == 1
    assert summary["totals"]["discoveryQueued"] == 1
    assert summary["failureClasses"] == {"provider": 1}
    assert summary["repositoriesByAdjudicationTier"] == {"local_primary": 1}


def test_enrich_telemetry_counts_verified_records_as_promoted() -> None:
    telemetry = {
        "crawls": [
            {"status": "written", "recordStatus": "verified", "adjudicationCalls": 0},
            {
                "status": "written",
                "recordStatus": "imported",
                "adjudicationCalls": 1,
                "escalation": {"adjudicationTiersUsed": ["local_primary"]},
            },
        ]
    }
    args = Namespace(
        index_root="index",
        state_path="index/.crawler-state.toml",
        batch_size=5,
        limit=20,
    )

    enriched = autonomous_batch.enrich_telemetry(telemetry, args)

    assert enriched["promoted"] == 1
    assert enriched["zeroModelRuns"] == 1
    assert enriched["repositoriesByAdjudicationTier"] == {"local_primary": 1}


def test_adjudication_tier_counts_records_unique_tiers_per_crawl() -> None:
    counts = autonomous_batch.adjudication_tier_counts(
        [
            {"escalation": {"adjudicationTiersUsed": ["local_primary"]}},
            {
                "escalation": {
                    "adjudicationTiersUsed": ["local_primary", "api_escalation"]
                }
            },
            {"escalation": {"adjudicationTiersUsed": []}},
        ]
    )

    assert counts == {"api_escalation": 1, "local_primary": 2}


def test_fixture_slug_normalizes_failure_fingerprints() -> None:
    assert (
        autonomous_batch.fixture_slug("OpenRouter HTTP 429: rate limit!")
        == "openrouter-http-429-rate-limit"
    )


def test_write_regression_fixture_candidate_artifacts(tmp_path: Path) -> None:
    summary = {
        "schema": "dotrepo/autonomous-telemetry-summary/v0.1",
        "generatedAt": "2026-03-18T12:00:00Z",
        "regressionFixtureCandidates": [
            {
                "failureClass": "parser",
                "fingerprint": "failed to parse TOML",
                "count": 2,
                "suggestedFixture": "failed-to-parse-toml",
            }
        ],
    }
    json_path = tmp_path / "regression-fixture-candidates.json"
    md_path = tmp_path / "regression-fixture-candidates.md"

    autonomous_batch.write_regression_fixture_candidate_artifacts(
        summary, json_path, md_path
    )

    payload = autonomous_batch.json.loads(json_path.read_text())
    assert payload["candidateCount"] == 1
    assert payload["candidates"][0]["suggestedFixture"] == "failed-to-parse-toml"
    rendered = md_path.read_text()
    assert "# Regression Fixture Candidates" in rendered
    assert "## failed-to-parse-toml" in rendered


def test_write_regression_fixture_stub_artifacts(tmp_path: Path) -> None:
    candidates = [
        {
            "failureClass": "parser",
            "fingerprint": "failed to parse TOML",
            "count": 2,
            "suggestedFixture": "failed-to-parse-toml",
        }
    ]
    stub_root = tmp_path / "stubs"

    autonomous_batch.write_regression_fixture_stub_artifacts(candidates, stub_root)

    metadata = autonomous_batch.json.loads(
        (stub_root / "failed-to-parse-toml" / "metadata.json").read_text()
    )
    assert metadata["schema"] == "dotrepo/regression-fixture-stub/v0.1"
    assert metadata["status"] == "needs_materialization"
    readme = (stub_root / "failed-to-parse-toml" / "README.md").read_text()
    assert "Materialization Checklist" in readme
    assert "failed to parse TOML" in readme


def test_crawl_env_caps_per_repo_calls_to_remaining_batch_budget() -> None:
    env = {
        "INDEX_MAX_ADJUDICATION_CALLS": "5",
        "DOTREPO_ADJUDICATION_URL": "http://127.0.0.1:8787/adjudicate",
    }

    capped = autonomous_batch.crawl_env_for_remaining_budget(env, 2)

    assert capped["INDEX_MAX_ADJUDICATION_CALLS"] == "2"
    assert capped["DOTREPO_ADJUDICATION_URL"] == "http://127.0.0.1:8787/adjudicate"


def test_crawl_env_disables_providers_when_batch_budget_is_exhausted() -> None:
    env = {
        "INDEX_MAX_ADJUDICATION_CALLS": "5",
        "DOTREPO_ADJUDICATION_URL": "http://127.0.0.1:8787/adjudicate",
        "DOTREPO_ADJUDICATION_SECOND_OPINION_URL": "http://127.0.0.1:8788/adjudicate",
        "DOTREPO_ADJUDICATION_API_URL": "https://example.com/adjudicate",
    }

    disabled = autonomous_batch.crawl_env_for_remaining_budget(env, 0)

    assert disabled["INDEX_MAX_ADJUDICATION_CALLS"] == "0"
    assert "DOTREPO_ADJUDICATION_URL" not in disabled
    assert "DOTREPO_ADJUDICATION_SECOND_OPINION_URL" not in disabled
    assert "DOTREPO_ADJUDICATION_API_URL" not in disabled


def test_adjudication_enabled_requires_budget_and_provider_url() -> None:
    assert autonomous_batch.adjudication_enabled(
        {
            "INDEX_MAX_ADJUDICATION_CALLS": "1",
            "DOTREPO_ADJUDICATION_URL": "http://127.0.0.1:8787/adjudicate",
        }
    )
    assert not autonomous_batch.adjudication_enabled(
        {
            "INDEX_MAX_ADJUDICATION_CALLS": "0",
            "DOTREPO_ADJUDICATION_URL": "http://127.0.0.1:8787/adjudicate",
        }
    )
    assert not autonomous_batch.adjudication_enabled({"INDEX_MAX_ADJUDICATION_CALLS": "1"})


def write_quality_record(
    index_root: Path,
    owner: str,
    repo: str,
    *,
    status: str,
    confidence: str,
    build: str | None = "make build",
    test: str | None = "make test",
    security: str | None = "security@example.com",
) -> None:
    record_dir = index_root / "repos" / "github.com" / owner / repo
    record_dir.mkdir(parents=True)
    lines = [
        'schema = "dotrepo/v0.1"',
        "",
        "[record]",
        'mode = "overlay"',
        f'status = "{status}"',
        "",
        "[record.trust]",
        f'confidence = "{confidence}"',
        'provenance = ["imported"]',
        "",
        "[repo]",
        f'name = "{repo}"',
        f'description = "{repo} description"',
        'languages = ["Rust"]',
    ]
    if build is not None:
        lines.append(f'build = "{build}"')
    if test is not None:
        lines.append(f'test = "{test}"')
    lines.extend(["", "[owners]"])
    if security is not None:
        lines.append(f'security_contact = "{security}"')
    (record_dir / "record.toml").write_text("\n".join(lines) + "\n")


def test_quality_reprocess_candidates_prioritize_lower_confidence(tmp_path: Path) -> None:
    index_root = tmp_path / "index"
    write_quality_record(index_root, "owner", "verified", status="verified", confidence="high")
    write_quality_record(
        index_root,
        "owner",
        "inferred",
        status="inferred",
        confidence="medium",
        build=None,
        test=None,
        security="unknown",
    )
    write_quality_record(index_root, "owner", "imported", status="imported", confidence="high")

    candidates = autonomous_batch.quality_reprocess_candidates(index_root)

    assert [candidate["identity"] for candidate in candidates] == [
        "github.com/owner/inferred",
        "github.com/owner/imported",
    ]


def test_fill_quality_reprocess_targets_supplements_open_batch_slots(tmp_path: Path) -> None:
    index_root = tmp_path / "index"
    selected_targets = tmp_path / "batch" / "selected-targets.txt"
    selected_metadata = tmp_path / "batch" / "selected-batch.json"
    selected_metadata.parent.mkdir(parents=True)
    selected_targets.write_text("github.com/owner/existing\n")
    selected_metadata.write_text(
        autonomous_batch.json.dumps(
            {"batch": {"id": "refresh-batch-01", "repositories": []}},
            indent=2,
        )
    )
    write_quality_record(index_root, "owner", "existing", status="imported", confidence="medium")
    write_quality_record(index_root, "owner", "alpha", status="inferred", confidence="medium")
    write_quality_record(index_root, "owner", "beta", status="imported", confidence="high")

    additions = autonomous_batch.fill_quality_reprocess_targets(
        index_root=index_root,
        selected_targets=selected_targets,
        selected_metadata=selected_metadata,
        batch_size=2,
    )

    assert [item["identity"] for item in additions] == ["github.com/owner/alpha"]
    assert selected_targets.read_text().splitlines() == [
        "github.com/owner/existing",
        "github.com/owner/alpha",
    ]
    metadata = autonomous_batch.json.loads(selected_metadata.read_text())
    assert metadata["qualityReprocessSupplement"]["repositoryCount"] == 1


def test_fill_discovery_targets_skips_existing_and_selected_repositories(tmp_path: Path) -> None:
    index_root = tmp_path / "index"
    selected_targets = tmp_path / "batch" / "selected-targets.txt"
    selected_metadata = tmp_path / "batch" / "selected-batch.json"
    selected_metadata.parent.mkdir(parents=True)
    selected_targets.write_text("github.com/owner/selected\n")
    selected_metadata.write_text(
        autonomous_batch.json.dumps(
            {"batch": {"id": "refresh-batch-01", "repositories": []}},
            indent=2,
        )
    )
    write_quality_record(index_root, "owner", "existing", status="verified", confidence="high")
    discovery_report = {
        "discovered": [
            {
                "repository": {
                    "host": "github.com",
                    "owner": "owner",
                    "repo": "selected",
                },
                "stars": 10,
                "defaultBranch": "main",
            },
            {
                "repository": {
                    "host": "github.com",
                    "owner": "owner",
                    "repo": "existing",
                },
                "stars": 20,
                "defaultBranch": "main",
            },
            {
                "repository": {
                    "host": "github.com",
                    "owner": "owner",
                    "repo": "new",
                },
                "stars": 30,
                "defaultBranch": "main",
            },
        ]
    }

    additions = autonomous_batch.fill_discovery_targets(
        index_root=index_root,
        selected_targets=selected_targets,
        selected_metadata=selected_metadata,
        batch_size=2,
        discovery_report=discovery_report,
    )

    assert [item["identity"] for item in additions] == ["github.com/owner/new"]
    assert selected_targets.read_text().splitlines() == [
        "github.com/owner/selected",
        "github.com/owner/new",
    ]
    metadata = autonomous_batch.json.loads(selected_metadata.read_text())
    assert metadata["discoverySupplement"]["repositoryCount"] == 1


def test_classify_failure_groups_known_operational_failures() -> None:
    assert autonomous_batch.classify_failure("failed to parse TOML") == "parser"
    assert autonomous_batch.classify_failure("repo.description is required") == "evidence"
    assert autonomous_batch.classify_failure("OpenRouter provider rejected model") == "provider"
    assert autonomous_batch.classify_failure("HTTP timeout fetching GitHub") == "infrastructure"
    assert autonomous_batch.classify_failure("autonomous writeback gate failed") == "validation"
