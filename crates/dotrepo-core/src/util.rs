use anyhow::{anyhow, bail, Result};
use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Component, Path, PathBuf};
use time::format_description::well_known::Rfc3339;
use time::OffsetDateTime;

pub(crate) fn contains_unsafe_shell_like_value(value: &str) -> bool {
    value.contains('\n')
        || value.contains('\r')
        || value.contains('\0')
        || value.contains('`')
        || value.contains("$(")
        || value.contains("${")
}

pub(crate) fn validate_shell_safe_command(field: &str, value: &str) -> Result<()> {
    if contains_unsafe_shell_like_value(value) {
        bail!("{field} contains an unsafe shell-like value");
    }
    Ok(())
}

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

/// Verifies that `path` resolves within `root`, including through symlinks.
pub(crate) fn ensure_path_contained_in_root(root: &Path, path: &Path) -> Result<PathBuf> {
    verify_path_contained_in_root(root, path)?;
    Ok(path.to_path_buf())
}

pub(crate) fn verify_path_contained_in_root(root: &Path, path: &Path) -> Result<()> {
    let canonical_root = fs::canonicalize(root).map_err(|err| {
        anyhow!(
            "failed to canonicalize repository root {}: {}",
            root.display(),
            err
        )
    })?;

    if path.exists()
        || path
            .symlink_metadata()
            .is_ok_and(|meta| meta.file_type().is_symlink())
    {
        let canonical_path = fs::canonicalize(path)
            .map_err(|err| anyhow!("failed to canonicalize path {}: {}", path.display(), err))?;
        if !canonical_path.starts_with(&canonical_root) {
            bail!("path must stay within the repository root");
        }
        return Ok(());
    }

    if let Some(parent) = path.parent() {
        if parent.exists() {
            let canonical_parent = fs::canonicalize(parent).map_err(|err| {
                anyhow!("failed to canonicalize path {}: {}", parent.display(), err)
            })?;
            if !canonical_parent.starts_with(&canonical_root) {
                bail!("path must stay within the repository root");
            }
        }
    }

    Ok(())
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

pub fn validate_repository_identity_segments(host: &str, owner: &str, repo: &str) -> Result<()> {
    for (field, value) in [("host", host), ("owner", owner), ("repo", repo)] {
        if value.trim().is_empty() {
            bail!("{field} must not be empty");
        }
        let path = Path::new(value);
        let mut components = path.components();
        if !matches!(components.next(), Some(Component::Normal(_))) || components.next().is_some() {
            bail!("{field} must be a single path segment");
        }
    }
    Ok(())
}
