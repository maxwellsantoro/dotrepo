use dotrepo_core::{
    append_claim_event, inspect_claim_directory, load_claim_directory, scaffold_claim_directory,
    validate_index_root, ClaimEventAppendInput, ClaimEventKind, ClaimHandoffOutcome,
    ClaimScaffoldInput, ClaimState,
};
use serde::Deserialize;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

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

fn temp_root(label: &str) -> PathBuf {
    let unique = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("clock works")
        .as_nanos();
    let path = std::env::temp_dir().join(format!(
        "dotrepo-claim-workflow-{}-{}-{}",
        label,
        std::process::id(),
        unique
    ));
    fs::create_dir_all(&path).expect("temp dir created");
    path
}

fn copy_seed_repo(fixture: &str, dest_root: &Path) {
    let source_repo = fixture_root()
        .join(fixture)
        .join("repos")
        .join("github.com")
        .join("acme")
        .join("widget");
    let dest_repo = dest_root
        .join("repos")
        .join("github.com")
        .join("acme")
        .join("widget");
    fs::create_dir_all(&dest_repo).expect("dest repo dir created");
    fs::copy(source_repo.join("record.toml"), dest_repo.join("record.toml"))
        .expect("record copied");
    fs::copy(source_repo.join("evidence.md"), dest_repo.join("evidence.md"))
        .expect("evidence copied");
}

fn write_scaffold(plan: &dotrepo_core::ClaimScaffoldPlan) {
    fs::create_dir_all(plan.claim_dir.join("events")).expect("events dir created");
    fs::write(&plan.claim_path, &plan.claim_text).expect("claim scaffold written");
    if let (Some(path), Some(contents)) = (&plan.review_path, &plan.review_text) {
        fs::write(path, contents).expect("review scaffold written");
    }
}

fn write_event(plan: &dotrepo_core::ClaimEventAppendPlan) {
    fs::write(&plan.event_path, &plan.event_text).expect("event written");
    fs::write(&plan.claim_path, &plan.claim_text).expect("claim updated");
}

