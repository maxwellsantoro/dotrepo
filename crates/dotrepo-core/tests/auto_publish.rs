use dotrepo_core::{
    import_repository, promote_to_verified, score_import_fields, verify_import_plan,
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
