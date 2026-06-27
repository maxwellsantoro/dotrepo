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
        "identity": {
            "host": "github.com",
            "owner": owner,
            "repo": repo,
            "source": f"https://github.com/{owner}/{repo}",
        },
        "purpose": f"{repo} purpose",
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
    assert report["summary"]["highSignalProfileCount"] == 1
    assert report["summary"]["highSignalRatio"] == 0.5
    assert report["gates"]["minProfiles"]["passed"] is True
    assert report["gates"]["minHighSignal"]["passed"] is True
    assert report["gates"]["minHighSignalRatio"]["actual"] == 0.5
    assert report["gates"]["minHighSignalRatio"]["passed"] is True
    assert report["summary"]["signalCounts"]["hasBuild"] == 1
    assert report["summary"]["signalCounts"]["hasPurpose"] == 2
    assert report["gates"]["minSignal"] == {}
    assert report["gates"]["maxMissingSignal"] == {}
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
    assert "`github.com/example/beta`" in markdown


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
