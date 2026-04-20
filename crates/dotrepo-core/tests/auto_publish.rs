use dotrepo_core::{
    analyze_index_promotion, import_repository, promote_to_verified, score_import_fields,
    verify_import_plan,
    FieldConfidence, FieldScore, FieldScoreReport, FieldScoreSummary, ImportMode,
};
use dotrepo_schema::{Manifest, Record, RecordMode, RecordStatus, Repo};
use std::fs;

fn temp_dir(name: &str) -> std::path::PathBuf {
    let dir = std::env::temp_dir().join(format!("dotrepo-auto-publish-test-{}", name));
    let _ = fs::remove_dir_all(&dir);
    fs::create_dir_all(&dir).expect("temp dir created");
    dir
}

fn make_eligible_report() -> FieldScoreReport {
    FieldScoreReport {
        scores: vec![
            FieldScore {
                field: "repo.name".into(),
                confidence: FieldConfidence::HighConfidencePresent,
                source: Some("README.md".into()),
                value: Some("test".into()),
                reason: "readme heading".into(),
            },
            FieldScore {
                field: "repo.build".into(),
                confidence: FieldConfidence::HighConfidenceAbsent,
                source: None,
                value: None,
                reason: "no sources".into(),
            },
        ],
        summary: FieldScoreSummary {
            high_confidence_present: vec!["repo.name".into()],
            medium_confidence_present: vec![],
            high_confidence_absent: vec!["repo.build".into()],
            unresolved: vec![],
            eligible_for_auto_publish: true,
        },
    }
}

fn make_unresolved_report() -> FieldScoreReport {
    FieldScoreReport {
        scores: vec![
            FieldScore {
                field: "repo.name".into(),
                confidence: FieldConfidence::HighConfidencePresent,
                source: Some("README.md".into()),
                value: Some("test".into()),
                reason: "readme heading".into(),
            },
            FieldScore {
                field: "repo.build".into(),
                confidence: FieldConfidence::Unresolved,
                source: None,
                value: None,
                reason: "conflicting candidates".into(),
            },
        ],
        summary: FieldScoreSummary {
            high_confidence_present: vec!["repo.name".into()],
            medium_confidence_present: vec![],
            high_confidence_absent: vec![],
            unresolved: vec!["repo.build".into()],
            eligible_for_auto_publish: false,
        },
    }
}

fn make_imported_manifest() -> Manifest {
    Manifest::new(
        Record {
            mode: RecordMode::Overlay,
            status: RecordStatus::Imported,
            source: Some("https://github.com/example/test".into()),
            generated_at: None,
            trust: Some(dotrepo_schema::Trust {
                confidence: Some("medium".into()),
                provenance: vec!["imported".into()],
                notes: Some("Bootstrapped from README.md.".into()),
            }),
        },
        Repo {
            name: "test".into(),
            description: "A test project.".into(),
            homepage: None,
            license: None,
            status: None,
            visibility: None,
            languages: vec![],
            build: None,
            test: None,
            topics: vec![],
        },
    )
}

#[test]
fn promote_eligible_manifest_to_verified() {
    let mut manifest = make_imported_manifest();
    let report = make_eligible_report();

    let outcome = promote_to_verified(&mut manifest, &report);

    assert!(outcome.promoted);
    assert_eq!(outcome.previous_status, "imported");
    assert_eq!(manifest.record.status, RecordStatus::Verified);
    assert!(manifest
        .record
        .trust
        .as_ref()
        .unwrap()
        .provenance
        .contains(&"verified".to_string()));
    assert_eq!(
        manifest
            .record
            .trust
            .as_ref()
            .unwrap()
            .confidence
            .as_deref(),
        Some("high")
    );
}

#[test]
fn promote_does_not_promote_unresolved() {
    let mut manifest = make_imported_manifest();
    let report = make_unresolved_report();

    let outcome = promote_to_verified(&mut manifest, &report);

    assert!(!outcome.promoted);
    assert_eq!(manifest.record.status, RecordStatus::Imported);
}

#[test]
fn promote_does_not_downgrade_reviewed() {
    let mut manifest = Manifest::new(
        Record {
            mode: RecordMode::Overlay,
            status: RecordStatus::Reviewed,
            source: Some("https://github.com/example/test".into()),
            generated_at: None,
            trust: None,
        },
        Repo {
            name: "test".into(),
            description: "A test project.".into(),
            homepage: None,
            license: None,
            status: None,
            visibility: None,
            languages: vec![],
            build: None,
            test: None,
            topics: vec![],
        },
    );
    let report = make_eligible_report();

    let outcome = promote_to_verified(&mut manifest, &report);

    assert!(!outcome.promoted);
    assert_eq!(outcome.previous_status, "reviewed");
    assert_eq!(manifest.record.status, RecordStatus::Reviewed);
}

