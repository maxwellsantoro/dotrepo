"""Retain development import/profile/selection observations; no upstream execution."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
from bench.own_projects import select_profile_instruction  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def command(arguments, directory, output):
    output.mkdir(parents=True)
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(arguments, cwd=directory, capture_output=True, timeout=120, check=False)
    (output / "stdout.txt").write_bytes(result.stdout)
    (output / "stderr.txt").write_bytes(result.stderr)
    receipt = {
        "arguments": [str(value) for value in arguments],
        "startedAt": started,
        "completedAt": datetime.now(timezone.utc).isoformat(),
        "exitCode": result.returncode,
        "stdoutSha256": sha(output / "stdout.txt"),
        "stderrSha256": sha(output / "stderr.txt"),
    }
    write(output / "receipt.json", receipt)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cli", type=Path, default=ROOT / "target/debug/dotrepo")
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.parent == HERE and output.name not in {"", ".", ".."}
    output.mkdir(exist_ok=False)
    cli = args.cli.resolve()
    ledger = json.loads((HERE / "development-ledger.json").read_text())
    source_inputs = [ROOT / "Cargo.toml", ROOT / "Cargo.lock"]
    source_inputs += sorted(
        path
        for path in (ROOT / "crates").rglob("*")
        if path.is_file()
        and (path.suffix == ".rs" or path.name in {"Cargo.toml", "Cargo.lock"})
        and "target" not in path.parts
    )
    source_inputs += [
        Path(__file__),
        HERE / "development-ledger.json",
        HERE.parent / "bench/own_projects.py",
        ROOT / "examples/external-consumer/lookup_before_scrape.py",
    ]
    frozen = {
        "classification": "exposed-development; not held-out qualification",
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "cliSha256": sha(cli),
        "inputs": {str(path.relative_to(ROOT)): sha(path) for path in source_inputs},
        "upstreamCodeExecuted": False,
        "consumerBenefitMeasured": False,
    }
    write(output / "implementation-inputs.json", frozen)
    observations = []
    with tempfile.TemporaryDirectory(prefix="dotrepo-e1-development-b-") as temp:
        temp = Path(temp)
        index = temp / "index"
        for row in ledger["repositories"]:
            identity = row["repository"]
            root = temp / "source" / identity
            root.mkdir(parents=True)
            for item in row["retainedSources"]:
                source = ROOT / item["path"]
                assert sha(source) == item["sha256"]
                target = root / item["upstreamPath"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            imported = command(
                [
                    str(cli),
                    "--root",
                    str(root),
                    "import",
                    "--mode",
                    "overlay",
                    "--source",
                    "https://" + identity,
                ],
                ROOT,
                output / "imports" / identity,
            )
            manifest = None
            if imported.returncode == 0:
                record = root / "record.toml"
                manifest = tomllib.loads(record.read_text())
                destination = index / "repos" / identity
                destination.mkdir(parents=True)
                for name in ["record.toml", "evidence.md"]:
                    if (root / name).is_file():
                        shutil.copyfile(root / name, destination / name)
                        shutil.copyfile(root / name, output / "imports" / identity / name)
            for item in row["retainedSources"]:
                assert sha(root / item["upstreamPath"]) == item["sha256"]
            profile = command(
                [str(cli), "public", "profile", "--index-root", str(index), *identity.split("/")],
                ROOT,
                output / "profiles" / identity,
            )
            gold = json.loads((ROOT / row["priorGold"]["path"]).read_text())
            assert sha(ROOT / row["priorGold"]["path"]) == row["priorGold"]["sha256"]
            for task in gold["tasks"]:
                if task["id"] not in row["priorGold"]["taskIds"]:
                    continue
                request = {"scope": task["scope"]}
                if task["component"] is not None:
                    request["component"] = task["component"]
                selected = select_profile_instruction(
                    identity,
                    200 if profile.returncode == 0 else 404,
                    profile.stdout if profile.returncode == 0 else b"",
                    "test",
                    request=request,
                )
                observations.append(
                    {
                        "id": task["id"],
                        "repository": identity,
                        "revision": row["revision"],
                        "request": request,
                        "rawRepo": manifest["repo"] if manifest else None,
                        "consumerSelection": selected,
                        "importExitCode": imported.returncode,
                        "profileExitCode": profile.returncode,
                    }
                )
    for path, digest in frozen["inputs"].items():
        assert sha(ROOT / path) == digest, f"implementation changed during run: {path}"
    assert sha(cli) == frozen["cliSha256"]
    write(output / "observations.json", observations)
    write(
        output / "artifact-hashes.json",
        {
            str(path.relative_to(output)): sha(path)
            for path in sorted(output.rglob("*"))
            if path.is_file() and path.name != "artifact-hashes.json"
        },
    )
    print(f"Retained {len(observations)} development observations in {output}")


if __name__ == "__main__":
    main()
