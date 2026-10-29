#!/usr/bin/env -S uv run python
"""Compare ordinary CLI/MCP behavior of two independently installed toolchains.

Only normal files and directories are used. Write refusal coverage belongs to
the native Rust regression suites, which must run against the fixed candidate.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def normalize(text, root):
    text = text.replace(str(root), "<root>")
    text = re.sub(r"\b1\.0\.\d+\b", "<stable-version>", text)
    return re.sub(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})",
        "<timestamp>",
        text,
    )


def cli(bin_dir, root, *args):
    result = subprocess.run(
        [str(bin_dir / "dotrepo"), "--root", str(root), *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return normalize(result.stdout, root)


def files(root):
    return {
        str(path.relative_to(root)): normalize(path.read_text(), root)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def mcp(bin_dir, root):
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "stable-comparison", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "dotrepo.import_write",
                "arguments": {"root": ".", "mode": "native"},
            },
        },
    ]
    result = subprocess.run(
        [str(bin_dir / "dotrepo-mcp")],
        cwd=root,
        input="".join(json.dumps(message) + "\n" for message in messages),
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert [response["id"] for response in responses] == [1, 2, 3], responses
    assert responses[0]["result"]["protocolVersion"] == "2025-11-25"
    assert not responses[2]["result"].get("isError"), responses[2]
    assert (root / ".repo").is_file(), responses[2]
    return json.loads(normalize(json.dumps(responses, sort_keys=True), root))


def exercise(bin_dir, source, base):
    results = {"help": cli(bin_dir, base, "--help")}
    native = base / "native"
    shutil.copytree(source / "examples/native-minimal", native)
    results["generate"] = cli(bin_dir, native, "generate")
    results["generateCheck"] = cli(bin_dir, native, "generate", "--check")
    for command in ["validate", "trust", "doctor"]:
        results[command] = cli(bin_dir, native, command)
    results["query"] = cli(bin_dir, native, "query", "repo.name", "--json")
    results["generatedFiles"] = files(native)
    for mode in ["native", "overlay"]:
        root = base / mode / "import"
        root.mkdir(parents=True)
        (root / "README.md").write_text("# ordinary-fixture\n\nA fixture project.\n")
        source_args = ["--source", "https://github.com/example/ordinary-fixture"]
        results[f"{mode}Import"] = cli(
            bin_dir, root, "import", "--mode", mode, *source_args
        )
        results[f"{mode}ForceImport"] = cli(
            bin_dir, root, "import", "--mode", mode, *source_args, "--force"
        )
        results[f"{mode}Files"] = files(root)
    root = base / "mcp"
    root.mkdir()
    (root / "README.md").write_text("# ordinary-fixture\n\nA fixture project.\n")
    results["mcp"] = mcp(bin_dir, root)
    results["mcpFiles"] = files(root)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-bin", required=True, type=Path)
    parser.add_argument("--candidate-bin", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="dotrepo-ordinary-comparison-") as tmp:
        base = Path(tmp)
        before = exercise(args.baseline_bin.resolve(), source, base / "baseline")
        after = exercise(args.candidate_bin.resolve(), source, base / "candidate")
    differences = [key for key in before if before[key] != after[key]]
    report = {
        "passed": not differences,
        "differences": differences,
        "normalizations": ["temporary roots", "stable patch version", "timestamps"],
        "checks": list(before),
        "baselineSha256": {
            name: hashlib.sha256((args.baseline_bin / name).read_bytes()).hexdigest()
            for name in ["dotrepo", "dotrepo-mcp"]
        },
        "candidateSha256": {
            name: hashlib.sha256((args.candidate_bin / name).read_bytes()).hexdigest()
            for name in ["dotrepo", "dotrepo-mcp"]
        },
        "baseline": before,
        "candidate": after,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    if differences:
        raise SystemExit(
            f"ordinary contract differences: {differences}; see {args.output}"
        )
    print(f"ordinary CLI/MCP outputs match: {args.output}")


if __name__ == "__main__":
    main()