fn read(path: &Path) -> String {
    fs::read_to_string(path).expect("file exists")
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

#[test]
fn reviewer_workflow_helpers_match_golden_claim_fixtures() {
    let pending_root = temp_root("pending-canonical");
    copy_seed_repo("pending-canonical", &pending_root);
    let pending_scaffold = scaffold_claim_directory(
        &pending_root,
        &ClaimScaffoldInput {
            host: "github.com".into(),
            owner: "acme".into(),
            repo: "widget".into(),
            claim_id: "2026-03-11-maintainer-claim-01".into(),
            claimant_display_name: "Acme maintainers".into(),
            asserted_role: "maintainer".into(),
            contact: None,
            record_sources: vec!["https://github.com/acme/widget".into()],
            canonical_repo_url: Some("https://github.com/acme/widget".into()),
            create_review_md: false,
            timestamp: "2026-03-11T10:00:00Z".into(),
        },
    )
    .expect("pending scaffold");
    write_scaffold(&pending_scaffold);
    write_event(
        &append_claim_event(
            &pending_root,
            &pending_scaffold.claim_dir,
            &ClaimEventAppendInput {
                kind: ClaimEventKind::Submitted,
                actor: "claimant".into(),
                summary: "Submitted maintainer claim.".into(),
                timestamp: "2026-03-11T10:00:00Z".into(),
                corrected_state: None,
                canonical_record_path: None,
                canonical_mirror_path: None,
            },
        )
        .expect("pending submitted"),
    );
    write_event(
        &append_claim_event(
            &pending_root,
            &pending_scaffold.claim_dir,
            &ClaimEventAppendInput {
                kind: ClaimEventKind::Accepted,
                actor: "index-reviewer".into(),
                summary: "Accepted claim pending canonical publication.".into(),
                timestamp: "2026-03-11T10:30:00Z".into(),
                corrected_state: None,
                canonical_record_path: None,
                canonical_mirror_path: None,
            },
        )
        .expect("pending accepted"),
    );
    let pending_expected = fixture_root()
        .join("pending-canonical")
        .join("repos/github.com/acme/widget/claims/2026-03-11-maintainer-claim-01");
    let pending_actual =
        pending_root.join("repos/github.com/acme/widget/claims/2026-03-11-maintainer-claim-01");
    assert_eq!(
        read(&pending_actual.join("claim.toml")),
        read(&pending_expected.join("claim.toml"))
    );
    assert_eq!(
        read(&pending_actual.join("events/0001-submitted.toml")),
        read(&pending_expected.join("events/0001-submitted.toml"))
    );
    assert_eq!(
        read(&pending_actual.join("events/0002-accepted.toml")),
        read(&pending_expected.join("events/0002-accepted.toml"))
    );
    fs::remove_dir_all(&pending_root).expect("temp dir removed");

    let accepted_root = temp_root("accepted-clean");
    copy_seed_repo("accepted-clean", &accepted_root);
    let accepted_scaffold = scaffold_claim_directory(
        &accepted_root,
        &ClaimScaffoldInput {
            host: "github.com".into(),
            owner: "acme".into(),
            repo: "widget".into(),
            claim_id: "2026-03-10-maintainer-claim-01".into(),
            claimant_display_name: "Acme maintainers".into(),
            asserted_role: "maintainer".into(),
            contact: Some("maintainers@acme.dev".into()),
            record_sources: vec!["https://github.com/acme/widget".into()],
            canonical_repo_url: Some("https://github.com/acme/widget".into()),
            create_review_md: true,
            timestamp: "2026-03-10T14:30:00Z".into(),
        },
    )
    .expect("accepted scaffold");
    write_scaffold(&accepted_scaffold);
    write_event(
        &append_claim_event(
            &accepted_root,
            &accepted_scaffold.claim_dir,
            &ClaimEventAppendInput {
                kind: ClaimEventKind::Submitted,
                actor: "claimant".into(),
                summary: "Submitted maintainer claim.".into(),
                timestamp: "2026-03-10T14:30:00Z".into(),
                corrected_state: None,
                canonical_record_path: None,
                canonical_mirror_path: None,
            },
        )
        .expect("accepted submitted"),
    );
    write_event(
        &append_claim_event(
            &accepted_root,
            &accepted_scaffold.claim_dir,
            &ClaimEventAppendInput {
                kind: ClaimEventKind::Accepted,
                actor: "index-reviewer".into(),
                summary: "Accepted maintainer claim after identity review.".into(),
                timestamp: "2026-03-12T09:15:00Z".into(),
                corrected_state: None,
                canonical_record_path: Some(".repo".into()),
                canonical_mirror_path: Some("repos/github.com/acme/widget/record.toml".into()),
            },
        )
        .expect("accepted handoff"),
    );
    let accepted_expected = fixture_root()
        .join("accepted-clean")
        .join("repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01");
    let accepted_actual =
        accepted_root.join("repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01");
    assert_eq!(
        read(&accepted_actual.join("claim.toml")),
        read(&accepted_expected.join("claim.toml"))
    );
    assert_eq!(
        read(&accepted_actual.join("events/0001-submitted.toml")),
        read(&accepted_expected.join("events/0001-submitted.toml"))
    );
    assert_eq!(
        read(&accepted_actual.join("events/0002-accepted.toml")),
        read(&accepted_expected.join("events/0002-accepted.toml"))
    );
    assert!(accepted_actual.join("review.md").exists());
    fs::remove_dir_all(&accepted_root).expect("temp dir removed");

    let corrected_root = temp_root("corrected");
    copy_seed_repo("corrected", &corrected_root);
    let corrected_scaffold = scaffold_claim_directory(
        &corrected_root,
        &ClaimScaffoldInput {
            host: "github.com".into(),
            owner: "acme".into(),
            repo: "widget".into(),
            claim_id: "2026-03-15-maintainer-claim-01".into(),
            claimant_display_name: "Acme maintainers".into(),
            asserted_role: "maintainer".into(),
            contact: None,
            record_sources: vec!["https://github.com/acme/widget".into()],
            canonical_repo_url: Some("https://github.com/acme/widget".into()),
            create_review_md: false,
            timestamp: "2026-03-15T09:00:00Z".into(),
        },
    )
    .expect("corrected scaffold");
    write_scaffold(&corrected_scaffold);
    write_event(
        &append_claim_event(
            &corrected_root,
            &corrected_scaffold.claim_dir,
            &ClaimEventAppendInput {
                kind: ClaimEventKind::Submitted,
                actor: "claimant".into(),
                summary: "Submitted maintainer claim.".into(),
                timestamp: "2026-03-15T09:00:00Z".into(),
                corrected_state: None,
                canonical_record_path: None,
                canonical_mirror_path: None,
            },
        )
        .expect("corrected submitted"),
    );
    write_event(
        &append_claim_event(
            &corrected_root,
            &corrected_scaffold.claim_dir,
            &ClaimEventAppendInput {
                kind: ClaimEventKind::Rejected,
                actor: "index-reviewer".into(),
                summary: "Rejected claim pending additional evidence.".into(),
                timestamp: "2026-03-15T11:00:00Z".into(),
                corrected_state: None,
                canonical_record_path: None,
                canonical_mirror_path: None,
            },
        )
        .expect("corrected rejected"),
    );
    write_event(
        &append_claim_event(
            &corrected_root,
            &corrected_scaffold.claim_dir,
            &ClaimEventAppendInput {
                kind: ClaimEventKind::Corrected,
                actor: "index-reviewer".into(),
                summary: "Corrected earlier rejection after evidence review.".into(),
                timestamp: "2026-03-15T15:00:00Z".into(),
                corrected_state: Some(ClaimState::Accepted),
                canonical_record_path: None,
                canonical_mirror_path: None,
            },
        )
        .expect("corrected accepted"),
    );
    let corrected_expected = fixture_root()
        .join("corrected")
        .join("repos/github.com/acme/widget/claims/2026-03-15-maintainer-claim-01");
    let corrected_actual =
        corrected_root.join("repos/github.com/acme/widget/claims/2026-03-15-maintainer-claim-01");
    assert_eq!(
        read(&corrected_actual.join("claim.toml")),
        read(&corrected_expected.join("claim.toml"))
    );
    assert_eq!(
        read(&corrected_actual.join("events/0001-submitted.toml")),
        read(&corrected_expected.join("events/0001-submitted.toml"))
    );
    assert_eq!(
        read(&corrected_actual.join("events/0002-rejected.toml")),
        read(&corrected_expected.join("events/0002-rejected.toml"))
    );
    assert_eq!(
        read(&corrected_actual.join("events/0003-corrected.toml")),
        read(&corrected_expected.join("events/0003-corrected.toml"))
    );
    fs::remove_dir_all(&corrected_root).expect("temp dir removed");
}
