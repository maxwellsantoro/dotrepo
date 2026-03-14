use dotrepo_core::{index_snapshot_digest, public_repository_query_or_error, PublicFreshness};
use serde::Serialize;
use serde_json::Value;
use std::fs;
use std::path::PathBuf;

fn fixture_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures")
        .join("public-query")
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
fn public_query_fixture_pack_matches_checked_in_outputs() {
    let cases = [
        (
            "orbit-description.json",
            serialize_outcome(public_repository_query_or_error(
                &fixture_index_root(),
                "github.com",
                "example",
                "orbit",
                "repo.description",
                sample_public_freshness(),
            )),
        ),
        (
            "nova-description.json",
            serialize_outcome(public_repository_query_or_error(
                &fixture_index_root(),
                "github.com",
                "example",
                "nova",
                "repo.description",
                sample_public_freshness(),
            )),
        ),
        (
            "missing-path.json",
            serialize_outcome(public_repository_query_or_error(
                &fixture_index_root(),
                "github.com",
                "example",
                "orbit",
                "repo.missing_field",
                sample_public_freshness(),
            )),
        ),
        (
            "missing-repo.json",
            serialize_outcome(public_repository_query_or_error(
                &fixture_index_root(),
                "github.com",
                "missing",
                "repo",
                "repo.description",
                sample_public_freshness(),
            )),
        ),
        (
            "invalid-identity.json",
            serialize_outcome(public_repository_query_or_error(
                &fixture_index_root(),
                "github.com",
                "example/nested",
                "orbit",
                "repo.description",
                sample_public_freshness(),
            )),
        ),
    ];

    for (name, generated) in cases {
        let expected = read_expected(name);
        assert_eq!(generated, expected, "{name} drifted");
    }
}

#[test]
fn public_query_fixture_pack_covers_success_and_error_contracts() {
    let orbit = serialize_outcome(public_repository_query_or_error(
        &fixture_index_root(),
        "github.com",
        "example",
        "orbit",
        "repo.description",
        sample_public_freshness(),
    ));
    assert_eq!(orbit["apiVersion"], Value::String("v0".into()));
    assert_eq!(
        orbit["links"]["self"],
        Value::String("/v0/repos/github.com/example/orbit/query?path=repo.description".into())
    );

    let nova = serialize_outcome(public_repository_query_or_error(
        &fixture_index_root(),
        "github.com",
        "example",
        "nova",
        "repo.description",
        sample_public_freshness(),
    ));
    assert_eq!(
        nova["selection"]["record"]["claim"]["handoff"],
        Value::String("pending_canonical".into())
    );

    let missing_path = serialize_outcome(public_repository_query_or_error(
        &fixture_index_root(),
        "github.com",
        "example",
        "orbit",
        "repo.missing_field",
        sample_public_freshness(),
    ));
    assert_eq!(
        missing_path["error"]["code"],
        Value::String("query_path_not_found".into())
    );

    let missing_repo = serialize_outcome(public_repository_query_or_error(
        &fixture_index_root(),
        "github.com",
        "missing",
        "repo",
        "repo.description",
        sample_public_freshness(),
    ));
    assert_eq!(
        missing_repo["error"]["code"],
        Value::String("repository_not_found".into())
    );

    let invalid_identity = serialize_outcome(public_repository_query_or_error(
        &fixture_index_root(),
        "github.com",
        "example/nested",
        "orbit",
        "repo.description",
        sample_public_freshness(),
    ));
    assert_eq!(
        invalid_identity["error"]["code"],
        Value::String("invalid_repository_identity".into())
    );
}
