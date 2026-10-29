"""Novel owned README imports using the author's exact first-party CLI."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import tomllib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
URL = "https://shared.example/orbit/manual"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    binary = ROOT / "target/debug/dotrepo"
    expected = "04f5e2aa8d80ce1701fb7ec2cbab7e431242dac7adb1aed41d73e93b9479ef8b"
    assert sha(binary) == expected
    bindings = {
        path: sha(ROOT / path)
        for path in [
            "crates/dotrepo-core/src/import/parsing/markdown.rs",
            "crates/dotrepo-core/src/import/parsing/markdown/docs_tests.rs",
        ]
    }
    cases = [
        (
            "wrapped-integration",
            f"Other has an integration with Orbit and offers\n[Orbit documentation]({URL})\nfor its setup.",
            None,
            None,
        ),
        (
            "list-wrapped-integration",
            f"- Other integration has its own\n  [Orbit documentation]({URL})\n  for setup.",
            None,
            None,
        ),
        (
            "wrapped-neutral-docs-prefix",
            f"Other's integration setup includes its own\nDocs: [manual]({URL})",
            None,
            None,
        ),
        (
            "list-wrapped-neutral-docs-prefix",
            f"- Other's integration setup includes its own\n  Documentation: [manual]({URL})",
            None,
            None,
        ),
        (
            "wrapped-start-prefix",
            f"Other's integration setup includes its own\nGetting started: [guide]({URL})",
            None,
            None,
        ),
        (
            "explicit-prefix-other-tail",
            f"Docs: [manual]({URL}) for Other's integration.",
            None,
            None,
        ),
        ("read-license", f"Read the [license]({URL}) for more information.", None, None),
        (
            "follow-coc",
            f"Follow the [code of conduct]({URL}) for further instructions.",
            None,
            None,
        ),
        ("visit-issues", f"Visit the [issue tracker]({URL}).", None, None),
        (
            "section-third-party",
            f"## Documentation\n\nOther's integration documentation includes\n[Docs]({URL}).",
            None,
            None,
        ),
        ("neutral-root-prefix", f"Docs: [manual]({URL})", URL, None),
        ("neutral-start-prefix", f"Getting started: [guide]({URL})", None, URL),
        (
            "project-subject-neutral",
            f"Documentation for Orbit is available at [handbook]({URL}).",
            URL,
            None,
        ),
        (
            "custom-domain-nav",
            f"[Orbit Docs]({URL}) | [Issues](https://issues.example/orbit)",
            URL,
            None,
        ),
        (
            "separate-list-subject",
            f"- Other integration is described separately.\n- [Docs]({URL})",
            URL,
            None,
        ),
        (
            "wrapped-direct-docs",
            f"Read the\n[Orbit documentation]({URL})\nfor more information.",
            URL,
            None,
        ),
    ]
    for count in [1000, 4000, 12000]:
        text = "\n".join(
            f"Other integration prose number {i}."
            if i % 10
            else f"See its [Orbit documentation]({URL}) for setup instructions."
            for i in range(count)
        )
        cases.append((f"long-contiguous-{count}", text, None, None))
    rows = []
    for name, body, want_root, want_start in cases:
        source = "# Orbit\n\n" + body + "\n"
        with tempfile.TemporaryDirectory(prefix="dotrepo-f1-docs-review-", dir="/tmp") as directory:
            folder = Path(directory)
            (folder / "README.md").write_text(source)
            argv = [
                str(binary),
                "--root",
                str(folder),
                "import",
                "--mode",
                "overlay",
                "--source",
                "https://example.test/orbit",
            ]
            started = time.monotonic()
            run = subprocess.run(argv, capture_output=True, text=True, timeout=30)
            elapsed = time.monotonic() - started
            assert run.returncode == 0, run.stderr
            record = (folder / "record.toml").read_text()
            docs = tomllib.loads(record).get("docs", {})
            got_root, got_start = docs.get("root"), docs.get("getting_started")
            rows.append(
                {
                    "case": name,
                    "input": source,
                    "inputBytes": len(source.encode()),
                    "argv": argv,
                    "exitCode": run.returncode,
                    "elapsedSeconds": elapsed,
                    "expectedRoot": want_root,
                    "expectedStart": want_start,
                    "actualRoot": got_root,
                    "actualStart": got_start,
                    "expectationMatched": (got_root, got_start) == (want_root, want_start),
                    "record": record,
                    "evidence": (folder / "evidence.md").read_text(),
                    "stdout": run.stdout,
                    "stderr": run.stderr,
                }
            )
    assert sha(binary) == expected
    assert all(sha(ROOT / path) == digest for path, digest in bindings.items())
    print(
        json.dumps(
            {
                "cliSha256": expected,
                "sourceBindings": bindings,
                "firstPartyImports": len(rows),
                "upstreamExecutionNetworkProviderCalls": 0,
                "controls": rows,
                "mismatches": [row["case"] for row in rows if not row["expectationMatched"]],
                "timingLimit": "Observed whole CLI imports on a shared host; timings are a regression diagnostic, not a benchmark or complexity proof.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
