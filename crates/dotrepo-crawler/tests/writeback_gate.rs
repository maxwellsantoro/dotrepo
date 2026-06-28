use dotrepo_core::{
    autonomous_writeback_eligible, import_repository_with_options, score_import_fields,
    verify_import_plan, ImportMode, ImportOptions,
};
use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

fn temp_dir(label: &str) -> PathBuf {
    let unique = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("clock works")
        .as_nanos();
    let path = std::env::temp_dir().join(format!(
        "dotrepo-crawler-writeback-gate-{}-{}-{}",
        label,
        std::process::id(),
        unique
    ));
    fs::create_dir_all(&path).expect("temp dir created");
    path
}

#[test]
fn crawler_writeback_gate_allows_partial_overlay_when_verification_passes() {
    let fixture = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../dotrepo-core/tests/fixtures/import/root-conventional-files");
    let source = "https://github.com/example/orbit";
    let plan = import_repository_with_options(
        &fixture,
        ImportMode::Overlay,
        Some(source),
        &ImportOptions {
            generated_at: Some("2026-03-17T12:00:00Z".into()),
        },
    )
    .expect("import succeeds");
    let verification = verify_import_plan(&fixture, &plan, source);
    let scores = score_import_fields(&plan, &verification);

    assert!(autonomous_writeback_eligible(&verification));
    assert!(
        !scores.summary.eligible_for_auto_publish,
        "writeback may proceed while verified auto-publish remains blocked"
    );
}

#[test]
fn crawler_writeback_gate_blocks_when_verification_fails() {
    let root = temp_dir("verification-failed");
    fs::write(root.join("README.md"), "# Broken\n\nNo identity.\n").expect("readme");

    let source = "https://github.com/example/broken";
    let plan = import_repository_with_options(
        &root,
        ImportMode::Overlay,
        Some(source),
        &ImportOptions {
            generated_at: Some("2026-03-17T12:00:00Z".into()),
        },
    )
    .expect("import plan still builds");
    let verification = verify_import_plan(&root, &plan, "https://evil.example/wrong-source");

    assert!(!autonomous_writeback_eligible(&verification));

    fs::remove_dir_all(root).expect("temp removed");
}
