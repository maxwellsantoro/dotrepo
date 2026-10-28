import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from measure_public_policy_coverage import markdown, measure
from render_public_efficiency_page import render_policy_coverage


def test_presence_acceptance_and_correctness_remain_distinct(tmp_path):
    checked = "2026-09-16T00:00:00Z"
    payload = {
        "apiVersion": "v0",
        "identity": {"host": "github.com", "owner": "example", "repo": "good"},
        "record": {"generatedAt": checked},
        "purpose": "Example project",
        "docs": {"root": "https://example.com/docs"},
        "execution": {"build": "make build", "test": "make test"},
        "fieldEvidence": {
            f"repo.{field}": {
                "state": "present",
                "method": "extracted",
                "confidence": "high",
                "source": "Makefile",
                "checkedAt": checked,
            }
            for field in ["build", "test"]
        },
    }
    payload["fieldEvidence"]["docs.root"] = {
        "state": "present",
        "method": "extracted",
        "confidence": "high",
        "source": "README.md",
        "checkedAt": checked,
    }
    for case in ["good", "inferred", "missing", "candidates", "medium", "stale"]:
        data = copy.deepcopy(payload)
        data["identity"]["repo"] = case
        if case == "inferred":
            data["fieldEvidence"]["repo.test"]["method"] = "inferred"
            data["fieldEvidence"]["docs.root"]["method"] = "inferred"
        elif case == "missing":
            del data["fieldEvidence"]
        elif case == "candidates":
            data["execution"] = {"buildCandidates": ["make build"], "testCandidates": ["make test"]}
        elif case == "medium":
            data["fieldEvidence"]["repo.build"]["confidence"] = "medium"
            data["fieldEvidence"]["docs.root"]["confidence"] = "medium"
        elif case == "stale":
            data["record"]["generatedAt"] = "2026-01-01T00:00:00Z"
        path = tmp_path / "v0/repos/github.com/example" / case / "profile.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(data))
    (tmp_path / "v0/meta.json").write_text(
        json.dumps({"generatedAt": checked, "snapshotDigest": "test"})
    )
    duplicate = tmp_path / "v0/snapshots/copy/repos/github.com/example/good/profile.json"
    duplicate.parent.mkdir(parents=True)
    duplicate.write_text(json.dumps(payload))
    report = measure(tmp_path)
    both = report["tasks"]["build-and-test"]
    assert (report["profileCount"], both["presentCount"], both["acceptableCount"]) == (6, 5, 1)
    assert report["commandSlots"] == {"total": 12, "present": 10, "acceptable": 4}
    docs = report["tasks"]["documentation"]
    assert (docs["presentCount"], docs["acceptableCount"]) == (6, 2)
    assert docs["fallbackReasonCounts"]["insufficient-docs-assessment:docs.root"] == 4
    assert report["documentationPolicy"] == "explicit-high-confidence-documentation-declaration"
    assert both["independentlyCorrectCount"] is None
    assert both["completedTaskCount"] is None
    assert both["fallbackReasonCounts"]["inferred-command:repo.test"] == 1
    assert both["fallbackReasonCounts"]["missing-command-assessment:repo.build"] == 1
    assert "Not measured" in markdown(report)
    rendered = render_policy_coverage(report, "/prefix")
    assert "1 (16.7%)" in rendered
    assert "5 (83.3%)" in rendered
    assert "/prefix/benchmarks/policy-coverage.json" in rendered
    assert "Not measured" in rendered
    # The evaluation time is explicit; later measurements cannot rejuvenate records.
    later = measure(tmp_path, "2026-11-01T00:00:00Z")
    assert later["tasks"]["build-and-test"]["acceptableCount"] == 0


def test_command_scope_shared_with_importer_and_contexts_remain_distinct(tmp_path):
    from measure_public_policy_coverage import consumer

    root = Path(__file__).resolve().parents[2]
    cases = json.loads(
        (root / "crates/dotrepo-core/tests/fixtures/command-scope-cases.json").read_text()
    )
    for case in cases:
        assert consumer.cargo_component_selector(case["command"]) == case["componentScoped"]
    checked = "2026-10-28T00:00:00Z"
    assessment = {
        "state": "present",
        "method": "extracted",
        "confidence": "high",
        "source": "README.md",
        "checkedAt": checked,
    }
    payload = {
        "apiVersion": "v0",
        "identity": {"host": "github.com", "owner": "example", "repo": "context"},
        "record": {"generatedAt": checked},
        "languages": ["Rust", "Python"],
        "purpose": "Context fixture",
        "execution": {},
        "fieldEvidence": {},
    }
    for purpose, command in [
        ("build", "cargo build --workspace"),
        ("test", "cargo test --workspace"),
    ]:
        payload["execution"][purpose] = command
        payload["execution"][purpose + "Context"] = {
            "command": command,
            "workingDirectory": ".",
            "scope": "repository",
            "prerequisites": ["Install Rust 1.90"],
            "source": "README.md",
        }
        payload["fieldEvidence"]["repo." + purpose] = dict(assessment)
        payload["fieldEvidence"]["repo." + purpose + "_context"] = dict(assessment)
    for name in ("complete", "scalar-only", "component-selector"):
        data = copy.deepcopy(payload)
        data["identity"]["repo"] = name
        if name == "scalar-only":
            del data["execution"]["testContext"]
        if name == "component-selector":
            data["execution"]["test"] = "cargo test --manifest-path crates/tool/Cargo.toml"
            del data["execution"]["testContext"]
        path = tmp_path / "v0/repos/github.com/example" / name / "profile.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(data))
    (tmp_path / "v0/meta.json").write_text(
        json.dumps({"generatedAt": checked, "snapshotDigest": "test"})
    )
    report = measure(tmp_path)
    rust = report["ecosystems"]["Rust"]
    assert rust["profileCount"] == 3
    assert rust["tasks"]["build-and-test"]["acceptableCount"] == 2
    assert rust["instructions"]["build-and-test"]["acceptableCount"] == 1
    assert (
        rust["tasks"]["test"]["fallbackReasonCounts"]["component-command-selector:repo.test"] == 1
    )
    assert (
        rust["instructions"]["test"]["fallbackReasonCounts"]["no-assessed-contextual-instruction"]
        == 2
    )
    assert rust["instructions"]["test"]["independentlyCorrectCount"] is None
    assert "Accepted contextual pairs" in render_policy_coverage(report, "")


def test_invalid_execution_is_counted_as_fallback(tmp_path):
    checked = "2026-10-28T00:00:00Z"
    for name, execution in [("null", None), ("list", []), ("string", "cargo test")]:
        path = tmp_path / "v0/repos/github.com/example" / name / "profile.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "apiVersion": "v0",
                    "identity": {"host": "github.com", "owner": "example", "repo": name},
                    "record": {"generatedAt": checked},
                    "execution": execution,
                }
            )
        )
    (tmp_path / "v0/meta.json").write_text(
        json.dumps({"generatedAt": checked, "snapshotDigest": "test"})
    )
    report = measure(tmp_path)
    pairs = report["instructionCoverage"]["tasks"]["build-and-test"]
    assert pairs["profileCount"] == 3
    assert pairs["presentCount"] == pairs["acceptableCount"] == 0
    assert pairs["fallbackReasonCounts"] == {"invalid-execution": 3}
