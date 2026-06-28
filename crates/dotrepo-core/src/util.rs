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

/// Resolve a repository root relative to the process working directory.
///
/// The path need not exist yet (for example before `import_write` creates it).
/// When the path is missing, containment is checked against the canonical working
/// directory via parent resolution instead of requiring `canonicalize` on the leaf.
pub fn resolve_workspace_repository_root(raw: &str, allow_absolute: bool) -> Result<PathBuf> {
    let raw_path = PathBuf::from(raw);
    let is_absolute = raw_path.is_absolute();
    let resolved = if is_absolute {
        raw_path
    } else {
        std::env::current_dir()?.join(raw_path)
    };

    let cwd = std::env::current_dir()?;
    let canonical_cwd = fs::canonicalize(&cwd).map_err(|err| {
        anyhow!(
            "failed to canonicalize working directory {}: {}",
            cwd.display(),
            err
        )
    })?;

    let canonical = if resolved.exists() {
        fs::canonicalize(&resolved)
            .map_err(|err| anyhow!("failed to resolve repository root `{}`: {}", raw, err))?
    } else {
        verify_path_contained_in_root(&canonical_cwd, &resolved)?;
        resolved
    };

    if !canonical.starts_with(&canonical_cwd) {
        if is_absolute && !allow_absolute {
            bail!(
                "absolute repository root outside the server working directory requires DOTREPO_MCP_ALLOW_ABSOLUTE_ROOT=1"
            );
        }
        if !is_absolute {
            bail!("repository root must stay within the server working directory");
        }
    }

    Ok(canonical)
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
///
/// Query strings, fragments, and trailing path segments after `repo` are ignored.
pub fn repository_identity(url: &str) -> Option<(String, String, String)> {
    let trimmed = url.trim();
    let without_scheme = trimmed
        .strip_prefix("https://")
        .or_else(|| trimmed.strip_prefix("http://"))?;
    let without_query = without_scheme
        .split(['?', '#'])
        .next()
        .unwrap_or(without_scheme)
        .trim_end_matches('/');
    let mut parts = without_query.split('/').filter(|part| !part.is_empty());
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

pub fn record_status_name(status: &dotrepo_schema::RecordStatus) -> &'static str {
    match status {
        dotrepo_schema::RecordStatus::Draft => "draft",
        dotrepo_schema::RecordStatus::Imported => "imported",
        dotrepo_schema::RecordStatus::Inferred => "inferred",
        dotrepo_schema::RecordStatus::Reviewed => "reviewed",
        dotrepo_schema::RecordStatus::Verified => "verified",
        dotrepo_schema::RecordStatus::Canonical => "canonical",
    }
}

pub fn index_record_mirror_path(host: &str, owner: &str, repo: &str) -> String {
    format!("repos/{host}/{owner}/{repo}/record.toml")
}

pub fn identity_from_index_claim_path(path: &Path) -> Option<(String, String, String)> {
    let segments = path
        .iter()
        .map(|segment| segment.to_string_lossy().to_string())
        .collect::<Vec<_>>();
    if segments.len() != 6
        || segments[0] != "repos"
        || segments[4] != "claims"
        || segments[1].trim().is_empty()
        || segments[2].trim().is_empty()
        || segments[3].trim().is_empty()
        || segments[5].trim().is_empty()
    {
        return None;
    }

    Some((
        segments[1].clone(),
        segments[2].clone(),
        segments[3].clone(),
    ))
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

#[cfg(test)]
mod tests {
    use super::{contains_unsafe_shell_like_value, resolve_workspace_repository_root};
    use std::fs;

    #[test]
    fn resolve_workspace_repository_root_accepts_missing_subdirectory() {
        let cwd = std::env::current_dir().expect("cwd available");
        let parent = cwd.join(format!(
            "dotrepo-resolve-root-parent-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("clock works")
                .as_nanos()
        ));
        let missing = parent.join("nested/new-repo");
        fs::create_dir_all(parent.join("nested")).expect("parent created");
        let relative = missing
            .strip_prefix(&cwd)
            .expect("path stays within cwd")
            .to_str()
            .expect("utf-8 path");

        let resolved = resolve_workspace_repository_root(relative, false)
            .expect("missing subdirectory resolves");
        assert_eq!(resolved, missing);

        fs::remove_dir_all(parent).expect("parent removed");
    }

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
