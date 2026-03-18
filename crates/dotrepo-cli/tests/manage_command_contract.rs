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
fn manage_adopt_preserves_unmanaged_readme_prose() {
    let root = temp_dir("manage-readme");
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
"#,
    )
    .expect(".repo written");
    fs::write(
        root.join("README.md"),
        "# Local README\n\nThis introduction stays.\n",
    )
    .expect("README written");

    let output = run_dotrepo(&[
        "--root",
        root.to_str().expect("temp path is utf-8"),
        "manage",
        "readme",
        "--adopt",
    ]);

    assert!(output.status.success(), "manage should succeed");
    assert!(output.stderr.is_empty(), "success should not write stderr");

    let stdout = String::from_utf8(output.stdout).expect("stdout is utf-8");
    assert!(stdout.contains("adopted"));

    let readme = fs::read_to_string(root.join("README.md")).expect("README readable");
    assert!(readme.contains("# Local README"));
    assert!(readme.contains("This introduction stays."));
    assert!(readme.contains("<!-- dotrepo:begin id=readme.body -->"));
    assert!(readme.contains("## Overview"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn manage_adopt_preserves_existing_github_security_path() {
    let root = temp_dir("manage-security");
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
security_contact = "security@example.com"

[compat.github]
security = "generate"
"#,
    )
    .expect(".repo written");
    fs::write(
        root.join(".github/SECURITY.md"),
        "Intro stays.\n\nFooter stays.\n",
    )
    .expect("SECURITY written");

    let output = run_dotrepo(&[
        "--root",
        root.to_str().expect("temp path is utf-8"),
        "manage",
        "security",
        "--adopt",
    ]);

    assert!(output.status.success(), "manage should succeed");
    assert!(output.stderr.is_empty(), "success should not write stderr");

    let security = fs::read_to_string(root.join(".github/SECURITY.md")).expect("SECURITY readable");
    assert!(security.contains("Intro stays."));
    assert!(security.contains("Footer stays."));
    assert!(security.contains("<!-- dotrepo:begin id=security.body -->"));
    assert!(security.contains("Please report vulnerabilities to security@example.com."));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn manage_adopt_refuses_pull_request_template() {
    let root = temp_dir("manage-pr-template");
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

[compat.github]
pull_request_template = "generate"
"#,
    )
    .expect(".repo written");
    fs::write(
        root.join(".github/pull_request_template.md"),
        "local template\n",
    )
    .expect("template written");

    let output = run_dotrepo(&[
        "--root",
        root.to_str().expect("temp path is utf-8"),
        "manage",
        "pull-request-template",
        "--adopt",
    ]);

    assert_eq!(output.status.code(), Some(1));
    let stderr = String::from_utf8(output.stderr).expect("stderr is utf-8");
    assert!(stderr.contains("partial management is not supported"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn manage_adopt_refuses_overlay_records() {
    let root = temp_dir("manage-overlay");
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
        "manage",
        "security",
        "--adopt",
    ]);

    assert_eq!(output.status.code(), Some(2));
    let stderr = String::from_utf8(output.stderr).expect("stderr is utf-8");
    assert!(stderr.contains("manage is only supported for native records"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn manage_adopt_refuses_missing_supported_file() {
    let root = temp_dir("manage-missing");
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
security_contact = "security@example.com"

[compat.github]
security = "generate"
"#,
    )
    .expect(".repo written");

    let output = run_dotrepo(&[
        "--root",
        root.to_str().expect("temp path is utf-8"),
        "manage",
        "security",
        "--adopt",
    ]);

    assert_eq!(output.status.code(), Some(1));
    let stderr = String::from_utf8(output.stderr).expect("stderr is utf-8");
    assert!(stderr.contains("manage --adopt` only converts existing files"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn manage_adopt_refuses_security_without_generate_enabled() {
    let root = temp_dir("manage-security-skip");
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
security_contact = "security@example.com"
"#,
    )
    .expect(".repo written");
    fs::write(root.join("SECURITY.md"), "Intro stays.\n").expect("SECURITY written");

    let output = run_dotrepo(&[
        "--root",
        root.to_str().expect("temp path is utf-8"),
        "manage",
        "security",
        "--adopt",
    ]);

    assert_eq!(output.status.code(), Some(1));
    let stderr = String::from_utf8(output.stderr).expect("stderr is utf-8");
    assert!(stderr.contains("security adoption requires compat.github.security = \"generate\""));

    fs::remove_dir_all(root).expect("temp dir removed");
}
