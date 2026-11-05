"""Exercise the real Node preflight process without installing host OS packages."""

import json
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("mode", "success", "expected"),
    [
        ("ready", True, ["launch", "close"]),
        ("repair", True, ["launch", "install-deps chromium", "launch", "close"]),
        ("installer-failure", False, ["launch", "install-deps chromium"]),
        ("persistent-failure", False, ["launch", "install-deps chromium", "launch"]),
    ],
)
def test_runner_probes_each_time_repairs_once_and_propagates_failure(
    tmp_path, mode, success, expected
):
    package = tmp_path / "node_modules" / "playwright"
    package.mkdir(parents=True)
    (package / "package.json").write_text(json.dumps({"name": "playwright", "main": "index.js"}))
    (package / "index.js").write_text(
        """const fs = require('node:fs');
const log = item => fs.appendFileSync(process.env.PROBE_LOG, item + '\\n');
exports.chromium = {launch: async () => {
  log('launch');
  if (process.env.PROBE_MODE !== 'ready' &&
      (process.env.PROBE_MODE === 'persistent-failure' || !fs.existsSync(process.env.PROBE_STATE)))
    throw new Error('fixture: required system library missing');
  return {close: async () => log('close')};
}};
"""
    )
    (package / "cli.js").write_text(
        """const fs = require('node:fs');
fs.appendFileSync(process.env.PROBE_LOG, process.argv.slice(2).join(' ') + '\\n');
if (process.env.PROBE_MODE === 'installer-failure') process.exit(7);
fs.writeFileSync(process.env.PROBE_STATE, 'ready');
"""
    )
    log = tmp_path / "calls"
    result = subprocess.run(
        ["node", str(ROOT / "scripts/ensure_playwright_chromium.cjs")],
        env={
            **os.environ,
            "NODE_PATH": str(package.parent),
            "PROBE_MODE": mode,
            "PROBE_LOG": str(log),
            "PROBE_STATE": str(tmp_path / "repaired"),
        },
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert (result.returncode == 0) == success, result.stderr
    assert log.read_text().splitlines() == expected
    if not success:
        assert "failed" in result.stderr or "missing" in result.stderr
