use anyhow::{anyhow, bail, Result};
use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};
use time::{Duration, OffsetDateTime};

use crate::util::{parse_rfc3339, render_rfc3339};

use super::*;

pub fn index_snapshot_digest(index_root: &Path) -> Result<String> {
    let mut files = Vec::new();
    collect_files(index_root, &mut files)?;
    files.sort();

    let mut hasher = Sha256::new();
    for path in files {
        let relative = crate::relative_to_root(index_root, &path)?;
        hasher.update(relative.as_os_str().as_encoded_bytes());
        hasher.update([0]);
        hasher.update(fs::read(&path).map_err(|err| {
            anyhow!(
                "failed to read {} for snapshot digest: {}",
                path.display(),
                err
            )
        })?);
        hasher.update([0xff]);
    }

    Ok(format!("{:x}", hasher.finalize()))
}

pub fn build_public_freshness(
    index_root: &Path,
    stale_after_hours: Option<i64>,
    generated_at: Option<&str>,
    stale_after: Option<&str>,
) -> Result<PublicFreshness> {
    build_public_freshness_with_digest(
        index_root,
        stale_after_hours,
        generated_at,
        stale_after,
        None,
    )
}

pub fn build_public_freshness_with_digest(
    index_root: &Path,
    stale_after_hours: Option<i64>,
    generated_at: Option<&str>,
    stale_after: Option<&str>,
    snapshot_digest: Option<&str>,
) -> Result<PublicFreshness> {
    if stale_after.is_some() && stale_after_hours.is_some() {
        bail!("--stale-after conflicts with --stale-after-hours");
    }
    if stale_after.is_some() && generated_at.is_none() {
        bail!("--stale-after requires --generated-at");
    }

    let generated_at = match generated_at {
        Some(value) => parse_rfc3339("--generated-at", value)?,
        None => OffsetDateTime::now_utc(),
    };
    let stale_after = match (stale_after, stale_after_hours) {
        (Some(value), None) => Some(render_rfc3339(
            "--stale-after",
            parse_rfc3339("--stale-after", value)?,
        )?),
        (None, Some(hours)) => Some(render_rfc3339(
            "stale-after timestamp",
            generated_at + Duration::hours(hours),
        )?),
        (None, None) => None,
        (Some(_), Some(_)) => unreachable!("validated above"),
    };

    Ok(PublicFreshness {
        generated_at: render_rfc3339("public freshness timestamp", generated_at)?,
        snapshot_digest: match snapshot_digest {
            Some(digest) => digest.to_string(),
            None => index_snapshot_digest(index_root)?,
        },
        stale_after,
    })
}

pub fn current_public_freshness(
    index_root: &Path,
    stale_after_hours: Option<i64>,
) -> Result<PublicFreshness> {
    build_public_freshness_with_digest(index_root, stale_after_hours, None, None, None)
}

pub fn public_snapshot_metadata(freshness: PublicFreshness) -> PublicSnapshotMetadata {
    let validators = public_cache_validators(&freshness.snapshot_digest);
    PublicSnapshotMetadata {
        api_version: PUBLIC_API_VERSION,
        generated_at: freshness.generated_at,
        snapshot_digest: freshness.snapshot_digest,
        stale_after: freshness.stale_after,
        strategy: PUBLIC_STATIC_STRATEGY,
        validators,
    }
}

pub fn public_cache_validators(snapshot_digest: &str) -> PublicCacheValidators {
    PublicCacheValidators {
        snapshot: format!("sha256:{snapshot_digest}"),
        etag: format!("\"dotrepo-v0-{snapshot_digest}\""),
    }
}

fn sha256_hex(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    format!("{:x}", hasher.finalize())
}

pub fn public_export_file_manifest(
    out_root: &Path,
    freshness: PublicFreshness,
    outputs: &[(PathBuf, String)],
) -> Result<PublicExportFileManifest> {
    let mut files = outputs
        .iter()
        .map(|(path, contents)| {
            let relative = crate::relative_to_root(out_root, path)?;
            let bytes = contents.as_bytes();
            Ok(PublicExportFileEntry {
                path: relative.display().to_string(),
                bytes: bytes.len(),
                sha256: sha256_hex(bytes),
            })
        })
        .collect::<Result<Vec<_>>>()?;
    files.sort_by(|left, right| left.path.cmp(&right.path));

    Ok(PublicExportFileManifest {
        api_version: PUBLIC_API_VERSION,
        freshness,
        file_count: files.len(),
        files,
    })
}

pub fn export_public_index_static(
    index_root: &Path,
    out_root: &Path,
    freshness: PublicFreshness,
) -> Result<Vec<(PathBuf, String)>> {
    export_public_index_static_with_base(index_root, out_root, freshness, "/")
}

