//! Conservative extraction of a single primary minimum toolchain version from
//! root package metadata.
//!
//! This intentionally stays narrower than a runtime matrix. If a root manifest
//! declares an unambiguous minimum version, publish it under `repo.toolchain`;
//! otherwise leave the field absent so consumers fall back to existing docs.
use super::types::{ImportSources, ImportedFile, ImportedToolchainMetadata};

pub(crate) fn infer_toolchain_metadata(sources: &ImportSources<'_>) -> ImportedToolchainMetadata {
    let candidates = [
        sources.cargo_toml.and_then(infer_cargo_rust_version),
        sources
            .rust_toolchain_toml
            .and_then(infer_rust_toolchain_toml_channel),
        sources
            .rust_toolchain
            .and_then(infer_rust_toolchain_channel),
        sources
            .pyproject_toml
            .and_then(infer_pyproject_requires_python),
        sources
            .package_json
            .and_then(infer_package_json_node_engine),
        sources.go_mod.and_then(infer_go_mod_version),
    ];

    let Some(candidate) = candidates.into_iter().flatten().next() else {
        return ImportedToolchainMetadata::default();
    };

    ImportedToolchainMetadata {
        min: Some(candidate.min.clone()),
        ecosystem: Some(candidate.ecosystem.clone()),
        source_path: Some(candidate.source_path.clone()),
        notes: vec![format!(
            "Imported `repo.toolchain.min` from `{}`.",
            candidate.source_path
        )],
        evidence_bullets: vec![format!(
            "Imported repo.toolchain.min from {} as `{}` ({}).",
            candidate.source_path, candidate.min, candidate.ecosystem
        )],
    }
}

struct ToolchainCandidate {
    min: String,
    ecosystem: String,
    source_path: String,
}

fn candidate(
    file: &ImportedFile,
    ecosystem: &str,
    min: Option<String>,
) -> Option<ToolchainCandidate> {
    Some(ToolchainCandidate {
        min: normalize_version(min?.as_str())?,
        ecosystem: ecosystem.to_string(),
        source_path: file.path.clone(),
    })
}

fn infer_cargo_rust_version(file: &ImportedFile) -> Option<ToolchainCandidate> {
    let parsed: toml::Value = toml::from_str(&file.contents).ok()?;
    let package = parsed.get("package").and_then(toml::Value::as_table);
    let workspace_package = parsed
        .get("workspace")
        .and_then(toml::Value::as_table)
        .and_then(|workspace| workspace.get("package"))
        .and_then(toml::Value::as_table);
    let rust_version = package
        .and_then(|table| table.get("rust-version"))
        .and_then(toml::Value::as_str)
        .or_else(|| {
            workspace_package
                .and_then(|table| table.get("rust-version"))
                .and_then(toml::Value::as_str)
        });
    candidate(file, "Rust", rust_version.map(str::to_string))
}

fn infer_rust_toolchain_toml_channel(file: &ImportedFile) -> Option<ToolchainCandidate> {
    let parsed: toml::Value = toml::from_str(&file.contents).ok()?;
    let channel = parsed
        .get("toolchain")
        .and_then(toml::Value::as_table)
        .and_then(|table| table.get("channel"))
        .and_then(toml::Value::as_str);
    candidate(file, "Rust", channel.map(str::to_string))
}

fn infer_rust_toolchain_channel(file: &ImportedFile) -> Option<ToolchainCandidate> {
    let first = file
        .contents
        .lines()
        .map(str::trim)
        .find(|line| !line.is_empty() && !line.starts_with('#'))?;
    candidate(file, "Rust", Some(first.to_string()))
}

fn infer_pyproject_requires_python(file: &ImportedFile) -> Option<ToolchainCandidate> {
    let parsed: toml::Value = toml::from_str(&file.contents).ok()?;
    let requires_python = parsed
        .get("project")
        .and_then(toml::Value::as_table)
        .and_then(|table| table.get("requires-python"))
        .and_then(toml::Value::as_str);
    candidate(
        file,
        "Python",
        requires_python.and_then(extract_min_version_from_specifier),
    )
}

fn infer_package_json_node_engine(file: &ImportedFile) -> Option<ToolchainCandidate> {
    let parsed: serde_json::Value = serde_json::from_str(&file.contents).ok()?;
    let node = parsed
        .get("engines")
        .and_then(serde_json::Value::as_object)
        .and_then(|engines| engines.get("node"))
        .and_then(serde_json::Value::as_str);
    candidate(
        file,
        "Node.js",
        node.and_then(extract_min_version_from_specifier),
    )
}

fn infer_go_mod_version(file: &ImportedFile) -> Option<ToolchainCandidate> {
    let version = file.contents.lines().map(str::trim).find_map(|line| {
        line.strip_prefix("go ")
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .map(str::to_string)
    });
    candidate(file, "Go", version)
}

