#!/usr/bin/env python3
"""Smoke-test .env adjudication: sidecar health, OpenRouter call, crawler escalation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"missing {path}")
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def wait_for_health(url: str, timeout_s: float = 20.0) -> None:
    deadline = time.time() + timeout_s
    health = url.replace("/adjudicate", "/health")
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health, timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.25)
    raise RuntimeError(f"sidecar did not become healthy at {health}")


def post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    load_dotenv(ROOT / ".env")

    required = [
        "OPENROUTER_API_KEY",
        "DOTREPO_ADJUDICATION_URL",
        "DOTREPO_ADJUDICATION_MODEL",
        "INDEX_MAX_ADJUDICATION_CALLS",
    ]
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        raise SystemExit(f"missing required env vars: {', '.join(missing)}")

    adjudication_url = os.environ["DOTREPO_ADJUDICATION_URL"].strip()
    model = os.environ["DOTREPO_ADJUDICATION_MODEL"].strip()

    sidecar_proc = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts/adjudication_openrouter_sidecar.py")],
        cwd=ROOT,
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_for_health(adjudication_url)
        print("sidecar: healthy")

        sample = {
            "field": "repo.build",
            "candidates": [
                {
                    "value": "cargo build --workspace",
                    "sourcePath": ".github/workflows/ci.yml",
                    "sourceTier": "workflow",
                },
                {
                    "value": "cargo build",
                    "sourcePath": ".github/workflows/release.yml",
                    "sourceTier": "workflow",
                },
            ],
            "provider": "openrouter",
            "model": model,
            "tier": "local_primary",
        }
        result = post_json(adjudication_url, sample)
        print("sidecar adjudication:", json.dumps(result, indent=2))
        if "error" in result:
            return 1
        if result.get("field") != "repo.build":
            raise RuntimeError("unexpected adjudication field")
        if result.get("value") not in {
            "cargo build --workspace",
            "cargo build",
            None,
        }:
            raise RuntimeError(f"value not in candidate set: {result.get('value')!r}")
        if int(result.get("tokensUsed") or 0) <= 0:
            raise RuntimeError("expected non-zero token usage")

        fixture_root = ROOT / "target/adjudication-env-fixture"
        fixture_root.mkdir(parents=True, exist_ok=True)
        (fixture_root / ".github/workflows").mkdir(parents=True, exist_ok=True)
        (fixture_root / "README.md").write_text(
            "# Conflict\n\nConflicting workflows.\n",
            encoding="utf-8",
        )
        (fixture_root / ".github/workflows/ci.yml").write_text(
            "name: CI\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build --workspace\n      - run: cargo test --workspace\n",
            encoding="utf-8",
        )
        (fixture_root / ".github/workflows/release.yml").write_text(
            "name: Release\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build\n      - run: cargo test\n",
            encoding="utf-8",
        )

        env = os.environ.copy()
        env["FIXTURE_ROOT"] = str(fixture_root)
        proc = subprocess.run(
            [
                "cargo",
                "test",
                "-p",
                "dotrepo-crawler",
                "--test",
                "openrouter_env_escalation",
                "--",
                "--nocapture",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        print(proc.stdout)
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)
        if proc.returncode != 0:
            return proc.returncode

        print("adjudication env smoke test passed")
        return 0
    finally:
        sidecar_proc.terminate()
        try:
            sidecar_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            sidecar_proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())