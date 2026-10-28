#![cfg(any(unix, windows))]
use std::fs;
#[cfg(unix)]
use std::os::unix::fs::{symlink as symlink_dir, symlink as symlink_file};
#[cfg(windows)]
use std::os::windows::fs::{symlink_dir, symlink_file};
use std::path::{Path, PathBuf};
use std::process::{Command, Output};
use std::sync::atomic::{AtomicU64, Ordering};

static NEXT: AtomicU64 = AtomicU64::new(0);
const MANIFEST: &str = r#"schema = "dotrepo/v0.1"
[record]
mode = "native"
status = "draft"
[repo]
name = "fixture"
description = "Fixture project"
[compat.github]
codeowners = "generate"
"#;

struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!(
            "dotrepo-write-cli-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir_all(path.join("checkout")).unwrap();
        fs::create_dir_all(path.join("outside")).unwrap();
        fs::write(path.join("checkout/.repo"), MANIFEST).unwrap();
        Self(path)
    }
    fn root(&self) -> PathBuf {
        self.0.join("checkout")
    }
    fn sentinel(&self, name: &str) -> PathBuf {
        let path = self.0.join("outside").join(name);
        fs::write(&path, "EXTERNAL SENTINEL\n").unwrap();
        path
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
fn run(root: &Path, args: &[&str]) -> Output {
    let output = Command::new(env!("CARGO_BIN_EXE_dotrepo"))
        .arg("--root")
        .arg(root)
        .args(args)
        .output()
        .unwrap();
    if !output.status.success() {
        eprintln!("{args:?}: {}", String::from_utf8_lossy(&output.stderr));
    }
    output
}

fn remove_directory_link(path: &Path) {
    #[cfg(unix)]
    fs::remove_file(path).unwrap();
    #[cfg(windows)]
    fs::remove_dir(path).unwrap();
}

#[test]
fn generate_rejects_leaf_parent_and_hardlink_without_changing_other_outputs() {
    for kind in ["leaf", "parent", "hardlink"] {
        let f = Fixture::new();
        let sentinel = f.sentinel("CODEOWNERS");
        if kind == "parent" {
            symlink_dir(f.0.join("outside"), f.root().join(".github")).unwrap();
        } else {
            fs::create_dir(f.root().join(".github")).unwrap();
            if kind == "leaf" {
                symlink_file(&sentinel, f.root().join(".github/CODEOWNERS")).unwrap();
            } else {
                fs::hard_link(&sentinel, f.root().join(".github/CODEOWNERS")).unwrap();
            }
        }
        assert!(!run(&f.root(), &["generate"]).status.success());
        assert_eq!(fs::read_to_string(sentinel).unwrap(), "EXTERNAL SENTINEL\n");
        assert!(!f.root().join("README.md").exists());
    }
    let f = Fixture::new();
    assert!(run(&f.root(), &["generate"]).status.success());
    assert!(run(&f.root(), &["generate", "--check"]).status.success());
}

#[test]
fn init_ci_and_manage_cannot_write_through_links() {
    let f = Fixture::new();
    let missing = f.0.join("outside/missing");
    fs::remove_file(f.root().join(".repo")).unwrap();
    symlink_file(&missing, f.root().join(".repo")).unwrap();
    assert!(!run(&f.root(), &["init"]).status.success());
    assert!(!missing.exists());
    fs::remove_file(f.root().join(".repo")).unwrap();
    fs::write(f.root().join(".repo"), MANIFEST).unwrap();
    symlink_dir(f.0.join("outside"), f.root().join(".github")).unwrap();
    assert!(!run(&f.root(), &["ci", "init"]).status.success());
    assert!(!f.0.join("outside/workflows").exists());
    let sentinel = f.sentinel("README.md");
    symlink_file(&sentinel, f.root().join("README.md")).unwrap();
    assert!(!run(&f.root(), &["manage", "readme", "--adopt"])
        .status
        .success());
    assert_eq!(fs::read_to_string(sentinel).unwrap(), "EXTERNAL SENTINEL\n");
}

const CLAIM_ARGS: &[&str] = &[
    "claim-init",
    "--host",
    "github.com",
    "--owner",
    "acme",
    "--repo",
    "widget",
    "--claim-id",
    "fixture-claim",
    "--claimant-name",
    "Fixture",
    "--asserted-role",
    "maintainer",
];

#[test]
fn claims_reject_symlinked_ancestors_events_and_event_leaf() {
    let f = Fixture::new();
    fs::create_dir_all(f.0.join("outside/github.com/acme/widget")).unwrap();
    fs::write(
        f.0.join("outside/github.com/acme/widget/record.toml"),
        MANIFEST,
    )
    .unwrap();
    symlink_dir(f.0.join("outside"), f.root().join("repos")).unwrap();
    assert!(!run(&f.root(), CLAIM_ARGS).status.success());
    assert!(!f.0.join("outside/github.com/acme/widget/claims").exists());
    remove_directory_link(&f.root().join("repos"));
    fs::create_dir_all(f.root().join("repos/github.com/acme/widget")).unwrap();
    fs::write(
        f.root().join("repos/github.com/acme/widget/record.toml"),
        MANIFEST,
    )
    .unwrap();
    assert!(run(&f.root(), CLAIM_ARGS).status.success());
    let relative = "repos/github.com/acme/widget/claims/fixture-claim";
    let claim = f.root().join(relative);
    let before = fs::read(claim.join("claim.toml")).unwrap();
    fs::remove_dir(claim.join("events")).unwrap();
    symlink_dir(f.0.join("outside"), claim.join("events")).unwrap();
    let event = [
        "claim-event",
        relative,
        "--kind",
        "submitted",
        "--actor",
        "fixture",
        "--summary",
        "submit",
    ];
    assert!(!run(&f.root(), &event).status.success());
    assert_eq!(fs::read(claim.join("claim.toml")).unwrap(), before);
    remove_directory_link(&claim.join("events"));
    fs::create_dir(claim.join("events")).unwrap();
    let sentinel = f.sentinel("event");
    symlink_file(&sentinel, claim.join("events/0001-submitted.toml")).unwrap();
    assert!(!run(&f.root(), &event).status.success());
    assert_eq!(fs::read_to_string(sentinel).unwrap(), "EXTERNAL SENTINEL\n");
    assert_eq!(fs::read(claim.join("claim.toml")).unwrap(), before);
}

#[test]
fn force_scaffold_preserves_history_refusal_and_removes_only_optional_review() {
    let f = Fixture::new();
    fs::create_dir_all(f.root().join("repos/github.com/acme/widget")).unwrap();
    fs::write(
        f.root().join("repos/github.com/acme/widget/record.toml"),
        MANIFEST,
    )
    .unwrap();
    let mut args = CLAIM_ARGS.to_vec();
    args.push("--review-md");
    assert!(run(&f.root(), &args).status.success());
    let claim = f
        .root()
        .join("repos/github.com/acme/widget/claims/fixture-claim");
    assert!(claim.join("review.md").exists());
    let mut args = CLAIM_ARGS.to_vec();
    args.push("--force");
    assert!(run(&f.root(), &args).status.success());
    assert!(!claim.join("review.md").exists());
    assert!(claim.join("events").is_dir());
    fs::write(claim.join("events/history.toml"), "history").unwrap();
    assert!(!run(&f.root(), &args).status.success());
    assert_eq!(
        fs::read_to_string(claim.join("events/history.toml")).unwrap(),
        "history"
    );
}

#[cfg(unix)]
#[test]
fn large_public_exports_keep_file_descriptor_use_bounded() {
    let f = Fixture::new();
    for index in 0..30 {
        let record = f
            .root()
            .join(format!("repos/github.com/example/repo{index}"));
        fs::create_dir_all(&record).unwrap();
        fs::write(
            record.join("record.toml"),
            format!(
                r#"schema = "dotrepo/v0.1"
[record]
mode = "overlay"
status = "imported"
source = "https://github.com/example/repo{index}"
[record.trust]
confidence = "medium"
provenance = ["imported"]
[repo]
name = "repo{index}"
description = "Ordinary export fixture."
"#
            ),
        )
        .unwrap();
    }
    let output = f.0.join("public");
    let result = Command::new("sh")
        .args(["-c", "ulimit -n 256; exec \"$@\"", "bounded-export"])
        .env("RAYON_NUM_THREADS", "2")
        .arg(env!("CARGO_BIN_EXE_dotrepo"))
        .args(["public", "export", "--index-root"])
        .arg(f.root())
        .arg("--out-dir")
        .arg(&output)
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    assert!(output
        .join("v0/repos/github.com/example/repo29/profile.json")
        .is_file());
}
