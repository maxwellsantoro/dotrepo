"""Host uv orchestration helpers; no host paths are mounted into the container."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
VERSION = "2.0.0-rc.2"
COMMIT = "94e02bd43d7cae1e5b6cd37ebd7a2a66a9b2b773"
IMAGE = "sha256:114c7a4425406451c2866b6aafe69fe29b1b298832db1277d411ac73c82d04d6"
PACKAGES = ("dotrepo-cli", "dotrepo-mcp", "dotrepo-lsp", "dotrepo")


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def command(label, argv, *, data=None, timeout=60):
    folder = HERE / "logs" / label
    folder.mkdir(parents=True, exist_ok=False)
    started = stamp()
    host_env = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
    error = None
    with (folder / "stdout.txt").open("wb") as stdout, (folder / "stderr.txt").open("wb") as stderr:
        try:
            result = subprocess.run(
                argv,
                input=data,
                stdout=stdout,
                stderr=stderr,
                timeout=timeout,
                check=False,
                env=host_env,
            )
            code = result.returncode
        except subprocess.TimeoutExpired:
            code, error = None, "timeout"
    receipt = {
        "startedAt": started,
        "endedAt": stamp(),
        "argv": argv,
        "exitCode": code,
        "error": error,
        "stdinBytes": len(data) if data else 0,
        "stdoutSha256": digest(folder / "stdout.txt"),
        "stderrSha256": digest(folder / "stderr.txt"),
    }
    write(folder / "receipt.json", receipt)
    return code, (folder / "stdout.txt").read_bytes(), (folder / "stderr.txt").read_bytes()


def container():
    return json.loads((HERE / "container-handle.json").read_text())["name"]


def execute(label, argv, *, data=None, timeout=60):
    return command(
        label,
        ["docker", "exec", *(["-i"] if data is not None else []), container(), *argv],
        data=data,
        timeout=timeout,
    )
