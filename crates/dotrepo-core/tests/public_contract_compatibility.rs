use dotrepo_core::{
    export_public_index_static, index_snapshot_digest, public_repository_query_or_error,
    public_repository_summary_or_error, public_repository_trust_or_error, ConflictRelationship,
    PublicFreshness, SelectionReason,
};
use serde::Deserialize;
use serde::Serialize;
use serde_json::Value;
use std::collections::BTreeSet;
use std::fs;
use std::path::PathBuf;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct CompatibilityManifest {
    api_version: String,
    freshness: KeySpec,
    identity: IdentitySpec,
    selection: KeySpec,
    conflict: ConflictSpec,
    record_summary: RecordSummarySpec,
    inventory: InventorySpec,
    summary: ResponseSpec,
    trust: ResponseSpec,
    query: ResponseSpec,
    errors: ErrorSpec,
}

#[derive(Debug, Deserialize)]
struct KeySpec {
    #[serde(rename = "requiredKeys")]
    required_keys: Vec<String>,
    #[serde(rename = "reasonValues", default)]
    reason_values: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct IdentitySpec {
    #[serde(rename = "requiredKeys")]
    required_keys: Vec<String>,
    #[serde(rename = "optionalKeys")]
    optional_keys: Vec<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct RecordSummarySpec {
    #[serde(rename = "requiredKeys")]
    required_keys: Vec<String>,
    record_keys: Vec<String>,
    trust_keys: Vec<String>,
    artifacts_keys: Vec<String>,
    claim_keys: Vec<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct InventorySpec {
    #[serde(rename = "requiredKeys")]
    required_keys: Vec<String>,
    entry_keys: Vec<String>,
    link_keys: Vec<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ResponseSpec {
    #[serde(rename = "requiredKeys")]
    required_keys: Vec<String>,
    link_keys: Vec<String>,
    #[serde(default)]
    repository_keys: Vec<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ConflictSpec {
    #[serde(rename = "requiredKeys")]
    required_keys: Vec<String>,
    query_required_keys: Vec<String>,
    relationship_values: Vec<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ErrorSpec {
    #[serde(rename = "requiredKeys")]
    required_keys: Vec<String>,
    query_required_keys: Vec<String>,
    error_keys: Vec<String>,
    codes: Vec<String>,
}

fn fixture_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures")
}

fn fixture_index_root() -> PathBuf {
    fixture_root().join("public-export").join("fixture-index")
}

fn expected_root() -> PathBuf {
    fixture_root()
        .join("public-export")
        .join("expected")
        .join("public")
}

fn compatibility_manifest() -> CompatibilityManifest {
    let path = fixture_root()
        .join("public-contract")
        .join("compatibility.json");
    serde_json::from_str(&fs::read_to_string(path).expect("compatibility manifest exists"))
        .expect("compatibility manifest parses")
}

fn sample_public_freshness() -> PublicFreshness {
    let index_root = fixture_index_root();
    PublicFreshness {
        generated_at: "2026-03-10T18:30:00Z".into(),
        snapshot_digest: index_snapshot_digest(&index_root).expect("snapshot digest"),
        stale_after: Some("2026-03-11T18:30:00Z".into()),
    }
}

fn object<'a>(value: &'a Value, context: &str) -> &'a serde_json::Map<String, Value> {
    value
        .as_object()
        .unwrap_or_else(|| panic!("{context} should be a JSON object"))
}

fn assert_has_keys(value: &Value, required_keys: &[String], context: &str) {
    let obj = object(value, context);
    for key in required_keys {
        assert!(
            obj.contains_key(key),
            "{context} is missing required key `{key}`"
        );
    }
}

fn assert_exact_keys(value: &Value, expected_keys: &[String], context: &str) {
    let actual_keys = object(value, context).keys().cloned().collect::<BTreeSet<_>>();
    let expected_keys = expected_keys.iter().cloned().collect::<BTreeSet<_>>();
    assert_eq!(actual_keys, expected_keys, "{context} keys drifted");
}

fn assert_string(value: &Value, context: &str) {
    assert!(value.is_string(), "{context} should be a string");
}

fn assert_claim_aware_record(
    manifest: &CompatibilityManifest,
    record_summary: &Value,
    expect_claim: bool,
    context: &str,
) {
    assert_has_keys(
        record_summary,
        &manifest.record_summary.required_keys,
        context,
    );
    let record = &record_summary["record"];
    assert_has_keys(
        record,
        &manifest.record_summary.record_keys,
        &format!("{context}.record"),
    );
    assert_has_keys(
        &record["trust"],
        &manifest.record_summary.trust_keys,
        &format!("{context}.record.trust"),
    );
    assert_has_keys(
        &record_summary["artifacts"],
        &manifest.record_summary.artifacts_keys,
        &format!("{context}.artifacts"),
    );

    if expect_claim {
        assert_has_keys(
            &record_summary["claim"],
            &manifest.record_summary.claim_keys,
            &format!("{context}.claim"),
        );
    }
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

fn assert_serialized_string_set<T: Serialize + Copy>(
    values: &[T],
    expected: &[String],
    label: &str,
) {
    let actual = values
        .iter()
        .map(|value| {
            serialize(*value)
                .as_str()
                .unwrap_or_else(|| panic!("{label} should serialize to a string"))
                .to_string()
        })
        .collect::<BTreeSet<_>>();
    let expected = expected.iter().cloned().collect::<BTreeSet<_>>();
    assert_eq!(actual, expected, "{label} vocabulary drifted");
}

#[test]
fn public_contract_compatibility_manifest_matches_live_outputs() {
    let manifest = compatibility_manifest();
    let freshness = sample_public_freshness();

    assert_serialized_string_set(
        &[
            SelectionReason::OnlyMatchingRecord,
            SelectionReason::CanonicalPreferred,
            SelectionReason::HigherStatusOverlay,
            SelectionReason::EqualAuthorityConflict,
        ],
        &manifest.selection.reason_values,
        "selection.reason",
    );
    assert_serialized_string_set(
        &[ConflictRelationship::Superseded, ConflictRelationship::Parallel],
        &manifest.conflict.relationship_values,
        "conflicts[].relationship",
    );

    let orbit_summary = serde_json::to_value(
        public_repository_summary_or_error(
            &fixture_index_root(),
            "github.com",
            "example",
            "orbit",
            freshness.clone(),
        )
        .expect("orbit summary succeeds"),
    )
    .expect("orbit summary serializes");
    assert_eq!(
        orbit_summary["apiVersion"],
        Value::String(manifest.api_version.clone())
    );
    assert_has_keys(&orbit_summary, &manifest.summary.required_keys, "summary");
    assert_has_keys(
        &orbit_summary["freshness"],
        &manifest.freshness.required_keys,
        "summary.freshness",
    );
    assert_has_keys(
        &orbit_summary["identity"],
        &manifest.identity.required_keys,
        "summary.identity",
    );
    for key in &manifest.identity.optional_keys {
        if orbit_summary["identity"].get(key).is_some() {
            assert_string(
                orbit_summary["identity"]
                    .get(key)
                    .expect("optional key exists"),
                &format!("summary.identity.{key}"),
            );
        }
    }
    assert_has_keys(
        &orbit_summary["repository"],
        &manifest.summary.repository_keys,
        "summary.repository",
    );
    assert_has_keys(
        &orbit_summary["selection"],
        &manifest.selection.required_keys,
        "summary.selection",
    );
    assert_claim_aware_record(
        &manifest,
        &orbit_summary["selection"]["record"],
        false,
        "summary.selection.record",
    );
    assert_has_keys(
        &orbit_summary["links"],
        &manifest.summary.link_keys,
        "summary.links",
    );
    assert_exact_keys(&orbit_summary["links"], &manifest.summary.link_keys, "summary.links");

    let nova_summary = serde_json::to_value(
        public_repository_summary_or_error(
            &fixture_index_root(),
            "github.com",
            "example",
            "nova",
            freshness.clone(),
        )
        .expect("nova summary succeeds"),
    )
    .expect("nova summary serializes");
    assert_claim_aware_record(
        &manifest,
        &nova_summary["selection"]["record"],
        true,
        "nova.summary.selection.record",
    );

    let orbit_trust = serde_json::to_value(
        public_repository_trust_or_error(
            &fixture_index_root(),
            "github.com",
            "example",
            "orbit",
            freshness.clone(),
        )
        .expect("orbit trust succeeds"),
    )
    .expect("orbit trust serializes");
    assert_eq!(
        orbit_trust["apiVersion"],
        Value::String(manifest.api_version.clone())
    );
    assert_has_keys(&orbit_trust, &manifest.trust.required_keys, "trust");
    assert_has_keys(
        &orbit_trust["freshness"],
        &manifest.freshness.required_keys,
        "trust.freshness",
    );
    assert_has_keys(
        &orbit_trust["identity"],
        &manifest.identity.required_keys,
        "trust.identity",
    );
    assert_has_keys(
        &orbit_trust["selection"],
        &manifest.selection.required_keys,
        "trust.selection",
    );
    assert_claim_aware_record(
        &manifest,
        &orbit_trust["selection"]["record"],
        false,
        "trust.selection.record",
    );
    assert_has_keys(
        &orbit_trust["links"],
        &manifest.trust.link_keys,
        "trust.links",
    );
    assert_exact_keys(&orbit_trust["links"], &manifest.trust.link_keys, "trust.links");
    for conflict in orbit_trust["conflicts"]
        .as_array()
        .expect("trust.conflicts array")
    {
        assert_has_keys(conflict, &manifest.conflict.required_keys, "trust.conflict");
    }

    let nova_trust = serde_json::to_value(
        public_repository_trust_or_error(
            &fixture_index_root(),
            "github.com",
            "example",
            "nova",
            freshness.clone(),
        )
        .expect("nova trust succeeds"),
    )
    .expect("nova trust serializes");
    assert_claim_aware_record(
        &manifest,
        &nova_trust["selection"]["record"],
        true,
        "nova.trust.selection.record",
    );
    for conflict in nova_trust["conflicts"]
        .as_array()
        .expect("nova.trust.conflicts array")
    {
        assert_has_keys(
            conflict,
            &manifest.conflict.required_keys,
            "nova.trust.conflict",
        );
    }

    let orbit_query = serde_json::to_value(
        public_repository_query_or_error(
            &fixture_index_root(),
            "github.com",
            "example",
            "orbit",
            "repo.description",
            freshness.clone(),
        )
        .expect("orbit query succeeds"),
    )
    .expect("orbit query serializes");
    assert_eq!(
        orbit_query["apiVersion"],
        Value::String(manifest.api_version.clone())
    );
    assert_has_keys(&orbit_query, &manifest.query.required_keys, "query");
    assert_has_keys(
        &orbit_query["freshness"],
        &manifest.freshness.required_keys,
        "query.freshness",
    );
    assert_has_keys(
        &orbit_query["identity"],
        &manifest.identity.required_keys,
        "query.identity",
    );
    assert_has_keys(
        &orbit_query["selection"],
        &manifest.selection.required_keys,
        "query.selection",
    );
    assert_claim_aware_record(
        &manifest,
        &orbit_query["selection"]["record"],
        false,
        "query.selection.record",
    );
    assert_has_keys(
        &orbit_query["links"],
        &manifest.query.link_keys,
        "query.links",
    );
    assert_exact_keys(&orbit_query["links"], &manifest.query.link_keys, "query.links");
    assert_string(&orbit_query["value"], "query.value");
    for conflict in orbit_query["conflicts"]
        .as_array()
        .expect("query.conflicts array")
    {
        assert_has_keys(
            conflict,
            &manifest.conflict.query_required_keys,
            "query.conflict",
        );
    }

    let nova_query = serde_json::to_value(
        public_repository_query_or_error(
            &fixture_index_root(),
            "github.com",
            "example",
            "nova",
            "repo.description",
            freshness.clone(),
        )
        .expect("nova query succeeds"),
    )
    .expect("nova query serializes");
    assert_claim_aware_record(
        &manifest,
        &nova_query["selection"]["record"],
        true,
        "nova.query.selection.record",
    );
    for conflict in nova_query["conflicts"]
        .as_array()
        .expect("nova.query.conflicts array")
    {
        assert_has_keys(
            conflict,
            &manifest.conflict.query_required_keys,
            "nova.query.conflict",
        );
    }

    let missing_path = serialize_outcome(public_repository_query_or_error(
        &fixture_index_root(),
        "github.com",
        "example",
        "orbit",
        "repo.missing_field",
        freshness.clone(),
    ));
    assert_has_keys(
        &missing_path,
        &manifest.errors.query_required_keys,
        "query.error",
    );
    assert_has_keys(
        &missing_path["error"],
        &manifest.errors.error_keys,
        "query.error.error",
    );
    assert_exact_keys(
        &missing_path["error"],
        &manifest.errors.error_keys,
        "query.error.error",
    );

    let missing_repo = serialize_outcome(public_repository_summary_or_error(
        &fixture_index_root(),
        "github.com",
        "missing",
        "repo",
        freshness.clone(),
    ));
    assert_has_keys(
        &missing_repo,
        &manifest.errors.required_keys,
        "summary.error",
    );
    assert_has_keys(
        &missing_repo["error"],
        &manifest.errors.error_keys,
        "summary.error.error",
    );
    assert_exact_keys(
        &missing_repo["error"],
        &manifest.errors.error_keys,
        "summary.error.error",
    );
    assert!(
        missing_repo.get("path").is_none(),
        "summary/trust errors should not include query path"
    );

    let invalid_identity = serialize_outcome(public_repository_trust_or_error(
        &fixture_index_root(),
        "github.com",
        "example/nested",
        "orbit",
        freshness,
    ));
    assert_has_keys(
        &invalid_identity,
        &manifest.errors.required_keys,
        "trust.error",
    );
    assert_has_keys(
        &invalid_identity["error"],
        &manifest.errors.error_keys,
        "trust.error.error",
    );
    assert_exact_keys(
        &invalid_identity["error"],
        &manifest.errors.error_keys,
        "trust.error.error",
    );
    assert!(
        invalid_identity.get("path").is_none(),
        "summary/trust errors should not include query path"
    );

    let expected_codes = manifest
        .errors
        .codes
        .iter()
        .cloned()
        .collect::<BTreeSet<_>>();
    let actual_codes = [
        missing_path["error"]["code"]
            .as_str()
            .expect("missing_path error code"),
        missing_repo["error"]["code"]
            .as_str()
            .expect("missing_repo error code"),
        invalid_identity["error"]["code"]
            .as_str()
            .expect("invalid_identity error code"),
    ]
    .into_iter()
    .map(str::to_string)
    .collect::<BTreeSet<_>>();
    assert_eq!(
        actual_codes, expected_codes,
        "public error code vocabulary drifted"
    );

    let generated_export = export_public_index_static(
        &fixture_index_root(),
        &expected_root(),
        sample_public_freshness(),
    )
    .expect("public export succeeds");
    let inventory_contents = generated_export
        .into_iter()
        .find_map(|(path, contents)| {
            path.strip_prefix(expected_root())
                .ok()
                .filter(|relative| relative == &PathBuf::from("v0/repos/index.json"))
                .map(|_| contents)
        })
        .expect("inventory output exists");
    let inventory = serde_json::from_str::<Value>(&inventory_contents).expect("inventory parses");
    assert_eq!(inventory["apiVersion"], Value::String(manifest.api_version));
    assert_has_keys(&inventory, &manifest.inventory.required_keys, "inventory");
    assert_has_keys(
        &inventory["freshness"],
        &manifest.freshness.required_keys,
        "inventory.freshness",
    );
    for entry in inventory["repositories"]
        .as_array()
        .expect("inventory.repositories array")
    {
        assert_has_keys(entry, &manifest.inventory.entry_keys, "inventory.entry");
        assert_has_keys(
            &entry["identity"],
            &manifest.identity.required_keys,
            "inventory.entry.identity",
        );
        assert_has_keys(
            &entry["links"],
            &manifest.inventory.link_keys,
            "inventory.entry.links",
        );
        assert_exact_keys(
            &entry["links"],
            &manifest.inventory.link_keys,
            "inventory.entry.links",
        );
    }
}

fn temp_dir(label: &str) -> PathBuf {
    let unique = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("clock works")
        .as_nanos();
    let path = std::env::temp_dir().join(format!(
        "dotrepo-contract-{}-{}-{}",
        label,
        std::process::id(),
        unique
    ));
    fs::create_dir_all(&path).expect("temp dir created");
    path
}

fn ad_hoc_public_freshness(snapshot_digest: &str) -> PublicFreshness {
    PublicFreshness {
        generated_at: "2026-03-10T18:30:00Z".into(),
        snapshot_digest: snapshot_digest.into(),
        stale_after: Some("2026-03-11T18:30:00Z".into()),
    }
}

#[test]
fn public_contract_compatibility_covers_equal_authority_query_conflicts() {
    let manifest = compatibility_manifest();
    let root = temp_dir("equal-authority-query");
    let record_dir = root.join("repos/github.com/example/orbit");
    let alt_dir = record_dir.join("alt");
    fs::create_dir_all(&alt_dir).expect("alt dir created");
    fs::write(
        record_dir.join("record.toml"),
        r#"
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
description = "Selected description"
"#,
    )
    .expect("selected record written");
    fs::write(
        alt_dir.join("record.toml"),
        r#"
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
description = "Competing description"
"#,
    )
    .expect("competing record written");

    let response = serialize_outcome(public_repository_query_or_error(
        &root,
        "github.com",
        "example",
        "orbit",
        "repo.description",
        ad_hoc_public_freshness("equal-authority-snapshot"),
    ));

    assert_eq!(
        response["selection"]["reason"],
        Value::String("equal_authority_conflict".into())
    );
    assert_eq!(
        response["selection"]["record"]["manifestPath"],
        Value::String("repos/github.com/example/orbit/alt/record.toml".into())
    );
    assert_eq!(
        response["value"],
        Value::String("Competing description".into())
    );
    assert_eq!(
        response["conflicts"][0]["relationship"],
        Value::String("parallel".into())
    );
    assert_has_keys(
        &response["conflicts"][0],
        &manifest.conflict.query_required_keys,
        "equal-authority.conflicts[0]",
    );
    assert_eq!(
        response["conflicts"][0]["reason"],
        Value::String("equal_authority_conflict".into())
    );
    assert_eq!(
        response["conflicts"][0]["value"],
        Value::String("Selected description".into())
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}
