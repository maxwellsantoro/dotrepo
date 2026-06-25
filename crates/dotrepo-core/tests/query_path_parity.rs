use dotrepo_core::query_manifest_value_from_json;
use serde::Deserialize;
use serde_json::Value;
use std::fs;

#[derive(Deserialize)]
struct QueryPathCase {
    manifest: Value,
    path: String,
    expected: Value,
}

fn fixture_cases() -> Vec<QueryPathCase> {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures/query-path-cases.json");
    let text = fs::read_to_string(path).expect("query path parity fixture readable");
    serde_json::from_str(&text).expect("query path parity fixture parses")
}

#[test]
fn query_path_cases_match_shared_contract() {
    for case in fixture_cases() {
        let actual = query_manifest_value_from_json(&case.manifest, &case.path)
            .expect("query path resolves");
        assert_eq!(actual, case.expected, "path `{}` drifted", case.path);
    }
}
