"""Real public exporter -> reference selector -> real bounded task execution.

These tiny controls establish plumbing, not usefulness on public projects.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parents[2] / "benchmarks/head-to-head"
sys.path.insert(0, str(BENCH))
from bench.own_projects import (  # noqa: E402
    execute_instruction,
    select_profile_instruction,
    screen_instruction_for_task,
)


def exported_control(tmp_path, *, component):
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    command = "uv run --no-project python -m unittest discover -s tests -v"
    context = {
        "command": command,
        "working_directory": "package" if component else ".",
        "scope": "component" if component else "repository",
        "prerequisites": ["ready fixture prepared in the working directory"],
        "source": "README.md",
    }
    if component:
        context["component"] = "package"
    candidate = {"command": command, "source": "README.md", "ecosystem": None, "context": context}

    def quoted(value):
        return json.dumps(value)

    lines = [
        "schema = 'dotrepo/v0.1'",
        "[record]",
        "mode = 'overlay'",
        "status = 'imported'",
        "generated_at = " + quoted(timestamp),
        "source = 'https://github.com/example/control'",
        "[record.trust]",
        "provenance = ['imported']",
        "[repo]",
        "name = 'control'",
        "description = 'Contextual instruction control.'",
    ]
    if component:
        lines += [
            "[[repo.test_candidates]]",
            "command = " + quoted(command),
            "source = 'README.md'",
            "[repo.test_candidates.context]",
        ]
        assessments = [("repo.test_candidates.0", candidate)]
    else:
        lines += ["test = " + quoted(command), "[repo.test_context]"]
        assessments = [("repo.test", command), ("repo.test_context", context)]
    lines += [f"{key} = {quoted(value)}" for key, value in context.items()]
    for path, value in assessments:
        lines += [
            f"[x.dotrepo.field_evidence.{quoted(path)}]",
            "state = 'present'",
            "method = 'extracted'",
            "confidence = 'high'",
            "source = 'README.md'",
            "checkedAt = " + quoted(timestamp),
            "valueJson = " + quoted(json.dumps(value)),
        ]
    index = tmp_path / "index"
    record = index / "repos/github.com/example/control/record.toml"
    record.parent.mkdir(parents=True)
    record.write_text("\n".join(lines) + "\n")
    body = subprocess.check_output(
        [
            "cargo",
            "run",
            "--quiet",
            "--locked",
            "-p",
            "dotrepo-cli",
            "--",
            "public",
            "profile",
            "--index-root",
            str(index),
            "github.com",
            "example",
            "control",
        ],
        cwd=BENCH.parents[1],
    )
    return body


@pytest.mark.parametrize("component", [False, True])
def test_exported_context_executes_without_source_fallback(tmp_path, component):
    body = exported_control(tmp_path, component=component)
    # Input is the actual Rust public envelope, not a mirror assembled for Python.
    selection = select_profile_instruction("github.com/example/control", 200, body, "test")
    assert not selection["fallbackReasons"]
    plan = selection["instruction"]
    assert plan["prerequisites"] == ["ready fixture prepared in the working directory"]
    assert plan["workingDirectory"] == ("package" if component else ".")
    assert plan["scope"] == ("component" if component else "repository")
    assert plan["component"] == ("package" if component else None)
    expected = {
        "command": "uv run --no-project python -m unittest discover -s tests -v",
        "workingDirectory": "package" if component else ".",
        "scope": "component" if component else "repository",
        "component": "package" if component else None,
        "prerequisites": ["ready fixture prepared in the working directory"],
        "parameters": {},
        "environment": {},
        "sourcePaths": ["README.md"],
        "purpose": "test",
    }
    approved, mismatch = screen_instruction_for_task(plan, expected)
    assert approved is plan and mismatch is None
    for key, wrong in [
        ("workingDirectory", "other"),
        ("component", "other"),
        ("prerequisites", []),
        ("command", "cargo test"),
    ]:
        incorrect = {**plan, key: wrong}
        approved, mismatch = screen_instruction_for_task(incorrect, expected)
        assert approved is None and mismatch["exitCode"] is None
        assert mismatch["instruction"] == incorrect and "not executed" in mismatch["executionError"]
    root = tmp_path / "checkout"
    directory = root / plan["workingDirectory"]
    (directory / "tests").mkdir(parents=True)
    (directory / "ready").touch()
    (directory / "tests/test_context.py").write_text(
        "import unittest\nfrom pathlib import Path\nclass Context(unittest.TestCase):\n"
        "    def test_ready(self):\n        self.assertTrue(Path('ready').is_file())\n"
    )
    commands, passed = execute_instruction(plan, [], root, os.environ, 30, "consumer-test")
    assert len(commands) == 1 and commands[0]["exitCode"] == 0 and passed
    assert selection["provenance"]["assessmentPaths"]
    # A wrong directory/component request is refused before execution.
    for request in [{"workingDirectory": "other"}, {"component": "other"}]:
        assert (
            select_profile_instruction("github.com/example/control", 200, body, "test", request)[
                "instruction"
            ]
            is None
        )


def test_context_binding_and_missing_prerequisites_cannot_pass_the_task(tmp_path):
    body = exported_control(tmp_path, component=True)
    payload = json.loads(body)
    candidate = payload["execution"]["testCandidates"][0]
    original = copy.deepcopy(candidate["context"])
    candidate["context"]["command"] = "cargo test"
    assert (
        select_profile_instruction("github.com/example/control", 200, json.dumps(payload), "test")[
            "instruction"
        ]
        is None
    )
    candidate["context"] = original
    candidate["context"].pop("prerequisites")
    assert (
        select_profile_instruction("github.com/example/control", 200, json.dumps(payload), "test")[
            "instruction"
        ]
        is None
    )
    candidate["context"] = original
    payload["fieldEvidence"]["repo.test_candidates.0"]["checkedAt"] = "2000-01-01T00:00:00Z"
    assert (
        select_profile_instruction("github.com/example/control", 200, json.dumps(payload), "test")[
            "instruction"
        ]
        is None
    )
