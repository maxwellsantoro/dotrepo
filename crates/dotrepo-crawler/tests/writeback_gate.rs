use dotrepo_core::{
    autonomous_writeback_eligible, import_repository, score_import_fields, verify_import_plan,
    ImportMode,
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
    let root = temp_dir("writeback-vs-auto-publish");
    fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir");
    fs::write(
        root.join("README.md"),
        "# Conflict\n\nConflicting workflows.\n",
    )
    .expect("readme");
    fs::write(
        root.join(".github/workflows/check.yml"),
        "name: Check\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build --workspace\n",
    )
    .expect("check");
    fs::write(
        root.join(".github/workflows/verify.yml"),
        "name: Verify\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build\n",
    )
    .expect("verify");

    let source = "https://github.com/example/writeback-vs-auto-publish";
    let plan =
        import_repository(&root, ImportMode::Overlay, Some(source)).expect("import succeeds");
    let verification = verify_import_plan(&root, &plan, source);
    let scores = score_import_fields(&plan, &verification);

    assert!(autonomous_writeback_eligible(&verification));
    assert!(
        !scores.summary.eligible_for_auto_publish,
        "writeback may proceed while verified auto-publish remains blocked"
    );

    fs::remove_dir_all(root).expect("temp removed");
}

#[test]
fn crawler_writeback_gate_blocks_when_verification_fails() {
    let root = temp_dir("verification-failed");
    fs::write(root.join("README.md"), "# Broken\n\nNo identity.\n").expect("readme");

    let source = "https://github.com/example/broken";
    let plan = import_repository(&root, ImportMode::Overlay, Some(source)).expect("import plan still builds");
    let verification = verify_import_plan(&root, &plan, "https://evil.example/wrong-source");

    assert!(!autonomous_writeback_eligible(&verification));

    fs::remove_dir_all(root).expect("temp removed");
}