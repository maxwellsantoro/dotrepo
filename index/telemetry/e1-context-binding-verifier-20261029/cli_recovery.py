"""Observe retained Keras candidate recovery, not CLI verification/scoring."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    source = ROOT / "crates/dotrepo-core/src/import/commands/context/python_recipe/testdata"
    binary = ROOT / "target/debug/dotrepo"
    with tempfile.TemporaryDirectory(
        prefix="dotrepo-e1-context-binding-cli-", dir="/tmp"
    ) as directory:
        folder = Path(directory)
        (folder / "keras/api").mkdir(parents=True)
        (folder / "keras/src").mkdir(parents=True)
        files = [
            "README.md",
            "CONTRIBUTING.md",
            "pyproject.toml",
            "requirements.txt",
            "requirements-common.txt",
        ]
        for name in files:
            shutil.copyfile(source / name, folder / name)
        argv = [
            str(binary),
            "--root",
            str(folder),
            "import",
            "--mode",
            "overlay",
            "--source",
            "https://github.com/keras-team/keras",
        ]
        run = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        assert run.returncode == 0, run.stderr
        text = (folder / "record.toml").read_text()
        manifest = tomllib.loads(text)
        candidates = manifest["repo"]["test_candidates"]
        assert len(candidates) == 1
        evidence = manifest["x"]["dotrepo"]["field_evidence"]["repo.test_candidates.0"]
        bindings = json.loads(evidence["sourceBindingsJson"])
        assert len(bindings) == 8 and len({b["path"] for b in bindings}) == 5
        print(
            json.dumps(
                {
                    "repository": "github.com/keras-team/keras",
                    "revision": "7efab4a60f5930fa81b0db15ed4ec6e4925e0c45",
                    "knownDevelopment": True,
                    "cliSha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                    "argv": argv,
                    "exitCode": run.returncode,
                    "stdout": run.stdout,
                    "stderr": run.stderr,
                    "manifest": text,
                    "evidence": (folder / "evidence.md").read_text(),
                    "sourceFiles": {
                        name: hashlib.sha256((source / name).read_bytes()).hexdigest()
                        for name in files
                    },
                    "observedScalarTest": manifest["repo"].get("test"),
                    "observedCandidateCount": 1,
                    "observedBindingCount": 8,
                    "upstreamExecuted": False,
                    "providerNetworkIndexCalls": 0,
                    "limit": "cmd_import recovers and writes the candidate but does not invoke verify_import_plan or score_import_fields. Actual integrity/score integration is exercised by the retained focused core tests; this CLI control alone does not establish verification or semantic completeness.",
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
