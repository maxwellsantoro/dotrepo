import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "check_public_quality_dashboard.py"
SPEC = importlib.util.spec_from_file_location("check_public_quality_dashboard", SCRIPT)
quality = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(quality)


def write_profile(
    public_root: Path,
    owner: str,
    repo: str,
    *,
    name: str,
    purpose: str,
    confidence: str = "high",
) -> None:
    path = public_root / "v0" / "repos" / "github.com" / owner / repo / "profile.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
{
  "apiVersion": "v0",
  "identity": {"host": "github.com", "owner": "%s", "repo": "%s"},
  "name": "%s",
  "purpose": "%s",
  "trust": {"selectedStatus": "verified", "confidence": "%s"},
  "completeness": {
    "conflictCount": 0,
    "hasBuild": true,
    "hasTest": true,
    "hasDocs": true,
    "hasSecurityContact": false,
    "hasOwnershipSignal": false,
    "hasLicense": true
  }
}
""".strip()
        % (owner, repo, name, purpose, confidence)
    )


def test_dashboard_counts_generic_duplicates_and_low_confidence(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_profile(
        public_root,
        "example",
        "forum",
        name="discussions",
        purpose="Please go to our discussion forum for general questions.",
    )
    write_profile(
        public_root,
        "example",
        "one",
        name="one",
        purpose="Same reusable project description for duplicate detection.",
    )
    write_profile(
        public_root,
        "example",
        "two",
        name="two",
        purpose="Same reusable project description for duplicate detection.",
    )
    write_profile(
        public_root,
        "example",
        "low",
        name="low",
        purpose="A real-looking but low confidence project.",
        confidence="low",
    )

    report = quality.summarize(
        public_root,
        max_items=10,
        thresholds={
            "minProfiles": 4,
            "maxGenericFieldHits": 2,
            "maxDuplicatedDescriptionValues": 1,
            "maxDuplicateDescriptionRecords": 2,
            "maxBadLookingRecords": 4,
        },
    )

    assert report["passed"] is True
    assert report["summary"]["profileCount"] == 4
    assert report["summary"]["genericFieldHitCount"] == 2
    assert report["summary"]["duplicatedDescriptionValueCount"] == 1
    assert report["summary"]["duplicateDescriptionRecordCount"] == 2
    assert report["summary"]["badLookingRecordCount"] == 4
    assert report["genericFieldExamples"][0]["identity"] == "github.com/example/forum"


def test_dashboard_gate_fails_when_bad_looking_records_regress(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_profile(
        public_root,
        "example",
        "low",
        name="low",
        purpose="A real-looking but low confidence project.",
        confidence="low",
    )

    report = quality.summarize(
        public_root,
        max_items=10,
        thresholds={
            "minProfiles": 1,
            "maxGenericFieldHits": 0,
            "maxDuplicatedDescriptionValues": 0,
            "maxDuplicateDescriptionRecords": 0,
            "maxBadLookingRecords": 0,
        },
    )

    assert report["passed"] is False
    assert report["gates"]["maxBadLookingRecords"]["actual"] == 1
