use serde_json::Value;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};
use std::time::{SystemTime, UNIX_EPOCH};

fn dotrepo_bin() -> &'static str {
    env!("CARGO_BIN_EXE_dotrepo")
}

fn run_dotrepo(args: &[&str]) -> Output {
    Command::new(dotrepo_bin())
        .args(args)
        .output()
        .expect("dotrepo command runs")
}

fn parse_stdout_json(output: &Output) -> Value {
    serde_json::from_slice(&output.stdout).expect("stdout contains json")
}

fn claims_fixture_root(fixture: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("dotrepo-core")
        .join("tests")
        .join("fixtures")
        .join("claims")
        .join(fixture)
}

fn claim_relative_path(claim_id: &str) -> String {
    format!("repos/github.com/acme/widget/claims/{claim_id}")
}

struct TempRoot {
    path: PathBuf,
}

impl TempRoot {
    fn new(label: &str) -> Self {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock works")
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "dotrepo-claim-command-{}-{}-{}",
            label,
            std::process::id(),
            unique
        ));
        fs::create_dir_all(&path).expect("temp dir created");
        Self { path }
    }

    fn path(&self) -> &Path {
        &self.path
    }
}

impl Drop for TempRoot {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.path);
    }
}

fn copy_seed_repo(fixture: &str, dest_root: &Path) {
    let source_repo = claims_fixture_root(fixture)
        .join("repos")
        .join("github.com")
        .join("acme")
        .join("widget");
    let dest_repo = dest_root
        .join("repos")
        .join("github.com")
        .join("acme")
        .join("widget");
    fs::create_dir_all(&dest_repo).expect("dest repo dir created");
    fs::copy(source_repo.join("record.toml"), dest_repo.join("record.toml"))
        .expect("record copied");
    fs::copy(source_repo.join("evidence.md"), dest_repo.join("evidence.md"))
        .expect("evidence copied");
}

#[test]
fn claim_command_reports_superseded_handoff_from_fixture() {
    let root = claims_fixture_root("accepted-clean");
    let claim_path = claim_relative_path("2026-03-10-maintainer-claim-01");
    let output = run_dotrepo(&[
        "--root",
        root.to_str().expect("fixture path is utf-8"),
        "claim",
        &claim_path,
        "--json",
    ]);

    assert!(output.status.success(), "command should succeed");
    assert!(output.stderr.is_empty(), "success should not write stderr");

    let json = parse_stdout_json(&output);
    assert_eq!(json["state"], Value::String("accepted".into()));
    assert_eq!(json["target"]["handoff"], Value::String("superseded".into()));
    assert_eq!(json["resolution"]["canonical_record_path"], Value::String(".repo".into()));
    assert_eq!(
        json["resolution"]["canonical_mirror_path"],
        Value::String("repos/github.com/acme/widget/record.toml".into())
    );
    assert_eq!(json["events"].as_array().expect("events array").len(), 2);
}

#[test]
fn claim_command_reports_corrected_history_from_fixture() {
    let root = claims_fixture_root("corrected");
    let claim_path = claim_relative_path("2026-03-15-maintainer-claim-01");
    let output = run_dotrepo(&[
        "--root",
        root.to_str().expect("fixture path is utf-8"),
        "claim",
        &claim_path,
        "--json",
    ]);

    assert!(output.status.success(), "command should succeed");
    assert!(output.stderr.is_empty(), "success should not write stderr");

    let json = parse_stdout_json(&output);
    let events = json["events"].as_array().expect("events array");
    assert_eq!(json["state"], Value::String("accepted".into()));
    assert_eq!(
        json["target"]["handoff"],
        Value::String("pending_canonical".into())
    );
    assert!(json.get("resolution").is_none(), "corrected fixture should not expose canonical resolution");
    assert_eq!(events.len(), 3);
    assert_eq!(events[1]["kind"], Value::String("rejected".into()));
    assert_eq!(events[2]["kind"], Value::String("corrected".into()));
}

