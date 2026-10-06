import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gate_timings import gate_timings, timed_stage  # noqa: E402
import check_release_gate  # noqa: E402


def test_failed_subprocess_retains_partial_timings_and_preserves_exception(tmp_path, monkeypatch):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(7, args[0])

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError) as error:
        with gate_timings(tmp_path / "gate"):
            with timed_stage("prepare"):
                pass
            check_release_gate.run(["fixture", "failed"], cwd=tmp_path)
    assert error.value.returncode == 7
    report = json.loads((tmp_path / "gate/timings.json").read_text())
    assert report["schema"] == "dotrepo-gate-timings/v0"
    assert report["status"] == "failed"
    assert [stage["status"] for stage in report["stages"]] == ["passed", "failed"]
    assert all(stage["elapsedSeconds"] >= 0 for stage in report["stages"])
    assert "fixture failed" in summary.read_text()


def test_successful_gate_writes_wall_time_and_restores_context(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    with gate_timings(tmp_path):
        with timed_stage("verify"):
            pass
    before = (tmp_path / "timings.json").read_bytes()
    assert json.loads(before)["status"] == "passed"
    with timed_stage("outside gate"):
        pass
    assert (tmp_path / "timings.json").read_bytes() == before


def test_metadata_failure_is_recorded_even_without_a_subprocess(tmp_path):
    with pytest.raises(ValueError, match="invalid artifact"):
        with gate_timings(tmp_path):
            with timed_stage("verify metadata"):
                raise ValueError("invalid artifact")
    report = json.loads((tmp_path / "timings.json").read_text())
    assert report["status"] == report["stages"][0]["status"] == "failed"
