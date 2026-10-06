"""Retain elapsed stages and failures for a single gate invocation."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
from pathlib import Path
import time

_recorder: ContextVar[dict | None] = ContextVar("gate_timing_recorder", default=None)


def write_timings(recorder: dict) -> None:
    payload = {
        "schema": "dotrepo-gate-timings/v0",
        "status": recorder["status"],
        "elapsedSeconds": round(time.perf_counter() - recorder["started"], 6),
        "stages": recorder["stages"],
    }
    root = recorder["root"]
    root.mkdir(parents=True, exist_ok=True)
    (root / "timings.json").write_text(json.dumps(payload, indent=2) + "\n")
    rows = [
        "### Gate timings",
        "",
        f"Status: {payload['status']}; wall time: {payload['elapsedSeconds']:.2f} seconds.",
        "",
        "| Stage | Seconds | Status |",
        "| --- | ---: | --- |",
    ]
    for stage in payload["stages"]:
        label = stage["name"].replace("|", "\\|").replace("\n", " ")
        rows.append(f"| {label} | {stage['elapsedSeconds']:.2f} | {stage['status']} |")
    (root / "timings.md").write_text("\n".join(rows) + "\n")


@contextmanager
def gate_timings(output_root: Path):
    recorder = {
        "root": output_root,
        "started": time.perf_counter(),
        "status": "running",
        "stages": [],
    }
    token = _recorder.set(recorder)
    try:
        yield
    except BaseException:
        recorder["status"] = "failed"
        raise
    else:
        recorder["status"] = "passed"
    finally:
        try:
            write_timings(recorder)
            if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
                with Path(summary).open("a") as stream:
                    stream.write((output_root / "timings.md").read_text())
        finally:
            _recorder.reset(token)


@contextmanager
def timed_stage(name: str):
    recorder = _recorder.get()
    if recorder is None:
        yield
        return
    started = time.perf_counter()
    status = "passed"
    try:
        yield
    except BaseException:
        status = "failed"
        raise
    finally:
        elapsed = round(time.perf_counter() - started, 6)
        recorder["stages"].append({"name": name, "elapsedSeconds": elapsed, "status": status})
        write_timings(recorder)
        print(f"[timing] {elapsed:.2f}s {status}: {name}", flush=True)
