use dotrepo_core::{
    build_public_freshness, export_public_index_static, import_repository_with_options,
    public_repository_query, public_repository_summary, public_repository_trust, query_repository,
    trust_repository, ImportMode, ImportOptions,
};
use serde_json::{to_value, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::PathBuf;

fn fixture_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures")
}

fn fixture_index_root() -> PathBuf {
    fixture_root().join("public-export").join("fixture-index")
}

fn fixture_import_case(name: &str) -> PathBuf {
    fixture_root().join("import").join(name)
}

fn deterministic_freshness(stale_after_hours: Option<i64>) -> dotrepo_core::PublicFreshness {
    build_public_freshness(
        &fixture_index_root(),
        stale_after_hours,
        Some("2026-03-10T18:30:00Z"),
        None,
    )
    .expect("public freshness builds")
}

fn temp_dir(label: &str) -> PathBuf {
    let unique = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("clock works")
        .as_nanos();
    let path = std::env::temp_dir().join(format!(
        "dotrepo-core-freshness-{}-{}-{}",
        label,
        std::process::id(),
        unique
    ));
    fs::create_dir_all(&path).expect("temp dir created");
    path
}

fn object_keys(value: &Value) -> BTreeSet<String> {
    value
        .as_object()
        .expect("value should be an object")
        .keys()
        .cloned()
        .collect()
}

fn without_root_field(value: &Value) -> Value {
    let mut object = value
        .as_object()
        .expect("value should be an object")
        .clone();
    object.remove("root");
    Value::Object(object)
}

fn export_outputs_map(
    outputs: Vec<(PathBuf, String)>,
    out_root: &PathBuf,
) -> BTreeMap<String, String> {
    outputs
        .into_iter()
        .map(|(path, contents)| {
            (
                path.strip_prefix(out_root)
                    .expect("output stays under export root")
                    .display()
                    .to_string(),
                contents,
            )
        })
        .collect()
}

#[test]
fn snapshot_freshness_stays_aligned_across_public_surfaces() {
    let freshness = deterministic_freshness(Some(24));
    let summary = to_value(
        public_repository_summary(
            &fixture_index_root(),
            "github.com",
            "example",
            "orbit",
            freshness.clone(),
        )
        .expect("summary builds"),
    )
    .expect("summary serializes");
    let trust = to_value(
        public_repository_trust(
            &fixture_index_root(),
            "github.com",
            "example",
            "orbit",
            freshness.clone(),
        )
        .expect("trust builds"),
    )
    .expect("trust serializes");
    let query = to_value(
        public_repository_query(
            &fixture_index_root(),
            "github.com",
            "example",
            "orbit",
            "repo.description",
            freshness.clone(),
        )
        .expect("query builds"),
    )
    .expect("query serializes");

    let out_root = temp_dir("export");
    let outputs = export_outputs_map(
        export_public_index_static(&fixture_index_root(), &out_root, freshness.clone())
            .expect("export succeeds"),
        &out_root,
    );
    let meta =
        serde_json::from_str::<Value>(outputs.get("v0/meta.json").expect("meta output present"))
            .expect("meta parses");
    let inventory = serde_json::from_str::<Value>(
        outputs
            .get("v0/repos/index.json")
            .expect("inventory output present"),
    )
    .expect("inventory parses");

    assert_eq!(summary["freshness"], trust["freshness"]);
    assert_eq!(trust["freshness"], query["freshness"]);
    assert_eq!(inventory["freshness"], summary["freshness"]);
    assert_eq!(meta["generatedAt"], summary["freshness"]["generatedAt"]);
    assert_eq!(
        meta["snapshotDigest"],
        summary["freshness"]["snapshotDigest"]
    );
    assert_eq!(meta["staleAfter"], summary["freshness"]["staleAfter"]);

    fs::remove_dir_all(out_root).expect("temp dir removed");
}

