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

use dotrepo_core::{import_repository, parse_rfc3339, ImportMode, ImportPlan};
use dotrepo_schema::RecordStatus;
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::collections::{BTreeSet, HashMap};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

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
    #[serde(default)]
    origin: Option<String>,
    #[serde(default)]
    fingerprint: Option<String>,
    #[serde(default)]
    captured_at: Option<String>,
    #[serde(default)]
    captured_files: Option<Vec<String>>,
    #[serde(default)]
    captured_file_sha256: Option<HashMap<String, String>>,
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

fn assert_metadata_matches(expectation: &RegressionExpectation, root: &std::path::Path) {
    if let Some(origin) = expectation.origin.as_deref() {
        let parts: Vec<_> = origin.split('/').collect();
        assert_eq!(
            parts.len(),
            3,
            "regression fixture `{}` origin must be host/owner/repo",
            expectation.fixture
        );
        assert!(
            parts.iter().all(|part| !part.trim().is_empty()),
            "regression fixture `{}` origin must not contain empty identity segments",
            expectation.fixture
        );
    }
    if let Some(fingerprint) = expectation.fingerprint.as_deref() {
        assert!(
            !fingerprint.trim().is_empty(),
            "regression fixture `{}` fingerprint must not be empty",
            expectation.fixture
        );
    }
    if let Some(captured_at) = expectation.captured_at.as_deref() {
        parse_rfc3339("captured_at", captured_at).unwrap_or_else(|err| {
            panic!(
                "regression fixture `{}` captured_at must be an RFC3339 timestamp: {}",
                expectation.fixture, err
            )
        });
    }
    if let Some(captured_files) = expectation.captured_files.as_deref() {
        assert!(
            !captured_files.is_empty(),
            "regression fixture `{}` captured_files must not be empty",
            expectation.fixture
        );
        for captured_file in captured_files {
            let path = std::path::Path::new(captured_file);
            assert!(
                !path.is_absolute()
                    && !path
                        .components()
                        .any(|component| matches!(component, std::path::Component::ParentDir)),
                "regression fixture `{}` captured_files contains unsafe path `{}`",
                expectation.fixture,
                captured_file
            );
            assert!(
                root.join(path).is_file(),
                "regression fixture `{}` captured file `{}` must exist",
                expectation.fixture,
                captured_file
            );
        }
    }
    if let Some(captured_file_sha256) = expectation.captured_file_sha256.as_ref() {
        let captured_files = expectation
            .captured_files
            .as_deref()
            .expect("captured_file_sha256 requires captured_files");
        assert_eq!(
            captured_file_sha256.len(),
            captured_files.len(),
            "regression fixture `{}` captured_file_sha256 must cover every captured file exactly once",
            expectation.fixture
        );
        for captured_file in captured_files {
            let expected = captured_file_sha256.get(captured_file).unwrap_or_else(|| {
                panic!(
                    "regression fixture `{}` is missing a digest for captured file `{}`",
                    expectation.fixture, captured_file
                )
            });
            assert!(
                expected.len() == 64 && expected.chars().all(|ch| ch.is_ascii_hexdigit()),
                "regression fixture `{}` captured file `{}` has invalid SHA-256 `{}`",
                expectation.fixture,
                captured_file,
                expected
            );
            let bytes = fs::read(root.join(captured_file)).unwrap_or_else(|err| {
                panic!(
                    "regression fixture `{}` captured file `{}` is unreadable: {}",
                    expectation.fixture, captured_file, err
                )
            });
            let actual = format!("{:x}", Sha256::digest(bytes));
            assert_eq!(
                actual, *expected,
                "regression fixture `{}` captured file `{}` digest",
                expectation.fixture, captured_file
            );
        }
    }
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
    assert!(
        !fixtures.is_empty(),
        "regression fixture pack must not be empty"
    );
    let mut covered_ecosystems = BTreeSet::new();

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
            covered_ecosystems.insert(ecosystem.to_string());
        }
        assert_metadata_matches(&expectation, root);
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

    let missing = KNOWN_ECOSYSTEMS
        .iter()
        .copied()
        .filter(|ecosystem| *ecosystem != "unknown")
        .filter(|ecosystem| !covered_ecosystems.contains(*ecosystem))
        .collect::<Vec<_>>();
    assert!(
        missing.is_empty(),
        "regression fixture pack must cover every named ecosystem; missing: {}",
        missing.join(", ")
    );
}

fn regression_stub_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("index")
        .join("telemetry")
        .join("regression-fixture-stubs")
}

fn discover_regression_stubs(root: &Path) -> Vec<PathBuf> {
    if !root.is_dir() {
        return Vec::new();
    }
    let mut found = Vec::new();
    for entry in fs::read_dir(root).expect("regression stub root is readable") {
        let entry = entry.expect("regression stub entry is readable");
        let metadata = entry.path().join("metadata.json");
        if metadata.is_file() {
            found.push(entry.path());
        }
    }
    found.sort();
    found
}

#[test]
fn regression_fixture_stubs_materialize_cleanly() {
    let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..");
    let stubs_root = regression_stub_root();
    let stubs = discover_regression_stubs(&stubs_root);
    if stubs.is_empty() {
        return;
    }

    for stub in stubs {
        let output = Command::new("uv")
            .current_dir(&repo_root)
            .args([
                "run",
                "python",
                "scripts/materialize_regression_fixture.py",
                "--stub",
            ])
            .arg(&stub)
            .arg("--dry-run")
            .output()
            .unwrap_or_else(|err| {
                panic!(
                    "failed to invoke materialize_regression_fixture.py for {}: {err}",
                    stub.display()
                )
            });
        assert!(
            output.status.success(),
            "regression stub {} failed dry-run materialization:\nstdout: {}\nstderr: {}",
            stub.display(),
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        );
    }
}
