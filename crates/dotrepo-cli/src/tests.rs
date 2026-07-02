use crate::cli::*;
use crate::commands::*;
use crate::error::CliExit;
use crate::format::*;
use dotrepo_core::*;
use serde_json::Value;
use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

#[test]
fn format_query_value_defaults_to_human_readable_strings() {
    let rendered = format_query_value(&Value::String("orbit".into()), false).expect("formats");
    assert_eq!(rendered, "orbit");
}

#[test]
fn format_query_value_rejects_raw_composite_values() {
    let err = format_query_value(&Value::Array(vec![Value::String("orbit".into())]), true)
        .expect_err("raw composite values should fail");
    assert!(err.to_string().contains("--raw"));
}

#[test]
fn format_claim_report_surfaces_handoff_and_events() {
    let report = ClaimInspectionReport {
            claim_path: "repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01/claim.toml".into(),
            state: dotrepo_core::ClaimState::Accepted,
            kind: dotrepo_core::ClaimKind::MaintainerAuthority,
            identity: dotrepo_core::ClaimIdentity {
                host: "github.com".into(),
                owner: "acme".into(),
                repo: "widget".into(),
            },
            claimant: dotrepo_core::Claimant {
                display_name: "Acme maintainers".into(),
                asserted_role: "maintainer".into(),
                contact: Some("maintainers@acme.dev".into()),
            },
            target: dotrepo_core::ClaimTargetInspection {
                index_paths: vec!["repos/github.com/acme/widget/record.toml".into()],
                record_sources: vec!["https://github.com/acme/widget".into()],
                canonical_repo_url: Some("https://github.com/acme/widget".into()),
                handoff: Some(ClaimHandoffOutcome::Superseded),
            },
            resolution: Some(dotrepo_core::ClaimResolution {
                canonical_record_path: Some(".repo".into()),
                canonical_mirror_path: Some("repos/github.com/acme/widget/record.toml".into()),
                result_event: Some("events/0002-accepted.toml".into()),
            }),
            review_path: Some(
                "repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01/review.md"
                    .into(),
            ),
            events: vec![dotrepo_core::ClaimEventInspection {
                path: "repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01/events/0002-accepted.toml".into(),
                sequence: 2,
                kind: dotrepo_core::ClaimEventKind::Accepted,
                timestamp: "2026-03-12T09:15:00Z".into(),
                actor: "index-reviewer".into(),
                summary: "Accepted claim.".into(),
                from: Some(dotrepo_core::ClaimState::Submitted),
                to: Some(dotrepo_core::ClaimState::Accepted),
            }],
        };

    let rendered = format_claim_report(&report);
    assert!(rendered.contains("handoff: superseded"));
    assert!(rendered.contains("target index paths:"));
    assert!(rendered.contains("events:"));
    assert!(rendered.contains("Accepted"));
}