#[test]
fn stale_after_remains_additive_only_for_public_response_shape() {
    let fresh = deterministic_freshness(None);
    let stale = deterministic_freshness(Some(24));
    let cases = [
        (
            "summary",
            to_value(
                public_repository_summary(
                    &fixture_index_root(),
                    "github.com",
                    "example",
                    "orbit",
                    fresh.clone(),
                )
                .expect("fresh summary builds"),
            )
            .expect("fresh summary serializes"),
            to_value(
                public_repository_summary(
                    &fixture_index_root(),
                    "github.com",
                    "example",
                    "orbit",
                    stale.clone(),
                )
                .expect("stale summary builds"),
            )
            .expect("stale summary serializes"),
        ),
        (
            "trust",
            to_value(
                public_repository_trust(
                    &fixture_index_root(),
                    "github.com",
                    "example",
                    "orbit",
                    fresh.clone(),
                )
                .expect("fresh trust builds"),
            )
            .expect("fresh trust serializes"),
            to_value(
                public_repository_trust(
                    &fixture_index_root(),
                    "github.com",
                    "example",
                    "orbit",
                    stale.clone(),
                )
                .expect("stale trust builds"),
            )
            .expect("stale trust serializes"),
        ),
        (
            "query",
            to_value(
                public_repository_query(
                    &fixture_index_root(),
                    "github.com",
                    "example",
                    "orbit",
                    "repo.description",
                    fresh.clone(),
                )
                .expect("fresh query builds"),
            )
            .expect("fresh query serializes"),
            to_value(
                public_repository_query(
                    &fixture_index_root(),
                    "github.com",
                    "example",
                    "orbit",
                    "repo.description",
                    stale.clone(),
                )
                .expect("stale query builds"),
            )
            .expect("stale query serializes"),
        ),
    ];

    for (label, fresh_json, stale_json) in cases {
        assert_eq!(
            object_keys(&fresh_json),
            object_keys(&stale_json),
            "{label} top-level keys changed",
        );
        assert!(
            fresh_json["freshness"].get("staleAfter").is_none(),
            "{label} fresh response should omit freshness.staleAfter",
        );
        assert!(
            stale_json["freshness"].get("staleAfter").is_some(),
            "{label} stale response should include freshness.staleAfter",
        );

        let mut fresh_freshness = fresh_json["freshness"]
            .as_object()
            .expect("fresh freshness is an object")
            .clone();
        let mut stale_freshness = stale_json["freshness"]
            .as_object()
            .expect("stale freshness is an object")
            .clone();
        fresh_freshness.remove("staleAfter");
        stale_freshness.remove("staleAfter");

        assert_eq!(
            fresh_freshness, stale_freshness,
            "{label} freshness keys drifted beyond staleAfter",
        );
    }
}

#[test]
fn record_generated_at_is_semantically_neutral_for_query_and_trust() {
    let without_generated_at = temp_dir("without-record-generated-at");
    let with_generated_at = temp_dir("with-record-generated-at");
    let base_manifest = r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Reviewed overlay"
"#;
    let generated_manifest = r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"
generated_at = "2026-03-10T18:30:00Z"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Reviewed overlay"
"#;
    fs::write(without_generated_at.join("record.toml"), base_manifest)
        .expect("base record written");
    fs::write(with_generated_at.join("record.toml"), generated_manifest)
        .expect("generated record written");

    assert_eq!(
        without_root_field(
            &to_value(
                query_repository(&without_generated_at, "repo.description").expect("base query")
            )
            .expect("base query serializes"),
        ),
        without_root_field(
            &to_value(
                query_repository(&with_generated_at, "repo.description").expect("generated query")
            )
            .expect("generated query serializes"),
        ),
    );
    assert_eq!(
        without_root_field(
            &to_value(trust_repository(&without_generated_at).expect("base trust"))
                .expect("base trust serializes"),
        ),
        without_root_field(
            &to_value(trust_repository(&with_generated_at).expect("generated trust"))
                .expect("generated trust serializes"),
        ),
    );

    fs::remove_dir_all(without_generated_at).expect("temp dir removed");
    fs::remove_dir_all(with_generated_at).expect("temp dir removed");
}

#[test]
fn import_options_can_populate_record_generated_at() {
    let plan = import_repository_with_options(
        &fixture_import_case("description-only-readme"),
        ImportMode::Overlay,
        Some("https://example.com/fixtures/description-only-readme"),
        &ImportOptions {
            generated_at: Some("2026-03-17T12:00:00Z".into()),
        },
    )
    .expect("overlay import succeeds");

    assert_eq!(
        plan.manifest.record.generated_at.as_deref(),
        Some("2026-03-17T12:00:00Z"),
    );
    assert!(
        plan.manifest_text
            .contains("generated_at = \"2026-03-17T12:00:00Z\""),
        "generated_at should be rendered into the imported manifest",
    );
}
