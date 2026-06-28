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
    path.parent.mkdir(parents=True)
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
    assert "| `name` | `github.com/example/orbit` | `repo.name` | mismatch |" in markdown
    assert "[README H1](https://github.com/example/orbit)" in markdown
