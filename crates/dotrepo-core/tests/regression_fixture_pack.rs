//! Runnable regression fixture pack.
//!
//! Each checked-in directory under `tests/fixtures/regression/<slug>/` holds the
//! minimal source material that reproduces a recurring autonomous crawl failure,
//! plus an `expectation.json` that pins the deterministic import behavior the fix
//! is meant to preserve. This test discovers those fixtures and replays the
//! offline overlay import pipeline against them — the same parser path the
//! autonomous crawler uses — so recurring parser/evidence defects are guarded in
//! `cargo test` with no network access.
//!
//! This is the "runnable" half of the regression-fixture conveyor:
//! telemetry stub -> `scripts/materialize_regression_fixture.py` capture ->
//! checked-in fixture here -> this harness. See
//! `docs/factual-crawl-automation.md` and `ROADMAP.md` (Milestone 1 execution
//! order) for the surrounding design.

use dotrepo_core::{import_repository, ImportMode, ImportPlan};
use dotrepo_schema::RecordStatus;
use serde::Deserialize;
use std::fs;
use std::path::PathBuf;

/// Ecosystems the telemetry classifier can emit. A checked-in regression
/// fixture's declared ecosystem must match one of these so capture typos fail
/// loudly instead of silently guarding the wrong parser.
const KNOWN_ECOSYSTEMS: &[&str] = &[
    "rust", "node", "python", "go", "jvm", "ruby", "php", "dotnet", "elixir", "erlang", "cpp",
    "unknown",
];

#[derive(Debug, Default, Deserialize)]
struct RegressionExpectation {
    fixture: String,
    /// Deterministic ecosystem classification (rust/node/python/go/...).
    #[serde(default)]
    ecosystem: Option<String>,
    #[serde(default)]
    repo_name: Option<String>,
    #[serde(default)]
    repo_description: Option<String>,
    #[serde(default)]
    repo_build: Option<String>,
    #[serde(default)]
    repo_test: Option<String>,
    #[serde(default)]
    docs_root: Option<String>,
    #[serde(default)]
    docs_getting_started: Option<String>,
    #[serde(default)]
    imported_sources: Option<Vec<String>>,
    #[serde(default)]
    inferred_fields: Option<Vec<String>>,
    #[serde(default)]
    maintainers: Option<Vec<String>>,
    #[serde(default)]
    team: Option<String>,
    #[serde(default)]
    security_contact: Option<String>,
    #[serde(default)]
    overlay_status: Option<String>,
    #[serde(default)]
    trust_provenance: Option<Vec<String>>,
}

fn regression_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures")
        .join("regression")
}

fn discover_fixtures() -> Vec<PathBuf> {
    let root = regression_root();
    if !root.is_dir() {
        return Vec::new();
    }
    let mut found = Vec::new();
    for entry in fs::read_dir(&root).expect("regression fixture root is readable") {
        let entry = entry.expect("regression fixture entry is readable");
        let expectation = entry.path().join("expectation.json");
        if expectation.is_file() {
            found.push(expectation);
        }
    }
    found.sort();
    found
}

fn status_name(status: &RecordStatus) -> &'static str {
    match status {
        RecordStatus::Draft => "draft",
        RecordStatus::Imported => "imported",
        RecordStatus::Inferred => "inferred",
        RecordStatus::Reviewed => "reviewed",
        RecordStatus::Verified => "verified",
        RecordStatus::Canonical => "canonical",
    }
}

fn load_expectation(path: &PathBuf) -> RegressionExpectation {
    let contents = fs::read_to_string(path).expect("expectation file is readable");
    let expectation: RegressionExpectation =
        serde_json::from_str(&contents).expect("expectation parses");
    assert!(
        !expectation.fixture.trim().is_empty(),
        "regression expectation at {} must set `fixture`",
        path.display()
    );
    expectation
}

