use anyhow::{anyhow, bail, Result};
use dotrepo_schema::Manifest;
use serde_json::Value;

pub fn manifest_to_json(manifest: &Manifest) -> Result<Value> {
    serde_json::to_value(manifest).map_err(Into::into)
}

/// Returns an owned JSON value because callers serialize, diff, or store the result.
pub fn query_manifest_value(manifest: &Manifest, key: &str) -> Result<Value> {
    query_manifest_value_from_json(&manifest_to_json(manifest)?, key)
}

pub fn query_manifest_value_from_json(document: &Value, key: &str) -> Result<Value> {
    let canonical_key = normalize_query_path(key);
    let value = query_value(document, &canonical_key).or_else(|_| {
        if canonical_key != key {
            query_value(document, key)
        } else {
            bail!("query path not found: {}", key)
        }
    })?;
    Ok(value.to_owned())
}

pub fn query_manifest(manifest: &Manifest, key: &str) -> Result<String> {
    Ok(serde_json::to_string_pretty(&query_manifest_value(
        manifest, key,
    )?)?)
}

fn normalize_query_path(key: &str) -> String {
    match key {
        "" | "." => ".".into(),
        "trust" => "record.trust".into(),
        _ if key.starts_with("trust.") => format!("record.{}", key),
        // Agent-facing conveniences for structured GitHub-native facts. The
        // manifest stores all languages in priority order and GitHub-only
        // archive state under the namespaced extension, but callers naturally
        // ask for these as singular repo facts.
        "repo.language" => "repo.languages.0".into(),
        "repo.archived" => "x.github.archived".into(),
        _ => key.into(),
    }
}

fn query_value<'a>(value: &'a Value, key: &str) -> Result<&'a Value> {
    if key.is_empty() || key == "." {
        return Ok(value);
    }

    let mut current = value;
    for segment in key.split('.') {
        current = match current {
            Value::Object(map) => map
                .get(segment)
                .ok_or_else(|| anyhow!("query path not found: {}", key))?,
            Value::Array(items) => {
                let index = segment
                    .parse::<usize>()
                    .map_err(|_| anyhow!("query path not found: {}", key))?;
                if index.to_string() != segment {
                    bail!("query path not found: {}", key);
                }
                items
                    .get(index)
                    .ok_or_else(|| anyhow!("query path not found: {}", key))?
            }
            _ => bail!("query path not found: {}", key),
        };
    }

    Ok(current)
}
