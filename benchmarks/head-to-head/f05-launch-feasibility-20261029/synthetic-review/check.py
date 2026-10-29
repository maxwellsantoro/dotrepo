"""Owned data-only review of the fixed synthetic campaign path."""

import json
from pathlib import Path
import sys

import pytest

ROOT = Path("/Users/maxwell/projects/agent/dotrepo")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts/tests"))
import test_agent_campaign_path as subject  # noqa: E402


def run():
    root = HERE / "owned-replay"
    root.mkdir(exist_ok=False)
    captured = {}
    original = subject.experiment.summarize

    def capture(*args):
        result = original(*args)
        captured.update(report=result, args=[str(x) for x in args])
        return result

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(subject.experiment, "summarize", capture)
        subject.test_full_synthetic_assignment_runtime_oracle_and_analysis_path(root, patch)
    manifest, assignment, observations = map(Path, captured["args"])
    value = json.loads(observations.read_bytes())
    tally = {}
    for row in value["runs"]:
        trace = json.loads((root / row["trace"]["path"]).read_bytes())
        score = json.loads((root / row["score"]["path"]).read_bytes())
        receipt = json.loads((root / row["usage"]["path"]).read_bytes())
        request = (
            json.loads((root / "prepared/requests" / (row["sessionId"] + ".json")).read_bytes())
            if (root / "prepared/requests" / (row["sessionId"] + ".json")).exists()
            else None
        )
        assert trace["requestSha256"] == row["requestSha256"] == receipt["requestSha256"]
        assert score["traceSha256"] == row["trace"]["sha256"]
        key = "dotrepo-access" if "dotrepo-access" in row["sessionId"] else "source-first"
        tally.setdefault(
            key,
            {"sessions": 0, "completed": 0, "wrongActionRetained": 0, "direct": 0, "fallback": 0},
        )
        t = tally[key]
        t["sessions"] += 1
        for dest, src in [
            ("completed", "correctCompletion"),
            ("wrongActionRetained", "incorrectAction"),
            ("direct", "directApplicableInstruction"),
            ("fallback", "correctAbstentionFallback"),
        ]:
            t[dest] += score[src]
        if request is not None:
            assert "gold" not in request["task"] and "oracle" not in request["task"]
    rejected = []
    for name, mutate in [
        ("missing-assigned-session", lambda v: v["runs"].pop()),
        ("changed-request-binding", lambda v: v["runs"][0].update(requestSha256="0" * 64)),
        ("cross-session-usage-reuse", lambda v: v["runs"][0].update(usage=v["runs"][1]["usage"])),
    ]:
        data = json.loads(observations.read_bytes())
        mutate(data)
        path = root / (name + ".json")
        path.write_text(json.dumps(data))
        try:
            original(manifest, assignment, path)
        except ValueError as exc:
            rejected.append({"name": name, "rejected": True, "reason": str(exc)})
        else:
            raise AssertionError(name)
    config = json.loads((root / "runtime.json").read_bytes())
    assert all(v is False for v in config["qualifications"].values())
    return {
        "state": "owned-synthetic-path-only",
        "sessions": len(value["runs"]),
        "tally": tally,
        "report": captured["report"],
        "independentPosthocControls": rejected,
        "allRuntimeQualificationsFalse": True,
        "realProviderDaemonUpstreamActions": False,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
