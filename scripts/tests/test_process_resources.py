from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import process_resources  # noqa: E402


def test_run_with_resource_sample_captures_cpu() -> None:
    proc, sample = process_resources.run_with_resource_sample(
        [sys.executable, "-c", "print('ok')"],
        sample_interval_s=0.05,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == "ok"
    assert sample.cpu_time_ms is not None
    assert sample.cpu_time_ms >= 0.0