#[test]
fn claim_init_scaffolds_valid_claim_directory() {
    let root = temp_dir("claim-init");
    let repo_dir = root.join("repos/github.com/acme/widget");
    fs::create_dir_all(&repo_dir).expect("repo dir created");
    fs::write(repo_dir.join("record.toml"), "schema = \"dotrepo/v0.1\"\n").expect("record written");

    cmd_claim_init(
        root.clone(),
        ClaimInitArgs {
            host: "github.com".into(),
            owner: "acme".into(),
            repo: "widget".into(),
            claim_id: "2026-03-10-maintainer-claim-03".into(),
            claimant_name: "Acme maintainers".into(),
            asserted_role: "maintainer".into(),
            contact: Some("maintainers@acme.dev".into()),
            record_sources: vec!["https://github.com/acme/widget".into()],
            canonical_repo_url: Some("https://github.com/acme/widget".into()),
            review_md: true,
            force: false,
        },
    )
    .expect("claim scaffold succeeds");

    let claim_dir = root.join("repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-03");
    assert!(claim_dir.join("claim.toml").exists());
    assert!(claim_dir.join("review.md").exists());
    assert!(claim_dir.join("events").is_dir());

    let report = inspect_claim_directory(&root, &claim_dir).expect("claim inspection works");
    assert_eq!(report.state, dotrepo_core::ClaimState::Draft);
    assert_eq!(report.events.len(), 0);

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn claim_from_native_derives_identity_and_canonical_source() {
    let repo_root = temp_dir("claim-from-native-repo");
    fs::write(
        repo_root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "draft"

[repo]
name = "widget"
description = "Native widget metadata."
homepage = "https://github.com/acme/widget"
"#,
    )
    .expect("native .repo written");
    let index_root = temp_dir("claim-from-native-index");
    let record_dir = index_root.join("repos/github.com/acme/widget");
    fs::create_dir_all(&record_dir).expect("index record dir created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"

[repo]
name = "widget"
description = "Overlay widget metadata."
"#,
    )
    .expect("overlay record written");

    cmd_claim_from_native(
        repo_root.clone(),
        ClaimFromNativeArgs {
            index_root: index_root.clone(),
            claim_id: "2026-03-10-maintainer-claim-04".into(),
            claimant_name: "Acme maintainers".into(),
            asserted_role: "maintainer".into(),
            contact: Some("maintainers@acme.dev".into()),
            review_md: true,
            force: false,
        },
    )
    .expect("claim scaffold succeeds");

    let claim_dir = record_dir.join("claims/2026-03-10-maintainer-claim-04");
    let report = inspect_claim_directory(&index_root, &claim_dir).expect("claim inspection works");
    assert_eq!(report.state, dotrepo_core::ClaimState::Draft);
    assert_eq!(
        report.target.record_sources,
        vec!["https://github.com/acme/widget".to_string()]
    );
    assert_eq!(
        report.target.canonical_repo_url,
        Some("https://github.com/acme/widget".to_string())
    );
    assert!(claim_dir.join("review.md").exists());

    fs::remove_dir_all(repo_root).expect("repo temp dir removed");
    fs::remove_dir_all(index_root).expect("index temp dir removed");
}

#[test]
fn claim_from_native_requires_homepage_identity() {
    let repo_root = temp_dir("claim-from-native-no-homepage");
    fs::write(
        repo_root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "draft"

[repo]
name = "widget"
description = "Native widget metadata."
"#,
    )
    .expect("native .repo written");
    let index_root = temp_dir("claim-from-native-index-empty");

    let err = cmd_claim_from_native(
        repo_root.clone(),
        ClaimFromNativeArgs {
            index_root: index_root.clone(),
            claim_id: "2026-03-10-maintainer-claim-04".into(),
            claimant_name: "Acme maintainers".into(),
            asserted_role: "maintainer".into(),
            contact: None,
            review_md: false,
            force: false,
        },
    )
    .expect_err("missing homepage should fail");

    assert!(err.to_string().contains("requires repo.homepage"));

    fs::remove_dir_all(repo_root).expect("repo temp dir removed");
    fs::remove_dir_all(index_root).expect("index temp dir removed");
}

#[test]
fn claim_accept_native_records_canonical_handoff_links() {
    let repo_root = temp_dir("claim-accept-native-repo");
    fs::write(
        repo_root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "draft"

[repo]
name = "widget"
description = "Native widget metadata."
homepage = "https://github.com/acme/widget"
"#,
    )
    .expect("native .repo written");
    let index_root = temp_dir("claim-accept-native-index");
    let record_dir = index_root.join("repos/github.com/acme/widget");
    fs::create_dir_all(&record_dir).expect("index record dir created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"

[repo]
name = "widget"
description = "Overlay widget metadata."
"#,
    )
    .expect("overlay record written");
    cmd_claim_from_native(
        repo_root.clone(),
        ClaimFromNativeArgs {
            index_root: index_root.clone(),
            claim_id: "2026-03-10-maintainer-claim-05".into(),
            claimant_name: "Acme maintainers".into(),
            asserted_role: "maintainer".into(),
            contact: None,
            review_md: false,
            force: false,
        },
    )
    .expect("claim scaffold succeeds");
    cmd_claim_submit_native(
        repo_root.clone(),
        ClaimSubmitNativeArgs {
            index_root: index_root.clone(),
            claim_id: "2026-03-10-maintainer-claim-05".into(),
            actor: "claimant".into(),
            summary: "Submitted maintainer claim.".into(),
        },
    )
    .expect("submitted event succeeds");

    cmd_claim_accept_native(
        repo_root.clone(),
        ClaimAcceptNativeArgs {
            index_root: index_root.clone(),
            path: None,
            claim_id: Some("2026-03-10-maintainer-claim-05".into()),
            actor: "index-reviewer".into(),
            summary: "Accepted maintainer claim with canonical native record.".into(),
        },
    )
    .expect("accepted event succeeds");

    let claim_dir = record_dir.join("claims/2026-03-10-maintainer-claim-05");
    let report = inspect_claim_directory(&index_root, &claim_dir).expect("claim inspection works");
    assert_eq!(report.state, dotrepo_core::ClaimState::Accepted);
    assert_eq!(report.target.handoff, Some(ClaimHandoffOutcome::Superseded));
    let resolution = report.resolution.expect("resolution recorded");
    assert_eq!(resolution.canonical_record_path.as_deref(), Some(".repo"));
    assert_eq!(
        resolution.canonical_mirror_path.as_deref(),
        Some("repos/github.com/acme/widget/record.toml")
    );

    fs::remove_dir_all(repo_root).expect("repo temp dir removed");
    fs::remove_dir_all(index_root).expect("index temp dir removed");
}

#[test]
fn claim_submit_native_requires_homepage_identity() {
    let repo_root = temp_dir("claim-submit-native-no-homepage");
    fs::write(
        repo_root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "draft"

[repo]
name = "widget"
description = "Native widget metadata."
"#,
    )
    .expect("native .repo written");
    let index_root = temp_dir("claim-submit-native-unused-index");

    let err = cmd_claim_submit_native(
        repo_root.clone(),
        ClaimSubmitNativeArgs {
            index_root: index_root.clone(),
            claim_id: "2026-03-10-maintainer-claim-05".into(),
            actor: "claimant".into(),
            summary: "Submitted maintainer claim.".into(),
        },
    )
    .expect_err("missing homepage should fail");

    assert!(err.to_string().contains("requires repo.homepage"));

    fs::remove_dir_all(repo_root).expect("repo temp dir removed");
    fs::remove_dir_all(index_root).expect("index temp dir removed");
}

#[test]
fn claim_accept_native_requires_homepage_identity() {
    let repo_root = temp_dir("claim-accept-native-no-homepage");
    fs::write(
        repo_root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "draft"

[repo]
name = "widget"
description = "Native widget metadata."
"#,
    )
    .expect("native .repo written");
    let index_root = temp_dir("claim-accept-native-unused-index");

    let err = cmd_claim_accept_native(
        repo_root.clone(),
        ClaimAcceptNativeArgs {
            index_root: index_root.clone(),
            path: None,
            claim_id: Some("claim".into()),
            actor: "index-reviewer".into(),
            summary: "Accepted maintainer claim.".into(),
        },
    )
    .expect_err("missing homepage should fail");

    assert!(err.to_string().contains("requires repo.homepage"));

    fs::remove_dir_all(repo_root).expect("repo temp dir removed");
    fs::remove_dir_all(index_root).expect("index temp dir removed");
}

#[test]
fn claim_accept_native_requires_path_or_claim_id() {
    let repo_root = temp_dir("claim-accept-native-no-path");
    fs::write(
        repo_root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "draft"

[repo]
name = "widget"
description = "Native widget metadata."
homepage = "https://github.com/acme/widget"
"#,
    )
    .expect("native .repo written");
    let index_root = temp_dir("claim-accept-native-no-path-index");

    let err = cmd_claim_accept_native(
        repo_root.clone(),
        ClaimAcceptNativeArgs {
            index_root: index_root.clone(),
            path: None,
            claim_id: None,
            actor: "index-reviewer".into(),
            summary: "Accepted maintainer claim.".into(),
        },
    )
    .expect_err("missing path and claim id should fail");

    assert!(err
        .to_string()
        .contains("requires a claim path or --claim-id"));

    fs::remove_dir_all(repo_root).expect("repo temp dir removed");
    fs::remove_dir_all(index_root).expect("index temp dir removed");
}

#[test]
fn adoption_status_reports_ready_native_loop() {
    let root = temp_dir("adoption-status-ready");
    fs::write(
        root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[record.trust]
confidence = "high"
provenance = ["declared", "verified"]
notes = "Maintainer-controlled source of truth."

[repo]
name = "widget"
description = "Fast widget toolkit."
homepage = "https://github.com/acme/widget"
license = "MIT"
status = "active"
visibility = "public"
languages = ["rust"]
build = "cargo build"
test = "cargo test"
topics = ["widgets"]

[owners]
maintainers = ["@acme/platform"]
security_contact = "security@example.com"

[compat.github]
codeowners = "generate"
"#,
    )
    .expect("native .repo written");

    cmd_generate(root.clone(), false).expect("generated surfaces written");
    cmd_ci_init(root.clone(), false, Some("0.1.0".into())).expect("ci workflow written");

    let report = adoption_status_repository(&root);
    assert!(report.has_native_record);
    assert!(report.validation_passed);
    assert!(report.can_claim_from_native);
    assert!(report.ci_workflow_present);
    assert!(report.managed_surface_check_passed);
    assert_eq!(
        report
            .repository_identity
            .as_ref()
            .map(|identity| identity.repo.as_str()),
        Some("widget")
    );
    assert!(report.next_steps.iter().any(|step| step.contains("ready")));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn adoption_status_reports_missing_native_onboarding_steps() {
    let root = temp_dir("adoption-status-missing");

    let report = adoption_status_repository(&root);
    assert!(!report.has_native_record);
    assert!(!report.validation_passed);
    assert!(!report.can_claim_from_native);
    assert!(!report.ci_workflow_present);
    assert!(!report.managed_surface_check_passed);
    assert!(report
        .next_steps
        .iter()
        .any(|step| step.contains("create a native .repo")));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn claim_init_refuses_existing_claim_dir_without_force() {
    let root = temp_dir("claim-init-no-force");
    let claim_dir = root.join("repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-03");
    fs::create_dir_all(claim_dir.join("events")).expect("claim dir created");
    fs::create_dir_all(root.join("repos/github.com/acme/widget")).expect("repo dir created");
    fs::write(
        root.join("repos/github.com/acme/widget/record.toml"),
        "schema = \"dotrepo/v0.1\"\n",
    )
    .expect("record written");
    fs::write(
        claim_dir.join("claim.toml"),
        "schema = \"dotrepo-claim/v0\"\n",
    )
    .expect("claim scaffold written");

    let err = cmd_claim_init(
        root.clone(),
        ClaimInitArgs {
            host: "github.com".into(),
            owner: "acme".into(),
            repo: "widget".into(),
            claim_id: "2026-03-10-maintainer-claim-03".into(),
            claimant_name: "Acme maintainers".into(),
            asserted_role: "maintainer".into(),
            contact: None,
            record_sources: Vec::new(),
            canonical_repo_url: None,
            review_md: false,
            force: false,
        },
    )
    .expect_err("existing claim dir should fail");
    assert!(err.to_string().contains("already exists"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn claim_init_force_refuses_existing_event_history() {
    let root = temp_dir("claim-init-history");
    let claim_dir = root.join("repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-03");
    fs::create_dir_all(claim_dir.join("events")).expect("claim dir created");
    fs::create_dir_all(root.join("repos/github.com/acme/widget")).expect("repo dir created");
    fs::write(
        root.join("repos/github.com/acme/widget/record.toml"),
        "schema = \"dotrepo/v0.1\"\n",
    )
    .expect("record written");
    fs::write(
        claim_dir.join("events/0001-submitted.toml"),
        "schema = \"dotrepo-claim-event/v0\"\n",
    )
    .expect("event written");

    let err = cmd_claim_init(
        root.clone(),
        ClaimInitArgs {
            host: "github.com".into(),
            owner: "acme".into(),
            repo: "widget".into(),
            claim_id: "2026-03-10-maintainer-claim-03".into(),
            claimant_name: "Acme maintainers".into(),
            asserted_role: "maintainer".into(),
            contact: None,
            record_sources: Vec::new(),
            canonical_repo_url: None,
            review_md: false,
            force: true,
        },
    )
    .expect_err("existing event history should fail");
    assert!(err
        .to_string()
        .contains("refusing to overwrite existing claim history"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn claim_event_appends_submitted_history_and_updates_claim_state() {
    let root = temp_dir("claim-event");
    let repo_dir = root.join("repos/github.com/acme/widget");
    fs::create_dir_all(&repo_dir).expect("repo dir created");
    fs::write(repo_dir.join("record.toml"), "schema = \"dotrepo/v0.1\"\n").expect("record written");
    cmd_claim_init(
        root.clone(),
        ClaimInitArgs {
            host: "github.com".into(),
            owner: "acme".into(),
            repo: "widget".into(),
            claim_id: "2026-03-10-maintainer-claim-03".into(),
            claimant_name: "Acme maintainers".into(),
            asserted_role: "maintainer".into(),
            contact: None,
            record_sources: vec!["https://github.com/acme/widget".into()],
            canonical_repo_url: None,
            review_md: true,
            force: false,
        },
    )
    .expect("claim scaffold succeeds");

    let claim_dir = root.join("repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-03");
    let claim_path =
        PathBuf::from("repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-03");
    cmd_claim_event(
        root.clone(),
        ClaimEventArgs {
            path: claim_path,
            kind: ClaimEventKindArg::Submitted,
            actor: "claimant".into(),
            summary: "Submitted maintainer claim.".into(),
            corrected_state: None,
            canonical_record_path: None,
            canonical_mirror_path: None,
        },
    )
    .expect("claim event succeeds");

    let report = inspect_claim_directory(&root, &claim_dir).expect("claim inspection works");
    assert_eq!(report.state, dotrepo_core::ClaimState::Submitted);
    assert_eq!(report.events.len(), 1);
    assert_eq!(
        report.events[0].kind,
        dotrepo_core::ClaimEventKind::Submitted
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn claim_event_refuses_invalid_transition() {
    let root = temp_dir("claim-event-invalid");
    let repo_dir = root.join("repos/github.com/acme/widget");
    fs::create_dir_all(&repo_dir).expect("repo dir created");
    fs::write(repo_dir.join("record.toml"), "schema = \"dotrepo/v0.1\"\n").expect("record written");
    cmd_claim_init(
        root.clone(),
        ClaimInitArgs {
            host: "github.com".into(),
            owner: "acme".into(),
            repo: "widget".into(),
            claim_id: "2026-03-10-maintainer-claim-03".into(),
            claimant_name: "Acme maintainers".into(),
            asserted_role: "maintainer".into(),
            contact: None,
            record_sources: vec!["https://github.com/acme/widget".into()],
            canonical_repo_url: None,
            review_md: false,
            force: false,
        },
    )
    .expect("claim scaffold succeeds");

    let err = cmd_claim_event(
        root.clone(),
        ClaimEventArgs {
            path: PathBuf::from(
                "repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-03",
            ),
            kind: ClaimEventKindArg::Accepted,
            actor: "index-reviewer".into(),
            summary: "Accepted maintainer claim.".into(),
            corrected_state: None,
            canonical_record_path: None,
            canonical_mirror_path: None,
        },
    )
    .expect_err("draft claim should not accept directly");
    assert!(err
        .to_string()
        .contains("accepted events are only valid for submitted or in_review claims"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn claim_event_records_canonical_handoff_links() {
    let root = temp_dir("claim-event-handoff");
    let repo_dir = root.join("repos/github.com/acme/widget");
    fs::create_dir_all(&repo_dir).expect("repo dir created");
    fs::write(repo_dir.join("record.toml"), "schema = \"dotrepo/v0.1\"\n").expect("record written");
    cmd_claim_init(
        root.clone(),
        ClaimInitArgs {
            host: "github.com".into(),
            owner: "acme".into(),
            repo: "widget".into(),
            claim_id: "2026-03-10-maintainer-claim-03".into(),
            claimant_name: "Acme maintainers".into(),
            asserted_role: "maintainer".into(),
            contact: None,
            record_sources: vec!["https://github.com/acme/widget".into()],
            canonical_repo_url: Some("https://github.com/acme/widget".into()),
            review_md: false,
            force: false,
        },
    )
    .expect("claim scaffold succeeds");

    let claim_dir = root.join("repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-03");
    let claim_path =
        PathBuf::from("repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-03");
    cmd_claim_event(
        root.clone(),
        ClaimEventArgs {
            path: claim_path.clone(),
            kind: ClaimEventKindArg::Submitted,
            actor: "claimant".into(),
            summary: "Submitted maintainer claim.".into(),
            corrected_state: None,
            canonical_record_path: None,
            canonical_mirror_path: None,
        },
    )
    .expect("submitted event succeeds");
    cmd_claim_event(
        root.clone(),
        ClaimEventArgs {
            path: claim_path,
            kind: ClaimEventKindArg::Accepted,
            actor: "index-reviewer".into(),
            summary: "Accepted maintainer claim after review.".into(),
            corrected_state: None,
            canonical_record_path: Some(".repo".into()),
            canonical_mirror_path: Some("repos/github.com/acme/widget/record.toml".into()),
        },
    )
    .expect("accepted handoff succeeds");

    let report = inspect_claim_directory(&root, &claim_dir).expect("claim inspection works");
    assert_eq!(report.target.handoff, Some(ClaimHandoffOutcome::Superseded));
    let resolution = report.resolution.expect("resolution recorded");
    assert_eq!(resolution.canonical_record_path.as_deref(), Some(".repo"));
    assert_eq!(
        resolution.canonical_mirror_path.as_deref(),
        Some("repos/github.com/acme/widget/record.toml")
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn query_raw_should_refuse_competing_records() {
    let root = temp_dir("query-raw-conflict");
    fs::write(
        root.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "selected"
"#,
    )
    .expect("root overlay written");
    let alt = root.join("alt");
    fs::create_dir_all(&alt).expect("alt dir created");
    fs::write(
        alt.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "competing"
"#,
    )
    .expect("competing overlay written");

    let err = cmd_query(root.clone(), "repo.description", false, true)
        .expect_err("raw conflict should fail");
    assert!(err.to_string().contains("competing records"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn format_trust_report_explains_canonical_handoff_plainly() {
    let root = temp_dir("trust-conflict-report");
    fs::write(
        root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[record.trust]
confidence = "high"
provenance = ["declared"]
notes = "Maintainer-authored root record."

[repo]
name = "orbit"
description = "Canonical project record"
homepage = "https://github.com/example/orbit"
"#,
    )
    .expect("canonical manifest written");
    let overlay_dir = root.join("repos/github.com/example/orbit");
    fs::create_dir_all(&overlay_dir).expect("overlay dir created");
    fs::write(
        overlay_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["imported", "verified"]
notes = "Reviewed overlay retained for audit history."

[repo]
name = "orbit"
description = "Reviewed overlay"
"#,
    )
    .expect("overlay manifest written");

    let report = trust_repository(&root).expect("trust report");
    let rendered = format_trust_report(&report);
    assert!(rendered.contains("selected: .repo (Native, Canonical)"));
    assert!(rendered.contains(
        "selection reason: canonical record preferred over lower-authority competing records"
    ));
    assert!(rendered.contains("conflicts:"));
    assert!(rendered.contains("- repos/github.com/example/orbit/record.toml (Overlay, Reviewed)"));
    assert!(rendered.contains("relationship: superseded"));
    assert!(rendered
        .contains("reason: canonical record preferred over lower-authority competing records"));
    assert!(rendered.contains("provenance: imported, verified"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn format_trust_report_explains_equal_authority_conflicts() {
    let root = temp_dir("trust-equal-authority-report");
    let first = root.join("a");
    let second = root.join("b");
    fs::create_dir_all(&first).expect("first dir created");
    fs::create_dir_all(&second).expect("second dir created");
    fs::write(
        first.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "First reviewed overlay"
"#,
    )
    .expect("first manifest written");
    fs::write(
        second.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Second reviewed overlay"
"#,
    )
    .expect("second manifest written");

    let report = trust_repository(&root).expect("trust report");
    let rendered = format_trust_report(&report);
    assert!(rendered.contains(
            "selection reason: equal-authority conflict; selected by stable path ordering while preserving competing records"
        ));
    assert!(rendered.contains("relationship: parallel"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn validate_index_allows_warning_only_runs() {
    let root = temp_dir("index-warning");
    let record_dir = root.join("repos/github.com/example/project");
    fs::create_dir_all(&record_dir).expect("record dir created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://github.com/example/project"

[record.trust]
confidence = "medium"
provenance = ["imported"]

[repo]
name = "project"
description = "Example project"
homepage = "https://github.com/example/project"

[owners]
security_contact = "unknown"
"#,
    )
    .expect("record written");
    fs::write(
        record_dir.join("evidence.md"),
        "# Evidence\n\n- Imported from the upstream repository.\n",
    )
    .expect("evidence written");

    cmd_validate_index(root.clone()).expect("warning-only index should pass");

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn validate_index_fails_on_structural_errors() {
    let root = temp_dir("index-error");
    let record_dir = root.join("repos/github.com/example/project");
    fs::create_dir_all(&record_dir).expect("record dir created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "project"
description = "Example project"
homepage = "https://github.com/example/project"
"#,
    )
    .expect("record written");

    let err = cmd_validate_index(root.clone()).expect_err("invalid index should fail");
    let exit = err.downcast_ref::<CliExit>().expect("returns a CliExit");
    assert_eq!(exit.code, 1);
    assert!(exit.message.contains("record.mode = \"overlay\""));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_writes_overlay_manifest_and_evidence() {
    let root = temp_dir("import-overlay");
    fs::write(
        root.join("README.md"),
        "# Example Project\n\nProject summary from the README.\n",
    )
    .expect("README written");
    fs::create_dir_all(root.join(".github")).expect(".github created");
    fs::write(root.join(".github/CODEOWNERS"), "* @example\n").expect("CODEOWNERS written");
    fs::write(
        root.join(".github/SECURITY.md"),
        "Report vulnerabilities to security@example.com.\n",
    )
    .expect("SECURITY written");

    cmd_import(
        root.clone(),
        ImportModeArg::Overlay,
        Some("https://github.com/example/project".into()),
        false,
    )
    .expect("overlay import succeeds");

    let manifest = load_manifest_from_root(&root).expect("manifest loads");
    assert_eq!(manifest.record.mode, dotrepo_schema::RecordMode::Overlay);
    assert_eq!(
        manifest.record.status,
        dotrepo_schema::RecordStatus::Imported
    );
    assert_eq!(manifest.repo.name, "Example Project");
    assert!(root.join("evidence.md").exists());

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn adopt_overlay_bootstraps_native_manifest() {
    let root = temp_dir("adopt-overlay-native");
    let overlay = root.join("overlay-record.toml");
    fs::write(
        &overlay,
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/project"
generated_at = "2026-03-10T18:30:00Z"

[record.trust]
confidence = "medium"
provenance = ["imported", "verified"]
notes = "Reviewed overlay."

[repo]
name = "project"
description = "Reviewed project metadata."
homepage = "https://github.com/example/project"

[docs]
root = "https://docs.example.com/project"
"#,
    )
    .expect("overlay written");

    cmd_adopt_overlay(root.clone(), overlay.clone(), false).expect("adoption succeeds");

    let manifest = load_manifest_from_root(&root).expect("native manifest loads");
    assert_eq!(manifest.record.mode, dotrepo_schema::RecordMode::Native);
    assert_eq!(manifest.record.status, dotrepo_schema::RecordStatus::Draft);
    assert_eq!(manifest.record.source, None);
    assert_eq!(manifest.record.generated_at, None);
    assert_eq!(manifest.repo.name, "project");
    assert!(manifest.docs.is_none());
    let trust = manifest.record.trust.clone().expect("adoption trust note");
    assert_eq!(trust.confidence, Some("low".into()));
    assert_eq!(trust.provenance, vec!["imported".to_string()]);
    let notes = trust.notes.expect("trust notes");
    assert!(notes.contains("maintainers should review before claiming canonical authority"));
    assert!(notes.contains("documentation URLs were omitted"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn adopt_overlay_refuses_existing_repo_without_force() {
    let root = temp_dir("adopt-overlay-no-force");
    let overlay = root.join("overlay-record.toml");
    fs::write(root.join(".repo"), "existing\n").expect("existing native record written");
    fs::write(
        &overlay,
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"

[repo]
name = "project"
description = "Reviewed project metadata."
"#,
    )
    .expect("overlay written");

    let err = cmd_adopt_overlay(root.clone(), overlay, false).expect_err("adoption should fail");
    assert!(err.to_string().contains("already exists"));
    assert_eq!(
        fs::read_to_string(root.join(".repo")).expect("native record readable"),
        "existing\n"
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn adopt_overlay_rejects_non_overlay_record() {
    let root = temp_dir("adopt-overlay-wrong-mode");
    let native = root.join("native-record.toml");
    fs::write(
        &native,
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "draft"

[repo]
name = "project"
description = "Native project metadata."
"#,
    )
    .expect("native record written");

    let err = cmd_adopt_overlay(root.clone(), native, false).expect_err("native should fail");
    assert!(err.to_string().contains("record.mode = \"overlay\""));
    assert!(!root.join(".repo").exists());

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn write_import_output_refuses_to_clobber_existing_file_without_force() {
    let root = temp_dir("import-output-no-force");
    let path = root.join(".repo");
    fs::write(&path, "existing\n").expect("existing file written");

    let err = write_import_outputs(
        vec![(path.clone(), "replacement\n".into())],
        false,
        "--force",
    )
    .expect_err("existing file should be preserved");
    assert!(err.to_string().contains("already exists"));
    assert_eq!(
        fs::read_to_string(&path).expect("file readable"),
        "existing\n"
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_refuses_existing_evidence_without_leaving_partial_manifest() {
    let root = temp_dir("import-no-partial-manifest");
    fs::write(
        root.join("README.md"),
        "# Example Project\n\nProject summary from the README.\n",
    )
    .expect("README written");
    fs::write(root.join("evidence.md"), "preexisting evidence\n").expect("evidence written");

    let err = cmd_import(
        root.clone(),
        ImportModeArg::Overlay,
        Some("https://github.com/example/project".into()),
        false,
    )
    .expect_err("import should refuse preexisting evidence");

    assert!(err.to_string().contains("already exists"));
    assert!(!root.join("record.toml").exists());
    assert_eq!(
        fs::read_to_string(root.join("evidence.md")).expect("evidence readable"),
        "preexisting evidence\n"
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn generate_refuses_overlay_records() {
    let root = temp_dir("generate-overlay");
    fs::write(
        root.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://github.com/example/project"

[record.trust]
confidence = "medium"
provenance = ["imported"]

[repo]
name = "project"
description = "Example project"
"#,
    )
    .expect("record written");

    let err = cmd_generate(root.clone(), false).expect_err("overlay generate should fail");
    let exit = err.downcast_ref::<CliExit>().expect("returns a CliExit");
    assert_eq!(exit.code, 2);
    assert!(exit
        .message
        .contains("generate is only supported for native records"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn generate_check_refuses_overlay_records() {
    let root = temp_dir("generate-check-overlay");
    fs::write(
        root.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://github.com/example/project"

[record.trust]
confidence = "medium"
provenance = ["imported"]

[repo]
name = "project"
description = "Example project"
"#,
    )
    .expect("record written");

    let err = cmd_generate(root.clone(), true).expect_err("overlay generate-check should fail");
    let exit = err.downcast_ref::<CliExit>().expect("returns a CliExit");
    assert_eq!(exit.code, 2);
    assert!(exit
        .message
        .contains("generate-check is only supported for native records"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn doctor_refuses_overlay_records() {
    let root = temp_dir("doctor-overlay");
    fs::write(
        root.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/project"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "project"
description = "Example project"
"#,
    )
    .expect("record written");

    let err = cmd_doctor(root.clone(), false).expect_err("overlay doctor should fail");
    let exit = err.downcast_ref::<CliExit>().expect("returns a CliExit");
    assert_eq!(exit.code, 2);
    assert!(exit
        .message
        .contains("doctor is only supported for native records"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn validate_reports_multiple_diagnostics() {
    let root = temp_dir("validate-many");
    fs::write(
        root.join("record.toml"),
        r#"
schema = "dotrepo/v9.9"

[record]
mode = "overlay"
status = "imported"

[repo]
name = " "
description = "Broken overlay"
"#,
    )
    .expect("record written");

    let err = cmd_validate(root.clone()).expect_err("invalid manifest should fail");
    let exit = err.downcast_ref::<CliExit>().expect("returns a CliExit");
    assert!(exit.message.contains("unsupported schema"));
    assert!(exit.message.contains("repo.name must not be empty"));
    assert!(exit.message.contains("record.source must be set"));
    assert!(exit.message.contains("record.trust must be set"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn public_export_writes_static_repository_and_trust_json() {
    let root = temp_dir("public-export");
    let index_root = root.join("index");
    let record_dir = index_root.join("repos/github.com/example/orbit");
    fs::create_dir_all(&record_dir).expect("record dir created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Reviewed overlay"
"#,
    )
    .expect("record written");
    fs::write(record_dir.join("evidence.md"), "# Evidence\n").expect("evidence written");

    let out_dir = root.join("public");
    cmd_public(PublicCommand::Export {
        index_root: index_root.clone(),
        out_dir: out_dir.clone(),
        base_path: "/".into(),
        stale_after_hours: Some(24),
        generated_at: None,
        stale_after: None,
        pagedigest_previous: None,
    })
    .expect("public export succeeds");

    assert!(out_dir.join("v0/meta.json").exists());
    assert!(out_dir
        .join("v0/repos/github.com/example/orbit/index.json")
        .exists());
    assert!(out_dir
        .join("v0/repos/github.com/example/orbit/trust.json")
        .exists());
    assert!(out_dir
        .join("query-input/github.com/example/orbit.json")
        .exists());

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn public_export_honors_base_path_in_inventory_links() {
    let root = temp_dir("public-export-base-path");
    let index_root = root.join("index");
    let record_dir = index_root.join("repos/github.com/example/orbit");
    fs::create_dir_all(&record_dir).expect("record dir created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Reviewed overlay"
"#,
    )
    .expect("record written");
    fs::write(record_dir.join("evidence.md"), "# Evidence\n").expect("evidence written");

    let out_dir = root.join("public");
    cmd_public(PublicCommand::Export {
        index_root: index_root.clone(),
        out_dir: out_dir.clone(),
        base_path: "/dotrepo".into(),
        stale_after_hours: Some(24),
        generated_at: None,
        stale_after: None,
        pagedigest_previous: None,
    })
    .expect("public export succeeds");

    let inventory = fs::read_to_string(out_dir.join("v0/repos/index.json")).expect("inventory");
    assert!(
        inventory.contains("\"self\": \"/dotrepo/v0/repos/github.com/example/orbit/index.json\"")
    );
    assert!(
        inventory.contains("\"trust\": \"/dotrepo/v0/repos/github.com/example/orbit/trust.json\"")
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn public_freshness_reuses_snapshot_digest() {
    let root = temp_dir("public-freshness");
    let index_root = root.join("index");
    let record_dir = index_root.join("repos/github.com/example/orbit");
    fs::create_dir_all(&record_dir).expect("record dir created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Reviewed overlay"
"#,
    )
    .expect("record written");
    fs::write(record_dir.join("evidence.md"), "# Evidence\n").expect("evidence written");

    let digest = index_snapshot_digest(&index_root).expect("snapshot digest");
    let freshness =
        current_public_freshness(&index_root, Some(24)).expect("public freshness builds");
    assert_eq!(freshness.snapshot_digest, digest);
    assert!(freshness.stale_after.is_some());

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn deterministic_public_export_repeats_byte_for_byte() {
    let root = temp_dir("public-export-deterministic");
    let index_root = root.join("index");
    let record_dir = index_root.join("repos/github.com/example/orbit");
    fs::create_dir_all(&record_dir).expect("record dir created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Reviewed overlay"
"#,
    )
    .expect("record written");
    fs::write(record_dir.join("evidence.md"), "# Evidence\n").expect("evidence written");

    let out_a = root.join("public-a");
    let out_b = root.join("public-b");
    let generated_at = "2026-03-10T18:30:00Z".to_string();
    let stale_after = "2026-03-11T18:30:00Z".to_string();

    cmd_public(PublicCommand::Export {
        index_root: index_root.clone(),
        out_dir: out_a.clone(),
        base_path: "/".into(),
        stale_after_hours: None,
        generated_at: Some(generated_at.clone()),
        stale_after: Some(stale_after.clone()),
        pagedigest_previous: None,
    })
    .expect("first deterministic export succeeds");
    cmd_public(PublicCommand::Export {
        index_root: index_root.clone(),
        out_dir: out_b.clone(),
        base_path: "/".into(),
        stale_after_hours: None,
        generated_at: Some(generated_at),
        stale_after: Some(stale_after),
        pagedigest_previous: None,
    })
    .expect("second deterministic export succeeds");

    assert_eq!(read_tree(&out_a), read_tree(&out_b));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn deterministic_public_export_requires_generated_at_for_fixed_stale_after() {
    let root = temp_dir("public-export-invalid");
    let index_root = root.join("index");
    let record_dir = index_root.join("repos/github.com/example/orbit");
    fs::create_dir_all(&record_dir).expect("record dir created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Reviewed overlay"
"#,
    )
    .expect("record written");
    fs::write(record_dir.join("evidence.md"), "# Evidence\n").expect("evidence written");

    let err = cmd_public(PublicCommand::Export {
        index_root: index_root.clone(),
        out_dir: root.join("public"),
        base_path: "/".into(),
        stale_after_hours: None,
        generated_at: None,
        stale_after: Some("2026-03-11T18:30:00Z".into()),
        pagedigest_previous: None,
    })
    .expect_err("fixed stale-after without generated-at should fail");
    assert!(
        err.to_string()
            .contains("--stale-after requires --generated-at"),
        "unexpected error: {err}"
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

fn read_tree(root: &PathBuf) -> Vec<(String, String)> {
    let mut paths = Vec::new();
    collect_files(root, &mut paths);
    paths
        .into_iter()
        .map(|path| {
            (
                path.strip_prefix(root)
                    .expect("relative path")
                    .display()
                    .to_string(),
                fs::read_to_string(&path).expect("file is readable"),
            )
        })
        .collect()
}

fn collect_files(root: &PathBuf, out: &mut Vec<PathBuf>) {
    let mut entries = fs::read_dir(root)
        .expect("directory exists")
        .filter_map(|entry| entry.ok())
        .map(|entry| entry.path())
        .collect::<Vec<_>>();
    entries.sort();

    for path in entries {
        if path.is_dir() {
            collect_files(&path, out);
        } else {
            out.push(path);
        }
    }
}

fn temp_dir(label: &str) -> PathBuf {
    let unique = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("clock works")
        .as_nanos();
    let path = std::env::temp_dir().join(format!(
        "dotrepo-cli-{}-{}-{}",
        label,
        std::process::id(),
        unique
    ));
    fs::create_dir_all(&path).expect("temp dir created");
    path
}
