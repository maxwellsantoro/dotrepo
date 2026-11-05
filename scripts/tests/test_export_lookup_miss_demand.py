import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "export_lookup_miss_demand.py"
FIXTURE = REPO / "scripts" / "fixtures" / "lookup_miss_sample.log"


def test_export_lookup_miss_demand_from_fixture(tmp_path: Path) -> None:
    out_dir = tmp_path / "telemetry"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(FIXTURE),
            "--output-dir",
            str(out_dir),
            "--stamp",
            "20260709",
        ],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert (out_dir / "lookup-miss-demand-20260709.json").is_file()
    assert (out_dir / "lookup-miss-demand-20260709.md").is_file()
    assert (out_dir / "lookup-miss-demand-latest.json").is_file()
    assert (out_dir / "lookup-miss-demand-latest.md").is_file()
    text = (out_dir / "lookup-miss-demand-latest.md").read_text()
    assert "lookup" in text.lower() or "miss" in text.lower() or "identity" in text.lower()


@pytest.mark.parametrize("input_kind", ["observed", "empty", "missing"])
def test_explicit_log_input_never_substitutes_fixture(tmp_path: Path, input_kind: str) -> None:
    source = tmp_path / "worker.log"
    if input_kind != "missing":
        source.write_text(
            'DOTREPO_LOOKUP_MISS {"host":"github.com","owner":"local-control",'
            '"repo":"observed","route":"query"}\n'
            if input_kind == "observed"
            else ""
        )
    output = tmp_path / "reports"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--input", str(source), "--output-dir", str(output)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=30,
    )
    report_path = output / "lookup-miss-demand-latest.json"
    if input_kind == "missing":
        assert completed.returncode != 0
        assert not report_path.exists()
    else:
        assert completed.returncode == 0, completed.stderr
        report = json.loads(report_path.read_text())
        assert report["missCount"] == (1 if input_kind == "observed" else 0)
        assert report["topMisses"] == (
            [{"identity": "github.com/local-control/observed", "count": 1}]
            if input_kind == "observed"
            else []
        )


def test_manual_workflow_executes_and_labels_fixture_proof(tmp_path: Path) -> None:
    workflow = yaml.load(
        (REPO / ".github/workflows/lookup-miss-demand.yml").read_text(), Loader=yaml.BaseLoader
    )
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert not workflow["on"]["workflow_dispatch"]
    assert workflow["permissions"] == {"contents": "read"}
    steps = workflow["jobs"]["export-demand"]["steps"]
    assert not any("download-artifact" in step.get("uses", "") for step in steps)
    export = next(step for step in steps if step.get("name") == "Export fixture proof")
    summary = next(step for step in steps if step.get("name") == "Publish step summary")
    summary_path = tmp_path / "summary.md"
    for step in [export, summary]:
        result = subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", step["run"]],
            cwd=REPO,
            env={
                **os.environ,
                "RUNNER_TEMP": str(tmp_path),
                "GITHUB_STEP_SUMMARY": str(summary_path),
            },
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
    output = tmp_path / "lookup-miss-fixture-proof"
    report = json.loads((output / "lookup-miss-demand-latest.json").read_text())
    assert report["missCount"] == 6
    assert report["uniqueIdentities"] == 4
    assert "Fixture proof only" in (output / "README.md").read_text()
    assert "no observed live demand" in summary_path.read_text()
    assert "log_artifact_name" not in summary_path.read_text()
