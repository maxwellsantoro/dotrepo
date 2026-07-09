from pathlib import Path
import subprocess
import sys


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
