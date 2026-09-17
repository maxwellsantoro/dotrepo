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
    for case in ["good", "inferred", "missing", "candidates", "medium", "stale"]:
        data = copy.deepcopy(payload)
        data["identity"]["repo"] = case
        if case == "inferred":
            data["fieldEvidence"]["repo.test"]["method"] = "inferred"
        elif case == "missing":
            del data["fieldEvidence"]
        elif case == "candidates":
            data["execution"] = {"buildCandidates": ["make build"], "testCandidates": ["make test"]}
        elif case == "medium":
            data["fieldEvidence"]["repo.build"]["confidence"] = "medium"
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
