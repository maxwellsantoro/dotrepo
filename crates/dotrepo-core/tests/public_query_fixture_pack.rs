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

fn temp_dir(label: &str) -> PathBuf {
    let unique = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("clock works")
        .as_nanos();
    let path = std::env::temp_dir().join(format!(
        "dotrepo-public-query-{}-{}-{}",
        label,
        std::process::id(),
        unique
    ));
    fs::create_dir_all(&path).expect("temp dir created");
    path
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
    assert_eq!(
        orbit["links"]["repository"],
        Value::String("/v0/repos/github.com/example/orbit/index.json".into())
    );
    assert_eq!(
        orbit["links"]["trust"],
        Value::String("/v0/repos/github.com/example/orbit/trust.json".into())
    );
    assert_eq!(
        orbit["links"]["profile"],
        Value::String("/v0/repos/github.com/example/orbit/profile.json".into())
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

#[test]
fn public_query_aliases_common_github_native_fields() {
    let root = temp_dir("aliases");
    let record_dir = root.join("repos/github.com/example/alias");
    fs::create_dir_all(&record_dir).expect("record dir created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://github.com/example/alias"

[record.trust]
confidence = "medium"
provenance = ["imported"]

[repo]
name = "alias"
description = "Alias coverage fixture."
languages = ["Rust", "Shell"]

[x.github]
archived = false
"#,
    )
    .expect("record written");
    let freshness = PublicFreshness {
        generated_at: "2026-03-10T18:30:00Z".into(),
        snapshot_digest: "alias-fixture".into(),
        stale_after: None,
    };

    let language = serialize_outcome(public_repository_query_or_error(
        &root,
        "github.com",
        "example",
        "alias",
        "repo.language",
        freshness.clone(),
    ));
    assert_eq!(language["path"], Value::String("repo.language".into()));
    assert_eq!(language["value"], Value::String("Rust".into()));

    let archived = serialize_outcome(public_repository_query_or_error(
        &root,
        "github.com",
        "example",
        "alias",
        "repo.archived",
        freshness,
    ));
    assert_eq!(archived["path"], Value::String("repo.archived".into()));
    assert_eq!(archived["value"], Value::Bool(false));

    fs::remove_dir_all(root).expect("temp dir removed");
}
