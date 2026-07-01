from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "measure_public_factual_accuracy.py"
SPEC = importlib.util.spec_from_file_location("measure_public_factual_accuracy", SCRIPT)
accuracy = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(accuracy)


def write_query_input(root: Path, repository: str, manifest: dict) -> None:
    host, owner, repo = repository.split("/")
    path = root / "query-input" / host / owner / f"{repo}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"selection": {"manifest": manifest}}))


def write_workload(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "dotrepo-public-factual-accuracy-workload/v0",
                "assertions": [
                    {
                        "id": "name",
                        "repository": "github.com/example/orbit",
                        "path": "repo.name",
                        "expected": "Orbit",
                        "source": {
                            "url": "https://github.com/example/orbit",
                            "locator": "README H1",
                            "checkedAt": "2026-06-28",
                        },
                    },
                    {
                        "id": "test",
                        "repository": "github.com/example/orbit",
                        "path": "repo.test",
                        "expected": "cargo test",
                        "source": {
                            "url": "https://github.com/example/orbit/blob/main/Cargo.toml",
                            "locator": "Cargo manifest",
                            "checkedAt": "2026-06-28",
                        },
                    },
                ],
            }
        )
    )


def test_accuracy_report_distinguishes_correct_and_missing_values(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    workload = tmp_path / "workload.json"
    write_query_input(public_root, "github.com/example/orbit", {"repo": {"name": "Orbit"}})
    write_workload(workload)

    report = accuracy.summarize(
        public_root,
        workload,
        generated_at="2026-06-28T00:00:00Z",
        min_assertions=2,
        min_repositories=1,
        min_accuracy_rate=1.0,
    )

    assert report["passed"] is False
    assert report["summary"] == {
        "assertionCount": 2,
        "repositoryCount": 1,
        "correctCount": 1,
        "missingCount": 1,
        "mismatchCount": 0,
        "accuracyRate": 0.5,
        "missingRate": 0.5,
        "mismatchRate": 0.0,
        "correctAbstentionCount": 0,
        "correctAbstentionRate": 0.0,
        "incorrectFactCount": 0,
        "missingFactCount": 1,
        "ecosystemSummaries": {
            "Other": {
                "assertionCount": 2,
                "repositoryCount": 1,
                "correctCount": 1,
                "missingCount": 1,
                "mismatchCount": 0,
                "accuracyRate": 0.5,
                "missingRate": 0.5,
                "mismatchRate": 0.0,
                "correctAbstentionCount": 0,
                "correctAbstentionRate": 0.0,
                "incorrectFactCount": 0,
                "missingFactCount": 1,
            }
        },
    }
    assert report["gates"]["maxMissingRate"] == {
        "threshold": 1.0,
        "actual": 0.5,
        "passed": True,
    }
    assert report["gates"]["maxMismatchRate"] == {
        "threshold": 1.0,
        "actual": 0.0,
        "passed": True,
    }
    assert report["assertions"][0]["outcome"] == "correct"
    assert report["assertions"][1]["outcome"] == "missing"


def test_accuracy_report_detects_mismatched_values_and_renders_sources(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    workload = tmp_path / "workload.json"
    write_query_input(
        public_root,
        "github.com/example/orbit",
        {"repo": {"name": "Wrong", "test": "cargo test"}},
    )
    write_workload(workload)

    report = accuracy.summarize(public_root, workload, min_accuracy_rate=0.5)
    markdown = accuracy.render_markdown(report)

    assert report["passed"] is True
    assert report["summary"]["mismatchCount"] == 1
    assert report["summary"]["mismatchRate"] == 0.5
    assert "| Missing rate | 0.0 |" in markdown
    assert "| Mismatch rate | 0.5 |" in markdown
    assert (
        "| `name` | `github.com/example/orbit` | Other | `repo.name` | mismatch |" in markdown
    )
    assert "[README H1](https://github.com/example/orbit)" in markdown
    assert "## Ecosystem Results" in markdown
    assert "| Other | 1 / 2 | 0.5 |" in markdown


def test_mismatch_rate_gate_failure_sets_passed_false(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    workload = tmp_path / "workload.json"
    write_query_input(
        public_root,
        "github.com/example/orbit",
        {"repo": {"name": "Wrong", "test": "cargo test"}},
    )
    write_workload(workload)

    report = accuracy.summarize(
        public_root,
        workload,
        min_accuracy_rate=0.0,
        max_missing_rate=0.0,
        max_mismatch_rate=0.25,
    )

    assert report["passed"] is False
    assert report["gates"]["maxMissingRate"] == {
        "threshold": 0.0,
        "actual": 0.0,
        "passed": True,
    }
    assert report["gates"]["maxMismatchRate"] == {
        "threshold": 0.25,
        "actual": 0.5,
        "passed": False,
    }


def write_ecosystem_workload(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "dotrepo-public-factual-accuracy-workload/v0",
                "assertions": [
                    {
                        "id": "rust-name",
                        "repository": "github.com/example/orbit",
                        "path": "repo.name",
                        "expected": "Orbit",
                        "source": {
                            "url": "https://github.com/example/orbit",
                            "locator": "README H1",
                            "checkedAt": "2026-06-28",
                        },
                    },
                    {
                        "id": "rust-homepage",
                        "repository": "github.com/example/orbit",
                        "path": "repo.homepage",
                        "expected": "Wrong",
                        "source": {
                            "url": "https://github.com/example/orbit",
                            "locator": "README H1",
                            "checkedAt": "2026-06-28",
                        },
                    },
                    {
                        "id": "py-security-contact",
                        "repository": "github.com/example/nova",
                        "path": "owners.security_contact",
                        "expected": None,
                        "source": {
                            "url": "https://github.com/example/nova",
                            "locator": "SECURITY.md",
                            "checkedAt": "2026-06-28",
                        },
                    },
                    {
                        "id": "py-license",
                        "repository": "github.com/example/nova",
                        "path": "repo.license",
                        "expected": "MIT",
                        "source": {
                            "url": "https://github.com/example/nova",
                            "locator": "LICENSE",
                            "checkedAt": "2026-06-28",
                        },
                    },
                ],
            }
        )
    )


def test_ecosystem_summaries_and_correct_abstention_are_reported(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    workload = tmp_path / "workload.json"
    write_query_input(
        public_root,
        "github.com/example/orbit",
        {"repo": {"name": "Orbit", "homepage": "https://orbit.example.com", "languages": ["Rust"]}},
    )
    write_query_input(
        public_root,
        "github.com/example/nova",
        {"repo": {"languages": ["Python"]}, "owners": {}},
    )
    write_ecosystem_workload(workload)

    report = accuracy.summarize(
        public_root,
        workload,
        generated_at="2026-06-28T00:00:00Z",
        min_ecosystem_accuracy_rates={"Rust": 0.4, "Python": 1.0},
        max_ecosystem_mismatch_rates={"Rust": 0.6, "Python": 0.0},
    )

    ecosystems = report["summary"]["ecosystemSummaries"]
    assert set(ecosystems) == {"Rust", "Python"}
    assert ecosystems["Rust"] == {
        "assertionCount": 2,
        "repositoryCount": 1,
        "correctCount": 1,
        "missingCount": 0,
        "mismatchCount": 1,
        "accuracyRate": 0.5,
        "missingRate": 0.0,
        "mismatchRate": 0.5,
        "correctAbstentionCount": 0,
        "correctAbstentionRate": 0.0,
        "incorrectFactCount": 1,
        "missingFactCount": 0,
    }
    assert ecosystems["Python"] == {
        "assertionCount": 2,
        "repositoryCount": 1,
        "correctCount": 1,
        "missingCount": 1,
        "mismatchCount": 0,
        "accuracyRate": 0.5,
        "missingRate": 0.5,
        "mismatchRate": 0.0,
        "correctAbstentionCount": 1,
        "correctAbstentionRate": 0.5,
        "incorrectFactCount": 0,
        "missingFactCount": 1,
    }
    assert report["summary"]["correctAbstentionCount"] == 1
    assert report["summary"]["correctAbstentionRate"] == 0.25

    py_security = next(
        result for result in report["assertions"] if result["id"] == "py-security-contact"
    )
    assert py_security["outcome"] == "correct"
    assert py_security["correctAbstention"] is True
    assert py_security["ecosystem"] == "Python"

    # Rust gate passes (0.5 >= 0.4) but Python gate does not (0.5 < 1.0).
    assert report["gates"]["minEcosystemAccuracyRate.Rust"]["passed"] is True
    assert report["gates"]["minEcosystemAccuracyRate.Python"]["passed"] is False
    # Rust mismatch rate (0.5) is within budget (0.6); Python's (0.0) is within its budget too.
    assert report["gates"]["maxEcosystemMismatchRate.Rust"]["passed"] is True
    assert report["gates"]["maxEcosystemMismatchRate.Python"]["passed"] is True
    assert report["passed"] is False

    markdown = accuracy.render_markdown(report)
    assert "## Ecosystem Results" in markdown
    assert "| Python | 1 / 2 | 0.5 |" in markdown
    assert "| Rust | 1 / 2 | 0.5 |" in markdown
    assert "minEcosystemAccuracyRate.Python" in markdown
    assert "maxEcosystemMismatchRate.Rust" in markdown


def test_parse_family_rates_validates_bounds() -> None:
    assert accuracy.parse_family_rates(
        ["Rust=0.9", "Python=0.3"], "--min-ecosystem-accuracy-rate"
    ) == {"Rust": 0.9, "Python": 0.3}


def test_parse_family_rates_rejects_malformed_input() -> None:
    import pytest

    with pytest.raises(SystemExit):
        accuracy.parse_family_rates(["Rust"], "--min-ecosystem-accuracy-rate")
    with pytest.raises(SystemExit):
        accuracy.parse_family_rates(["Rust=1.5"], "--min-ecosystem-accuracy-rate")
    with pytest.raises(SystemExit):
        accuracy.parse_family_rates(["=0.5"], "--min-ecosystem-accuracy-rate")


def test_ecosystem_gate_for_absent_family_reports_none_and_fails(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    workload = tmp_path / "workload.json"
    write_query_input(public_root, "github.com/example/orbit", {"repo": {"name": "Orbit"}})
    write_workload(workload)

    report = accuracy.summarize(
        public_root,
        workload,
        min_ecosystem_accuracy_rates={"Go": 0.5},
    )

    assert report["gates"]["minEcosystemAccuracyRate.Go"] == {
        "threshold": 0.5,
        "actual": None,
        "passed": False,
    }
    assert report["passed"] is False
