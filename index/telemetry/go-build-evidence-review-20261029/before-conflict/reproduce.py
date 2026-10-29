"""One first-party CLI import of owned conflicting maintainer declarations."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    inputs = {
        "README.md": "# Conflict control\n\nOwned synthetic conflict fixture.\n\n## Build\n\n```sh\ngo build ./...\n```\n",
        "CONTRIBUTING.md": "# Contributing\n\n## Build\n\n```sh\ngo build -tags=integration ./...\n```\n",
        "go.mod": "module example.test/conflict\n\ngo 1.22\n",
    }
    paths = [
        "crates/dotrepo-core/src/import/commands/mod.rs",
        "crates/dotrepo-core/src/import/commands/go_context.rs",
        "crates/dotrepo-core/src/import/commands/go_context/tests.rs",
        "crates/dotrepo-core/src/import/fields.rs",
        "crates/dotrepo-core/src/facade_tests/import_repository.rs",
        "crates/dotrepo-core/tests/fixtures/import/expectations.json",
    ]
    bindings = {path: sha(ROOT / path) for path in paths}
    for path in paths:
        dest = HERE / "source-before" / (path + ".txt")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((ROOT / path).read_bytes())
    binary = ROOT / "target/debug/dotrepo"
    with tempfile.TemporaryDirectory(
        prefix="dotrepo-go-build-conflict-before-", dir="/tmp"
    ) as directory:
        folder = Path(directory)
        for name, text in inputs.items():
            (folder / name).write_text(text)
        argv = [
            str(binary),
            "--root",
            str(folder),
            "import",
            "--mode",
            "overlay",
            "--source",
            "https://example.test/conflict",
        ]
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        assert completed.returncode == 0, completed.stderr
        manifest_text = (folder / "record.toml").read_text()
        evidence = (folder / "evidence.md").read_text()
        manifest = tomllib.loads(manifest_text)
        assert manifest["repo"].get("build") is None
        assert manifest["repo"].get("test") == "go test ./..."
        assert (
            "CONTRIBUTING.md" in evidence
            and "README.md" in evidence
            and "conflicting build commands" in evidence
        )
        assert "root go.mod supplies only a conventional build candidate" in evidence
        for path, digest in bindings.items():
            assert sha(ROOT / path) == digest
        print(
            json.dumps(
                {
                    "case": "two-eligible-maintainer-build-alternatives-plus-module-default",
                    "base": "72c654caaba1c88a7206815296bec91fa3bb5760",
                    "firstPartyCliImports": 1,
                    "upstreamCodeExecuted": False,
                    "providerNetworkIndexCalls": 0,
                    "inputs": inputs,
                    "codeBindings": bindings,
                    "cliSha256": sha(binary),
                    "argv": argv,
                    "exitCode": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                    "manifest": manifest_text,
                    "evidence": evidence,
                    "observedBuild": None,
                    "observedTest": "go test ./...",
                    "observation": "Importer retains declared conflict but additionally emits the module-only field-block note. Frozen source sets blocked_scalar_fields on this exact branch; request builder then skips the whole field before per-candidate eligibility filtering.",
                    "adjudicationRequestSuppression": "Source-path proof, not directly exposed by this CLI report; follow-up author regression must assert both declared candidates remain selectable and go.mod does not.",
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
