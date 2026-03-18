use serde_json::Value;
use std::collections::BTreeSet;
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

fn object_keys(value: &Value) -> BTreeSet<String> {
    value.as_object()
        .expect("json value should be an object")
        .keys()
        .cloned()
        .collect()
}

#[test]
fn doctor_json_reports_lossy_generate_recommendations() {
    let root = temp_dir("doctor-json");
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
        "doctor",
        "--json",
    ]);

    assert!(output.status.success(), "doctor --json should succeed");
    assert!(output.stderr.is_empty(), "success should not write stderr");

    let json = parse_stdout_json(&output);
    assert_eq!(json["mode"], Value::String("native".into()));
    assert_eq!(json["status"], Value::String("reviewed".into()));

    let findings = json["findings"]
        .as_array()
        .expect("findings should be an array");
    let contributing = findings
        .iter()
        .find(|finding| finding["surface"] == Value::String("contributing".into()))
        .expect("contributing finding present");

    let expected_keys = BTreeSet::from([
        "advice".to_string(),
        "declaredMode".to_string(),
        "message".to_string(),
        "ownershipHonesty".to_string(),
        "path".to_string(),
        "recommendedMode".to_string(),
        "rendererCoverage".to_string(),
        "state".to_string(),
        "supportsFullGeneration".to_string(),
        "supportsManagedRegions".to_string(),
        "surface".to_string(),
        "wouldDropUnmanagedContent".to_string(),
    ]);
    assert_eq!(object_keys(contributing), expected_keys);

    assert_eq!(
        contributing["ownershipHonesty"],
        Value::String("lossy_full_generation".into())
    );
    assert_eq!(
        contributing["declaredMode"],
        Value::String("generate".into())
    );
    assert_eq!(contributing["supportsManagedRegions"], Value::Bool(true));
    assert_eq!(contributing["supportsFullGeneration"], Value::Bool(true));
    assert_eq!(
        contributing["recommendedMode"],
        Value::String("partially_managed".into())
    );
    assert_eq!(contributing["wouldDropUnmanagedContent"], Value::Bool(true));
    assert_eq!(
        contributing["rendererCoverage"],
        Value::String("stub_only".into())
    );
    assert!(
        contributing["advice"]
            .as_array()
            .expect("advice should be an array")
            .iter()
            .any(|item| item
                .as_str()
                .expect("advice items should be strings")
                .contains("managed regions")
                || item
                    .as_str()
                    .expect("advice items should be strings")
                    .contains("dotrepo preview"))
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}
