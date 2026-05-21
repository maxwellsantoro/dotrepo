use dotrepo_core::{import_repository, verify_import_plan, ImportMode, VerificationSeverity};
use std::fs;
use std::path::PathBuf;

fn fixture_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures")
        .join("import")
}

fn temp_dir(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("dotrepo-verify-test-{}", name));
    let _ = fs::remove_dir_all(&dir);
    fs::create_dir_all(&dir).expect("temp dir created");
    dir
}

#[test]
fn verify_passes_for_full_signals_fixture() {
    let root = fixture_root().join("full-signals");
    let source = "https://github.com/example/full-signals";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let report = verify_import_plan(&root, &plan, source);
    assert!(report.passed, "expected verification to pass");
    let failures: Vec<_> = report
        .checks
        .iter()
        .filter(|c| c.severity == VerificationSeverity::Failure)
        .collect();
    assert!(failures.is_empty(), "unexpected failures: {:?}", failures);
}

#[test]
fn verify_detects_identity_mismatch() {
    let root = fixture_root().join("full-signals");
    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/full-signals"),
    )
    .expect("import succeeds");
    let report = verify_import_plan(&root, &plan, "https://github.com/different/repo");
    assert!(!report.passed);
    assert!(report
        .checks
        .iter()
        .any(|c| c.check_id == "identity/source-mismatch"
            && c.severity == VerificationSeverity::Failure));
}

#[test]
fn verify_records_command_candidates() {
    let root = fixture_root().join("manifest-workflow-conflict");
    let source = "https://github.com/example/manifest-workflow-conflict";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let report = verify_import_plan(&root, &plan, source);

    assert!(
        !report.candidate_provenance.is_empty(),
        "expected candidate provenance entries"
    );
    assert!(
        report
            .candidate_provenance
            .iter()
            .any(|p| p.source_path == "Cargo.toml"),
        "expected Cargo.toml in manifest candidates"
    );
    assert!(
        report
            .candidate_provenance
            .iter()
            .any(|p| p.source_path == ".github/workflows/ci.yml"),
        "expected ci.yml in workflow candidates"
    );
}

#[test]
fn verify_records_unresolved_fields() {
    let root = temp_dir("unresolved-workflow-conflict");
    fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir");
    fs::write(root.join("README.md"), "# Test\n\nA test repo.\n").expect("README");
    fs::write(
        root.join(".github/workflows/ci.yml"),
        "name: CI\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build --workspace\n",
    ).expect("ci.yml");
    fs::write(
        root.join(".github/workflows/release.yml"),
        "name: Release\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build\n",
    ).expect("release.yml");

    let source = "https://github.com/example/unresolved-test";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let report = verify_import_plan(&root, &plan, source);

    assert!(
        report.unresolved_fields.contains(&"repo.build".to_string())
            || report.unresolved_fields.contains(&"repo.test".to_string()),
        "expected unresolved build/test fields, got: {:?}",
        report.unresolved_fields
    );

    fs::remove_dir_all(&root).expect("cleanup");
}

#[test]
fn verify_records_absent_fields() {
    let root = fixture_root().join("no-conventional-surfaces");
    let source = "https://github.com/example/no-commands";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let report = verify_import_plan(&root, &plan, source);

    assert!(
        report.absent_fields.contains(&"repo.build".to_string())
            || report.absent_fields.contains(&"repo.test".to_string()),
        "expected absent build/test fields for repo without manifest or workflows"
    );
}
