"""Current first-party CLI only; owned synthetic workflows, no upstream execution."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import tomllib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CLI = ROOT / "target/debug/dotrepo"
ROOT_WORKFLOW = "jobs:\n  unit:\n    steps:\n      - run: go test ./...\n"
SERVICE = "jobs:\n  unit:\n    services:\n      redis:\n        image: redis:7\n    steps:\n      - run: go test -race ./...\n"
DATA = "working-directory: examples\nuses: shogo82148/actions-setup-redis@v1\nservices:\n  redis:\n    image: redis:7\ngo test ./...\n"


def indented(text, count):
    return "".join(" " * count + line + "\n" for line in text.splitlines())


def cases():
    rows = [
        ("root-default", ROOT_WORKFLOW, True, True, None),
        ("plain-service", SERVICE, True, False, None),
    ]
    for key in ("jobs", "steps", "services", "run"):
        for quote in ('"', "'"):
            rows.append(
                (
                    "quoted-" + key + ("-double" if quote == '"' else "-single"),
                    SERVICE.replace(key + ":", quote + key + quote + ":"),
                    True,
                    False,
                    None,
                )
            )
    for style in ("|", "|-", ">", ">-"):
        for location in ("workflow-env", "job-env", "step-name", "step-env"):
            if location == "workflow-env":
                workflow = "env:\n  CONFIG: " + style + "\n" + indented(DATA, 4) + ROOT_WORKFLOW
            elif location == "job-env":
                workflow = (
                    "jobs:\n  unit:\n    env:\n      CONFIG: "
                    + style
                    + "\n"
                    + indented(DATA, 8)
                    + "    steps:\n      - run: go test ./...\n"
                )
            elif location == "step-name":
                workflow = (
                    "jobs:\n  unit:\n    steps:\n      - name: "
                    + style
                    + "\n"
                    + indented(DATA, 10)
                    + "        run: go test ./...\n"
                )
            else:
                workflow = (
                    "jobs:\n  unit:\n    steps:\n      - env:\n          CONFIG: "
                    + style
                    + "\n"
                    + indented(DATA, 12)
                    + "        run: go test ./...\n"
                )
            rows.append((location + "-" + style, workflow, True, True, None))
    for name, workflow, build, test in [
        (
            "step-root-over-job-component",
            "defaults:\n  run:\n    working-directory: v2\njobs:\n  unit:\n    defaults:\n      run:\n        working-directory: nested\n    steps:\n      - run: go test ./...\n        working-directory: .\n",
            True,
            True,
        ),
        (
            "job-root-over-workflow-component",
            "defaults:\n  run:\n    working-directory: v2\njobs:\n  unit:\n    defaults:\n      run:\n        working-directory: .\n    steps:\n      - run: go test ./...\n",
            True,
            True,
        ),
        (
            "step-component-over-root",
            "defaults:\n  run:\n    working-directory: .\njobs:\n  unit:\n    steps:\n      - working-directory: v2\n        run: go test ./...\n",
            False,
            False,
        ),
        (
            "heredoc-data-followed-by-root",
            "jobs:\n  unit:\n    steps:\n      - run: |\n          cat <<'END'\n"
            + indented(DATA + "cd v2\nredis-server --daemonize yes\n", 10)
            + "          END\n          go test ./...\n",
            True,
            True,
        ),
        (
            "heredoc-then-real-component",
            "jobs:\n  unit:\n    steps:\n      - run: |\n          cat <<END\n          cd data\n          END\n          cd v2\n          go test ./...\n",
            False,
            False,
        ),
        (
            "heredoc-then-real-service",
            "jobs:\n  unit:\n    steps:\n      - run: |\n          cat <<END\n          cd data\n          END\n          redis-server --daemonize yes\n          go test ./...\n",
            True,
            False,
        ),
        ("unsupported-flow-jobs", "jobs: {unit: {steps: [{run: go test ./...}]}}\n", False, False),
        (
            "unsupported-flow-job",
            "jobs:\n  unit: {services: {redis: {image: redis:7}}, steps: [{run: go test -race ./...}]}\n",
            False,
            False,
        ),
        (
            "unsupported-flow-steps",
            "jobs:\n  unit:\n    steps: [{run: go test ./...}]\n",
            False,
            False,
        ),
        (
            "unsupported-flow-individual-step",
            "jobs:\n  unit:\n    services:\n      redis:\n        image: redis:7\n    steps:\n      - {run: go test -race ./...}\n",
            False,
            False,
        ),
        (
            "unsupported-dynamic-run",
            "jobs:\n  unit:\n    steps:\n      - run: ${{ inputs.command }}\n",
            False,
            False,
        ),
        (
            "unsupported-folded-run",
            "jobs:\n  unit:\n    steps:\n      - run: >\n          go\n          test ./...\n",
            False,
            False,
        ),
        (
            "unsupported-unclosed-heredoc",
            "jobs:\n  unit:\n    steps:\n      - run: |\n          cat <<END\n          cd v2\n          go test ./...\n",
            False,
            False,
        ),
        (
            "unrelated-service-job",
            ROOT_WORKFLOW
            + "  docs:\n    steps:\n      - uses: shogo82148/actions-setup-redis@v1\n      - run: echo documentation\n",
            True,
            True,
        ),
    ]:
        rows.append((name, workflow, build, test, None))
    declared = (
        ROOT / "crates/dotrepo-core/tests/fixtures/import/f1-go-declared-context/CONTRIBUTING.md"
    ).read_text()
    rows.append(("explicit-maintainer-default-with-service", SERVICE, True, True, declared))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-cli-sha256", required=True)
    args = parser.parse_args()
    digest = hashlib.sha256(CLI.read_bytes()).hexdigest()
    assert digest == args.expected_cli_sha256, "CLI differs from author handoff"
    scratch = Path(tempfile.mkdtemp(prefix="dotrepo-go-context-amendment-review-", dir="/tmp"))
    results = []
    for number, (name, workflow, build, test, contributing) in enumerate(cases()):
        root = scratch / str(number)
        folder = root / ".github/workflows"
        folder.mkdir(parents=True)
        (root / "go.mod").write_text("module example.test/review\n\ngo 1.23\n")
        (root / "README.md").write_text("# Owned synthetic Go amendment fixture\n")
        (folder / "ci.yml").write_text(workflow)
        if contributing is not None:
            (root / "CONTRIBUTING.md").write_text(contributing)
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
        expected = {
            "build": "go build ./..." if build else None,
            "test": "go test ./..." if test else None,
        }
        observed = {field: manifest["repo"].get(field) for field in ("build", "test")}
        results.append(
            {
                "case": name,
                "workflow": workflow,
                "expected": expected,
                "observed": observed,
                "pass": observed == expected,
                "contributing": contributing,
                "argv": argv,
                "exitCode": run.returncode,
                "stdout": run.stdout,
                "stderr": run.stderr,
                "evidence": (root / "evidence.md").read_text(),
            }
        )
    print(
        json.dumps(
            {
                "cliSha256": digest,
                "scratch": str(scratch),
                "cases": len(results),
                "failedCases": [r["case"] for r in results if not r["pass"]],
                "firstPartyImporterOnly": True,
                "upstreamExecution": False,
                "providerOrNetworkCalls": 0,
                "results": results,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