pub fn export_public_index_static_with_base(
    index_root: &Path,
    out_root: &Path,
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<Vec<(PathBuf, String)>> {
    use rayon::prelude::*;

    let mut outputs = Vec::new();
    outputs.push((
        out_root.join("v0/meta.json"),
        serde_json::to_string_pretty(&public_snapshot_metadata(freshness.clone()))?,
    ));

    let identities = list_index_repository_identities(index_root)?;

    // Each repository's exported files are computed in parallel. The per-repo
    // work is independent -- each reads only its own record and evidence from
    // disk and shares no mutable state -- so it parallelizes safely. Results are
    // collected in identity order and emitted serially so the `outputs` vector,
    // and therefore the derived `files.json` manifest, stays byte-identical to
    // the serial exporter.
    let per_repo: Vec<(PublicRepositoryInventoryEntry, Vec<(PathBuf, String)>)> = identities
        .par_iter()
        .map(
            |identity| -> Result<(PublicRepositoryInventoryEntry, Vec<(PathBuf, String)>)> {
                let repo_base = out_root
                    .join("v0/repos")
                    .join(&identity.host)
                    .join(&identity.owner)
                    .join(&identity.repo);
                let candidates = resolve_repository_candidates(
                    index_root,
                    &identity.host,
                    &identity.owner,
                    &identity.repo,
                )?;
                let summary = public_repository_summary_with_candidates(
                    index_root,
                    &identity.host,
                    &identity.owner,
                    &identity.repo,
                    &candidates,
                    freshness.clone(),
                    base_path,
                )?;
                let trust = public_repository_trust_with_candidates(
                    index_root,
                    &identity.host,
                    &identity.owner,
                    &identity.repo,
                    &candidates,
                    freshness.clone(),
                    base_path,
                )?;
                let profile = public_repository_profile_with_candidates(
                    index_root,
                    &identity.host,
                    &identity.owner,
                    &identity.repo,
                    &candidates,
                    freshness.clone(),
                    base_path,
                )?;
                let relations = public_repository_relations_with_base(
                    index_root,
                    &identity.host,
                    &identity.owner,
                    &identity.repo,
                    freshness.clone(),
                    base_path,
                )?;
                let inventory = PublicRepositoryInventoryEntry {
                    identity: summary.identity.clone(),
                    name: summary.repository.name.clone(),
                    description: summary.repository.description.clone(),
                    links: summary.links.clone(),
                };
                let files = vec![
                    (
                        repo_base.join("index.json"),
                        serde_json::to_string_pretty(&summary)?,
                    ),
                    (
                        repo_base.join("trust.json"),
                        serde_json::to_string_pretty(&trust)?,
                    ),
                    (
                        repo_base.join("profile.json"),
                        serde_json::to_string_pretty(&profile)?,
                    ),
                    (
                        repo_base.join("relations.json"),
                        serde_json::to_string_pretty(&relations)?,
                    ),
                    (
                        out_root.join(public_query_input_relative_path(
                            &identity.host,
                            &identity.owner,
                            &identity.repo,
                        )),
                        serde_json::to_string_pretty(
                            &public_query_input_snapshot_with_candidates(
                                index_root,
                                &identity.host,
                                &identity.owner,
                                &identity.repo,
                                &candidates,
                                freshness.clone(),
                            )?,
                        )?,
                    ),
                ];
                Ok((inventory, files))
            },
        )
        .collect::<Result<Vec<_>>>()?;

    let mut inventory = Vec::with_capacity(per_repo.len());
    for (entry, files) in per_repo {
        outputs.extend(files);
        inventory.push(entry);
    }

    outputs.push((
        out_root.join("v0/repos/index.json"),
        serde_json::to_string_pretty(&PublicRepositoryInventoryResponse {
            api_version: PUBLIC_API_VERSION,
            freshness: freshness.clone(),
            repository_count: inventory.len(),
            repositories: inventory,
        })?,
    ));
    let file_manifest = public_export_file_manifest(out_root, freshness, &outputs)?;
    outputs.push((
        out_root.join("v0/files.json"),
        serde_json::to_string_pretty(&file_manifest)?,
    ));

    Ok(outputs)
}
fn collect_files(root: &Path, out: &mut Vec<PathBuf>) -> Result<()> {
    crate::walk_dir_entries(root, |path, file_type| {
        if file_type.is_file() {
            out.push(path.to_path_buf());
            Ok(false)
        } else if file_type.is_dir() {
            Ok(true)
        } else {
            Ok(false)
        }
    })
}
