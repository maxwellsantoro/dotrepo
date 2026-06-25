use dotrepo_core::resolve_claim_directory;
use std::fs;
use std::os::unix::fs::symlink;
use std::path::PathBuf;

fn temp_dir(label: &str) -> PathBuf {
    let unique = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("clock")
        .as_nanos();
    let path = std::env::temp_dir().join(format!("dotrepo-path-containment-{label}-{unique}"));
    fs::create_dir_all(&path).expect("temp dir created");
    path
}

#[test]
fn resolve_claim_directory_rejects_absolute_paths() {
    let root = temp_dir("absolute-claim");
    let err = resolve_claim_directory(&root, "/tmp/outside-claim")
        .expect_err("absolute claim paths should be rejected");
    assert!(err.to_string().contains("relative to root"));
    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn resolve_claim_directory_rejects_symlink_escape() {
    let root = temp_dir("symlink-escape");
    let outside = temp_dir("outside-root");
    let claim_dir = root.join("repos/github.com/acme/widget/claims/claim-01");
    fs::create_dir_all(claim_dir.parent().expect("parent")).expect("claim parent created");
    symlink(&outside, &claim_dir).expect("symlink created");

    let err = resolve_claim_directory(&root, "repos/github.com/acme/widget/claims/claim-01")
        .expect_err("symlink escape should be rejected");
    assert!(err.to_string().contains("stay within the repository root"));

    fs::remove_dir_all(root).expect("temp dir removed");
    fs::remove_dir_all(outside).expect("outside dir removed");
}
