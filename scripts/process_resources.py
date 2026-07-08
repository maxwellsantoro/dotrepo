"""Best-effort CPU and peak-RSS measurement for child subprocesses.

Used by autonomous index batch orchestration so unit-cost reports can include
process-level CPU time and peak memory without inventing zero values when
measurement fails.

- CPU time uses ``resource.RUSAGE_CHILDREN`` deltas (accurate for sequential
  children of the same orchestrator process).
- Peak RSS is sampled from the process group via ``ps`` while the child runs.
  Values are best-effort and may under-count short-lived subprocess trees.
"""

from __future__ import annotations

import os
import resource
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class ProcessResourceSample:
    cpu_time_ms: float | None
    peak_memory_bytes: int | None
    note: str | None = None


def _rusage_children() -> resource.struct_rusage:
    return resource.getrusage(resource.RUSAGE_CHILDREN)


def cpu_time_ms_delta(before: resource.struct_rusage, after: resource.struct_rusage) -> float:
    cpu_s = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
    return round(max(0.0, cpu_s) * 1000.0, 3)


def _sample_process_group_rss_bytes(pid: int) -> int | None:
    """Return total RSS in bytes for ``pid``'s process group, or None on failure.

    ``ps -o rss=`` reports kilobytes on Linux and macOS.
    """
    try:
        pgid = os.getpgid(pid)
    except OSError:
        return None
    try:
        completed = subprocess.run(
            ["ps", "-o", "rss=", "-g", str(pgid)],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode not in (0, None) and not completed.stdout.strip():
        # Some platforms return non-zero when the group is gone mid-sample.
        return None
    total_kb = 0
    saw_value = False
    for line in completed.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            total_kb += int(stripped)
            saw_value = True
        except ValueError:
            continue
    if not saw_value:
        return None
    return total_kb * 1024


def run_with_resource_sample(
    command: Sequence[str],
    *,
    env: dict[str, str] | None = None,
    sample_interval_s: float = 0.2,
) -> tuple[subprocess.CompletedProcess[str], ProcessResourceSample]:
    """Run ``command`` and return completed process plus resource sample."""
    before = _rusage_children()
    try:
        proc = subprocess.Popen(
            list(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            start_new_session=True,
        )
    except OSError as exc:
        after = _rusage_children()
        return (
            subprocess.CompletedProcess(list(command), 127, "", str(exc)),
            ProcessResourceSample(
                cpu_time_ms=cpu_time_ms_delta(before, after),
                peak_memory_bytes=None,
                note=f"failed to start: {exc}",
            ),
        )

    peak_rss: int | None = None
    stop = threading.Event()

    def sampler() -> None:
        nonlocal peak_rss
        while not stop.is_set():
            sample = _sample_process_group_rss_bytes(proc.pid)
            if sample is not None:
                peak_rss = sample if peak_rss is None else max(peak_rss, sample)
            if proc.poll() is not None:
                break
            stop.wait(sample_interval_s)

    thread = threading.Thread(target=sampler, name="process-rss-sampler", daemon=True)
    thread.start()
    stdout, stderr = proc.communicate()
    stop.set()
    thread.join(timeout=2.0)
    # Final sample after exit (covers very short-lived processes).
    final_sample = _sample_process_group_rss_bytes(proc.pid)
    if final_sample is not None:
        peak_rss = final_sample if peak_rss is None else max(peak_rss, final_sample)

    after = _rusage_children()
    note = None
    if peak_rss is None:
        note = "peak RSS sampling unavailable on this host"
    return (
        subprocess.CompletedProcess(list(command), proc.returncode, stdout, stderr),
        ProcessResourceSample(
            cpu_time_ms=cpu_time_ms_delta(before, after),
            peak_memory_bytes=peak_rss,
            note=note,
        ),
    )


def sleep_for_tests(seconds: float) -> None:
    """Test seam — keep import side effects free of sleeps outside tests."""
    time.sleep(seconds)