fn extract_min_version_from_specifier(value: &str) -> Option<String> {
    let normalized = value.trim();
    for operator in [">=", "==", "="] {
        if let Some(rest) = normalized.strip_prefix(operator) {
            return first_version_token(rest);
        }
    }
    first_version_token(normalized)
}

fn first_version_token(value: &str) -> Option<String> {
    value
        .split(|ch: char| {
            ch.is_whitespace() || matches!(ch, ',' | ';' | '|' | '<' | '>' | '=' | '^' | '~')
        })
        .find_map(normalize_version)
}

fn normalize_version(value: &str) -> Option<String> {
    let trimmed = value
        .trim()
        .trim_start_matches('v')
        .trim_start_matches("rust-");
    if trimmed.eq_ignore_ascii_case("stable")
        || trimmed.eq_ignore_ascii_case("beta")
        || trimmed.eq_ignore_ascii_case("nightly")
        || trimmed.is_empty()
    {
        return None;
    }
    let mut chars = trimmed.chars().peekable();
    let mut version = String::new();
    let mut saw_digit = false;
    let mut last_was_dot = false;
    while let Some(ch) = chars.peek().copied() {
        if ch.is_ascii_digit() {
            saw_digit = true;
            last_was_dot = false;
            version.push(ch);
            chars.next();
        } else if ch == '.' && saw_digit && !last_was_dot {
            last_was_dot = true;
            version.push(ch);
            chars.next();
        } else {
            break;
        }
    }
    while version.ends_with('.') {
        version.pop();
    }
    if version.is_empty() {
        None
    } else {
        Some(version)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn file(path: &str, contents: &str) -> ImportedFile {
        ImportedFile {
            path: path.into(),
            contents: contents.into(),
        }
    }

    #[test]
    fn extracts_cargo_package_rust_version() {
        let cargo = file(
            "Cargo.toml",
            r#"
[package]
rust-version = "1.90.0"
"#,
        );
        let sources = ImportSources {
            cargo_toml: Some(&cargo),
            rust_toolchain_toml: None,
            rust_toolchain: None,
            package_json: None,
            pyproject_toml: None,
            setup_py: None,
            setup_cfg: None,
            go_mod: None,
            pom_xml: None,
            maven_wrapper: false,
            build_gradle: None,
            gradle_wrapper: false,
            composer_json: None,
            csproj: None,
            mix_exs: None,
            rebar_config: None,
            cmake_presets_json: None,
            makefile: None,
            justfile: None,
            rakefile: None,
            contributing: None,
            workflow_files: &[],
        };
        let metadata = infer_toolchain_metadata(&sources);
        assert_eq!(metadata.min.as_deref(), Some("1.90.0"));
        assert_eq!(metadata.ecosystem.as_deref(), Some("Rust"));
        assert_eq!(metadata.source_path.as_deref(), Some("Cargo.toml"));
    }

    #[test]
    fn prefers_cargo_minimum_over_rust_toolchain_pin() {
        let cargo = file(
            "Cargo.toml",
            r#"
[workspace]

[workspace.package]
rust-version = "1.88"
"#,
        );
        let rust_toolchain = file(
            "rust-toolchain.toml",
            r#"
[toolchain]
channel = "1.94.0"
"#,
        );
        let sources = ImportSources {
            cargo_toml: Some(&cargo),
            rust_toolchain_toml: Some(&rust_toolchain),
            rust_toolchain: None,
            package_json: None,
            pyproject_toml: None,
            setup_py: None,
            setup_cfg: None,
            go_mod: None,
            pom_xml: None,
            maven_wrapper: false,
            build_gradle: None,
            gradle_wrapper: false,
            composer_json: None,
            csproj: None,
            mix_exs: None,
            rebar_config: None,
            cmake_presets_json: None,
            makefile: None,
            justfile: None,
            rakefile: None,
            contributing: None,
            workflow_files: &[],
        };
        let metadata = infer_toolchain_metadata(&sources);
        assert_eq!(metadata.min.as_deref(), Some("1.88"));
    }

    #[test]
    fn extracts_python_node_and_go_minimums() {
        assert_eq!(
            infer_pyproject_requires_python(&file(
                "pyproject.toml",
                r#"
[project]
requires-python = ">=3.10"
"#,
            ))
            .map(|candidate| candidate.min),
            Some("3.10".into())
        );
        assert_eq!(
            infer_package_json_node_engine(&file(
                "package.json",
                r#"{ "engines": { "node": ">=20.0.0" } }"#,
            ))
            .map(|candidate| candidate.min),
            Some("20.0.0".into())
        );
        assert_eq!(
            infer_go_mod_version(&file("go.mod", "module example.test/widget\n\ngo 1.22.1\n"))
                .map(|candidate| candidate.min),
            Some("1.22.1".into())
        );
    }
}
