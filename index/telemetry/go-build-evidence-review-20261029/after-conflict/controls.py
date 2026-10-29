"""First-party local importer controls; no upstream command is executed."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import tomllib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    binary = ROOT / "target/debug/dotrepo"
    module = {"go.mod": "module example.test/control\n\ngo 1.22\n"}
    readme = "# Owned control\n\n## Build\n\n```sh\ngo build ./...\n```\n"
    contrib = "# Contributing\n\n## Build\n\n```sh\ngo build -tags=integration ./...\n```\n"
    cases = [
        ("module-only", {}, None, "go test ./..."),
        ("explicit", {"README.md": readme}, "go build ./...", "go test ./..."),
        (
            "explicit-conflict",
            {"README.md": readme, "CONTRIBUTING.md": contrib},
            None,
            "go test ./...",
        ),
        (
            "tagged-workflow",
            {
                ".github/workflows/ci.yml": "jobs:\n  build:\n    steps:\n      - run: go build -tags=integration ./...\n"
            },
            "go build -tags=integration ./...",
            "go test ./...",
        ),
        (
            "service-test",
            {
                ".github/workflows/ci.yml": "jobs:\n  test:\n    services:\n      redis:\n        image: redis:7\n    steps:\n      - run: go test -race ./...\n"
            },
            None,
            None,
        ),
    ]
    results = []
    for name, extra, expected_build, expected_test in cases:
        inputs = module | extra
        with tempfile.TemporaryDirectory(
            prefix="dotrepo-go-build-review-after-", dir="/tmp"
        ) as directory:
            folder = Path(directory)
            for path, text in inputs.items():
                target = folder / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
            argv = [
                str(binary),
                "--root",
                str(folder),
                "import",
                "--mode",
                "overlay",
                "--source",
                "https://example.test/control",
            ]
            run = subprocess.run(argv, capture_output=True, text=True, timeout=30)
            assert run.returncode == 0, run.stderr
            manifest_text = (folder / "record.toml").read_text()
            manifest = tomllib.loads(manifest_text)
            evidence = (folder / "evidence.md").read_text()
            assert manifest["repo"].get("build") == expected_build, name
            assert manifest["repo"].get("test") == expected_test, name
            if name == "explicit-conflict":
                assert "conflicting build commands" in evidence
                assert "root go.mod supplies only a conventional build candidate" not in evidence
            results.append(
                {
                    "case": name,
                    "inputs": inputs,
                    "argv": argv,
                    "exitCode": run.returncode,
                    "stdout": run.stdout,
                    "stderr": run.stderr,
                    "manifest": manifest_text,
                    "evidence": evidence,
                }
            )
    print(
        json.dumps(
            {
                "cliSha256": sha(binary),
                "firstPartyCliImports": len(results),
                "upstreamExecuted": False,
                "providerNetworkIndexCalls": 0,
                "results": results,
                "limits": "CLI observes deterministic imports; direct request eligibility and budgets 0/2 are separately exercised in core tests. Workflow command preservation does not prove repository-default applicability.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
