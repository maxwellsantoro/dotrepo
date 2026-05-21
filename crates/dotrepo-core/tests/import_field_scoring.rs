use dotrepo_core::{
    import_repository, score_import_fields, verify_import_plan, FieldConfidence, ImportMode,
};
use std::fs;
use std::path::PathBuf;

fn fixture_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures")
        .join("import")
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
fn score_auto_publish_eligibility() {
    // A repo with all fields either high-confidence present or high-confidence absent
    // should be eligible for auto-publish.
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
        report.summary.eligible_for_auto_publish,
        "expected auto-publish eligibility, but got unresolved: {:?}, medium: {:?}",
        report.summary.unresolved, report.summary.medium_confidence_present
    );

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