fn assert_plan_matches(plan: &ImportPlan, expectation: &RegressionExpectation) {
    if let Some(expected) = expectation.repo_name.as_deref() {
        assert_eq!(plan.manifest.repo.name, expected, "repo.name");
    }
    if let Some(expected) = expectation.repo_description.as_deref() {
        assert_eq!(plan.manifest.repo.description, expected, "repo.description");
    }
    if let Some(expected) = expectation.repo_build.as_deref() {
        assert_eq!(
            plan.manifest.repo.build.as_deref(),
            Some(expected),
            "repo.build"
        );
    }
    if let Some(expected) = expectation.repo_test.as_deref() {
        assert_eq!(
            plan.manifest.repo.test.as_deref(),
            Some(expected),
            "repo.test"
        );
    }
    if let Some(expected) = expectation.docs_root.as_deref() {
        let actual = plan
            .manifest
            .docs
            .as_ref()
            .and_then(|docs| docs.root.as_deref());
        assert_eq!(actual, Some(expected), "docs.root");
    }
    if let Some(expected) = expectation.docs_getting_started.as_deref() {
        let actual = plan
            .manifest
            .docs
            .as_ref()
            .and_then(|docs| docs.getting_started.as_deref());
        assert_eq!(actual, Some(expected), "docs.getting_started");
    }
    if let Some(expected) = expectation.imported_sources.as_deref() {
        assert_eq!(
            plan.imported_sources.as_slice(),
            expected,
            "imported_sources"
        );
    }
    if let Some(expected) = expectation.inferred_fields.as_deref() {
        assert_eq!(plan.inferred_fields.as_slice(), expected, "inferred_fields");
    }
    let owners = plan.manifest.owners.as_ref();
    if let Some(expected) = expectation.maintainers.as_deref() {
        let actual = owners
            .map(|owners| owners.maintainers.as_slice())
            .unwrap_or(&[]);
        assert_eq!(actual, expected, "owners.maintainers");
    }
    if let Some(expected) = expectation.team.as_deref() {
        assert_eq!(
            owners.and_then(|owners| owners.team.as_deref()),
            Some(expected),
            "owners.team"
        );
    }
    if let Some(expected) = expectation.security_contact.as_deref() {
        assert_eq!(
            owners.and_then(|owners| owners.security_contact.as_deref()),
            Some(expected),
            "owners.security_contact"
        );
    }
    if let Some(expected) = expectation.trust_provenance.as_deref() {
        let trust = plan
            .manifest
            .record
            .trust
            .as_ref()
            .expect("trust metadata present");
        assert_eq!(trust.provenance.as_slice(), expected, "trust.provenance");
    }
}

#[test]
fn regression_fixture_pack_replays_checked_in_fixtures() {
    let fixtures = discover_fixtures();
    // No fixtures yet is a valid state: the harness no-ops and stays green as the
    // checked-in set grows.
    if fixtures.is_empty() {
        return;
    }

    for expectation_path in fixtures {
        let expectation = load_expectation(&expectation_path);
        let root = expectation_path
            .parent()
            .expect("expectation has a parent fixture directory");
        assert_eq!(
            root.file_name().and_then(|name| name.to_str()),
            Some(expectation.fixture.as_str()),
            "regression fixture directory must match its `fixture` slug: {}",
            expectation_path.display()
        );
        if let Some(ecosystem) = expectation.ecosystem.as_deref() {
            assert!(
                KNOWN_ECOSYSTEMS.contains(&ecosystem),
                "regression fixture `{}` declares unknown ecosystem `{}`",
                expectation.fixture,
                ecosystem
            );
        }
        let overlay_source = format!("https://example.com/regression/{}", expectation.fixture);

        // Replay the overlay import path the autonomous crawler uses. The parser
        // (name, description, build, test, owners, security, docs) is mode-
        // independent; overlay is the conveyor's actual import mode and avoids
        // native-only local-path validation that does not apply to overlays.
        let overlay = import_repository(root, ImportMode::Overlay, Some(&overlay_source))
            .expect("overlay import succeeds");
        assert_plan_matches(&overlay, &expectation);
        if let Some(expected) = expectation.overlay_status.as_deref() {
            assert_eq!(
                status_name(&overlay.manifest.record.status),
                expected,
                "overlay status for {}",
                expectation.fixture
            );
        }
    }
}
