use anyhow::{anyhow, Result};
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};
use time::format_description::well_known::Rfc3339;
use time::OffsetDateTime;

pub fn render_rfc3339(label: &str, timestamp: OffsetDateTime) -> Result<String> {
    timestamp
        .format(&Rfc3339)
        .map_err(|err| anyhow!("failed to render {label}: {err}"))
}

pub fn parse_rfc3339(label: &str, value: &str) -> Result<OffsetDateTime> {
    OffsetDateTime::parse(value, &Rfc3339)
        .map_err(|err| anyhow!("failed to parse {label} as RFC3339: {err}"))
}

pub fn normalize_rfc3339(label: &str, value: &str) -> Result<String> {
    render_rfc3339(label, parse_rfc3339(label, value)?)
}

pub fn current_timestamp_rfc3339() -> Result<String> {
    render_rfc3339("current timestamp", OffsetDateTime::now_utc())
}

pub fn display_path(root: &Path, path: &Path) -> String {
    path.strip_prefix(root)
        .unwrap_or(path)
        .display()
        .to_string()
}

pub(crate) fn manifest_path(root: &Path) -> PathBuf {
    let canonical = root.join(".repo");
    if canonical.exists() {
        canonical
    } else {
        root.join("record.toml")
    }
}

pub fn source_digest(source_bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(source_bytes);
    format!("{:x}", hasher.finalize())
}

/// Parses `https://host/owner/repo` style URLs into identity triples.
pub(crate) fn repository_identity(url: &str) -> Option<(String, String, String)> {
    let trimmed = url.trim();
    let without_scheme = trimmed
        .strip_prefix("https://")
        .or_else(|| trimmed.strip_prefix("http://"))?;
    let mut parts = without_scheme.split('/');
    let host = parts.next()?.trim().trim_end_matches(':').to_string();
    if host.is_empty() {
        return None;
    }

    let owner = parts.next()?.trim().to_string();
    let repo = parts.next()?.trim().trim_end_matches(".git").to_string();
    if owner.is_empty() || repo.is_empty() {
        return None;
    }

    Some((host, owner, repo))
}
