from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capture_upstream_accuracy_sample import repository_selection


def test_capture_provenance_describes_the_actual_input_list():
    repositories, selection = repository_selection("github.com/example/tool\n")
    assert repositories == ["github.com/example/tool"]
    assert "1 identities" in selection
    assert "September" not in selection
    assert "first 32" not in selection
    assert "caller-supplied" in selection
    assert repository_selection("\n github.com/example/tool \n")[1] == selection
    assert repository_selection("github.com/example/other\n")[1] != selection


@pytest.mark.parametrize(
    "text",
    [
        "",
        "\n",
        "github.com/a/b\ngithub.com/a/b",
        "gitlab.com/a/b",
        "github.com/a/..",
        "github.com/a/b/c",
        "github.com/../b",
    ],
)
def test_invalid_or_duplicate_input_is_rejected_before_network_calls(text):
    with pytest.raises(ValueError):
        repository_selection(text)


def test_current_release_workload_preserves_cohort_and_matches_frozen_sources():
    root = Path(__file__).resolve().parents[2]
    original = json.loads(
        (root / "scripts/fixtures/public_upstream_accuracy_workload.json").read_text()
    )
    capture = root / "benchmarks/head-to-head/upstream-2026-10-04"
    current = json.loads((capture / "workload.json").read_text())
    assert {a["id"] for a in current["assertions"]} == {a["id"] for a in original["assertions"]}
    identities, selection = repository_selection((capture / "identities.txt").read_text())
    assert current["selection"] == selection
    assert len(identities) == 32
    assert len(current["assertions"]) == 123
    for assertion in current["assertions"]:
        _, owner, repo = assertion["repository"].split("/")
        source = json.loads((capture / f"{owner}--{repo}.json").read_text())
        value = source
        for segment in assertion["source"]["locator"].split("."):
            value = value[segment]
        assert value == assertion["expected"]
        assert assertion["source"]["checkedAt"] == source["checkedAt"]
