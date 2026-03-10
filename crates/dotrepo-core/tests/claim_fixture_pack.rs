use dotrepo_core::{
    inspect_claim_directory, load_claim_directory, validate_index_root, ClaimHandoffOutcome,
};
use serde::Deserialize;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Deserialize)]
struct ClaimFixtureExpectation {
    fixture: String,
    claim_id: String,
    state: String,
    event_count: usize,
    handoff: String,
    valid_index: bool,
}

fn fixture_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures")
        .join("claims")
}

fn expectations() -> Vec<ClaimFixtureExpectation> {
    let path = fixture_root().join("expectations.json");
    let contents = fs::read_to_string(path).expect("expectations file exists");
    serde_json::from_str(&contents).expect("expectations parse")
}

fn claim_dir(case_root: &Path, claim_id: &str) -> PathBuf {
    case_root
        .join("repos")
        .join("github.com")
        .join("acme")
        .join("widget")
        .join("claims")
        .join(claim_id)
}

fn handoff_name(handoff: ClaimHandoffOutcome) -> &'static str {
    match handoff {
        ClaimHandoffOutcome::PendingCanonical => "pending_canonical",
        ClaimHandoffOutcome::Superseded => "superseded",
        ClaimHandoffOutcome::Parallel => "parallel",
        ClaimHandoffOutcome::Rejected => "rejected",
        ClaimHandoffOutcome::Withdrawn => "withdrawn",
        ClaimHandoffOutcome::Disputed => "disputed",
    }
}

#[test]
fn claim_fixture_pack_loads_representative_claim_histories() {
    for expectation in expectations() {
        let root = fixture_root().join(&expectation.fixture);
        let loaded = load_claim_directory(&root, &claim_dir(&root, &expectation.claim_id))
            .expect("claim fixture loads");
        assert_eq!(
            format!("{:?}", loaded.claim.claim.state).to_lowercase(),
            expectation.state,
            "unexpected state for {}",
            expectation.fixture
        );
        assert_eq!(
            loaded.events.len(),
            expectation.event_count,
            "unexpected event count for {}",
            expectation.fixture
        );
    }
}

#[test]
fn claim_fixture_pack_builds_read_only_claim_reports() {
    for expectation in expectations() {
        let root = fixture_root().join(&expectation.fixture);
        let report = inspect_claim_directory(&root, &claim_dir(&root, &expectation.claim_id))
            .expect("claim inspection report builds");
        assert_eq!(
            format!("{:?}", report.state).to_lowercase(),
            expectation.state,
            "unexpected report state for {}",
            expectation.fixture
        );
        assert_eq!(
            report.events.len(),
            expectation.event_count,
            "unexpected report event count for {}",
            expectation.fixture
        );
        assert_eq!(
            report
                .target
                .handoff
                .map(handoff_name)
                .expect("handoff outcome"),
            expectation.handoff,
            "unexpected derived handoff for {}",
            expectation.fixture
        );
    }
}

#[test]
fn claim_fixture_pack_matches_validation_expectations() {
    for expectation in expectations() {
        let root = fixture_root().join(&expectation.fixture);
        let findings = validate_index_root(&root).expect("fixture index validates");
        let has_errors = findings.iter().any(|finding| matches!(finding.severity, dotrepo_core::IndexFindingSeverity::Error));
        assert_eq!(
            !has_errors,
            expectation.valid_index,
            "unexpected validation result for {}: {findings:#?}",
            expectation.fixture
        );
    }
}
