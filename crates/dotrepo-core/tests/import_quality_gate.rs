use dotrepo_core::{import_repository, ImportMode, ImportPlan};
use dotrepo_schema::RecordStatus;
use serde::Deserialize;
use std::fs;
use std::path::PathBuf;

#[derive(Debug, Deserialize)]
struct FixtureExpectation {
    fixture: String,
    repo_name: String,
    repo_description: String,
    #[serde(default)]
    repo_build: Option<String>,
    #[serde(default)]
    repo_test: Option<String>,
    #[serde(default)]
    docs_root: Option<String>,
    #[serde(default)]
    docs_getting_started: Option<String>,
    imported_sources: Vec<String>,
    inferred_fields: Vec<String>,
    maintainers: Vec<String>,
    team: Option<String>,
    security_contact: Option<String>,
    native_status: String,
    overlay_status: String,
    trust_provenance: Vec<String>,
    native_trust_note_contains: Vec<String>,
    overlay_trust_note_contains: Vec<String>,
    overlay_evidence_contains: Vec<String>,
}

fn fixture_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures")
        .join("import")
}

fn expectations() -> Vec<FixtureExpectation> {
    let path = fixture_root().join("expectations.json");
    let contents = fs::read_to_string(path).expect("expectations file exists");
    serde_json::from_str(&contents).expect("expectations parse")
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

fn assert_common_plan_fields(plan: &ImportPlan, expectation: &FixtureExpectation) {
    assert_eq!(plan.manifest.repo.name, expectation.repo_name);
    assert_eq!(plan.manifest.repo.description, expectation.repo_description);
    assert_eq!(
        plan.manifest.repo.build.as_deref(),
        expectation.repo_build.as_deref()
    );
    assert_eq!(
        plan.manifest.repo.test.as_deref(),
        expectation.repo_test.as_deref()
    );
    assert_eq!(
        plan.manifest
            .docs
            .as_ref()
            .and_then(|docs| docs.root.as_deref()),
        expectation.docs_root.as_deref()
    );
    assert_eq!(
        plan.manifest
            .docs
            .as_ref()
            .and_then(|docs| docs.getting_started.as_deref()),
        expectation.docs_getting_started.as_deref()
    );
    assert_eq!(plan.imported_sources, expectation.imported_sources);
    assert_eq!(plan.inferred_fields, expectation.inferred_fields);

    let owners = plan.manifest.owners.as_ref();
    assert_eq!(
        owners
            .map(|owners| owners.maintainers.clone())
            .unwrap_or_default(),
        expectation.maintainers
    );
    assert_eq!(
        owners.and_then(|owners| owners.team.as_deref()),
        expectation.team.as_deref()
    );
    assert_eq!(
        owners.and_then(|owners| owners.security_contact.as_deref()),
        expectation.security_contact.as_deref()
    );

    let trust = plan.manifest.record.trust.as_ref().expect("trust metadata");
    assert_eq!(trust.provenance, expectation.trust_provenance);
}

fn assert_note_contains(note: &str, expected_substrings: &[String]) {
    for expected in expected_substrings {
        assert!(
            note.contains(expected),
            "expected note to contain `{}` but got:\n{}",
            expected,
            note
        );
    }
}

#[test]
fn import_quality_gate_matches_checked_in_expectations() {
    for expectation in expectations() {
        let root = fixture_root().join(&expectation.fixture);
        let overlay_source = format!("https://example.com/fixtures/{}", expectation.fixture);

        let native =
            import_repository(&root, ImportMode::Native, None).expect("native import succeeds");
        assert_common_plan_fields(&native, &expectation);
        assert_eq!(
            status_name(&native.manifest.record.status),
            expectation.native_status
        );
        let native_note = native
            .manifest
            .record
            .trust
            .as_ref()
            .and_then(|trust| trust.notes.as_deref())
            .expect("native trust notes");
        assert_note_contains(native_note, &expectation.native_trust_note_contains);

        let overlay = import_repository(&root, ImportMode::Overlay, Some(&overlay_source))
            .expect("overlay import succeeds");
        assert_common_plan_fields(&overlay, &expectation);
        assert_eq!(
            status_name(&overlay.manifest.record.status),
            expectation.overlay_status
        );
        let overlay_note = overlay
            .manifest
            .record
            .trust
            .as_ref()
            .and_then(|trust| trust.notes.as_deref())
            .expect("overlay trust notes");
        assert_note_contains(overlay_note, &expectation.overlay_trust_note_contains);

        let evidence = overlay.evidence_text.as_deref().expect("overlay evidence");
        assert!(evidence.starts_with("# Evidence\n\n"));
        assert_note_contains(evidence, &expectation.overlay_evidence_contains);
    }
}
