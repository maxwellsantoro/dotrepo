use anyhow::{anyhow, bail, Result};
use dotrepo_schema::Manifest;
use serde_json::Value;

/// Returns an owned JSON value because callers serialize, diff, or store the result.
pub fn query_manifest_value(manifest: &Manifest, key: &str) -> Result<Value> {
    let document = serde_json::to_value(manifest)?;
    let canonical_key = normalize_query_path(key);
    let value = query_value(&document, &canonical_key).or_else(|_| {
        if canonical_key != key {
            query_value(&document, key)
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
                items
                    .get(index)
                    .ok_or_else(|| anyhow!("query path not found: {}", key))?
            }
            _ => bail!("query path not found: {}", key),
        };
    }

    Ok(current)
}
