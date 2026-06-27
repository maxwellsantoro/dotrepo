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
        || value.contains(';')
        || value.contains('|')
        || value.contains('&')
        || value.contains('<')
        || value.contains('>')
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

    // Attempt full canonicalization first. This resolves symlinks and checks the final target.
    // If the path (or its target) does not exist, canonicalize fails and we fall back to parent check.
    // This reduces (but cannot eliminate) TOCTOU between check and use for non-existing paths.
    // Non-existing paths are only allowed when their resolved parent is contained and the
    // leaf component(s) were already validated to contain only Normal segments by the caller
    // (see resolve_repository_local_path).
    if let Ok(canonical_path) = fs::canonicalize(path) {
        if !canonical_path.starts_with(&canonical_root) {
            bail!("path must stay within the repository root");
        }
        return Ok(());
    }

    // Path does not (currently) exist or is dangling. Verify containing parent if it exists.
    if let Some(parent) = path.parent() {
        // Avoid canonicalizing empty or root-like parents unnecessarily.
        if !parent.as_os_str().is_empty() && parent.exists() {
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

pub fn display_path(root: &Path, path: &Path) -> Result<String> {
    Ok(relative_to_root(root, path)?.display().to_string())
}

pub(crate) fn display_root(root: &Path) -> String {
    fs::canonicalize(root)
        .unwrap_or_else(|_| root.to_path_buf())
        .display()
        .to_string()
}

/// Returns `path` made relative to `root` when `path` is under `root`.
/// Used to avoid leaking absolute paths into user-facing reports, digests, and public JSON.
pub(crate) fn relative_to_root(root: &Path, path: &Path) -> Result<PathBuf> {
    path.strip_prefix(root)
        .map(|relative| relative.to_path_buf())
        .map_err(|_| {
            anyhow!(
                "path {} is not under repository root {}",
                path.display(),
                root.display()
            )
        })
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

/// Shared depth-limited directory walker that *skips symlinks*.
/// This eliminates TOCTOU-adjacent symlink handling divergence and symlink-cycle risks
/// across validation, public export, selection, and claims code paths.
///
/// The `on_entry` closure is invoked for every non-symlink entry (file or dir).
/// Return `true` from the closure to indicate that directories should be recursed into.
pub(crate) fn walk_dir_entries<F>(dir: &Path, mut on_entry: F) -> Result<()>
where
    F: FnMut(&Path, fs::FileType) -> Result<bool>,
{
    walk_dir_entries_impl(dir, 0, &mut on_entry)
}

#[cfg(test)]
mod tests {
    use super::contains_unsafe_shell_like_value;

    #[test]
    fn contains_unsafe_shell_like_value_rejects_chaining_and_substitution() {
        assert!(!contains_unsafe_shell_like_value("cargo test"));
        assert!(!contains_unsafe_shell_like_value("npm run build"));
        assert!(contains_unsafe_shell_like_value("echo $(whoami)"));
        assert!(contains_unsafe_shell_like_value(
            "cargo test; curl attacker"
        ));
        assert!(contains_unsafe_shell_like_value("cargo test && rm -rf /"));
        assert!(contains_unsafe_shell_like_value("cargo test | sh"));
        assert!(contains_unsafe_shell_like_value("cargo test > /tmp/out"));
    }
}

fn walk_dir_entries_impl(
    dir: &Path,
    depth: u32,
    on_entry: &mut dyn FnMut(&Path, fs::FileType) -> Result<bool>,
) -> Result<()> {
    if depth > 20 {
        bail!(
            "directory traversal depth exceeded at {} — possible symlink cycle",
            dir.display()
        );
    }
    for entry in
        fs::read_dir(dir).map_err(|err| anyhow!("failed to read {}: {}", dir.display(), err))?
    {
        let entry = entry?;
        let path = entry.path();
        let file_type = entry.file_type()?;
        if file_type.is_symlink() {
            continue;
        }
        let should_recurse = on_entry(&path, file_type)?;
        if should_recurse && file_type.is_dir() {
            walk_dir_entries_impl(&path, depth + 1, on_entry)?;
        }
    }
    Ok(())
}
