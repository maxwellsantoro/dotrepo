//! Explicit Cargo selectors cannot establish a repository-default command.
//! This is a scope screen, not shell validation or execution evidence.
pub(super) fn cargo_component_selector(command: &str) -> bool {
    let tokens = command
        .split_whitespace()
        .map(|word| word.trim_matches(['\'', '"']))
        .collect::<Vec<_>>();
    if !tokens.contains(&"cargo") {
        return false;
    }
    for (index, token) in tokens.iter().enumerate() {
        if *token == "--package"
            || *token == "-p"
            || token.starts_with("--package=")
            || (token.starts_with("-p") && token.len() > 2 && !token.starts_with("--"))
        {
            return true;
        }
        let path = if *token == "--manifest-path" {
            tokens.get(index + 1).copied()
        } else if let Some(value) = token.strip_prefix("--manifest-path=") {
            Some(value.trim_matches(['\'', '"']))
        } else {
            continue;
        };
        if !matches!(path, Some("Cargo.toml" | "./Cargo.toml")) {
            return true;
        }
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn scope_cases_match_reference_consumer() {
        let cases: serde_json::Value = serde_json::from_str(include_str!(
            "../../../tests/fixtures/command-scope-cases.json"
        ))
        .unwrap();
        for case in cases.as_array().unwrap() {
            assert_eq!(
                cargo_component_selector(case["command"].as_str().unwrap()),
                case["componentScoped"].as_bool().unwrap(),
                "{}",
                case["command"]
            );
        }
    }
}