#[test]
fn promote_does_not_downgrade_canonical() {
    let mut manifest = Manifest::new(
        Record {
            mode: RecordMode::Native,
            status: RecordStatus::Canonical,
            source: None,
            generated_at: None,
            trust: None,
        },
        Repo {
            name: "test".into(),
            description: "A test project.".into(),
            homepage: None,
            license: None,
            status: None,
            visibility: None,
            languages: vec![],
            build: None,
            test: None,
            topics: vec![],
        },
    );
    let report = make_eligible_report();

    let outcome = promote_to_verified(&mut manifest, &report);

    assert!(!outcome.promoted);
    assert_eq!(manifest.record.status, RecordStatus::Canonical);
}

#[test]
fn promote_preserves_existing_trust_notes() {
    let mut manifest = make_imported_manifest();
    manifest.record.trust = Some(dotrepo_schema::Trust {
        confidence: Some("medium".into()),
        provenance: vec!["imported".into()],
        notes: Some("Bootstrapped from README.md.".into()),
    });
    let report = make_eligible_report();

    let outcome = promote_to_verified(&mut manifest, &report);

    assert!(outcome.promoted);
    let notes = manifest
        .record
        .trust
        .as_ref()
        .unwrap()
        .notes
        .as_deref()
        .unwrap();
    assert!(notes.contains("Bootstrapped from README.md"));
    assert!(notes.contains("Auto-promoted to verified"));
}

#[test]
fn end_to_end_eligible_repo_promotes() {
    let root = temp_dir("e2e-promote");
    fs::write(
        root.join("README.md"),
        "# AutoPub\n\nA well-documented project.\n",
    )
    .expect("README");
    fs::write(
        root.join("Cargo.toml"),
        "[package]\nname = \"autopub\"\nversion = \"0.1.0\"\n",
    )
    .expect("Cargo.toml");

    let source = "https://github.com/example/autopub";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let verification = verify_import_plan(&root, &plan, source);
    let report = score_import_fields(&plan, &verification);

    assert!(
        report.summary.eligible_for_auto_publish,
        "expected eligible, got unresolved: {:?}, medium: {:?}",
        report.summary.unresolved, report.summary.medium_confidence_present
    );

    let mut manifest = plan.manifest.clone();
    let outcome = promote_to_verified(&mut manifest, &report);

    assert!(outcome.promoted);
    assert_eq!(manifest.record.status, RecordStatus::Verified);

    fs::remove_dir_all(&root).expect("cleanup");
}

#[test]
fn end_to_end_conflict_repo_does_not_promote() {
    let root = temp_dir("e2e-no-promote");
    fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir");
    fs::write(
        root.join("README.md"),
        "# Conflict\n\nConflicting workflows.\n",
    )
    .expect("README");
    fs::write(
        root.join(".github/workflows/ci.yml"),
        "name: CI\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build --workspace\n",
    ).expect("ci.yml");
    fs::write(
        root.join(".github/workflows/release.yml"),
        "name: Release\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build\n",
    ).expect("release.yml");

    let source = "https://github.com/example/conflict";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let verification = verify_import_plan(&root, &plan, source);
    let report = score_import_fields(&plan, &verification);

    let mut manifest = plan.manifest.clone();
    let outcome = promote_to_verified(&mut manifest, &report);

    assert!(!outcome.promoted);
    assert_eq!(manifest.record.status, RecordStatus::Imported);

    fs::remove_dir_all(&root).expect("cleanup");
}

// ---------------------------------------------------------------------------
// Invariant tests: promotion must never violate these contracts
// ---------------------------------------------------------------------------

#[test]
fn promotion_never_rewrites_field_values() {
    let root = temp_dir("invariant-no-rewrite");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nPolicy-aware release orchestration.\n",
    )
    .expect("README");
    fs::write(
        root.join("Cargo.toml"),
        "[package]\nname = \"orbit\"\nversion = \"0.1.0\"\n",
    )
    .expect("Cargo.toml");

    let source = "https://github.com/example/orbit";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let verification = verify_import_plan(&root, &plan, source);
    let report = score_import_fields(&plan, &verification);

    let pre_name = plan.manifest.repo.name.clone();
    let pre_description = plan.manifest.repo.description.clone();
    let pre_build = plan.manifest.repo.build.clone();
    let pre_test = plan.manifest.repo.test.clone();
    let pre_homepage = plan.manifest.repo.homepage.clone();

    let mut manifest = plan.manifest.clone();
    let _ = promote_to_verified(&mut manifest, &report);

    assert_eq!(manifest.repo.name, pre_name, "name must not change");
    assert_eq!(
        manifest.repo.description, pre_description,
        "description must not change"
    );
    assert_eq!(manifest.repo.build, pre_build, "build must not change");
    assert_eq!(manifest.repo.test, pre_test, "test must not change");
    assert_eq!(
        manifest.repo.homepage, pre_homepage,
        "homepage must not change"
    );

    fs::remove_dir_all(&root).expect("cleanup");
}

