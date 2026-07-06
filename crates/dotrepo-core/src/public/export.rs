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
        if relative == Path::new(".crawler-state.toml") {
            continue;
        }
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
    public_snapshot_metadata_with_base(freshness, "/")
}

fn public_snapshot_metadata_with_base(
    freshness: PublicFreshness,
    base_path: &str,
) -> PublicSnapshotMetadata {
    let validators = public_cache_validators(&freshness.snapshot_digest);
    let snapshot_id = snapshot_id(&freshness.snapshot_digest);
    let base_path = base_path.trim().trim_end_matches('/');
    let root = format!("{base_path}/v0/snapshots/{snapshot_id}");
    PublicSnapshotMetadata {
        api_version: PUBLIC_API_VERSION,
        generated_at: freshness.generated_at,
        snapshot_digest: freshness.snapshot_digest,
        stale_after: freshness.stale_after,
        strategy: PUBLIC_CONTENT_ADDRESSED_STRATEGY,
        validators,
        snapshot_id,
        retention: PublicSnapshotRetention {
            edge_guarantee: "current_and_previous_snapshot".into(),
            archive_guarantee: "all_published_snapshots_retrievable_from_archive".into(),
            log_guarantee: "append_only_never_pruned".into(),
        },
        paths: PublicSnapshotPaths {
            inventory: format!("{root}/repos/index.json"),
            files: format!("{root}/files.json"),
            stats: format!("{base_path}/v0/stats.json"),
            query_input_root: format!("{root}/query-input/"),
            snapshot_log: format!("{base_path}/v0/snapshots/log.json"),
            root,
        },
    }
}

