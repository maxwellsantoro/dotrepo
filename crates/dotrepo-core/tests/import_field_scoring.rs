use dotrepo_core::{
    build_adjudication_requests, import_repository, import_repository_with_options,
    score_import_fields, verify_import_plan, FieldConfidence, GitHubSnapshotFacts, ImportMode,
    ImportOptions,
};
use std::fs;
use std::path::PathBuf;

fn fixture_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures")
        .join("import")
}

#[test]
fn known_bad_catalog_examples_are_suspect_and_escalated() {
    let cases = [
        (
            "alist",
            "# discussions\n\nDownload the latest release here.\n",
            "alist",
            "A file list program that supports multiple storage providers.",
        ),
        (
            "v2rayn",
            "# v2rayN\n\nDownload the latest release here.\n",
            "v2rayN",
            "A GUI client for Windows that supports Xray and V2Ray.",
        ),
        (
            "uad",
            "# Universal Android Debloater\n\nDISCLAIMER: Use at your own risk.\n",
            "universal-android-debloater",
            "Cross-platform GUI written in Rust using ADB to debloat Android devices.",
        ),
    ];

    for (case, readme, repo_name, github_description) in cases {
        let root = temp_dir(case);
        fs::write(root.join("README.md"), readme).expect("README");
        let source = format!("https://github.com/example/{repo_name}");
        let plan = import_repository_with_options(
            &root,
            ImportMode::Overlay,
            Some(&source),
            &ImportOptions {
                github: Some(GitHubSnapshotFacts {
                    repo_name: Some(repo_name.into()),
                    description: Some(github_description.into()),
                    topics: vec!["android".into(), "proxy".into(), "storage".into()],
                    ..GitHubSnapshotFacts::default()
                }),
                ..ImportOptions::default()
            },
        )
        .expect("import succeeds");
        let verification = verify_import_plan(&root, &plan, &source);
        let report = score_import_fields(&plan, &verification);

        assert!(!report.summary.suspect.is_empty(), "case {case}");
        assert!(!report.summary.eligible_for_auto_publish, "case {case}");
        let requests = build_adjudication_requests(&report, &plan);
        assert!(
            requests.iter().any(|request| {
                request.field == "repo.name" || request.field == "repo.description"
            }),
            "case {case} should be escalation-visible"
        );
        fs::remove_dir_all(&root).expect("cleanup");
    }
}

#[test]
fn matching_github_metadata_remains_high_confidence() {
    let root = temp_dir("matching-github-metadata");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
    )
    .expect("README");
    let source = "https://github.com/example/orbit";
    let plan = import_repository_with_options(
        &root,
        ImportMode::Overlay,
        Some(source),
        &ImportOptions {
            github: Some(GitHubSnapshotFacts {
                repo_name: Some("orbit".into()),
                description: Some("Release orchestration for multi-service deploys.".into()),
                topics: vec!["release".into(), "orchestration".into()],
                ..GitHubSnapshotFacts::default()
            }),
            ..ImportOptions::default()
        },
    )
    .expect("import succeeds");
    let verification = verify_import_plan(&root, &plan, source);
    let report = score_import_fields(&plan, &verification);

    assert!(report.summary.suspect.is_empty());
    assert_eq!(
        report
            .scores
            .iter()
            .find(|score| score.field == "repo.description")
            .map(|score| &score.confidence),
        Some(&FieldConfidence::HighConfidencePresent)
    );
    fs::remove_dir_all(&root).expect("cleanup");
}

fn temp_dir(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("dotrepo-score-test-{}", name));
    let _ = fs::remove_dir_all(&dir);
    fs::create_dir_all(&dir).expect("temp dir created");
    dir
}

#[test]
fn score_full_signals_all_high() {
    let root = fixture_root().join("full-signals");
    let source = "https://github.com/example/full-signals";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let verification = verify_import_plan(&root, &plan, source);
    let report = score_import_fields(&plan, &verification);

    let high_present: Vec<_> = report
        .scores
        .iter()
        .filter(|s| s.confidence == FieldConfidence::HighConfidencePresent)
        .map(|s| s.field.as_str())
        .collect();
    assert!(
        high_present.contains(&"repo.name"),
        "repo.name should be high confidence, got: {:?}",
        high_present
    );
    assert!(
        high_present.contains(&"repo.description"),
        "repo.description should be high confidence"
    );
}

#[test]
fn score_absent_fields_high_confidence() {
    let root = temp_dir("score-absent-fields");
    fs::write(root.join("README.md"), "# Noop\n\nA tool with nothing.\n").expect("README");

    let source = "https://github.com/example/noop";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let verification = verify_import_plan(&root, &plan, source);
    let report = score_import_fields(&plan, &verification);

    let absent: Vec<_> = report
        .scores
        .iter()
        .filter(|s| s.confidence == FieldConfidence::HighConfidenceAbsent)
        .map(|s| s.field.as_str())
        .collect();
    assert!(
        absent.contains(&"repo.build"),
        "repo.build should be high-confidence absent, got: {:?}",
        absent
    );
    assert!(
        absent.contains(&"repo.test"),
        "repo.test should be high-confidence absent"
    );

    fs::remove_dir_all(&root).expect("cleanup");
}

#[test]
fn score_security_unknown_high_confidence() {
    let root = fixture_root().join("security-contact-unknown");
    let source = "https://github.com/example/security-unknown";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let verification = verify_import_plan(&root, &plan, source);
    let report = score_import_fields(&plan, &verification);

    let security_score = report
        .scores
        .iter()
        .find(|s| s.field == "owners.security_contact")
        .expect("security contact score exists");
    assert_eq!(
        security_score.confidence,
        FieldConfidence::HighConfidenceAbsent,
        "security_contact 'unknown' should be high-confidence absent"
    );
}

#[test]
fn ecosystem_defaults_prevent_auto_publish() {
    // Cargo.toml establishes the ecosystem, not that the conventional build and
    // test commands actually work. Those defaults must require validation.
    let root = temp_dir("score-auto-publish");
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
        !report.summary.eligible_for_auto_publish,
        "ecosystem defaults must not auto-publish; unresolved: {:?}, medium: {:?}",
        report.summary.unresolved, report.summary.medium_confidence_present
    );
    assert!(report
        .summary
        .medium_confidence_present
        .contains(&"repo.build".to_string()));
    assert!(report
        .summary
        .medium_confidence_present
        .contains(&"repo.test".to_string()));

    fs::remove_dir_all(&root).expect("cleanup");
}

#[test]
fn score_unresolved_prevents_auto_publish() {
    let root = temp_dir("score-no-auto-publish");
    fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir");
    fs::write(
        root.join("README.md"),
        "# Conflict\n\nConflicting workflows.\n",
    )
    .expect("README");
    fs::write(
        root.join(".github/workflows/check.yml"),
        "name: Check\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build --workspace\n",
    )
    .expect("check.yml");
    fs::write(
        root.join(".github/workflows/verify.yml"),
        "name: Verify\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build\n",
    )
    .expect("verify.yml");

    let source = "https://github.com/example/conflict";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let verification = verify_import_plan(&root, &plan, source);
    let report = score_import_fields(&plan, &verification);

    assert!(
        !report.summary.eligible_for_auto_publish,
        "expected unresolved fields to prevent auto-publish"
    );
    assert!(
        !report.summary.unresolved.is_empty(),
        "expected some unresolved fields"
    );

    fs::remove_dir_all(&root).expect("cleanup");
}