#[test]
fn promotion_preserves_imported_provenance_origins() {
    let root = temp_dir("invariant-provenance");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nPolicy-aware release orchestration.\n",
    )
    .expect("README");
    fs::write(
        root.join("Cargo.toml"),
        "[package]\nname = \"orbit\"\nversion = \"0.1.0\"\n",
    )
    .expect("Cargo.toml");

    let source = "https://github.com/example/orbit";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let verification = verify_import_plan(&root, &plan, source);
    let report = score_import_fields(&plan, &verification);

    let mut manifest = plan.manifest.clone();
    let pre_provenance = manifest.record.trust.as_ref().unwrap().provenance.clone();

    let _ = promote_to_verified(&mut manifest, &report);

    let post_provenance = manifest.record.trust.as_ref().unwrap().provenance.clone();

    for entry in &pre_provenance {
        assert!(
            post_provenance.contains(entry),
            "provenance origin '{}' must not be erased, got: {:?}",
            entry,
            post_provenance
        );
    }

    assert!(
        post_provenance.contains(&"verified".to_string()),
        "'verified' should be added to provenance"
    );

    fs::remove_dir_all(&root).expect("cleanup");
}

#[test]
fn promotion_does_not_upgrade_unresolved_fields() {
    let root = temp_dir("invariant-no-upgrade");
    fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir");
    fs::write(
        root.join("README.md"),
        "# Conflict\n\nConflicting workflows.\n",
    )
    .expect("README");
    fs::write(
        root.join(".github/workflows/ci.yml"),
        "name: CI\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build --workspace\n",
    ).expect("ci.yml");
    fs::write(
        root.join(".github/workflows/release.yml"),
        "name: Release\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build\n",
    ).expect("release.yml");

    let source = "https://github.com/example/conflict";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let verification = verify_import_plan(&root, &plan, source);
    let report = score_import_fields(&plan, &verification);

    let mut manifest = plan.manifest.clone();
    let outcome = promote_to_verified(&mut manifest, &report);

    assert!(!outcome.promoted);
    assert!(
        manifest.repo.build.is_none(),
        "build must stay None when unresolved"
    );
    assert!(
        manifest.repo.test.is_none(),
        "test must stay None when unresolved"
    );

    fs::remove_dir_all(&root).expect("cleanup");
}

#[test]
fn promotion_only_touches_status_trust_and_evidence_wording() {
    let root = temp_dir("invariant-scope");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nPolicy-aware release orchestration.\n",
    )
    .expect("README");
    fs::write(
        root.join("Cargo.toml"),
        "[package]\nname = \"orbit\"\nversion = \"0.1.0\"\n",
    )
    .expect("Cargo.toml");

    let source = "https://github.com/example/orbit";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let verification = verify_import_plan(&root, &plan, source);
    let report = score_import_fields(&plan, &verification);

    let mut manifest = plan.manifest.clone();

    let outcome = promote_to_verified(&mut manifest, &report);
    assert!(outcome.promoted);

    assert_eq!(manifest.repo.name, plan.manifest.repo.name);
    assert_eq!(manifest.repo.description, plan.manifest.repo.description);
    assert_eq!(manifest.repo.homepage, plan.manifest.repo.homepage);
    assert_eq!(manifest.repo.build, plan.manifest.repo.build);
    assert_eq!(manifest.repo.test, plan.manifest.repo.test);
    assert_eq!(manifest.repo.license, plan.manifest.repo.license);
    assert_eq!(manifest.repo.languages, plan.manifest.repo.languages);
    assert_eq!(manifest.repo.topics, plan.manifest.repo.topics);
    assert_eq!(
        manifest.owners.as_ref().map(|o| &o.security_contact),
        plan.manifest.owners.as_ref().map(|o| &o.security_contact)
    );
    assert_eq!(
        manifest.owners.as_ref().map(|o| &o.team),
        plan.manifest.owners.as_ref().map(|o| &o.team)
    );
    assert_eq!(
        manifest.docs.as_ref().and_then(|d| d.root.as_ref()),
        plan.manifest.docs.as_ref().and_then(|d| d.root.as_ref())
    );
    assert_eq!(manifest.record.source, plan.manifest.record.source);
    assert_eq!(
        manifest.record.generated_at,
        plan.manifest.record.generated_at
    );
    assert_eq!(manifest.record.mode, plan.manifest.record.mode);
    assert_eq!(manifest.x, plan.manifest.x);

    assert_eq!(manifest.record.status, RecordStatus::Verified);

    fs::remove_dir_all(&root).expect("cleanup");
}