fn snapshot_id(snapshot_digest: &str) -> String {
    snapshot_digest.chars().take(12).collect()
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

fn snapshot_log_path(out_root: &Path) -> PathBuf {
    out_root.join("v0/snapshots/log.json")
}

fn load_snapshot_log(out_root: &Path) -> Result<Vec<PublicSnapshotLogEntry>> {
    let path = snapshot_log_path(out_root);
    if !path.exists() {
        return Ok(Vec::new());
    }
    let text = fs::read_to_string(&path).map_err(|err| {
        anyhow!(
            "failed to read previous snapshot log {}: {}",
            path.display(),
            err
        )
    })?;
    let log: PublicSnapshotLog = serde_json::from_str(&text)
        .map_err(|err| anyhow!("invalid snapshot log {}: {}", path.display(), err))?;
    Ok(log.entries)
}

fn public_snapshot_log(
    out_root: &Path,
    freshness: &PublicFreshness,
    repository_count: usize,
    file_count: usize,
) -> Result<PublicSnapshotLog> {
    let mut entries = load_snapshot_log(out_root)?;
    let current = PublicSnapshotLogEntry {
        snapshot_id: snapshot_id(&freshness.snapshot_digest),
        snapshot_digest: freshness.snapshot_digest.clone(),
        generated_at: freshness.generated_at.clone(),
        repository_count,
        file_count,
    };
    match entries
        .iter()
        .position(|entry| entry.snapshot_digest == current.snapshot_digest)
    {
        Some(index) => entries[index] = current,
        None => entries.push(current),
    }
    entries.sort_by(|left, right| {
        left.generated_at
            .cmp(&right.generated_at)
            .then_with(|| left.snapshot_digest.cmp(&right.snapshot_digest))
    });
    Ok(PublicSnapshotLog {
        api_version: PUBLIC_API_VERSION.into(),
        snapshot_count: entries.len(),
        entries,
    })
}

fn public_snapshot_stats(
    log: &PublicSnapshotLog,
    pagedigest: Option<serde_json::Value>,
) -> serde_json::Value {
    let latest = log.entries.last().cloned();
    let deltas = log
        .entries
        .windows(2)
        .map(|pair| {
            let previous = &pair[0];
            let current = &pair[1];
            serde_json::json!({
                "fromSnapshotId": previous.snapshot_id,
                "toSnapshotId": current.snapshot_id,
                "repositoryCountDelta": current.repository_count as isize - previous.repository_count as isize,
                "fileCountDelta": current.file_count as isize - previous.file_count as isize,
            })
        })
        .collect::<Vec<_>>();
    let mut stats = serde_json::json!({
        "apiVersion": PUBLIC_API_VERSION,
        "latest": latest,
        "snapshotCount": log.snapshot_count,
        "history": log.entries,
        "deltas": deltas,
    });
    if let Some(pagedigest) = pagedigest {
        stats["pagedigest"] = pagedigest;
    }
    stats
}

fn pagedigest_economics_stats(
    previous: Option<&PagedigestManifest>,
    current: &PagedigestManifest,
    base_path: &str,
    out_root: &Path,
    outputs: &[(PathBuf, String)],
    manifest_bytes: usize,
) -> Result<serde_json::Value> {
    const COVERED_PREFIX: &str = "v0/repos/";
    let base = normalize_public_base_path(base_path)?;
    let mut bytes_by_key = std::collections::BTreeMap::new();
    for (path, contents) in outputs {
        let relative = crate::relative_to_root(out_root, path)?;
        let relative = relative.display().to_string();
        if relative.starts_with(COVERED_PREFIX) {
            bytes_by_key.insert(format!("{base}/{relative}"), contents.len());
        }
    }

    let mut new_records = 0usize;
    let mut changed_records = 0usize;
    let mut unchanged_records = 0usize;
    let mut bytes_covered = 0usize;
    let mut bytes_avoided = 0usize;
    for (key, entry) in &current.entries {
        let bytes = bytes_by_key.get(key).copied().unwrap_or(0);
        bytes_covered += bytes;
        match previous.and_then(|manifest| manifest.entries.get(key)) {
            None => new_records += 1,
            Some(prior) if prior.content_digest == entry.content_digest => {
                unchanged_records += 1;
                bytes_avoided += bytes;
            }
            Some(_) => changed_records += 1,
        }
    }
    let removed_records = previous
        .map(|manifest| {
            manifest
                .entries
                .keys()
                .filter(|key| !current.entries.contains_key(*key))
                .count()
        })
        .unwrap_or(0);
    let records_needing_fetch = new_records + changed_records;
    Ok(serde_json::json!({
        "version": current.version,
        "siteRev": current.site_rev,
        "generated": current.generated,
        "manifestBytes": manifest_bytes,
        "recordsCovered": current.entries.len(),
        "newRecords": new_records,
        "changedRecords": changed_records,
        "unchangedRecords": unchanged_records,
        "removedRecords": removed_records,
        "recordsNeedingFetch": records_needing_fetch,
        "fetchesAvoided": unchanged_records,
        "bytesCovered": bytes_covered,
        "bytesAvoided": bytes_avoided,
        "estimatedTokensAvoided": bytes_avoided / 4,
    }))
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
    export_public_index_static_with_options(index_root, out_root, freshness, base_path, None)
}

/// Full-option export. `pagedigest_previous` points at the previously
/// published pagedigest manifest that carries revision state forward; when
/// `None`, the exporter looks for one at the manifest's location inside
/// `out_root`, and a first export without any previous manifest seeds
/// revisions at 1.
pub fn export_public_index_static_with_options(
    index_root: &Path,
    out_root: &Path,
    freshness: PublicFreshness,
    base_path: &str,
    pagedigest_previous: Option<&Path>,
) -> Result<Vec<(PathBuf, String)>> {
    use rayon::prelude::*;

    let mut outputs = Vec::new();
    outputs.push((
        out_root.join("v0/meta.json"),
        serde_json::to_string_pretty(&public_snapshot_metadata_with_base(
            freshness.clone(),
            base_path,
        ))?,
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

    let repository_count = inventory.len();
    outputs.push((
        out_root.join("v0/repos/index.json"),
        serde_json::to_string_pretty(&PublicRepositoryInventoryResponse {
            api_version: PUBLIC_API_VERSION,
            freshness: freshness.clone(),
            repository_count,
            repositories: inventory,
        })?,
    ));
    let generated_at = freshness.generated_at.clone();
    let snapshot_root = out_root
        .join("v0/snapshots")
        .join(snapshot_id(&freshness.snapshot_digest));
    let canonical_outputs = outputs
        .iter()
        .filter_map(|(path, contents)| {
            let relative = path.strip_prefix(out_root).ok()?;
            let canonical_relative = if let Ok(rest) = relative.strip_prefix("v0/repos") {
                PathBuf::from("repos").join(rest)
            } else if let Ok(rest) = relative.strip_prefix("query-input") {
                PathBuf::from("query-input").join(rest)
            } else {
                return None;
            };
            Some((snapshot_root.join(canonical_relative), contents.clone()))
        })
        .collect::<Vec<_>>();
    let canonical_file_count = canonical_outputs.len();
    let file_manifest = public_export_file_manifest(out_root, freshness, &canonical_outputs)?;
    outputs.extend(canonical_outputs);
    let rendered_file_manifest = serde_json::to_string_pretty(&file_manifest)?;
    outputs.push((
        out_root.join("v0/files.json"),
        rendered_file_manifest.clone(),
    ));
    outputs.push((snapshot_root.join("files.json"), rendered_file_manifest));
    let snapshot_log = public_snapshot_log(
        out_root,
        &file_manifest.freshness,
        repository_count,
        canonical_file_count,
    )?;
    outputs.push((
        snapshot_log_path(out_root),
        serde_json::to_string_pretty(&snapshot_log)?,
    ));

    let pagedigest_previous_path = pagedigest_previous
        .map(Path::to_path_buf)
        .unwrap_or_else(|| out_root.join(PAGEDIGEST_RELATIVE_PATH));
    let pagedigest_previous_manifest = load_pagedigest_manifest(&pagedigest_previous_path)?;
    let pagedigest_manifest = build_pagedigest_manifest(
        pagedigest_previous_manifest.as_ref(),
        &generated_at,
        base_path,
        out_root,
        &outputs,
    )?;
    let rendered_pagedigest_manifest = serde_json::to_string_pretty(&pagedigest_manifest)?;
    let pagedigest_stats = pagedigest_economics_stats(
        pagedigest_previous_manifest.as_ref(),
        &pagedigest_manifest,
        base_path,
        out_root,
        &outputs,
        rendered_pagedigest_manifest.len(),
    )?;
    outputs.push((
        out_root.join("v0/stats.json"),
        serde_json::to_string_pretty(&public_snapshot_stats(
            &snapshot_log,
            Some(pagedigest_stats),
        ))?,
    ));
    outputs.push((
        out_root.join(PAGEDIGEST_RELATIVE_PATH),
        rendered_pagedigest_manifest,
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
