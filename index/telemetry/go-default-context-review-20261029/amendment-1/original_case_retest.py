"""Run only the local first-party importer on owned synthetic workflow data."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import tomllib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CLI = ROOT / "target/debug/dotrepo"


def main():
    workflows = {
        "root-default": "jobs:\n  unit:\n    steps:\n      - run: go test ./...\n",
        "service-standard": "jobs:\n  unit:\n    services:\n      redis:\n        image: redis:7\n    steps:\n      - run: go test -race ./...\n",
        "service-quoted-jobs": '"jobs":\n  unit:\n    services:\n      redis:\n        image: redis:7\n    steps:\n      - run: go test -race ./...\n',
        "service-quoted-steps": 'jobs:\n  unit:\n    services:\n      redis:\n        image: redis:7\n    "steps":\n      - run: go test -race ./...\n',
        "environment-data-working-directory": "env:\n  EXAMPLE_CONFIGURATION: |\n    working-directory: examples\njobs:\n  unit:\n    steps:\n      - run: go test ./...\n",
        "job-environment-data-working-directory": "jobs:\n  unit:\n    env:\n      EXAMPLE_CONFIGURATION: |\n        working-directory: examples\n    steps:\n      - run: go test ./...\n",
    }
    results = []
    scratch = Path(tempfile.mkdtemp(prefix="dotrepo-go-context-review-", dir="/tmp"))
    for name, workflow in workflows.items():
        root = scratch / name
        folder = root / ".github/workflows"
        folder.mkdir(parents=True)
        (root / "go.mod").write_text("module example.test/review\n\ngo 1.23\n")
        (root / "README.md").write_text("# Owned synthetic Go context fixture\n")
        (folder / "ci.yml").write_text(workflow)
        argv = [
            str(CLI),
            "--root",
            str(root),
            "import",
            "--mode",
            "overlay",
            "--source",
            "https://example.test/review",
        ]
        run = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        assert run.returncode == 0, (name, run.stderr)
        manifest = tomllib.loads((root / "record.toml").read_text())
        evidence = (root / "evidence.md").read_text() if (root / "evidence.md").exists() else None
        results.append(
            {
                "case": name,
                "workflow": workflow,
                "argv": argv,
                "exitCode": run.returncode,
                "stdout": run.stdout,
                "stderr": run.stderr,
                "build": manifest["repo"].get("build"),
                "test": manifest["repo"].get("test"),
                "manifest": manifest,
                "evidence": evidence,
            }
        )
    assert results[0]["test"] == "go test ./..."
    assert results[1]["test"] is None
    assert results[2]["test"] is None
    assert results[3]["test"] is None
    assert results[4]["test"] == "go test ./..." and results[5]["test"] == "go test ./..."
    print(
        json.dumps(
            {
                "cliSha256": hashlib.sha256(CLI.read_bytes()).hexdigest(),
                "scratch": str(scratch),
                "actualFirstPartyImporterRuns": len(results),
                "upstreamCodeExecuted": False,
                "providerOrNetworkCalls": 0,
                "results": results,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