#[test]
fn promotion_does_not_change_record_authority_semantics() {
    let root = temp_dir("invariant-authority");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nPolicy-aware release orchestration.\n",
    )
    .expect("README");
    fs::write(
        root.join("Cargo.toml"),
        "[package]\nname = \"orbit\"\nversion = \"0.1.0\"\n",
    )
    .expect("Cargo.toml");

    let source = "https://github.com/example/orbit";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let verification = verify_import_plan(&root, &plan, source);
    let report = score_import_fields(&plan, &verification);

    let mut manifest = plan.manifest.clone();
    let _ = promote_to_verified(&mut manifest, &report);

    assert_eq!(
        manifest.record.mode,
        RecordMode::Overlay,
        "mode must remain overlay"
    );
    assert_eq!(
        manifest.record.source.as_deref(),
        Some("https://github.com/example/orbit"),
        "source must remain unchanged"
    );

    fs::remove_dir_all(&root).expect("cleanup");
}

#[test]
fn promotion_analysis_includes_malformed_records_as_blocked() {
    let root = temp_dir("promotion-analysis-malformed");
    let repos_root = root.join("repos/github.com/example");

    fs::create_dir_all(repos_root.join("good")).expect("good dir");
    fs::create_dir_all(repos_root.join("bad")).expect("bad dir");

    fs::write(
        repos_root.join("good/record.toml"),
        r#"schema = "dotrepo/v0.1"
[record]
mode = "overlay"
status = "imported"
source = "https://github.com/example/good"

[record.trust]
confidence = "medium"
provenance = ["imported"]

[repo]
name = "good"
description = "good"
homepage = "https://github.com/example/good"
languages = []
topics = []

[relations]
references = []
"#,
    )
    .expect("good record");
    fs::write(repos_root.join("bad/record.toml"), "not toml\n").expect("bad record");

    let report = analyze_index_promotion(&root).expect("promotion analysis succeeds");

    assert_eq!(report.summary.total_records, 2);
    assert_eq!(report.summary.eligible_count, 1);

    let malformed = report
        .records
        .iter()
        .find(|record| record.path.ends_with("github.com/example/bad/record.toml"))
        .expect("malformed record included");
    assert!(!malformed.eligible);
    assert!(
        malformed
            .scores
            .iter()
            .any(|score| score.field == "record.parse"),
        "expected parse blocker, got: {:?}",
        malformed.scores
    );

    fs::remove_dir_all(&root).expect("cleanup");
}

#[test]
fn justfile_only_assignments_do_not_import_as_commands() {
    let root = temp_dir("justfile-assignments");
    fs::write(
        root.join("README.md"),
        "# AssignOnly\n\nUses justfile variables.\n",
    )
    .expect("README");
    fs::write(
        root.join("justfile"),
        "build := \"cargo build\"\ntest := \"cargo test\"\n",
    )
    .expect("justfile");

    let source = "https://github.com/example/assignonly";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");

    assert!(
        plan.manifest.repo.build.is_none(),
        "justfile variable assignments must not be treated as recipes, got build = {:?}",
        plan.manifest.repo.build
    );
    assert!(
        plan.manifest.repo.test.is_none(),
        "justfile variable assignments must not be treated as recipes, got test = {:?}",
        plan.manifest.repo.test
    );

    fs::remove_dir_all(&root).expect("cleanup");
}

#[test]
fn contributing_make_lint_is_not_imported_as_build() {
    let root = temp_dir("contributing-make-lint");
    fs::write(
        root.join("README.md"),
        "# LintOnly\n\nHas CONTRIBUTING with make lint.\n",
    )
    .expect("README");
    fs::write(
        root.join("CONTRIBUTING.md"),
        "# Contributing\n\n## Setup\n\n```bash\nmake lint\nmake fmt\n```\n",
    )
    .expect("CONTRIBUTING");

    let source = "https://github.com/example/lintonly";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");

    assert!(
        plan.manifest.repo.build.is_none(),
        "'make lint' must not be imported as repo.build, got {:?}",
        plan.manifest.repo.build
    );

    fs::remove_dir_all(&root).expect("cleanup");
}
