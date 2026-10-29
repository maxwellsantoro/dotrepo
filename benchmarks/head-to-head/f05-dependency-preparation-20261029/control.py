"""Packet-local bounded Docker command capture; every Python invocation uses uv."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
from capture import limited_process  # noqa: E402


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(row, stream, indent=2)
        stream.write("\n")


def command(folder, label, argv, *, data=b"", timeout=60, limit=2 * 1024**2):
    output = folder / "logs" / label
    output.mkdir(parents=True)
    started_at, start = datetime.now(timezone.utc).isoformat(), time.monotonic()
    result = limited_process(argv, data=data, timeout=timeout, output_limit=limit)
    (output / "stdout.txt").write_text(result["stdout"])
    (output / "stderr.txt").write_text(result["stderr"])
    receipt = {
        "argv": argv,
        "startedAt": started_at,
        "elapsedSeconds": time.monotonic() - start,
        "exitCode": result["exitCode"],
        "error": result["error"],
        "stdinBytes": len(data),
        "stdinSha256": sha(data),
        "stdoutSha256": sha(result["stdout"].encode()),
        "stderrSha256": sha(result["stderr"].encode()),
        "costUsd": None,
        "costExclusions": ["No metered container/host charge source."],
    }
    write(output / "receipt.json", receipt)
    return result


def checked(folder, label, argv, **kwargs):
    result = command(folder, label, argv, **kwargs)
    assert result["exitCode"] == 0 and not result["error"], (label, result)
    return result
