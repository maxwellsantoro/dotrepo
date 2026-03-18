use std::fs;
use std::path::PathBuf;
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

fn dotrepo_bin() -> &'static str {
    env!("CARGO_BIN_EXE_dotrepo")
}

fn run_dotrepo(args: &[&str]) -> std::process::Output {
    Command::new(dotrepo_bin())
        .args(args)
        .output()
        .expect("dotrepo command runs")
}

fn temp_dir(label: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system time is after unix epoch")
        .as_nanos();
    let root = std::env::temp_dir().join(format!("dotrepo-cli-{label}-{nanos}"));
    fs::create_dir_all(&root).expect("temp dir created");
    root
}

#[test]
fn ci_init_writes_pinned_native_repo_workflow() {
    let root = temp_dir("ci-init");
    fs::write(
        root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "reviewed"

[repo]
name = "example"
description = "Example project"
build = "cargo build --locked"
"#,
    )
    .expect(".repo written");

    let output = run_dotrepo(&[
        "--root",
        root.to_str().expect("temp path is utf-8"),
        "ci",
        "init",
        "--version",
        "1.2.3",
    ]);

    assert!(output.status.success(), "ci init should succeed");
    assert!(output.stderr.is_empty(), "success should not write stderr");

    let workflow =
        fs::read_to_string(root.join(".github/workflows/dotrepo-check.yml")).expect("workflow");
    assert!(workflow.contains("DOTREPO_VERSION: \"1.2.3\""));
    assert!(workflow.contains("https://github.com/maxwellsantoro/dotrepo/releases/download/v1.2.3"));
    assert!(workflow.contains("sha256sum -c"));
    assert!(workflow.contains("dotrepo --root . validate"));
    assert!(workflow.contains("dotrepo --root . query repo.build --raw"));
    assert!(workflow.contains("dotrepo --root . trust"));
    assert!(workflow.contains("dotrepo --root . doctor"));
    assert!(workflow.contains("dotrepo --root . generate --check"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn ci_init_refuses_to_overwrite_without_force() {
    let root = temp_dir("ci-init-force");
    fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir created");
    fs::write(
        root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "reviewed"

[repo]
name = "example"
description = "Example project"
"#,
    )
    .expect(".repo written");
    fs::write(
        root.join(".github/workflows/dotrepo-check.yml"),
        "name: existing\n",
    )
    .expect("workflow written");

    let output = run_dotrepo(&[
        "--root",
        root.to_str().expect("temp path is utf-8"),
        "ci",
        "init",
    ]);

    assert_eq!(output.status.code(), Some(1));
    let stderr = String::from_utf8(output.stderr).expect("stderr is utf-8");
    assert!(stderr.contains("already exists; rerun with --force"));

    let workflow =
        fs::read_to_string(root.join(".github/workflows/dotrepo-check.yml")).expect("workflow");
    assert_eq!(workflow, "name: existing\n");

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn ci_init_refuses_overlay_records() {
    let root = temp_dir("ci-init-overlay");
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

    let output = run_dotrepo(&[
        "--root",
        root.to_str().expect("temp path is utf-8"),
        "ci",
        "init",
    ]);

    assert_eq!(output.status.code(), Some(2));
    let stderr = String::from_utf8(output.stderr).expect("stderr is utf-8");
    assert!(stderr.contains("ci init is only supported for native records"));

    fs::remove_dir_all(root).expect("temp dir removed");
}
