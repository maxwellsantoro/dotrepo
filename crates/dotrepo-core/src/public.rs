use anyhow::{anyhow, bail, Result};
use dotrepo_schema::Manifest;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};
use time::{Duration, OffsetDateTime};

use crate::claims::{require_path_segment, RecordClaimContext};
use crate::query::query_manifest_value;
use crate::selection::{
    public_selected_record, resolve_candidates, resolve_competing_value, resolve_conflict_reason,
    resolve_selection_reason, CandidateManifest,
};
use crate::util::{display_path, parse_rfc3339, render_rfc3339, repository_identity};
use crate::validation::collect_record_dirs;
use crate::{ConflictRelationship, RecordSummary, SelectionReason};

pub(crate) const PUBLIC_API_VERSION: &str = "v0";
pub(crate) const PUBLIC_STATIC_STRATEGY: &str = "static_summary_and_trust";

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct PublicFreshness {
    pub generated_at: String,
    pub snapshot_digest: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stale_after: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct PublicRepositoryIdentity {
    pub host: String,
    pub owner: String,
    pub repo: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicRepositoryFields {
    pub name: String,
    pub description: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub homepage: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub docs_root: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub getting_started: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub owners_team: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub security_contact: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicRecordArtifacts {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub evidence_path: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicSelectedRecord {
    pub manifest_path: String,
    pub record: RecordSummary,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub claim: Option<RecordClaimContext>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub artifacts: Option<PublicRecordArtifacts>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicSelectionReport {
    pub reason: SelectionReason,
    pub record: PublicSelectedRecord,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicConflictReport {
    pub relationship: ConflictRelationship,
    pub reason: SelectionReason,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<Value>,
    pub record: PublicSelectedRecord,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicRepositoryLinks {
    #[serde(rename = "self")]
    pub self_link: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub repository: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub trust: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub query_template: Option<String>,
    pub index_path: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicRepositoryInventoryEntry {
    pub identity: PublicRepositoryIdentity,
    pub name: String,
    pub description: String,
    pub links: PublicRepositoryLinks,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicRepositoryInventoryResponse {
    pub api_version: &'static str,
    pub freshness: PublicFreshness,
    pub repository_count: usize,
    pub repositories: Vec<PublicRepositoryInventoryEntry>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicRepositorySummaryResponse {
    pub api_version: &'static str,
    pub freshness: PublicFreshness,
    pub identity: PublicRepositoryIdentity,
    pub repository: PublicRepositoryFields,
    pub selection: PublicSelectionReport,
    pub conflicts: Vec<PublicConflictReport>,
    pub links: PublicRepositoryLinks,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicTrustResponse {
    pub api_version: &'static str,
    pub freshness: PublicFreshness,
    pub identity: PublicRepositoryIdentity,
    pub selection: PublicSelectionReport,
    pub conflicts: Vec<PublicConflictReport>,
    pub links: PublicRepositoryLinks,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicQueryResponse {
    pub api_version: &'static str,
    pub freshness: PublicFreshness,
    pub identity: PublicRepositoryIdentity,
    pub path: String,
    pub value: Value,
    pub selection: PublicSelectionReport,
    pub conflicts: Vec<PublicConflictReport>,
    pub links: PublicRepositoryLinks,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicQueryInputSelection {
    pub reason: SelectionReason,
    pub record: PublicSelectedRecord,
    pub manifest: Manifest,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicQueryInputConflict {
    pub relationship: ConflictRelationship,
    pub reason: SelectionReason,
    pub record: PublicSelectedRecord,
    pub manifest: Manifest,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicQueryInputSnapshot {
    pub api_version: String,
    pub freshness: PublicFreshness,
    pub identity: PublicRepositoryIdentity,
    pub selection: PublicQueryInputSelection,
    pub conflicts: Vec<PublicQueryInputConflict>,
}

#[derive(Debug, Clone, Copy, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum PublicErrorCode {
    QueryPathNotFound,
    RepositoryNotFound,
    InvalidRepositoryIdentity,
    InternalError,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct PublicErrorDetail {
    pub code: PublicErrorCode,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct PublicErrorResponse {
    pub api_version: &'static str,
    pub freshness: Box<PublicFreshness>,
    pub identity: Box<PublicRepositoryIdentity>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub path: Option<String>,
    pub error: Box<PublicErrorDetail>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicSnapshotMetadata {
    pub api_version: &'static str,
    pub generated_at: String,
    pub snapshot_digest: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stale_after: Option<String>,
    pub strategy: &'static str,
}
pub(crate) fn public_record_artifacts(
    display_root: &Path,
    candidate: &CandidateManifest,
) -> Option<PublicRecordArtifacts> {
    let evidence_path = candidate
        .path
        .parent()
        .map(|parent| parent.join("evidence.md"));
    let evidence_path = evidence_path
        .filter(|path| path.is_file())
        .map(|path| display_path(display_root, &path));

    evidence_path.as_ref()?;

    Some(PublicRecordArtifacts { evidence_path })
}

#[derive(Debug, Clone, Copy)]
enum PublicLinkKind {
    Repository,
    Trust,
    Query,
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

fn validate_public_identity(host: &str, owner: &str, repo: &str) -> Result<()> {
    for (field, value) in [("host", host), ("owner", owner), ("repo", repo)] {
        require_path_segment(field, value)
            .map_err(|err| anyhow!("invalid repository identity: {err}"))?;
    }
    Ok(())
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

fn public_repository_fields(manifest: &Manifest) -> PublicRepositoryFields {
    PublicRepositoryFields {
        name: manifest.repo.name.clone(),
        description: manifest.repo.description.clone(),
        homepage: non_empty_value(manifest.repo.homepage.as_deref()),
        docs_root: manifest
            .docs
            .as_ref()
            .and_then(|docs| non_empty_value(docs.root.as_deref())),
        getting_started: manifest
            .docs
            .as_ref()
            .and_then(|docs| non_empty_value(docs.getting_started.as_deref())),
        owners_team: manifest
            .owners
            .as_ref()
            .and_then(|owners| non_empty_value(owners.team.as_deref())),
        security_contact: manifest
            .owners
            .as_ref()
            .and_then(|owners| non_empty_value(owners.security_contact.as_deref()))
            .filter(|value| value != "unknown"),
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
    let trust = format!("{repository_root}/trust.json");
    let query_template = format!("{repository_root}/query?path={{dot_path}}");
    let index_path = format!("repos/{host}/{owner}/{repo}/");

    Ok(match kind {
        PublicLinkKind::Repository => PublicRepositoryLinks {
            self_link: repository,
            repository: None,
            trust: Some(trust),
            query_template: Some(query_template),
            index_path,
        },
        PublicLinkKind::Trust => PublicRepositoryLinks {
            self_link: trust,
            repository: Some(repository),
            trust: None,
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

fn ensure_public_query_input_version(snapshot: &PublicQueryInputSnapshot) -> Result<()> {
    if snapshot.api_version != PUBLIC_API_VERSION {
        bail!(
            "unsupported public query input apiVersion: {}",
            snapshot.api_version
        );
    }
    Ok(())
}

fn non_empty_value(value: Option<&str>) -> Option<String> {
    value
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
}
pub fn index_snapshot_digest(index_root: &Path) -> Result<String> {
    let mut files = Vec::new();
    collect_files(index_root, &mut files)?;
    files.sort();

    let mut hasher = Sha256::new();
    for path in files {
        let relative = path.strip_prefix(index_root).unwrap_or(&path);
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
        snapshot_digest: index_snapshot_digest(index_root)?,
        stale_after,
    })
}

pub fn current_public_freshness(
    index_root: &Path,
    stale_after_hours: Option<i64>,
) -> Result<PublicFreshness> {
    build_public_freshness(index_root, stale_after_hours, None, None)
}

pub fn public_snapshot_metadata(freshness: PublicFreshness) -> PublicSnapshotMetadata {
    PublicSnapshotMetadata {
        api_version: PUBLIC_API_VERSION,
        generated_at: freshness.generated_at,
        snapshot_digest: freshness.snapshot_digest,
        stale_after: freshness.stale_after,
        strategy: PUBLIC_STATIC_STRATEGY,
    }
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

pub fn public_repository_summary(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
) -> Result<PublicRepositorySummaryResponse> {
    public_repository_summary_with_base(index_root, host, owner, repo, freshness, "/")
}

pub fn public_repository_summary_with_base(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicRepositorySummaryResponse> {
    let scope_root = index_repository_scope(index_root, host, owner, repo)?;
    let candidates = resolve_candidates(&scope_root)?;
    let selected = &candidates[0];
    let reason = resolve_selection_reason(&candidates, selected);

    Ok(PublicRepositorySummaryResponse {
        api_version: PUBLIC_API_VERSION,
        freshness,
        identity: public_identity(host, owner, repo, selected),
        repository: public_repository_fields(&selected.manifest),
        selection: PublicSelectionReport {
            reason,
            record: public_selected_record(index_root, selected),
        },
        conflicts: candidates
            .iter()
            .skip(1)
            .map(|candidate| PublicConflictReport {
                relationship: if candidate.rank == selected.rank {
                    ConflictRelationship::Parallel
                } else {
                    ConflictRelationship::Superseded
                },
                reason: resolve_conflict_reason(reason, selected, candidate),
                value: None,
                record: public_selected_record(index_root, candidate),
            })
            .collect(),
        links: public_links_with_base(
            host,
            owner,
            repo,
            PublicLinkKind::Repository,
            None,
            base_path,
        )?,
    })
}

pub fn public_repository_trust(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
) -> Result<PublicTrustResponse> {
    public_repository_trust_with_base(index_root, host, owner, repo, freshness, "/")
}

pub fn public_repository_trust_with_base(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicTrustResponse> {
    let scope_root = index_repository_scope(index_root, host, owner, repo)?;
    let candidates = resolve_candidates(&scope_root)?;
    let selected = &candidates[0];
    let reason = resolve_selection_reason(&candidates, selected);

    Ok(PublicTrustResponse {
        api_version: PUBLIC_API_VERSION,
        freshness,
        identity: public_identity(host, owner, repo, selected),
        selection: PublicSelectionReport {
            reason,
            record: public_selected_record(index_root, selected),
        },
        conflicts: candidates
            .iter()
            .skip(1)
            .map(|candidate| PublicConflictReport {
                relationship: if candidate.rank == selected.rank {
                    ConflictRelationship::Parallel
                } else {
                    ConflictRelationship::Superseded
                },
                reason: resolve_conflict_reason(reason, selected, candidate),
                value: None,
                record: public_selected_record(index_root, candidate),
            })
            .collect(),
        links: public_links_with_base(host, owner, repo, PublicLinkKind::Trust, None, base_path)?,
    })
}

pub fn public_repository_query(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    path: &str,
    freshness: PublicFreshness,
) -> Result<PublicQueryResponse> {
    public_repository_query_with_base(index_root, host, owner, repo, path, freshness, "/")
}

pub fn public_repository_query_with_base(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    path: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicQueryResponse> {
    let scope_root = index_repository_scope(index_root, host, owner, repo)?;
    let candidates = resolve_candidates(&scope_root)?;
    let selected = &candidates[0];
    let value = query_manifest_value(&selected.manifest, path)?;
    let reason = resolve_selection_reason(&candidates, selected);

    Ok(PublicQueryResponse {
        api_version: PUBLIC_API_VERSION,
        freshness,
        identity: public_identity(host, owner, repo, selected),
        path: path.to_string(),
        value,
        selection: PublicSelectionReport {
            reason,
            record: public_selected_record(index_root, selected),
        },
        conflicts: candidates
            .iter()
            .skip(1)
            .map(|candidate| PublicConflictReport {
                relationship: if candidate.rank == selected.rank {
                    ConflictRelationship::Parallel
                } else {
                    ConflictRelationship::Superseded
                },
                reason: resolve_conflict_reason(reason, selected, candidate),
                value: resolve_competing_value(candidate, path),
                record: public_selected_record(index_root, candidate),
            })
            .collect(),
        links: public_links_with_base(
            host,
            owner,
            repo,
            PublicLinkKind::Query,
            Some(path),
            base_path,
        )?,
    })
}

pub fn public_query_input_snapshot(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
) -> Result<PublicQueryInputSnapshot> {
    let scope_root = index_repository_scope(index_root, host, owner, repo)?;
    let candidates = resolve_candidates(&scope_root)?;
    let selected = &candidates[0];
    let reason = resolve_selection_reason(&candidates, selected);

    Ok(PublicQueryInputSnapshot {
        api_version: PUBLIC_API_VERSION.to_string(),
        freshness,
        identity: public_identity(host, owner, repo, selected),
        selection: PublicQueryInputSelection {
            reason,
            record: public_selected_record(index_root, selected),
            manifest: (*selected.manifest).clone(),
        },
        conflicts: candidates
            .iter()
            .skip(1)
            .map(|candidate| PublicQueryInputConflict {
                relationship: if candidate.rank == selected.rank {
                    ConflictRelationship::Parallel
                } else {
                    ConflictRelationship::Superseded
                },
                reason: resolve_conflict_reason(reason, selected, candidate),
                record: public_selected_record(index_root, candidate),
                manifest: (*candidate.manifest).clone(),
            })
            .collect(),
    })
}

pub fn public_repository_query_from_input_with_base(
    snapshot: &PublicQueryInputSnapshot,
    path: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicQueryResponse> {
    ensure_public_query_input_version(snapshot)?;
    let value = query_manifest_value(&snapshot.selection.manifest, path)?;
    let identity = &snapshot.identity;

    Ok(PublicQueryResponse {
        api_version: PUBLIC_API_VERSION,
        freshness,
        identity: identity.clone(),
        path: path.to_string(),
        value,
        selection: PublicSelectionReport {
            reason: snapshot.selection.reason,
            record: snapshot.selection.record.clone(),
        },
        conflicts: snapshot
            .conflicts
            .iter()
            .map(|candidate| PublicConflictReport {
                relationship: candidate.relationship,
                reason: candidate.reason,
                value: query_manifest_value(&candidate.manifest, path).ok(),
                record: candidate.record.clone(),
            })
            .collect(),
        links: public_links_with_base(
            &identity.host,
            &identity.owner,
            &identity.repo,
            PublicLinkKind::Query,
            Some(path),
            base_path,
        )?,
    })
}

pub fn public_repository_query_from_input_or_error_with_base(
    snapshot: &PublicQueryInputSnapshot,
    path: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> std::result::Result<PublicQueryResponse, PublicErrorResponse> {
    let identity = &snapshot.identity;
    public_repository_query_from_input_with_base(snapshot, path, freshness.clone(), base_path)
        .map_err(|error| {
            public_error_response(
                &identity.host,
                &identity.owner,
                &identity.repo,
                Some(path),
                freshness,
                &error,
            )
        })
}

pub fn load_public_query_input_snapshot(
    export_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
) -> Result<PublicQueryInputSnapshot> {
    validate_public_identity(host, owner, repo)?;
    let path = export_root.join(public_query_input_relative_path(host, owner, repo));
    let text = fs::read_to_string(&path)
        .map_err(|error| anyhow!("failed to read {}: {}", path.display(), error))?;
    let snapshot = serde_json::from_str::<PublicQueryInputSnapshot>(&text)
        .map_err(|error| anyhow!("failed to parse {}: {}", path.display(), error))?;
    ensure_public_query_input_version(&snapshot)?;
    Ok(snapshot)
}

fn classify_public_error(message: &str) -> PublicErrorCode {
    if message.starts_with("query path not found: ") {
        PublicErrorCode::QueryPathNotFound
    } else if message.starts_with("repository not found in index: ") {
        PublicErrorCode::RepositoryNotFound
    } else if message.starts_with("invalid repository identity: ") {
        PublicErrorCode::InvalidRepositoryIdentity
    } else {
        PublicErrorCode::InternalError
    }
}

pub fn public_error_response(
    host: &str,
    owner: &str,
    repo: &str,
    path: Option<&str>,
    freshness: PublicFreshness,
    error: &anyhow::Error,
) -> PublicErrorResponse {
    let message = error.to_string();
    PublicErrorResponse {
        api_version: PUBLIC_API_VERSION,
        freshness: Box::new(freshness),
        identity: Box::new(PublicRepositoryIdentity {
            host: host.to_string(),
            owner: owner.to_string(),
            repo: repo.to_string(),
            source: None,
        }),
        path: path.map(ToOwned::to_owned),
        error: Box::new(PublicErrorDetail {
            code: classify_public_error(&message),
            message,
        }),
    }
}

pub fn public_repository_summary_or_error(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
) -> std::result::Result<PublicRepositorySummaryResponse, PublicErrorResponse> {
    public_repository_summary_or_error_with_base(index_root, host, owner, repo, freshness, "/")
}

pub fn public_repository_summary_or_error_with_base(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> std::result::Result<PublicRepositorySummaryResponse, PublicErrorResponse> {
    public_repository_summary_with_base(index_root, host, owner, repo, freshness.clone(), base_path)
        .map_err(|error| public_error_response(host, owner, repo, None, freshness, &error))
}

pub fn public_repository_trust_or_error(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
) -> std::result::Result<PublicTrustResponse, PublicErrorResponse> {
    public_repository_trust_or_error_with_base(index_root, host, owner, repo, freshness, "/")
}

pub fn public_repository_trust_or_error_with_base(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> std::result::Result<PublicTrustResponse, PublicErrorResponse> {
    public_repository_trust_with_base(index_root, host, owner, repo, freshness.clone(), base_path)
        .map_err(|error| public_error_response(host, owner, repo, None, freshness, &error))
}

pub fn public_repository_query_or_error(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    path: &str,
    freshness: PublicFreshness,
) -> std::result::Result<PublicQueryResponse, PublicErrorResponse> {
    public_repository_query_or_error_with_base(index_root, host, owner, repo, path, freshness, "/")
}

pub fn public_repository_query_or_error_with_base(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    path: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> std::result::Result<PublicQueryResponse, PublicErrorResponse> {
    public_repository_query_with_base(
        index_root,
        host,
        owner,
        repo,
        path,
        freshness.clone(),
        base_path,
    )
    .map_err(|error| public_error_response(host, owner, repo, Some(path), freshness, &error))
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
    let mut outputs = Vec::new();
    outputs.push((
        out_root.join("v0/meta.json"),
        serde_json::to_string_pretty(&public_snapshot_metadata(freshness.clone()))?,
    ));

    let mut inventory = Vec::new();
    for identity in list_index_repository_identities(index_root)? {
        let repo_base = out_root
            .join("v0/repos")
            .join(&identity.host)
            .join(&identity.owner)
            .join(&identity.repo);
        let summary = public_repository_summary_with_base(
            index_root,
            &identity.host,
            &identity.owner,
            &identity.repo,
            freshness.clone(),
            base_path,
        )?;
        let trust = public_repository_trust_with_base(
            index_root,
            &identity.host,
            &identity.owner,
            &identity.repo,
            freshness.clone(),
            base_path,
        )?;
        inventory.push(PublicRepositoryInventoryEntry {
            identity: summary.identity.clone(),
            name: summary.repository.name.clone(),
            description: summary.repository.description.clone(),
            links: summary.links.clone(),
        });
        outputs.push((
            repo_base.join("index.json"),
            serde_json::to_string_pretty(&summary)?,
        ));
        outputs.push((
            repo_base.join("trust.json"),
            serde_json::to_string_pretty(&trust)?,
        ));
        outputs.push((
            out_root.join(public_query_input_relative_path(
                &identity.host,
                &identity.owner,
                &identity.repo,
            )),
            serde_json::to_string_pretty(&public_query_input_snapshot(
                index_root,
                &identity.host,
                &identity.owner,
                &identity.repo,
                freshness.clone(),
            )?)?,
        ));
    }
    outputs.push((
        out_root.join("v0/repos/index.json"),
        serde_json::to_string_pretty(&PublicRepositoryInventoryResponse {
            api_version: PUBLIC_API_VERSION,
            freshness,
            repository_count: inventory.len(),
            repositories: inventory,
        })?,
    ));

    Ok(outputs)
}
fn collect_files(root: &Path, out: &mut Vec<PathBuf>) -> Result<()> {
    collect_files_recursive(root, out, 0)
}

fn collect_files_recursive(root: &Path, out: &mut Vec<PathBuf>, depth: u32) -> Result<()> {
    if depth > 20 {
        bail!(
            "directory traversal depth exceeded at {} — possible symlink cycle",
            root.display()
        );
    }
    for entry in
        fs::read_dir(root).map_err(|err| anyhow!("failed to read {}: {}", root.display(), err))?
    {
        let entry = entry?;
        let path = entry.path();
        let file_type = entry.file_type()?;
        if file_type.is_symlink() {
            continue;
        }
        if file_type.is_dir() {
            collect_files_recursive(&path, out, depth + 1)?;
        } else if file_type.is_file() {
            out.push(path);
        }
    }
    Ok(())
}
