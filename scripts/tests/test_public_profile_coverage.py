import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "check_public_profile_coverage.py"
SPEC = importlib.util.spec_from_file_location("check_public_profile_coverage", SCRIPT)
coverage = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(coverage)


def write_profile(
    root: Path,
    owner: str,
    repo: str,
    *,
    status: str = "verified",
    confidence: str = "high",
    has_build: bool = True,
    has_test: bool = True,
    has_docs: bool = True,
    has_security: bool = True,
    has_ownership: bool = True,
    has_license: bool = True,
    conflict_count: int = 0,
) -> None:
    profile_dir = root / "v0" / "repos" / "github.com" / owner / repo
    profile_dir.mkdir(parents=True)
    profile = {
        "apiVersion": "v0",
        "freshness": {
            "generatedAt": "2026-06-28T00:00:00Z",
            "snapshotDigest": "a" * 64,
        },
        "identity": {
            "host": "github.com",
            "owner": owner,
            "repo": repo,
            "source": f"https://github.com/{owner}/{repo}",
        },
        "record": {
            "manifestPath": f"repos/github.com/{owner}/{repo}/record.toml",
            "mode": "overlay",
        },
        "purpose": f"{repo} purpose",
        "name": repo,
        "execution": {},
        "docs": {},
        "ownership": {},
        "completeness": {
            "hasBuild": has_build,
            "hasTest": has_test,
            "hasDocs": has_docs,
            "hasSecurityContact": has_security,
            "hasOwnershipSignal": has_ownership,
            "hasLicense": has_license,
            "conflictCount": conflict_count,
        },
        "trust": {
            "selectedStatus": status,
            "confidence": confidence,
            "selectionReason": "only_matching_record",
        },
        "conflicts": [],
        "links": {
            "self": f"/v0/repos/github.com/{owner}/{repo}/profile.json",
            "repository": f"/v0/repos/github.com/{owner}/{repo}/index.json",
            "trust": f"/v0/repos/github.com/{owner}/{repo}/trust.json",
            "queryTemplate": f"/v0/repos/github.com/{owner}/{repo}/query?path={{dot_path}}",
            "indexPath": f"repos/github.com/{owner}/{repo}/",
        },
    }
    (profile_dir / "profile.json").write_text(json.dumps(profile, indent=2) + "\n")


