use serde_json::Value;
use std::path::PathBuf;
use std::process::Command;

fn fixture_index_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("dotrepo-core")
        .join("tests")
        .join("fixtures")
        .join("public-export")
        .join("fixture-index")
}

fn dotrepo_bin() -> &'static str {
    env!("CARGO_BIN_EXE_dotrepo")
}

fn run_public(args: &[&str]) -> std::process::Output {
    Command::new(dotrepo_bin())
        .args(args)
        .output()
        .expect("dotrepo command runs")
}

fn parse_stdout_json(output: &std::process::Output) -> Value {
    serde_json::from_slice(&output.stdout).expect("stdout contains json")
}

#[test]
fn public_query_success_prints_json_to_stdout() {
    let index_root = fixture_index_root();
    let output = run_public(&[
        "public",
        "query",
        "github.com",
        "example",
        "nova",
        "repo.description",
        "--index-root",
        index_root.to_str().expect("fixture path is utf-8"),
    ]);

    assert!(output.status.success(), "command should succeed");
    assert!(output.stderr.is_empty(), "success should not write stderr");

    let json = parse_stdout_json(&output);
    assert_eq!(json["apiVersion"], Value::String("v0".into()));
    assert_eq!(
        json["selection"]["record"]["claim"]["handoff"],
        Value::String("pending_canonical".into())
    );
}

#[test]
fn public_summary_honors_base_path_in_links() {
    let index_root = fixture_index_root();
    let output = run_public(&[
        "public",
        "summary",
        "github.com",
        "example",
        "orbit",
        "--index-root",
        index_root.to_str().expect("fixture path is utf-8"),
        "--base-path",
        "/dotrepo",
    ]);

    assert!(output.status.success(), "command should succeed");
    assert!(output.stderr.is_empty(), "success should not write stderr");

    let json = parse_stdout_json(&output);
    assert_eq!(
        json["links"]["self"],
        Value::String("/dotrepo/v0/repos/github.com/example/orbit".into())
    );
    assert_eq!(
        json["links"]["trust"],
        Value::String("/dotrepo/v0/repos/github.com/example/orbit/trust".into())
    );
}

#[test]
fn public_query_missing_path_prints_json_error_and_exit_code_1() {
    let index_root = fixture_index_root();
    let output = run_public(&[
        "public",
        "query",
        "github.com",
        "example",
        "orbit",
        "repo.missing_field",
        "--index-root",
        index_root.to_str().expect("fixture path is utf-8"),
    ]);

    assert_eq!(output.status.code(), Some(1));
    assert!(
        output.stderr.is_empty(),
        "public error json should not be duplicated on stderr"
    );

    let json = parse_stdout_json(&output);
    assert_eq!(
        json["error"]["code"],
        Value::String("query_path_not_found".into())
    );
    assert_eq!(json["path"], Value::String("repo.missing_field".into()));
}

#[test]
fn public_summary_missing_repo_prints_json_error_and_exit_code_1() {
    let index_root = fixture_index_root();
    let output = run_public(&[
        "public",
        "summary",
        "github.com",
        "missing",
        "repo",
        "--index-root",
        index_root.to_str().expect("fixture path is utf-8"),
    ]);

    assert_eq!(output.status.code(), Some(1));
    assert!(
        output.stderr.is_empty(),
        "public error json should not be duplicated on stderr"
    );

    let json = parse_stdout_json(&output);
    assert_eq!(
        json["error"]["code"],
        Value::String("repository_not_found".into())
    );
    assert!(
        json.get("path").is_none(),
        "summary failures should not include a query path"
    );
}

#[test]
fn public_trust_invalid_identity_prints_json_error_and_exit_code_1() {
    let index_root = fixture_index_root();
    let output = run_public(&[
        "public",
        "trust",
        "github.com",
        "example/nested",
        "orbit",
        "--index-root",
        index_root.to_str().expect("fixture path is utf-8"),
    ]);

    assert_eq!(output.status.code(), Some(1));
    assert!(
        output.stderr.is_empty(),
        "public error json should not be duplicated on stderr"
    );

    let json = parse_stdout_json(&output);
    assert_eq!(
        json["error"]["code"],
        Value::String("invalid_repository_identity".into())
    );
    assert!(
        json.get("path").is_none(),
        "trust failures should not include a query path"
    );
}
