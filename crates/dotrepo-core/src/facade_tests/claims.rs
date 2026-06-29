use super::common::*;

#[test]
fn scaffold_claim_directory_renders_valid_draft_claim() {
    let root = temp_dir("claim-scaffold");
    let repo_dir = root.join("repos/github.com/acme/widget");
    fs::create_dir_all(&repo_dir).expect("repo dir created");
    fs::write(repo_dir.join("record.toml"), "schema = \"dotrepo/v0.1\"\n").expect("record written");

    let plan = scaffold_claim_directory(
        &root,
        &ClaimScaffoldInput {
            host: "github.com".into(),
            owner: "acme".into(),
            repo: "widget".into(),
            claim_id: "2026-03-10-maintainer-claim-02".into(),
            claimant_display_name: "Acme maintainers".into(),
            asserted_role: "maintainer".into(),
            contact: Some("maintainers@acme.dev".into()),
            record_sources: vec!["https://github.com/acme/widget".into()],
            canonical_repo_url: Some("https://github.com/acme/widget".into()),
            create_review_md: true,
            timestamp: "2026-03-10T18:00:00Z".into(),
        },
    )
    .expect("claim plan");

    assert_eq!(
        display_path(&root, &plan.claim_path).expect("claim path is under root"),
        "repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-02/claim.toml"
    );
    let claim = parse_claim_record(&plan.claim_text).expect("claim parses");
    assert_eq!(claim.claim.state, ClaimState::Draft);
    assert_eq!(
        claim.claim.id,
        "github.com/acme/widget/2026-03-10-maintainer-claim-02"
    );
    assert_eq!(
        claim.target.index_paths,
        vec!["repos/github.com/acme/widget/record.toml"]
    );
    assert!(plan
        .review_text
        .as_ref()
        .expect("review template")
        .contains("# Claim review"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn scaffold_claim_directory_requires_existing_index_record() {
    let root = temp_dir("claim-scaffold-missing-record");
    let err = scaffold_claim_directory(
        &root,
        &ClaimScaffoldInput {
            host: "github.com".into(),
            owner: "acme".into(),
            repo: "widget".into(),
            claim_id: "2026-03-10-maintainer-claim-02".into(),
            claimant_display_name: "Acme maintainers".into(),
            asserted_role: "maintainer".into(),
            contact: None,
            record_sources: Vec::new(),
            canonical_repo_url: None,
            create_review_md: false,
            timestamp: "2026-03-10T18:00:00Z".into(),
        },
    )
    .expect_err("missing record should fail");

    assert!(err.to_string().contains("no index record found"));
    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn append_claim_event_advances_draft_claim_to_submitted() {
    let root = temp_dir("claim-event-submit");
    let repo_dir = root.join("repos/github.com/acme/widget");
    fs::create_dir_all(&repo_dir).expect("repo dir created");
    fs::write(repo_dir.join("record.toml"), "schema = \"dotrepo/v0.1\"\n").expect("record written");
    let scaffold = scaffold_claim_directory(
        &root,
        &ClaimScaffoldInput {
            host: "github.com".into(),
            owner: "acme".into(),
            repo: "widget".into(),
            claim_id: "2026-03-10-maintainer-claim-04".into(),
            claimant_display_name: "Acme maintainers".into(),
            asserted_role: "maintainer".into(),
            contact: None,
            record_sources: vec!["https://github.com/acme/widget".into()],
            canonical_repo_url: None,
            create_review_md: true,
            timestamp: "2026-03-10T18:00:00Z".into(),
        },
    )
    .expect("claim scaffold");
    fs::create_dir_all(scaffold.claim_dir.join("events")).expect("events dir created");
    fs::write(&scaffold.claim_path, scaffold.claim_text).expect("claim written");
    fs::write(
        scaffold.review_path.as_ref().expect("review path"),
        scaffold.review_text.as_ref().expect("review text"),
    )
    .expect("review written");

    let plan = append_claim_event(
        &root,
        &scaffold.claim_dir,
        &ClaimEventAppendInput {
            kind: ClaimEventKind::Submitted,
            actor: "claimant".into(),
            summary: "Submitted maintainer claim.".into(),
            timestamp: "2026-03-10T18:05:00Z".into(),
            corrected_state: None,
            canonical_record_path: None,
            canonical_mirror_path: None,
        },
    )
    .expect("submit event");

    assert_eq!(
            display_path(&root, &plan.event_path).expect("event path is under root"),
            "repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-04/events/0001-submitted.toml"
        );
    let updated_claim = parse_claim_record(&plan.claim_text).expect("updated claim parses");
    assert_eq!(updated_claim.claim.state, ClaimState::Submitted);
    let event = parse_claim_event(&plan.event_text).expect("event parses");
    assert_eq!(event.event.sequence, 1);
    assert_eq!(
        event.transition.expect("transition").to,
        ClaimState::Submitted
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn append_claim_event_rejects_invalid_acceptance_from_draft() {
    let root = temp_dir("claim-event-invalid");
    let repo_dir = root.join("repos/github.com/acme/widget");
    fs::create_dir_all(&repo_dir).expect("repo dir created");
    fs::write(repo_dir.join("record.toml"), "schema = \"dotrepo/v0.1\"\n").expect("record written");
    let scaffold = scaffold_claim_directory(
        &root,
        &ClaimScaffoldInput {
            host: "github.com".into(),
            owner: "acme".into(),
            repo: "widget".into(),
            claim_id: "2026-03-10-maintainer-claim-05".into(),
            claimant_display_name: "Acme maintainers".into(),
            asserted_role: "maintainer".into(),
            contact: None,
            record_sources: vec!["https://github.com/acme/widget".into()],
            canonical_repo_url: None,
            create_review_md: false,
            timestamp: "2026-03-10T18:00:00Z".into(),
        },
    )
    .expect("claim scaffold");
    fs::create_dir_all(scaffold.claim_dir.join("events")).expect("events dir created");
    fs::write(&scaffold.claim_path, scaffold.claim_text).expect("claim written");

    let err = append_claim_event(
        &root,
        &scaffold.claim_dir,
        &ClaimEventAppendInput {
            kind: ClaimEventKind::Accepted,
            actor: "index-reviewer".into(),
            summary: "Accepted maintainer claim.".into(),
            timestamp: "2026-03-10T18:05:00Z".into(),
            corrected_state: None,
            canonical_record_path: None,
            canonical_mirror_path: None,
        },
    )
    .expect_err("draft claim should not accept");

    assert!(err
        .to_string()
        .contains("accepted events are only valid for submitted or in_review claims"));
    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn append_claim_event_records_canonical_links_for_accepted_handoff() {
    let root = temp_dir("claim-event-accepted-handoff");
    let repo_dir = root.join("repos/github.com/acme/widget");
    fs::create_dir_all(&repo_dir).expect("repo dir created");
    fs::write(repo_dir.join("record.toml"), "schema = \"dotrepo/v0.1\"\n").expect("record written");
    let scaffold = scaffold_claim_directory(
        &root,
        &ClaimScaffoldInput {
            host: "github.com".into(),
            owner: "acme".into(),
            repo: "widget".into(),
            claim_id: "2026-03-10-maintainer-claim-06".into(),
            claimant_display_name: "Acme maintainers".into(),
            asserted_role: "maintainer".into(),
            contact: None,
            record_sources: vec!["https://github.com/acme/widget".into()],
            canonical_repo_url: Some("https://github.com/acme/widget".into()),
            create_review_md: false,
            timestamp: "2026-03-10T18:00:00Z".into(),
        },
    )
    .expect("claim scaffold");
    fs::create_dir_all(scaffold.claim_dir.join("events")).expect("events dir created");
    fs::write(&scaffold.claim_path, scaffold.claim_text).expect("claim written");

    let submitted = append_claim_event(
        &root,
        &scaffold.claim_dir,
        &ClaimEventAppendInput {
            kind: ClaimEventKind::Submitted,
            actor: "claimant".into(),
            summary: "Submitted maintainer claim.".into(),
            timestamp: "2026-03-10T18:05:00Z".into(),
            corrected_state: None,
            canonical_record_path: None,
            canonical_mirror_path: None,
        },
    )
    .expect("submitted event");
    fs::write(&submitted.event_path, submitted.event_text).expect("submitted event written");
    fs::write(&submitted.claim_path, submitted.claim_text).expect("submitted claim written");

    let accepted = append_claim_event(
        &root,
        &scaffold.claim_dir,
        &ClaimEventAppendInput {
            kind: ClaimEventKind::Accepted,
            actor: "index-reviewer".into(),
            summary: "Accepted maintainer claim after review.".into(),
            timestamp: "2026-03-10T18:10:00Z".into(),
            corrected_state: None,
            canonical_record_path: Some(".repo".into()),
            canonical_mirror_path: Some("repos/github.com/acme/widget/record.toml".into()),
        },
    )
    .expect("accepted event");

    let updated_claim = parse_claim_record(&accepted.claim_text).expect("updated claim parses");
    let resolution = updated_claim.resolution.expect("resolution recorded");
    assert_eq!(updated_claim.claim.state, ClaimState::Accepted);
    assert_eq!(resolution.canonical_record_path.as_deref(), Some(".repo"));
    assert_eq!(
        resolution.canonical_mirror_path.as_deref(),
        Some("repos/github.com/acme/widget/record.toml")
    );
    assert_eq!(
        resolution.result_event.as_deref(),
        Some("events/0002-accepted.toml")
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn append_claim_event_allows_corrected_handoff_adjustments() {
    let root = temp_dir("claim-event-corrected-handoff");
    let repo_dir = root.join("repos/github.com/acme/widget");
    fs::create_dir_all(&repo_dir).expect("repo dir created");
    fs::write(repo_dir.join("record.toml"), "schema = \"dotrepo/v0.1\"\n").expect("record written");
    let scaffold = scaffold_claim_directory(
        &root,
        &ClaimScaffoldInput {
            host: "github.com".into(),
            owner: "acme".into(),
            repo: "widget".into(),
            claim_id: "2026-03-10-maintainer-claim-07".into(),
            claimant_display_name: "Acme maintainers".into(),
            asserted_role: "maintainer".into(),
            contact: None,
            record_sources: vec!["https://github.com/acme/widget".into()],
            canonical_repo_url: Some("https://github.com/acme/widget".into()),
            create_review_md: false,
            timestamp: "2026-03-10T18:00:00Z".into(),
        },
    )
    .expect("claim scaffold");
    fs::create_dir_all(scaffold.claim_dir.join("events")).expect("events dir created");
    fs::write(&scaffold.claim_path, scaffold.claim_text).expect("claim written");

    let submitted = append_claim_event(
        &root,
        &scaffold.claim_dir,
        &ClaimEventAppendInput {
            kind: ClaimEventKind::Submitted,
            actor: "claimant".into(),
            summary: "Submitted maintainer claim.".into(),
            timestamp: "2026-03-10T18:05:00Z".into(),
            corrected_state: None,
            canonical_record_path: None,
            canonical_mirror_path: None,
        },
    )
    .expect("submitted event");
    fs::write(&submitted.event_path, submitted.event_text).expect("submitted event written");
    fs::write(&submitted.claim_path, submitted.claim_text).expect("submitted claim written");

    let accepted = append_claim_event(
        &root,
        &scaffold.claim_dir,
        &ClaimEventAppendInput {
            kind: ClaimEventKind::Accepted,
            actor: "index-reviewer".into(),
            summary: "Accepted maintainer claim without canonical links yet.".into(),
            timestamp: "2026-03-10T18:10:00Z".into(),
            corrected_state: None,
            canonical_record_path: None,
            canonical_mirror_path: None,
        },
    )
    .expect("accepted event");
    fs::write(&accepted.event_path, accepted.event_text).expect("accepted event written");
    fs::write(&accepted.claim_path, accepted.claim_text).expect("accepted claim written");

    let corrected = append_claim_event(
        &root,
        &scaffold.claim_dir,
        &ClaimEventAppendInput {
            kind: ClaimEventKind::Corrected,
            actor: "index-reviewer".into(),
            summary: "Linked accepted claim to canonical artifacts.".into(),
            timestamp: "2026-03-10T18:15:00Z".into(),
            corrected_state: None,
            canonical_record_path: Some(".repo".into()),
            canonical_mirror_path: Some("repos/github.com/acme/widget/record.toml".into()),
        },
    )
    .expect("corrected event");

    let updated_claim = parse_claim_record(&corrected.claim_text).expect("updated claim parses");
    let resolution = updated_claim.resolution.expect("resolution recorded");
    assert_eq!(updated_claim.claim.state, ClaimState::Accepted);
    assert_eq!(
        resolution.result_event.as_deref(),
        Some("events/0003-corrected.toml")
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn append_claim_event_rejects_canonical_links_for_non_accepted_states() {
    let root = temp_dir("claim-event-invalid-handoff");
    let repo_dir = root.join("repos/github.com/acme/widget");
    fs::create_dir_all(&repo_dir).expect("repo dir created");
    fs::write(repo_dir.join("record.toml"), "schema = \"dotrepo/v0.1\"\n").expect("record written");
    let scaffold = scaffold_claim_directory(
        &root,
        &ClaimScaffoldInput {
            host: "github.com".into(),
            owner: "acme".into(),
            repo: "widget".into(),
            claim_id: "2026-03-10-maintainer-claim-08".into(),
            claimant_display_name: "Acme maintainers".into(),
            asserted_role: "maintainer".into(),
            contact: None,
            record_sources: vec!["https://github.com/acme/widget".into()],
            canonical_repo_url: None,
            create_review_md: false,
            timestamp: "2026-03-10T18:00:00Z".into(),
        },
    )
    .expect("claim scaffold");
    fs::create_dir_all(scaffold.claim_dir.join("events")).expect("events dir created");
    fs::write(&scaffold.claim_path, scaffold.claim_text).expect("claim written");
    let submitted = append_claim_event(
        &root,
        &scaffold.claim_dir,
        &ClaimEventAppendInput {
            kind: ClaimEventKind::Submitted,
            actor: "claimant".into(),
            summary: "Submitted maintainer claim.".into(),
            timestamp: "2026-03-10T18:05:00Z".into(),
            corrected_state: None,
            canonical_record_path: None,
            canonical_mirror_path: None,
        },
    )
    .expect("submitted event");
    fs::write(&submitted.event_path, submitted.event_text).expect("event written");
    fs::write(&submitted.claim_path, submitted.claim_text).expect("claim written");

    let err = append_claim_event(
        &root,
        &scaffold.claim_dir,
        &ClaimEventAppendInput {
            kind: ClaimEventKind::Rejected,
            actor: "index-reviewer".into(),
            summary: "Rejected maintainer claim.".into(),
            timestamp: "2026-03-10T18:10:00Z".into(),
            corrected_state: None,
            canonical_record_path: Some(".repo".into()),
            canonical_mirror_path: None,
        },
    )
    .expect_err("non-accepted states should reject canonical links");

    assert!(err.to_string().contains(
        "canonical handoff links are only valid when the resulting claim state is accepted"
    ));
    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn parse_claim_record_rejects_unknown_schema() {
    let err = parse_claim_record(
        r#"
schema = "dotrepo-claim/v9"

[claim]
id = "github.com/acme/widget/2026-03-10-maintainer-claim-01"
kind = "maintainer_authority"
state = "submitted"
created_at = "2026-03-10T14:30:00Z"
updated_at = "2026-03-10T14:30:00Z"

[identity]
host = "github.com"
owner = "acme"
repo = "widget"

[claimant]
display_name = "Acme maintainers"
asserted_role = "maintainer"

[target]
record_sources = ["https://github.com/acme/widget"]
"#,
    )
    .expect_err("claim schema should fail");

    assert!(
        err.to_string().contains("unsupported claim schema"),
        "unexpected error: {err}"
    );
}

#[test]
fn parse_claim_event_rejects_zero_sequence() {
    let err = parse_claim_event(
        r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 0
kind = "submitted"
timestamp = "2026-03-10T14:30:00Z"
actor = "claimant"

[summary]
text = "Submitted claim."
"#,
    )
    .expect_err("zero sequence should fail");

    assert!(
        err.to_string()
            .contains("event.sequence must be greater than zero"),
        "unexpected error: {err}"
    );
}

#[test]
fn load_claim_directory_reads_claim_and_events() {
    let root = temp_dir("claim-directory");
    let claim_dir = root.join("repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01");
    fs::create_dir_all(claim_dir.join("events")).expect("claim events dir created");
    fs::write(
        claim_dir.join("claim.toml"),
        r#"
schema = "dotrepo-claim/v0"

[claim]
id = "github.com/acme/widget/2026-03-10-maintainer-claim-01"
kind = "maintainer_authority"
state = "accepted"
created_at = "2026-03-10T14:30:00Z"
updated_at = "2026-03-12T09:15:00Z"

[identity]
host = "github.com"
owner = "acme"
repo = "widget"

[claimant]
display_name = "Acme maintainers"
asserted_role = "maintainer"
contact = "maintainers@acme.dev"

[target]
index_paths = ["repos/github.com/acme/widget/record.toml"]
record_sources = ["https://github.com/acme/widget"]
canonical_repo_url = "https://github.com/acme/widget"

[resolution]
canonical_record_path = ".repo"
canonical_mirror_path = "repos/github.com/acme/widget/record.toml"
result_event = "events/0002-accepted.toml"
"#,
    )
    .expect("claim written");
    fs::write(claim_dir.join("review.md"), "Reviewed.").expect("review written");
    fs::write(
        claim_dir.join("events/0001-submitted.toml"),
        r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 1
kind = "submitted"
timestamp = "2026-03-10T14:30:00Z"
actor = "claimant"

[transition]
from = "draft"
to = "submitted"

[summary]
text = "Submitted maintainer claim."
"#,
    )
    .expect("submitted event written");
    fs::write(
        claim_dir.join("events/0002-accepted.toml"),
        r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 2
kind = "accepted"
timestamp = "2026-03-12T09:15:00Z"
actor = "index-reviewer"

[transition]
from = "in_review"
to = "accepted"

[summary]
text = "Accepted maintainer claim."

[links]
claim = "../claim.toml"
review_notes = "../review.md"
canonical_record_path = ".repo"
"#,
    )
    .expect("accepted event written");

    let loaded = load_claim_directory(&root, &claim_dir).expect("claim directory loads");
    assert_eq!(
        loaded.claim.claim.state,
        ClaimState::Accepted,
        "current state should parse"
    );
    assert_eq!(loaded.events.len(), 2, "events should be loaded");
    assert_eq!(
        loaded.events[0].event.event.kind,
        ClaimEventKind::Submitted,
        "events should be ordered by filename"
    );
    assert_eq!(
        loaded.review_path.as_deref(),
        Some("repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01/review.md")
    );

    let json = serde_json::to_value(&loaded).expect("claim directory serializes");
    assert_eq!(
        json["claim"]["claim"]["state"],
        Value::String("accepted".into())
    );
    assert_eq!(
        json["events"][1]["event"]["event"]["kind"],
        Value::String("accepted".into())
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn validate_index_root_accepts_well_formed_claim_directory() {
    let root = temp_dir("index-claims-ok");
    let record_dir = root.join("repos/github.com/acme/widget");
    let claim_dir = record_dir.join("claims/2026-03-10-maintainer-claim-01");
    fs::create_dir_all(claim_dir.join("events")).expect("claim events dir created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/acme/widget"

[record.trust]
confidence = "medium"
provenance = ["imported", "verified"]

[repo]
name = "widget"
description = "Reviewed overlay"
"#,
    )
    .expect("record written");
    fs::write(
        record_dir.join("evidence.md"),
        "Imported from README and validated against repository surfaces.\n",
    )
    .expect("evidence written");
    fs::write(
        claim_dir.join("claim.toml"),
        r#"
schema = "dotrepo-claim/v0"

[claim]
id = "github.com/acme/widget/2026-03-10-maintainer-claim-01"
kind = "maintainer_authority"
state = "accepted"
created_at = "2026-03-10T14:30:00Z"
updated_at = "2026-03-12T09:15:00Z"

[identity]
host = "github.com"
owner = "acme"
repo = "widget"

[claimant]
display_name = "Acme maintainers"
asserted_role = "maintainer"
contact = "maintainers@acme.dev"

[target]
index_paths = ["repos/github.com/acme/widget/record.toml"]
record_sources = ["https://github.com/acme/widget"]
canonical_repo_url = "https://github.com/acme/widget"

[resolution]
canonical_record_path = ".repo"
canonical_mirror_path = "repos/github.com/acme/widget/record.toml"
result_event = "events/0002-accepted.toml"
"#,
    )
    .expect("claim written");
    fs::write(claim_dir.join("review.md"), "Reviewed.").expect("review written");
    fs::write(
        claim_dir.join("events/0001-submitted.toml"),
        r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 1
kind = "submitted"
timestamp = "2026-03-10T14:30:00Z"
actor = "claimant"

[transition]
from = "draft"
to = "submitted"

[summary]
text = "Submitted claim."
"#,
    )
    .expect("submitted event written");
    fs::write(
        claim_dir.join("events/0002-accepted.toml"),
        r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 2
kind = "accepted"
timestamp = "2026-03-12T09:15:00Z"
actor = "index-reviewer"

[transition]
from = "submitted"
to = "accepted"

[summary]
text = "Accepted claim."

[links]
claim = "../claim.toml"
review_notes = "../review.md"
canonical_record_path = ".repo"
"#,
    )
    .expect("accepted event written");

    let findings = validate_index_root(&root).expect("index validates");
    assert!(
        findings
            .iter()
            .all(|finding| finding.severity != IndexFindingSeverity::Error),
        "unexpected findings: {findings:#?}"
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn validate_index_root_reports_claim_identity_mismatch() {
    let root = temp_dir("index-claims-identity");
    let record_dir = root.join("repos/github.com/acme/widget");
    let claim_dir = record_dir.join("claims/2026-03-10-maintainer-claim-01");
    fs::create_dir_all(claim_dir.join("events")).expect("claim events dir created");
    fs::write(
        claim_dir.join("claim.toml"),
        r#"
schema = "dotrepo-claim/v0"

[claim]
id = "github.com/acme/widget/2026-03-10-maintainer-claim-01"
kind = "maintainer_authority"
state = "submitted"
created_at = "2026-03-10T14:30:00Z"
updated_at = "2026-03-10T14:30:00Z"

[identity]
host = "github.com"
owner = "acme"
repo = "other-widget"

[claimant]
display_name = "Acme maintainers"
asserted_role = "maintainer"

[target]
record_sources = ["https://github.com/acme/widget"]
"#,
    )
    .expect("claim written");
    fs::write(
        claim_dir.join("events/0001-submitted.toml"),
        r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 1
kind = "submitted"
timestamp = "2026-03-10T14:30:00Z"
actor = "claimant"

[transition]
from = "draft"
to = "submitted"

[summary]
text = "Submitted claim."
"#,
    )
    .expect("submitted event written");

    let findings = validate_index_root(&root).expect("index validates");
    assert!(
        findings.iter().any(|finding| finding
            .message
            .contains("claim.identity resolves to github.com/acme/other-widget")),
        "expected claim identity mismatch, found: {findings:#?}"
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn validate_index_root_reports_claim_event_history_errors() {
    let root = temp_dir("index-claims-history");
    let record_dir = root.join("repos/github.com/acme/widget");
    let claim_dir = record_dir.join("claims/2026-03-10-maintainer-claim-01");
    fs::create_dir_all(claim_dir.join("events")).expect("claim events dir created");
    fs::write(
        claim_dir.join("claim.toml"),
        r#"
schema = "dotrepo-claim/v0"

[claim]
id = "github.com/acme/widget/2026-03-10-maintainer-claim-01"
kind = "maintainer_authority"
state = "accepted"
created_at = "2026-03-10T14:30:00Z"
updated_at = "2026-03-12T09:15:00Z"

[identity]
host = "github.com"
owner = "acme"
repo = "widget"

[claimant]
display_name = "Acme maintainers"
asserted_role = "maintainer"

[target]
record_sources = ["https://github.com/acme/widget"]
"#,
    )
    .expect("claim written");
    fs::write(
        claim_dir.join("events/0002-submitted.toml"),
        r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 2
kind = "submitted"
timestamp = "2026-03-10T14:30:00Z"
actor = "claimant"

[transition]
from = "draft"
to = "submitted"

[summary]
text = "Submitted claim."
"#,
    )
    .expect("submitted event written");

    let findings = validate_index_root(&root).expect("index validates");
    assert!(
        findings.iter().any(|finding| finding
            .message
            .contains("claim events must use contiguous sequence numbers starting at 1")),
        "expected sequence error, found: {findings:#?}"
    );
    assert!(
        findings
            .iter()
            .any(|finding| finding.message.contains("claim.state is Accepted")),
        "expected claim state mismatch, found: {findings:#?}"
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}
