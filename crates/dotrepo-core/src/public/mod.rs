use anyhow::{anyhow, bail, Result};
use std::path::{Path, PathBuf};

use crate::selection::{resolve_candidates, CandidateManifest};
use crate::util::{repository_identity, validate_repository_identity_segments};
use crate::validation::collect_record_dirs;

mod compare;
mod error;
mod export;
mod pagedigest;
mod profile;
mod relations;
mod search;
mod types;

pub use types::*;

pub use compare::{public_profile_compare, public_profile_compare_with_base};
pub use error::{
    public_error_response, public_repository_profile_or_error,
    public_repository_profile_or_error_with_base, public_repository_profile_or_error_with_base_ref,
    public_repository_query_from_input_or_error_with_base, public_repository_query_or_error,
    public_repository_query_or_error_with_base, public_repository_query_or_error_with_base_ref,
    public_repository_summary_or_error, public_repository_summary_or_error_with_base,
    public_repository_trust_or_error, public_repository_trust_or_error_with_base,
};
pub use export::{
    build_public_freshness, build_public_freshness_with_digest, current_public_freshness,
    export_public_index_static, export_public_index_static_with_base,
    export_public_index_static_with_options, index_snapshot_digest, public_cache_validators,
    public_export_file_manifest, public_snapshot_metadata,
};
pub use pagedigest::{
    build_pagedigest_manifest, load_pagedigest_manifest, PagedigestCoverage, PagedigestEntry,
    PagedigestManifest, PAGEDIGEST_RELATIVE_PATH,
};
pub use profile::{
    load_public_query_input_snapshot, public_query_input_snapshot,
    public_repository_batch_profiles, public_repository_batch_profiles_with_base,
    public_repository_batch_query, public_repository_batch_query_with_base,
    public_repository_profile, public_repository_profile_with_base, public_repository_query,
    public_repository_query_from_input_with_base, public_repository_query_with_base,
    public_repository_summary, public_repository_summary_with_base, public_repository_trust,
    public_repository_trust_with_base,
};
pub use relations::{public_repository_relations, public_repository_relations_with_base};
pub use search::{public_profile_search, public_profile_search_with_base};

pub(crate) use profile::{
    public_query_input_snapshot_with_candidates, public_record_artifacts,
    public_repository_profile_with_candidates, public_repository_summary_with_candidates,
    public_repository_trust_with_candidates,
};
pub(crate) use search::{normalize_search_value, search_item_from_profile};

#[cfg(test)]
pub(crate) use search::{search_ranking_from_profile, trust_confidence_boost};

pub(crate) const PUBLIC_API_VERSION: &str = "v0";
pub(crate) const PUBLIC_CONTENT_ADDRESSED_STRATEGY: &str =
    "content_addressed_summary_trust_and_profile";

/// Maximum repositories per batch profile or batch query request.
pub const PUBLIC_BATCH_MAX_IDENTITIES: usize = 50;
/// Maximum distinct query paths per batch query request.
pub const PUBLIC_BATCH_MAX_PATHS: usize = 25;
/// Maximum `identities × paths` results per batch query request.
pub const PUBLIC_BATCH_MAX_QUERY_RESULTS: usize = 500;

fn validate_batch_identities(identities: &[PublicRepositoryIdentity]) -> Result<()> {
    if identities.is_empty() {
        bail!("batch request requires at least one repository identity");
    }
    if identities.len() > PUBLIC_BATCH_MAX_IDENTITIES {
        bail!(
            "batch request exceeds the maximum of {} repositories (received {})",
            PUBLIC_BATCH_MAX_IDENTITIES,
            identities.len()
        );
    }
    Ok(())
}

fn validate_batch_query_paths(
    identities: &[PublicRepositoryIdentity],
    paths: &[String],
) -> Result<()> {
    validate_batch_identities(identities)?;
    if paths.is_empty() {
        bail!("batch query requires at least one path");
    }
    if paths.len() > PUBLIC_BATCH_MAX_PATHS {
        bail!(
            "batch query exceeds the maximum of {} paths (received {})",
            PUBLIC_BATCH_MAX_PATHS,
            paths.len()
        );
    }
    let result_count = identities
        .len()
        .checked_mul(paths.len())
        .ok_or_else(|| anyhow!("batch query result count overflow"))?;
    if result_count > PUBLIC_BATCH_MAX_QUERY_RESULTS {
        bail!(
            "batch query exceeds the maximum of {} results ({} repositories × {} paths)",
            PUBLIC_BATCH_MAX_QUERY_RESULTS,
            identities.len(),
            paths.len()
        );
    }
    Ok(())
}

#[derive(Debug, Clone, Copy)]
enum PublicLinkKind {
    Repository,
    Profile,
    Trust,
    Query,
    Relations,
}

fn index_repository_scope(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
) -> Result<PathBuf> {
    validate_public_identity(host, owner, repo)?;
    let scope_root = index_root.join("repos").join(host).join(owner).join(repo);
    let manifest_path = scope_root.join("record.toml");
    if !manifest_path.is_file() {
        bail!(
            "repository not found in index: repos/{}/{}/{}/record.toml",
            host,
            owner,
            repo
        );
    }
    Ok(scope_root)
}

