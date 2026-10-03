import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from public_product_content import freshness_summary, record_status


def test_new_export_does_not_reset_record_age():
    assert record_status({"generatedAt": "2026-07-06T00:00:00Z"}, "2026-09-16T00:00:00Z") == (
        "stale",
        72,
    )
    assert record_status({"generatedAt": "2026-09-17T00:00:00Z"}, "2026-09-16T00:00:00Z") == (
        "unknown",
        None,
    )
    assert record_status({"generatedAt": "2026-09-16"}, "2026-09-16T00:00:00Z") == ("unknown", None)


def test_missing_profile_counts_as_unknown_and_export_dates_are_not_substituted(tmp_path):
    inventory = {
        "repositoryCount": 2,
        "repositories": [
            {"identity": {"host": "github.com", "owner": "example", "repo": repo}}
            for repo in ["old", "missing"]
        ],
    }
    root = tmp_path / "v0/repos/github.com/example/old"
    root.mkdir(parents=True)
    (root / "profile.json").write_text(
        json.dumps(
            {
                "record": {"generatedAt": "2026-07-06T00:00:00Z"},
                "freshness": {"generatedAt": "2026-09-16T00:00:00Z"},
            }
        )
    )
    summary = freshness_summary(tmp_path, inventory, "2026-09-16T00:00:00Z")
    assert (summary["fresh"], summary["stale"], summary["unknown"]) == (0, 1, 1)