#[test]
fn claim_commands_execute_documented_operator_workflow() {
    let root = TempRoot::new("operator-workflow");
    copy_seed_repo("accepted-clean", root.path());

    let root_str = root.path().to_str().expect("temp path is utf-8");
    let claim_id = "2026-03-18-maintainer-claim-01";
    let claim_path = claim_relative_path(claim_id);
    let claim_dir = root.path().join(&claim_path);

    let init = run_dotrepo(&[
        "--root",
        root_str,
        "claim-init",
        "--host",
        "github.com",
        "--owner",
        "acme",
        "--repo",
        "widget",
        "--claim-id",
        claim_id,
        "--claimant-name",
        "Acme maintainers",
        "--asserted-role",
        "maintainer",
        "--contact",
        "maintainers@acme.dev",
        "--record-source",
        "https://github.com/acme/widget",
        "--canonical-repo-url",
        "https://github.com/acme/widget",
        "--review-md",
    ]);
    assert!(init.status.success(), "claim-init should succeed");
    assert!(init.stderr.is_empty(), "claim-init should not write stderr");
    assert!(claim_dir.join("claim.toml").is_file(), "claim scaffold should exist");
    assert!(claim_dir.join("review.md").is_file(), "review scaffold should exist");

    let submitted = run_dotrepo(&[
        "--root",
        root_str,
        "claim-event",
        &claim_path,
        "--kind",
        "submitted",
        "--actor",
        "claimant",
        "--summary",
        "Submitted maintainer claim.",
    ]);
    assert!(submitted.status.success(), "submitted event should succeed");
    assert!(submitted.stderr.is_empty(), "submitted event should not write stderr");

    let review_started = run_dotrepo(&[
        "--root",
        root_str,
        "claim-event",
        &claim_path,
        "--kind",
        "review-started",
        "--actor",
        "index-reviewer",
        "--summary",
        "Started maintainer authority review.",
    ]);
    assert!(review_started.status.success(), "review-started event should succeed");
    assert!(
        review_started.stderr.is_empty(),
        "review-started event should not write stderr"
    );

    let accepted = run_dotrepo(&[
        "--root",
        root_str,
        "claim-event",
        &claim_path,
        "--kind",
        "accepted",
        "--actor",
        "index-reviewer",
        "--summary",
        "Accepted claim after identity review.",
        "--canonical-record-path",
        ".repo",
        "--canonical-mirror-path",
        "repos/github.com/acme/widget/record.toml",
    ]);
    assert!(accepted.status.success(), "accepted event should succeed");
    assert!(accepted.stderr.is_empty(), "accepted event should not write stderr");

    assert!(
        claim_dir.join("events/0001-submitted.toml").is_file(),
        "submitted event should be sequenced as 0001"
    );
    assert!(
        claim_dir.join("events/0002-review-started.toml").is_file(),
        "review-started event should be sequenced as 0002"
    );
    assert!(
        claim_dir.join("events/0003-accepted.toml").is_file(),
        "accepted event should be sequenced as 0003"
    );

    let report = run_dotrepo(&[
        "--root",
        root_str,
        "claim",
        &claim_path,
        "--json",
    ]);
    assert!(report.status.success(), "claim inspection should succeed");
    assert!(report.stderr.is_empty(), "claim inspection should not write stderr");
    let json = parse_stdout_json(&report);
    let events = json["events"].as_array().expect("events array");
    assert_eq!(json["state"], Value::String("accepted".into()));
    assert_eq!(json["target"]["handoff"], Value::String("superseded".into()));
    assert_eq!(
        json["resolution"]["result_event"],
        Value::String("events/0003-accepted.toml".into())
    );
    assert_eq!(events.len(), 3);
    assert_eq!(events[1]["kind"], Value::String("review_started".into()));
    assert_eq!(events[2]["kind"], Value::String("accepted".into()));

    let validate = run_dotrepo(&["validate-index", "--index-root", root_str]);
    assert!(validate.status.success(), "validate-index should succeed");
    assert!(validate.stderr.is_empty(), "validate-index success should not write stderr");
    assert_eq!(
        String::from_utf8(validate.stdout).expect("stdout is utf-8"),
        "index valid\n"
    );
}

#[test]
fn validate_index_rejects_invalid_claim_history() {
    let root = claims_fixture_root("invalid-history");
    let output = run_dotrepo(&[
        "validate-index",
        "--index-root",
        root.to_str().expect("fixture path is utf-8"),
    ]);

    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty(), "failing validate-index should not write stdout");

    let stderr = String::from_utf8(output.stderr).expect("stderr is utf-8");
    assert!(
        stderr.contains("claim events must use contiguous sequence numbers starting at 1"),
        "expected sequence validation error, got: {stderr}"
    );
    assert!(
        stderr.contains("claim.state is Accepted"),
        "expected claim state mismatch error, got: {stderr}"
    );
}
