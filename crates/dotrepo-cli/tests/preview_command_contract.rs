use serde_json::Value;
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

fn parse_stdout_json(output: &std::process::Output) -> Value {
    serde_json::from_slice(&output.stdout).expect("stdout contains json")
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
fn preview_json_reports_lossy_contributing_replacement() {
    let root = temp_dir("preview-contributing");
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
test = "cargo nextest run --locked"

[owners]
maintainers = ["@alice"]
security_contact = "security@example.com"

[compat.github]
contributing = "generate"
"#,
    )
    .expect(".repo written");
    fs::write(
        root.join("CONTRIBUTING.md"),
        r#"# Contributing

Use the repository-specific release checklist before you open a pull request.
"#,
    )
    .expect("CONTRIBUTING written");

    let output = run_dotrepo(&[
        "--root",
        root.to_str().expect("temp path is utf-8"),
        "preview",
        "--surface",
        "contributing",
        "--json",
    ]);

    assert!(output.status.success(), "preview --json should succeed");
    assert!(output.stderr.is_empty(), "success should not write stderr");

    let json = parse_stdout_json(&output);
    let previews = json["previews"]
        .as_array()
        .expect("previews should be an array");
    assert_eq!(previews.len(), 1);
    let preview = &previews[0];

    assert_eq!(preview["surface"], Value::String("contributing".into()));
    assert_eq!(
        preview["ownershipHonesty"],
        Value::String("lossy_full_generation".into())
    );
    assert_eq!(
        preview["recommendedMode"],
        Value::String("partially_managed".into())
    );
    assert_eq!(preview["wouldDropUnmanagedContent"], Value::Bool(true));
    assert_eq!(preview["fullReplacement"], Value::Bool(true));
    assert_eq!(preview["preservesUnmanagedContent"], Value::Bool(false));
    assert!(preview["proposed"]
        .as_str()
        .expect("proposed is a string")
        .contains("## Before you open a change"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn preview_json_preserves_outer_readme_prose_for_partially_managed_files() {
    let root = temp_dir("preview-readme");
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

[readme]
title = "Example"
tagline = "Managed README"
"#,
    )
    .expect(".repo written");
    fs::write(
        root.join("README.md"),
        r#"Project-specific introduction.

<!-- dotrepo:begin id=readme.body -->
old managed content
<!-- dotrepo:end id=readme.body -->

Repository-specific footer.
"#,
    )
    .expect("README written");

    let output = run_dotrepo(&[
        "--root",
        root.to_str().expect("temp path is utf-8"),
        "preview",
        "--surface",
        "readme",
        "--json",
    ]);

    assert!(output.status.success(), "preview --json should succeed");
    assert!(output.stderr.is_empty(), "success should not write stderr");

    let json = parse_stdout_json(&output);
    let preview = &json["previews"]
        .as_array()
        .expect("previews should be an array")[0];

    assert_eq!(preview["surface"], Value::String("readme".into()));
    assert_eq!(preview["ownershipHonesty"], Value::String("honest".into()));
    assert_eq!(
        preview["recommendedMode"],
        Value::String("partially_managed".into())
    );
    assert_eq!(preview["wouldDropUnmanagedContent"], Value::Bool(false));
    assert_eq!(preview["fullReplacement"], Value::Bool(false));
    assert_eq!(preview["preservesUnmanagedContent"], Value::Bool(true));

    let proposed = preview["proposed"].as_str().expect("proposed is a string");
    assert!(proposed.contains("Project-specific introduction."));
    assert!(proposed.contains("# Example"));
    assert!(proposed.contains("> Managed README"));
    assert!(proposed.contains("Repository-specific footer."));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn preview_json_preserves_outer_security_prose_for_partially_managed_files() {
    let root = temp_dir("preview-security");
    fs::create_dir_all(root.join(".github")).expect(".github created");
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

[owners]
maintainers = ["@alice"]
security_contact = "security@example.com"

[compat.github]
security = "generate"
"#,
    )
    .expect(".repo written");
    fs::write(
        root.join(".github/SECURITY.md"),
        r#"Project-specific introduction.

<!-- dotrepo:begin id=security.body -->
old managed content
<!-- dotrepo:end id=security.body -->

Repository-specific disclosure notes.
"#,
    )
    .expect("SECURITY written");

    let output = run_dotrepo(&[
        "--root",
        root.to_str().expect("temp path is utf-8"),
        "preview",
        "--surface",
        "security",
        "--json",
    ]);

    assert!(output.status.success(), "preview --json should succeed");
    assert!(output.stderr.is_empty(), "success should not write stderr");

    let json = parse_stdout_json(&output);
    let preview = &json["previews"]
        .as_array()
        .expect("previews should be an array")[0];

    assert_eq!(preview["surface"], Value::String("security".into()));
    assert_eq!(preview["ownershipHonesty"], Value::String("honest".into()));
    assert_eq!(
        preview["recommendedMode"],
        Value::String("partially_managed".into())
    );
    assert_eq!(preview["wouldDropUnmanagedContent"], Value::Bool(false));
    assert_eq!(preview["fullReplacement"], Value::Bool(false));
    assert_eq!(preview["preservesUnmanagedContent"], Value::Bool(true));

    let proposed = preview["proposed"].as_str().expect("proposed is a string");
    assert!(proposed.contains("Project-specific introduction."));
    assert!(proposed.contains("Please report vulnerabilities to security@example.com."));
    assert!(proposed.contains("Repository-specific disclosure notes."));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn preview_human_output_explains_all_or_nothing_pull_request_template_behavior() {
    let root = temp_dir("preview-pr-template");
    fs::create_dir_all(root.join(".github")).expect(".github created");
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
test = "cargo nextest run --locked"

[compat.github]
pull_request_template = "generate"
"#,
    )
    .expect(".repo written");
    fs::write(
        root.join(".github/pull_request_template.md"),
        r#"## Type of change

- [ ] Feature
- [ ] Fix

## Repo-specific checks

- [ ] Mention the rollout plan.
"#,
    )
    .expect("PR template written");

    let output = run_dotrepo(&[
        "--root",
        root.to_str().expect("temp path is utf-8"),
        "preview",
        "--surface",
        "pull-request-template",
    ]);

    assert!(output.status.success(), "preview should succeed");
    assert!(output.stderr.is_empty(), "success should not write stderr");

    let stdout = String::from_utf8(output.stdout).expect("stdout is utf-8");
    assert!(stdout.contains("surface: pull_request_template"));
    assert!(stdout.contains("recommended mode: skip"));
    assert!(stdout.contains("replacement mode: full_replacement"));
    assert!(stdout.contains("partial management is not supported"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn preview_refuses_overlay_records() {
    let root = temp_dir("preview-overlay");
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
        "preview",
        "--surface",
        "security",
    ]);

    assert_eq!(output.status.code(), Some(2));
    let stderr = String::from_utf8(output.stderr).expect("stderr is utf-8");
    assert!(stderr.contains("preview is only supported for native records"));

    fs::remove_dir_all(root).expect("temp dir removed");
}
