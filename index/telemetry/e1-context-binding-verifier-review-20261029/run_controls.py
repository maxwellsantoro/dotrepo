"""Run bounded independent local-fixture Cargo controls after slot release only."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()
    args.scratch.mkdir()
    logs = HERE / "execution"
    logs.mkdir()
    manifest = HERE / "harness/Cargo.toml"
    inputs = [
        REPO / name
        for name in [
            "Cargo.toml",
            "Cargo.lock",
            "crates/dotrepo-core/src/import/context_verification.rs",
            "crates/dotrepo-core/src/import/context_verification/tests.rs",
            "crates/dotrepo-core/src/import/read.rs",
            "crates/dotrepo-core/src/import/fields.rs",
            "crates/dotrepo-core/src/import/mod.rs",
            "crates/dotrepo-core/src/import/commands/context/python_recipe.rs",
            "index/telemetry/e1-context-binding-verifier-20261029/shared-wiring.patch",
            "index/telemetry/e1-keras-source-disposition-20261029/FREEZE.json",
        ]
    ]
    inputs += [manifest, HERE / "harness/src/main.rs", Path(__file__).resolve()]
    bindings = {str(path): sha(path) for path in inputs}
    write(
        HERE / "BEFORE.json",
        {
            "inputs": bindings,
            "scratch": str(args.scratch),
            "state": "before independent Cargo local-fixture controls",
            "context": "Prior F05/E1 project context; not fresh blinded qualification",
        },
    )
    env = {name: os.environ[name] for name in ["HOME", "PATH"] if name in os.environ}
    env["CARGO_TARGET_DIR"] = str(args.scratch / "target")

    def run(name, argv):
        folder = logs / name
        folder.mkdir()
        started = datetime.now(timezone.utc).isoformat()
        clock = time.monotonic()
        error = None
        with (
            (folder / "stdout.txt").open("xb") as stdout,
            (folder / "stderr.txt").open("xb") as stderr,
        ):
            try:
                completed = subprocess.run(
                    argv, cwd=REPO, env=env, stdout=stdout, stderr=stderr, timeout=240, check=False
                )
                code = completed.returncode
            except subprocess.TimeoutExpired:
                code, error = None, "local Cargo control timed out"
        receipt = {
            "argv": argv,
            "startedAt": started,
            "elapsedSeconds": time.monotonic() - clock,
            "exitCode": code,
            "error": error,
            "stdoutSha256": sha(folder / "stdout.txt"),
            "stderrSha256": sha(folder / "stderr.txt"),
            "costUsd": None,
            "costExclusions": [
                "Unmetered local operator/Cargo work; no native upstream task or paid provider call."
            ],
        }
        write(folder / "receipt.json", receipt)
        assert all(
            (folder / f"{role}.txt").stat().st_size <= 2 * 1024**2 for role in ["stdout", "stderr"]
        )
        assert code == 0 and error is None, receipt

    run("lock", ["cargo", "generate-lockfile", "--offline", "--manifest-path", str(manifest)])
    write(
        logs / "lock-binding.json",
        {"manifestSha256": sha(manifest), "lockSha256": sha(HERE / "harness/Cargo.lock")},
    )
    run(
        "controls",
        [
            "cargo",
            "run",
            "--offline",
            "--locked",
            "--manifest-path",
            str(manifest),
            "--",
            str(args.scratch / "fixtures"),
            str(args.scratch / "result.json"),
        ],
    )
    result = json.loads((args.scratch / "result.json").read_text())
    write(HERE / "controls.json", result)
    assert all(sha(Path(name)) == digest for name, digest in bindings.items()), (
        "evaluated source changed"
    )
    write(
        logs / "AFTER.json",
        {
            "sourceBindingsUnchanged": True,
            "lockSha256": sha(HERE / "harness/Cargo.lock"),
            "controlBinarySha256": sha(
                args.scratch / "target/debug/dotrepo-context-binding-independent-controls"
            ),
            "controls": len(result["independentControls"]),
            "noFixtureCommandsExecuted": True,
            "scratchFixtureCleanupConfirmed": not (args.scratch / "fixtures").exists(),
        },
    )


if __name__ == "__main__":
    main()
