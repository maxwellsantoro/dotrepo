use dotrepo_core::query_manifest_value_from_json;
use serde::Deserialize;
use serde_json::Value;
use std::fs;

#[derive(Deserialize)]
struct QueryPathCase {
    manifest: Value,
    path: String,
    expected: Option<Value>,
    #[serde(rename = "expectedError")]
    expected_error: Option<String>,
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
        let result = query_manifest_value_from_json(&case.manifest, &case.path);
        match (case.expected, case.expected_error) {
            (Some(expected), None) => {
                assert_eq!(
                    result.expect("query path resolves"),
                    expected,
                    "path `{}` drifted",
                    case.path
                );
            }
            (None, Some(expected_error)) => {
                assert_eq!(
                    result.expect_err("query path fails").to_string(),
                    expected_error,
                    "path `{}` error drifted",
                    case.path
                );
            }
            _ => panic!("path `{}` must define exactly one expectation", case.path),
        }
    }
}
