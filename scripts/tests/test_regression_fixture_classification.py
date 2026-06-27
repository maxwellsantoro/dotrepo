from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "run_autonomous_index_batch.py"
SPEC = importlib.util.spec_from_file_location("run_autonomous_index_batch", SCRIPT)
autonomous_batch = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(autonomous_batch)


def test_classify_ecosystem_detects_manifest_signals() -> None:
    assert autonomous_batch.classify_ecosystem("Cargo.toml parse error") == "rust"
    assert autonomous_batch.classify_ecosystem("package.json missing") == "node"
    assert autonomous_batch.classify_ecosystem("pyproject.toml bad") == "python"
    assert autonomous_batch.classify_ecosystem("go.mod not found") == "go"
    assert autonomous_batch.classify_ecosystem("pom.xml parse error") == "jvm"
    assert autonomous_batch.classify_ecosystem("Gemfile missing") == "ruby"
    assert autonomous_batch.classify_ecosystem("composer.json missing") == "php"
    assert autonomous_batch.classify_ecosystem("CMakeLists / cmake error") == "cpp"


def test_classify_ecosystem_is_unknown_without_a_signal() -> None:
    assert autonomous_batch.classify_ecosystem("OpenRouter HTTP 429") == "unknown"
    assert autonomous_batch.classify_ecosystem("") == "unknown"
    assert autonomous_batch.classify_ecosystem(None, None) == "unknown"


def test_classify_ecosystem_prefers_specific_manifest_over_loose_hint() -> None:
    # "cargo.toml" is a stronger signal than a bare language word and is listed first.
    assert autonomous_batch.classify_ecosystem("cargo.toml + python bindings") == "rust"


def test_fixture_eligible_only_for_deterministic_failure_classes() -> None:
    assert autonomous_batch.fixture_eligible("parser") is True
    assert autonomous_batch.fixture_eligible("evidence") is True
    assert autonomous_batch.fixture_eligible("validation") is True
    assert autonomous_batch.fixture_eligible("provider") is False
    assert autonomous_batch.fixture_eligible("infrastructure") is False
    assert autonomous_batch.fixture_eligible("writeback") is False
    assert autonomous_batch.fixture_eligible(None) is False
    assert autonomous_batch.fixture_eligible("unknown") is False


def test_aggregate_runs_marks_environmental_failures_not_fixture_eligible() -> None:
    run = {
        "crawled": 2,
        "failed": 2,
        "failureClasses": {"provider": 1, "parser": 1},
        "failureFingerprints": {
            "OpenRouter provider timeout": 1,
            "package.json parse error": 1,
        },
        "failureFingerprintClasses": {
            "OpenRouter provider timeout": "provider",
            "package.json parse error": "parser",
        },
        "failureFingerprintEcosystems": {
            "OpenRouter provider timeout": "unknown",
            "package.json parse error": "node",
        },
    }
    runs = [
        {"generatedAt": "2026-03-17T12:00:00Z", **run},
        {"generatedAt": "2026-03-18T12:00:00Z", **run},
    ]

    summary = autonomous_batch.aggregate_runs(runs)
    by_fixture = {
        item["fingerprint"]: item
        for item in summary["regressionFixtureCandidates"]
    }

    assert by_fixture["package.json parse error"]["fixtureEligible"] is True
    assert by_fixture["package.json parse error"]["ecosystem"] == "node"
    assert by_fixture["OpenRouter provider timeout"]["fixtureEligible"] is False
    assert by_fixture["OpenRouter provider timeout"]["ecosystem"] == "unknown"
    assert summary["failureClassesByEcosystem"] == {
        "parser/node": 2,
        "provider/unknown": 2,
    }


def test_aggregate_runs_infers_ecosystem_from_fingerprint_when_unset() -> None:
    # Older run records may not carry failureFingerprintEcosystems yet; the
    # classifier falls back to the fingerprint text deterministically.
    runs = [
        {
            "generatedAt": "2026-03-17T12:00:00Z",
            "crawled": 1,
            "failed": 1,
            "failureClasses": {"parser": 1},
            "failureFingerprints": {"go.mod parse error": 2},
            "failureFingerprintClasses": {"go.mod parse error": "parser"},
        },
    ]

    summary = autonomous_batch.aggregate_runs(runs)
    candidate = summary["regressionFixtureCandidates"][0]
    assert candidate["ecosystem"] == "go"
    assert candidate["fixtureEligible"] is True
