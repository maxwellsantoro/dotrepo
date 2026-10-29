"""Reproduce reviewed Markdown/setup boundaries using only the installed importer."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DATA = ROOT / "crates/dotrepo-core/src/import/commands/context/python_recipe/testdata"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.parent == HERE
    output.mkdir(exist_ok=False)
    cli = ROOT / "target/debug/dotrepo"
    original = (DATA / "CONTRIBUTING.md").read_text()
    start = original.index("### Run all tests")
    end = original.index("## Backend-agnostic", start)
    section = original[start:end]
    cases = {
        "retained-positive": original,
        "html-commented-section": original[:start] + "<!--\n" + section + "-->\n" + original[end:],
        "four-space-indented-section": original[:start]
        + "".join("    " + line + "\n" for line in section.splitlines())
        + original[end:],
        "indented-test-fence": original.replace(
            "```shell\npytest keras\n```", "    ```shell\n    pytest keras\n    ```"
        ),
        "four-backtick-fenced-guide": "````markdown\n" + original + "\n````\n",
        "external-pretest-install": original.replace(
            "## Run tests", "Before testing, install PostgreSQL 16.\n\n## Run tests"
        ),
    }
    results = []
    scalars = None
    for name, contributing in cases.items():
        destination = output / name
        destination.mkdir()
        with tempfile.TemporaryDirectory(prefix="dotrepo-e1-boundary-") as temp:
            repo = Path(temp) / "keras"
            shutil.copytree(DATA, repo)
            (repo / "keras/api").mkdir(parents=True)
            (repo / "CONTRIBUTING.md").write_text(contributing)
            arguments = [
                str(cli),
                "--root",
                str(repo),
                "import",
                "--mode",
                "overlay",
                "--source",
                "https://github.com/keras-team/keras",
            ]
            result = subprocess.run(
                arguments, cwd=ROOT, capture_output=True, timeout=60, check=False
            )
            (destination / "stdout.txt").write_bytes(result.stdout)
            (destination / "stderr.txt").write_bytes(result.stderr)
            assert result.returncode == 0, result.stderr
            raw = (repo / "record.toml").read_bytes()
            (destination / "record.toml").write_bytes(raw)
            record = tomllib.loads(raw.decode())
            candidates = record["repo"].get("test_candidates", [])
            expected = 1 if name == "retained-positive" else 0
            assert len(candidates) == expected, name
            current = {key: record["repo"].get(key) for key in ["build", "test"]}
            if scalars is None:
                scalars = current
            assert current == scalars
            if candidates:
                assert (
                    record["x"]["dotrepo"]["field_evidence"]["repo.test_candidates.0"]["confidence"]
                    == "medium"
                )
            results.append(
                {
                    "case": name,
                    "exitCode": result.returncode,
                    "candidateCount": len(candidates),
                    "expectedCandidateCount": expected,
                    "contributingSha256": sha(repo / "CONTRIBUTING.md"),
                    "recordSha256": sha(destination / "record.toml"),
                    "scalarBuildTestUnchanged": True,
                    "result": "passed",
                }
            )
    receipt = {
        "classification": "known development boundary controls, not qualification",
        "cliSha256": sha(cli),
        "controlSourceSha256": sha(Path(__file__)),
        "fixtureSourceHashes": {path.name: sha(path) for path in sorted(DATA.iterdir())},
        "upstreamCodeExecuted": False,
        "results": results,
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"Passed {len(results)} actual CLI boundary controls: {output}")


if __name__ == "__main__":
    main()