def test_summarize_reports_profile_and_high_signal_counts(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_profile(public_root, "example", "alpha")
    write_profile(
        public_root,
        "example",
        "beta",
        status="inferred",
        confidence="medium",
        has_build=False,
        has_test=False,
    )

    report = coverage.summarize(public_root, min_profiles=2, min_high_signal=1, max_items=10)

    assert report["schema"] == "dotrepo-public-profile-coverage/v0"
    assert report["summary"]["profileCount"] == 2
    assert report["summary"]["discoveredProfileCount"] == 2
    assert report["summary"]["malformedProfileCount"] == 0
    assert report["summary"]["highSignalProfileCount"] == 1
    assert report["summary"]["highSignalRatio"] == 0.5
    assert report["summary"]["conflictProfileCount"] == 0
    assert report["summary"]["conflictRate"] == 0.0
    assert report["summary"]["totalConflictCount"] == 0
    assert report["gates"]["minProfiles"]["passed"] is True
    assert report["gates"]["minHighSignal"]["passed"] is True
    assert report["gates"]["minHighSignalRatio"]["actual"] == 0.5
    assert report["gates"]["minHighSignalRatio"]["passed"] is True
    assert report["gates"]["maxConflictRate"] == {
        "threshold": 1.0,
        "actual": 0.0,
        "passed": True,
    }
    assert report["summary"]["signalCounts"]["hasBuild"] == 1
    assert report["summary"]["signalCounts"]["hasPurpose"] == 2
    assert report["gates"]["minSignal"] == {}
    assert report["gates"]["maxMissingSignal"] == {}
    assert report["gates"]["maxMalformedProfiles"]["passed"] is True
    assert report["lowerSignalProfiles"][0]["identity"] == "github.com/example/beta"
    assert "hasBuild" in report["lowerSignalProfiles"][0]["missingSignals"]


def test_gate_failure_sets_passed_false(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_profile(public_root, "example", "alpha")

    report = coverage.summarize(public_root, min_profiles=2, min_high_signal=2, max_items=10)

    assert report["passed"] is False
    assert report["gates"]["minProfiles"]["actual"] == 1
    assert report["gates"]["minHighSignal"]["actual"] == 1


def test_high_signal_ratio_gate_failure_sets_passed_false(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_profile(public_root, "example", "alpha")
    write_profile(public_root, "example", "beta", status="imported")

    report = coverage.summarize(
        public_root,
        min_profiles=2,
        min_high_signal=1,
        max_items=10,
        min_high_signal_ratio=0.75,
    )

    assert report["passed"] is False
    assert report["gates"]["minHighSignalRatio"] == {
        "threshold": 0.75,
        "actual": 0.5,
        "passed": False,
    }


def test_conflict_rate_gate_failure_sets_passed_false(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_profile(public_root, "example", "alpha")
    write_profile(public_root, "example", "beta", conflict_count=2)

    report = coverage.summarize(
        public_root,
        min_profiles=2,
        min_high_signal=1,
        max_items=10,
        max_conflict_rate=0.25,
    )

    assert report["passed"] is False
    assert report["summary"]["conflictProfileCount"] == 1
    assert report["summary"]["conflictRate"] == 0.5
    assert report["summary"]["totalConflictCount"] == 2
    assert report["gates"]["maxConflictRate"] == {
        "threshold": 0.25,
        "actual": 0.5,
        "passed": False,
    }
    assert report["conflictProfiles"][0]["identity"] == "github.com/example/beta"


def test_missing_signal_gate_failure_sets_passed_false(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_profile(public_root, "example", "alpha")
    write_profile(public_root, "example", "beta", has_security=False)

    report = coverage.summarize(
        public_root,
        min_profiles=2,
        min_high_signal=1,
        max_items=10,
        max_missing_signal={"hasSecurityContact": 0, "hasLicense": 0},
    )

    assert report["passed"] is False
    assert report["gates"]["maxMissingSignal"] == {
        "hasLicense": {"threshold": 0, "actual": 0, "passed": True},
        "hasSecurityContact": {"threshold": 0, "actual": 1, "passed": False},
    }


def test_min_signal_gate_failure_sets_passed_false(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_profile(public_root, "example", "alpha")
    write_profile(public_root, "example", "beta", has_build=False)

    report = coverage.summarize(
        public_root,
        min_profiles=2,
        min_high_signal=1,
        max_items=10,
        min_signal={"hasBuild": 2, "hasLicense": 2},
    )

    assert report["passed"] is False
    assert report["summary"]["signalCounts"]["hasBuild"] == 1
    assert report["summary"]["signalCounts"]["hasLicense"] == 2
    assert report["gates"]["minSignal"] == {
        "hasBuild": {"threshold": 2, "actual": 1, "passed": False},
        "hasLicense": {"threshold": 2, "actual": 2, "passed": True},
    }


def test_parse_max_missing_signal_accepts_repeated_limits() -> None:
    assert coverage.parse_max_missing_signal(
        ["hasBuild=2", "hasSecurityContact=0"]
    ) == {
        "hasBuild": 2,
        "hasSecurityContact": 0,
    }


def test_parse_min_signal_accepts_repeated_limits() -> None:
    assert coverage.parse_min_signal(["hasBuild=2", "hasDocs=10"]) == {
        "hasBuild": 2,
        "hasDocs": 10,
    }


def test_render_markdown_lists_lower_signal_profiles(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_profile(public_root, "example", "alpha")
    write_profile(
        public_root,
        "example",
        "beta",
        status="imported",
        confidence="low",
        has_license=False,
    )

    markdown = coverage.render_markdown(
        coverage.summarize(public_root, min_profiles=1, min_high_signal=1, max_items=10)
    )

    assert "# dotrepo public profile coverage" in markdown
    assert "| Profiles | 2 |" in markdown
    assert "| Min high-signal ratio gate | 0.5 / 0.0 |" in markdown
    assert "| Max conflict rate gate | 0.0 / 1.0 |" in markdown
    assert "`github.com/example/beta`" in markdown


def test_render_markdown_lists_conflict_profiles(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_profile(public_root, "example", "alpha")
    write_profile(public_root, "example", "beta", conflict_count=3)

    markdown = coverage.render_markdown(
        coverage.summarize(
            public_root,
            min_profiles=1,
            min_high_signal=1,
            max_items=10,
            max_conflict_rate=0.0,
        )
    )

    assert "| Conflict-bearing profiles | 1 |" in markdown
    assert "| Conflict rate | 0.5 |" in markdown
    assert "## Conflict-Bearing Profiles" in markdown
    assert "`github.com/example/beta`: 3 selected-record conflicts" in markdown


def test_render_markdown_lists_missing_signal_gates(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_profile(public_root, "example", "alpha")
    write_profile(public_root, "example", "beta", has_security=False)

    markdown = coverage.render_markdown(
        coverage.summarize(
            public_root,
            min_profiles=1,
            min_high_signal=1,
            max_items=10,
            max_missing_signal={"hasSecurityContact": 0},
        )
    )

    assert "## Missing-Signal Gates" in markdown
    assert "- `hasSecurityContact`: 1 / 0 (fail)" in markdown


def test_render_markdown_lists_min_signal_gates(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_profile(public_root, "example", "alpha")
    write_profile(public_root, "example", "beta", has_docs=False)

    markdown = coverage.render_markdown(
        coverage.summarize(
            public_root,
            min_profiles=1,
            min_high_signal=1,
            max_items=10,
            min_signal={"hasDocs": 2},
        )
    )

    assert "## Signal Minimum Gates" in markdown
    assert "- `hasDocs`: 1 / 2 (fail)" in markdown


def test_malformed_profiles_do_not_satisfy_coverage_counts(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_profile(public_root, "example", "valid")
    write_profile(public_root, "example", "wrong-path")
    malformed_path = (
        public_root
        / "v0/repos/github.com/example/wrong-path/profile.json"
    )
    malformed = json.loads(malformed_path.read_text())
    malformed["identity"]["repo"] = "different"
    malformed_path.write_text(json.dumps(malformed))

    report = coverage.summarize(
        public_root,
        min_profiles=2,
        min_high_signal=2,
        max_items=10,
    )

    assert report["passed"] is False
    assert report["summary"]["discoveredProfileCount"] == 2
    assert report["summary"]["profileCount"] == 1
    assert report["summary"]["malformedProfileCount"] == 1
    assert report["gates"]["minProfiles"]["actual"] == 1
    assert report["gates"]["maxMalformedProfiles"] == {
        "threshold": 0,
        "actual": 1,
        "passed": False,
    }
    assert "identity does not match profile path" in report["malformedProfiles"][0][
        "contractErrors"
    ][0]


def test_invalid_json_profile_is_reported_without_aborting_audit(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    write_profile(public_root, "example", "valid")
    invalid_path = public_root / "v0/repos/github.com/example/invalid/profile.json"
    invalid_path.parent.mkdir(parents=True)
    invalid_path.write_text("{not-json")

    report = coverage.summarize(
        public_root,
        min_profiles=1,
        min_high_signal=1,
        max_items=10,
        max_malformed_profiles=1,
    )

    assert report["passed"] is True
    assert report["summary"]["profileCount"] == 1
    assert report["summary"]["malformedProfileCount"] == 1
    assert report["malformedProfiles"][0]["contractErrors"][0].startswith(
        "invalid JSON:"
    )