fn resolve_repository_candidates(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
) -> Result<Vec<CandidateManifest>> {
    let scope_root = index_repository_scope(index_root, host, owner, repo)?;
    resolve_candidates(&scope_root)
}

fn validate_public_identity(host: &str, owner: &str, repo: &str) -> Result<()> {
    validate_repository_identity_segments(host, owner, repo)
        .map_err(|err| anyhow!("invalid repository identity: {err}"))
}

fn public_identity(
    host: &str,
    owner: &str,
    repo: &str,
    selected: &CandidateManifest,
) -> PublicRepositoryIdentity {
    let source = selected.manifest.record.source.clone().or_else(|| {
        selected.manifest.repo.homepage.clone().filter(|homepage| {
            repository_identity(homepage)
                .map(|identity| identity == (host.to_string(), owner.to_string(), repo.to_string()))
                .unwrap_or(false)
        })
    });

    PublicRepositoryIdentity {
        host: host.to_string(),
        owner: owner.to_string(),
        repo: repo.to_string(),
        source,
    }
}

fn normalize_public_base_path(base_path: &str) -> Result<String> {
    let trimmed = base_path.trim();
    if trimmed.is_empty() || trimmed == "/" {
        return Ok(String::new());
    }
    if !trimmed.starts_with('/') {
        bail!("public base path must start with `/`");
    }

    let normalized = trimmed.trim_end_matches('/');
    if normalized.is_empty() {
        Ok(String::new())
    } else {
        Ok(normalized.to_string())
    }
}

fn public_links_with_base(
    host: &str,
    owner: &str,
    repo: &str,
    kind: PublicLinkKind,
    query_path: Option<&str>,
    base_path: &str,
) -> Result<PublicRepositoryLinks> {
    let base_path = normalize_public_base_path(base_path)?;
    let repository_root = format!("{base_path}/v0/repos/{host}/{owner}/{repo}");
    let repository = format!("{repository_root}/index.json");
    let profile = format!("{repository_root}/profile.json");
    let trust = format!("{repository_root}/trust.json");
    let query_template = format!("{repository_root}/query?path={{dot_path}}");
    let index_path = format!("repos/{host}/{owner}/{repo}/");

    Ok(match kind {
        PublicLinkKind::Repository => PublicRepositoryLinks {
            self_link: repository,
            repository: None,
            trust: Some(trust),
            profile: Some(profile),
            query_template: Some(query_template),
            index_path,
        },
        PublicLinkKind::Profile => PublicRepositoryLinks {
            self_link: profile,
            repository: Some(repository),
            trust: Some(trust),
            profile: None,
            query_template: Some(query_template),
            index_path,
        },
        PublicLinkKind::Trust => PublicRepositoryLinks {
            self_link: trust,
            repository: Some(repository),
            trust: None,
            profile: Some(profile),
            query_template: Some(query_template),
            index_path,
        },
        PublicLinkKind::Query => PublicRepositoryLinks {
            self_link: format!(
                "{repository_root}/query?path={}",
                query_path.unwrap_or("{dot_path}")
            ),
            repository: Some(repository),
            trust: Some(trust),
            profile: Some(profile),
            query_template: Some(query_template),
            index_path,
        },
        PublicLinkKind::Relations => PublicRepositoryLinks {
            self_link: format!("{repository_root}/relations"),
            repository: Some(repository),
            trust: Some(trust),
            profile: Some(profile),
            query_template: Some(query_template),
            index_path,
        },
    })
}

fn public_query_input_relative_path(host: &str, owner: &str, repo: &str) -> PathBuf {
    PathBuf::from("query-input")
        .join(host)
        .join(owner)
        .join(format!("{repo}.json"))
}

fn non_empty_value(value: Option<&str>) -> Option<String> {
    value
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
}

pub fn list_index_repository_identities(
    index_root: &Path,
) -> Result<Vec<PublicRepositoryIdentity>> {
    let repos_root = index_root.join("repos");
    if !repos_root.is_dir() {
        bail!(
            "index root does not contain a repos/ directory: {}",
            repos_root.display()
        );
    }

    let mut record_dirs = Vec::new();
    collect_record_dirs(&repos_root, &mut record_dirs)?;
    record_dirs.sort();

    let mut identities = Vec::new();
    for record_dir in record_dirs {
        let relative = match record_dir.strip_prefix(&repos_root) {
            Ok(relative) => relative,
            Err(_) => continue,
        };
        let segments = relative
            .iter()
            .map(|segment| segment.to_string_lossy().to_string())
            .collect::<Vec<_>>();
        if segments.len() != 3 {
            continue;
        }
        let identity = PublicRepositoryIdentity {
            host: segments[0].clone(),
            owner: segments[1].clone(),
            repo: segments[2].clone(),
            source: None,
        };
        if !identities
            .iter()
            .any(|existing: &PublicRepositoryIdentity| {
                existing.host == identity.host
                    && existing.owner == identity.owner
                    && existing.repo == identity.repo
            })
        {
            identities.push(identity);
        }
    }

    Ok(identities)
}
