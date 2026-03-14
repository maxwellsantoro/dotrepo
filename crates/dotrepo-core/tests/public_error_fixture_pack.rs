use dotrepo_core::{
    index_snapshot_digest, public_repository_summary_or_error, public_repository_trust_or_error,
    PublicFreshness,
};
use serde::Serialize;
use serde_json::Value;
use std::fs;
use std::path::PathBuf;

fn fixture_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures")
        .join("public-errors")
}

fn fixture_index_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures")
        .join("public-export")
        .join("fixture-index")
}

fn expected_root() -> PathBuf {
    fixture_root().join("expected")
}

fn sample_public_freshness() -> PublicFreshness {
    let index_root = fixture_index_root();
    PublicFreshness {
        generated_at: "2026-03-10T18:30:00Z".into(),
        snapshot_digest: index_snapshot_digest(&index_root).expect("snapshot digest"),
        stale_after: Some("2026-03-11T18:30:00Z".into()),
    }
}

fn read_expected(name: &str) -> Value {
    serde_json::from_str(
        &fs::read_to_string(expected_root().join(name)).expect("expected fixture file is readable"),
    )
    .expect("expected fixture json parses")
}

fn serialize<T: Serialize>(value: T) -> Value {
    serde_json::to_value(value).expect("value serializes")
}

fn serialize_outcome<T: Serialize, E: Serialize>(value: std::result::Result<T, E>) -> Value {
    match value {
        Ok(value) => serialize(value),
        Err(value) => serialize(value),
    }
}

#[test]
fn public_error_fixture_pack_matches_checked_in_outputs() {
    let missing_repo_expected = read_expected("missing-repo.json");
    let invalid_identity_expected = read_expected("invalid-identity.json");

    let summary_missing_repo = serialize_outcome(public_repository_summary_or_error(
        &fixture_index_root(),
        "github.com",
        "missing",
        "repo",
        sample_public_freshness(),
    ));
    let trust_missing_repo = serialize_outcome(public_repository_trust_or_error(
        &fixture_index_root(),
        "github.com",
        "missing",
        "repo",
        sample_public_freshness(),
    ));
    let summary_invalid_identity = serialize_outcome(public_repository_summary_or_error(
        &fixture_index_root(),
        "github.com",
        "example/nested",
        "orbit",
        sample_public_freshness(),
    ));
    let trust_invalid_identity = serialize_outcome(public_repository_trust_or_error(
        &fixture_index_root(),
        "github.com",
        "example/nested",
        "orbit",
        sample_public_freshness(),
    ));

    assert_eq!(summary_missing_repo, missing_repo_expected);
    assert_eq!(trust_missing_repo, missing_repo_expected);
    assert_eq!(summary_invalid_identity, invalid_identity_expected);
    assert_eq!(trust_invalid_identity, invalid_identity_expected);
}

#[test]
fn public_error_fixture_pack_uses_summary_and_trust_error_codes() {
    let summary_missing_repo = serialize_outcome(public_repository_summary_or_error(
        &fixture_index_root(),
        "github.com",
        "missing",
        "repo",
        sample_public_freshness(),
    ));
    let trust_invalid_identity = serialize_outcome(public_repository_trust_or_error(
        &fixture_index_root(),
        "github.com",
        "example/nested",
        "orbit",
        sample_public_freshness(),
    ));

    assert_eq!(
        summary_missing_repo["error"]["code"],
        Value::String("repository_not_found".into())
    );
    assert!(summary_missing_repo.get("path").is_none());

    assert_eq!(
        trust_invalid_identity["error"]["code"],
        Value::String("invalid_repository_identity".into())
    );
    assert!(trust_invalid_identity.get("path").is_none());
}
