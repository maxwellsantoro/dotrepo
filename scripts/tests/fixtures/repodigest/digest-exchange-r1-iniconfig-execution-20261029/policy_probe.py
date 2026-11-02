"""Temporary-index Rust export and reference-consumer diagnostic; no execution."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[2]
CLIENT = ROOT / "examples/external-consumer/lookup_before_scrape.py"
spec = importlib.util.spec_from_file_location("execution_policy_consumer", CLIENT)
consumer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = consumer
spec.loader.exec_module(consumer)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(binary, output):
    if output.exists():
        raise FileExistsError("preserve prior results; choose a fresh output")
    output.mkdir(parents=True)
    frozen = json.loads((PACKET / "SPEC.json").read_text())
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    command = " ".join(frozen["recipe"]["test"])
    context = {
        "command": command,
        "working_directory": ".",
        "scope": "repository",
        "prerequisites": [" ".join(frozen["recipe"]["setup"])],
        "source": "EXPERIMENT-RECIPE.json",
    }
    (output / "EXPERIMENT-RECIPE.json").write_text(
        json.dumps({"specification": frozen, "context": context}, indent=2) + "\n"
    )
    receipt = {
        "binarySha256": digest(binary),
        "consumerSha256": digest(CLIENT),
        "probeSha256": digest(Path(__file__)),
        "executionReportSha256": digest(PACKET / "run-004/report.json"),
        "inputsSha256": digest(PACKET / "INPUTS.json"),
        "timestamp": timestamp,
        "purpose": "Check current contract; no confidence promotion or public index write.",
    }
    (output / "input-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    rows = []
    for confidence in ("medium", "high"):
        directory = output / confidence
        directory.mkdir()
        quote = json.dumps
        lines = [
            "schema = 'dotrepo/v0.1'",
            "[record]",
            "mode = 'overlay'",
            "status = 'inferred'",
            "source = 'https://github.com/pytest-dev/iniconfig'",
            "generated_at = " + quote(timestamp),
            "[record.trust]",
            "confidence = 'medium'",
            "provenance = ['inferred']",
            "[repo]",
            "name = 'iniconfig'",
            "description = 'Experimentally observed synthesized recipe; temporary diagnostic record.'",
            "test = " + quote(command),
            "[repo.test_context]",
            *[key + " = " + quote(value) for key, value in context.items()],
        ]
        for path, value in (("repo.test", command), ("repo.test_context", context)):
            lines.extend(
                [
                    "[x.dotrepo.field_evidence." + quote(path) + "]",
                    "state = 'present'",
                    "method = 'inferred'",
                    "confidence = " + quote(confidence),
                    "source = 'EXPERIMENT-RECIPE.json'",
                    "checkedAt = " + quote(timestamp),
                    "valueJson = " + quote(json.dumps(value)),
                ]
            )
        record = "\n".join(lines) + "\n"
        (directory / "record.toml").write_text(record)
        with tempfile.TemporaryDirectory(prefix="iniconfig-policy-") as temporary:
            index = Path(temporary) / "index"
            path = index / "repos/github.com/pytest-dev/iniconfig/record.toml"
            path.parent.mkdir(parents=True)
            path.write_text(record)
            process = subprocess.run(
                [
                    str(binary),
                    "public",
                    "profile",
                    "--index-root",
                    str(index),
                    "github.com",
                    "pytest-dev",
                    "iniconfig",
                ],
                capture_output=True,
                timeout=30,
                check=False,
            )
            (directory / "export.stdout").write_bytes(process.stdout)
            (directory / "export.stderr").write_bytes(process.stderr)
            process.check_returncode()
        profile = json.loads(process.stdout)
        result = consumer.interpret_http_response(
            identity="github.com/pytest-dev/iniconfig", status_code=200, body=process.stdout
        )
        selection = consumer.select_instruction(
            result,
            "test",
            request={"scope": "repository", "component": None, "workingDirectory": "."},
            now=datetime.now(timezone.utc),
        )
        row = {
            "fieldConfidence": confidence,
            "kind": "honest inferred candidate"
            if confidence == "medium"
            else "synthetic favorable-confidence diagnostic only",
            "exportExitCode": process.returncode,
            "exportedEvidence": profile.get("fieldEvidence"),
            "selection": selection,
        }
        (directory / "selection.json").write_text(json.dumps(row, indent=2) + "\n")
        rows.append(row)
    report = {
        "outcome": "current-consumer-abstains"
        if all(row["selection"]["instruction"] is None for row in rows)
        else "unexpected-selection",
        "runs": rows,
        "upstreamExecutions": 0,
        "networkCalls": 0,
        "publicIndexWrites": 0,
        "claim": "Observation is not extraction; current public context also lacks revision/environment bindings.",
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["outcome"])
    return 0 if report["outcome"] == "current-consumer-abstains" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.binary.resolve(strict=True), args.output))
