use anyhow::{anyhow, bail, Result};
use dotrepo_schema::{
    parse_synthesis_document, Manifest, RelationKind, SynthesisDocument, SynthesisMode,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;
use std::fs;
use std::path::{Path, PathBuf};
use time::{Duration, OffsetDateTime};

use crate::claims::RecordClaimContext;
use crate::query::query_manifest_value;
use crate::selection::{
    public_selected_record, resolve_candidates, resolve_competing_value, resolve_conflict_reason,
    resolve_selection_reason, CandidateManifest,
};
use crate::synthesis::validate_synthesis;
use crate::util::{
    display_path, parse_rfc3339, record_status_name, render_rfc3339, repository_identity,
};
use crate::util::{repository_reference_identity, validate_repository_identity_segments};
use crate::validation::collect_record_dirs;
use crate::{ConflictRelationship, RecordSummary, SelectionReason};

pub(crate) const PUBLIC_API_VERSION: &str = "v0";
pub(crate) const PUBLIC_STATIC_STRATEGY: &str = "static_summary_trust_and_profile";

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

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicResearchExecution {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub build: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub test: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicResearchDocs {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub root: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub getting_started: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub architecture: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub api: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicResearchOwnership {
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub maintainers: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub team: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub security_contact: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicResearchCompleteness {
    pub has_build: bool,
    pub has_test: bool,
    pub has_docs: bool,
    pub has_security_contact: bool,
    pub has_ownership_signal: bool,
    pub has_license: bool,
    pub conflict_count: usize,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicResearchRecord {
    pub manifest_path: String,
    pub mode: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub generated_at: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub evidence_path: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicResearchTrust {
    pub selected_status: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub confidence: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub provenance: Vec<String>,
    pub selection_reason: SelectionReason,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicResearchSynthesisArchitecture {
    pub summary: String,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub entry_points: Vec<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub key_concepts: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicResearchSynthesisForAgents {
    pub how_to_build: String,
    pub how_to_test: String,
    pub how_to_contribute: String,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub gotchas: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicResearchSynthesis {
    pub synthesis_path: String,
    pub generated_at: String,
    pub source_commit: String,
    pub model: String,
    pub provider: String,
    pub mode: String,
    pub architecture: PublicResearchSynthesisArchitecture,
    pub for_agents: PublicResearchSynthesisForAgents,
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
    pub profile: Option<String>,
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

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicResearchProfileResponse {
    pub api_version: &'static str,
    pub freshness: PublicFreshness,
    pub identity: PublicRepositoryIdentity,
    pub record: PublicResearchRecord,
    pub purpose: String,
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub homepage: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub license: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub visibility: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub project_status: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub languages: Vec<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub topics: Vec<String>,
    pub execution: PublicResearchExecution,
    pub docs: PublicResearchDocs,
    pub ownership: PublicResearchOwnership,
    pub completeness: PublicResearchCompleteness,
    pub trust: PublicResearchTrust,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub synthesis: Option<PublicResearchSynthesis>,
    pub conflicts: Vec<PublicConflictReport>,
    pub links: PublicRepositoryLinks,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicBatchProfileItem {
    pub identity: PublicRepositoryIdentity,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub profile: Option<Box<PublicResearchProfileResponse>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<Box<PublicErrorDetail>>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicBatchProfileResponse {
    pub api_version: &'static str,
    pub freshness: PublicFreshness,
    pub result_count: usize,
    pub results: Vec<PublicBatchProfileItem>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicBatchQueryItem {
    pub identity: PublicRepositoryIdentity,
    pub path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub query: Option<Box<PublicQueryResponse>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<Box<PublicErrorDetail>>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicBatchQueryResponse {
    pub api_version: &'static str,
    pub freshness: PublicFreshness,
    pub repository_count: usize,
    pub path_count: usize,
    pub result_count: usize,
    pub results: Vec<PublicBatchQueryItem>,
}

#[derive(Debug, Clone, Default)]
pub struct PublicProfileSearchOptions {
    pub query: Option<String>,
    pub languages: Vec<String>,
    pub topics: Vec<String>,
    pub statuses: Vec<String>,
    pub confidences: Vec<String>,
    pub require_build: bool,
    pub require_test: bool,
    pub require_docs: bool,
    pub require_security_contact: bool,
    pub require_license: bool,
    pub limit: Option<usize>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicProfileSearchItem {
    pub identity: PublicRepositoryIdentity,
    pub name: String,
    pub purpose: String,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub languages: Vec<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub topics: Vec<String>,
    pub completeness: PublicResearchCompleteness,
    pub trust: PublicResearchTrust,
    pub matched: Vec<String>,
    pub ranking: PublicProfileSearchRanking,
    pub links: PublicRepositoryLinks,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicProfileSearchRanking {
    pub score: usize,
    pub matched_field_count: usize,
    pub completeness_signal_count: usize,
    pub basis: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicProfileSearchResponse {
    pub api_version: &'static str,
    pub freshness: PublicFreshness,
    pub query: Option<String>,
    pub filters: PublicProfileSearchAppliedFilters,
    pub total_repository_count: usize,
    pub matched_count: usize,
    pub returned_count: usize,
    pub results: Vec<PublicProfileSearchItem>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicProfileSearchAppliedFilters {
    #[serde(default)]
    pub languages: Vec<String>,
    #[serde(default)]
    pub topics: Vec<String>,
    #[serde(default)]
    pub statuses: Vec<String>,
    #[serde(default)]
    pub confidences: Vec<String>,
    pub require_build: bool,
    pub require_test: bool,
    pub require_docs: bool,
    pub require_security_contact: bool,
    pub require_license: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub limit: Option<usize>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicProfileCompareItem {
    pub identity: PublicRepositoryIdentity,
    pub name: String,
    pub purpose: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub homepage: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub license: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub languages: Vec<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub topics: Vec<String>,
    pub execution: PublicResearchExecution,
    pub docs: PublicResearchDocs,
    pub ownership: PublicResearchOwnership,
    pub completeness: PublicResearchCompleteness,
    pub trust: PublicResearchTrust,
    pub links: PublicRepositoryLinks,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicProfileCompareTextValue {
    pub identity: PublicRepositoryIdentity,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicProfileCompareBoolValue {
    pub identity: PublicRepositoryIdentity,
    pub value: bool,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicProfileCompareSignals {
    #[serde(default)]
    pub shared_languages: Vec<String>,
    #[serde(default)]
    pub shared_topics: Vec<String>,
    pub licenses: Vec<PublicProfileCompareTextValue>,
    pub selected_statuses: Vec<PublicProfileCompareTextValue>,
    pub confidences: Vec<PublicProfileCompareTextValue>,
    pub has_build: Vec<PublicProfileCompareBoolValue>,
    pub has_test: Vec<PublicProfileCompareBoolValue>,
    pub has_docs: Vec<PublicProfileCompareBoolValue>,
    pub has_security_contact: Vec<PublicProfileCompareBoolValue>,
    pub has_license: Vec<PublicProfileCompareBoolValue>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicProfileCompareResponse {
    pub api_version: &'static str,
    pub freshness: PublicFreshness,
    pub repository_count: usize,
    pub results: Vec<PublicProfileCompareItem>,
    pub signals: PublicProfileCompareSignals,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicRelationItem {
    pub relationship: String,
    pub direction: String,
    pub target: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub notes: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub trust: Option<PublicRelationTrust>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub identity: Option<PublicRepositoryIdentity>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub profile: Option<Box<PublicProfileSearchItem>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<Box<PublicErrorDetail>>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicRelationTrust {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub confidence: Option<String>,
    pub provenance: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub notes: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicRelationsResponse {
    pub api_version: &'static str,
    pub freshness: PublicFreshness,
    pub identity: PublicRepositoryIdentity,
    pub relation_count: usize,
    pub references: Vec<PublicRelationItem>,
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
    pub validators: PublicCacheValidators,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicCacheValidators {
    pub snapshot: String,
    pub etag: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicExportFileEntry {
    pub path: String,
    pub bytes: usize,
    pub sha256: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicExportFileManifest {
    pub api_version: &'static str,
    pub freshness: PublicFreshness,
    pub file_count: usize,
    pub files: Vec<PublicExportFileEntry>,
}
pub(crate) fn public_record_artifacts(
    display_root: &Path,
    candidate: &CandidateManifest,
) -> Option<PublicRecordArtifacts> {
    let evidence_path = candidate.path.parent()?.join("evidence.md");
    if !evidence_path.is_file() {
        return None;
    }
    let relative = display_path(display_root, &evidence_path).ok()?;
    Some(PublicRecordArtifacts {
        evidence_path: Some(relative),
    })
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

fn public_research_execution(manifest: &Manifest) -> PublicResearchExecution {
    PublicResearchExecution {
        build: non_empty_value(manifest.repo.build.as_deref()),
        test: non_empty_value(manifest.repo.test.as_deref()),
    }
}

fn public_research_docs(manifest: &Manifest) -> PublicResearchDocs {
    let docs = manifest.docs.as_ref();
    PublicResearchDocs {
        root: docs.and_then(|docs| non_empty_value(docs.root.as_deref())),
        getting_started: docs.and_then(|docs| non_empty_value(docs.getting_started.as_deref())),
        architecture: docs.and_then(|docs| non_empty_value(docs.architecture.as_deref())),
        api: docs.and_then(|docs| non_empty_value(docs.api.as_deref())),
    }
}

fn public_research_ownership(manifest: &Manifest) -> PublicResearchOwnership {
    let owners = manifest.owners.as_ref();
    PublicResearchOwnership {
        maintainers: owners
            .map(|owners| owners.maintainers.clone())
            .unwrap_or_default(),
        team: owners.and_then(|owners| non_empty_value(owners.team.as_deref())),
        security_contact: owners
            .and_then(|owners| non_empty_value(owners.security_contact.as_deref()))
            .filter(|value| value != "unknown"),
    }
}

fn public_research_completeness(
    manifest: &Manifest,
    docs: &PublicResearchDocs,
    ownership: &PublicResearchOwnership,
    conflict_count: usize,
) -> PublicResearchCompleteness {
    PublicResearchCompleteness {
        has_build: non_empty_value(manifest.repo.build.as_deref()).is_some(),
        has_test: non_empty_value(manifest.repo.test.as_deref()).is_some(),
        has_docs: docs.root.is_some()
            || docs.getting_started.is_some()
            || docs.architecture.is_some()
            || docs.api.is_some(),
        has_security_contact: ownership.security_contact.is_some(),
        has_ownership_signal: !ownership.maintainers.is_empty() || ownership.team.is_some(),
        has_license: non_empty_value(manifest.repo.license.as_deref()).is_some(),
        conflict_count,
    }
}

fn record_mode_name(mode: &dotrepo_schema::RecordMode) -> &'static str {
    match mode {
        dotrepo_schema::RecordMode::Native => "native",
        dotrepo_schema::RecordMode::Overlay => "overlay",
    }
}

fn public_research_record(index_root: &Path, selected: &CandidateManifest) -> PublicResearchRecord {
    PublicResearchRecord {
        manifest_path: display_path(index_root, &selected.path)
            .unwrap_or_else(|_| selected.path.display().to_string()),
        mode: record_mode_name(&selected.manifest.record.mode).to_string(),
        source: selected.manifest.record.source.clone(),
        generated_at: selected.manifest.record.generated_at.clone(),
        evidence_path: public_record_artifacts(index_root, selected)
            .and_then(|artifacts| artifacts.evidence_path),
    }
}

fn public_research_trust(
    selected: &CandidateManifest,
    selection_reason: SelectionReason,
) -> PublicResearchTrust {
    let trust = selected.manifest.record.trust.as_ref();
    PublicResearchTrust {
        selected_status: record_status_name(&selected.manifest.record.status).to_string(),
        confidence: trust.and_then(|trust| non_empty_value(trust.confidence.as_deref())),
        provenance: trust
            .map(|trust| trust.provenance.clone())
            .unwrap_or_default(),
        selection_reason,
    }
}

fn synthesis_mode_name(mode: &SynthesisMode) -> &'static str {
    match mode {
        SynthesisMode::Generated => "generated",
        SynthesisMode::Contributed => "contributed",
    }
}

fn public_research_synthesis_from_document(
    display_root: &Path,
    synthesis_path: &Path,
    synthesis: SynthesisDocument,
) -> PublicResearchSynthesis {
    PublicResearchSynthesis {
        synthesis_path: display_path(display_root, synthesis_path)
            .unwrap_or_else(|_| synthesis_path.display().to_string()),
        generated_at: synthesis.synthesis.generated_at,
        source_commit: synthesis.synthesis.source_commit,
        model: synthesis.synthesis.model,
        provider: synthesis.synthesis.provider,
        mode: synthesis_mode_name(&synthesis.synthesis.mode).to_string(),
        architecture: PublicResearchSynthesisArchitecture {
            summary: synthesis.synthesis.architecture.summary,
            entry_points: synthesis.synthesis.architecture.entry_points,
            key_concepts: synthesis.synthesis.architecture.key_concepts,
        },
        for_agents: PublicResearchSynthesisForAgents {
            how_to_build: synthesis.synthesis.for_agents.how_to_build,
            how_to_test: synthesis.synthesis.for_agents.how_to_test,
            how_to_contribute: synthesis.synthesis.for_agents.how_to_contribute,
            gotchas: synthesis.synthesis.for_agents.gotchas,
        },
    }
}

fn public_research_synthesis(
    index_root: &Path,
    selected: &CandidateManifest,
) -> Result<Option<PublicResearchSynthesis>> {
    let Some(record_root) = selected.path.parent() else {
        return Ok(None);
    };
    let synthesis_path = record_root.join("synthesis.toml");
    if !synthesis_path.is_file() {
        return Ok(None);
    }
    let raw = fs::read_to_string(&synthesis_path)
        .map_err(|err| anyhow!("failed to read {}: {}", synthesis_path.display(), err))?;
    let synthesis = parse_synthesis_document(&raw)
        .map_err(|err| anyhow!("failed to parse {}: {}", synthesis_path.display(), err))?;
    validate_synthesis(&selected.manifest, &synthesis)
        .map_err(|err| anyhow!("invalid {}: {}", synthesis_path.display(), err))?;
    Ok(Some(public_research_synthesis_from_document(
        index_root,
        &synthesis_path,
        synthesis,
    )))
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
    let candidates = resolve_repository_candidates(index_root, host, owner, repo)?;
    public_repository_summary_with_candidates(
        index_root,
        host,
        owner,
        repo,
        &candidates,
        freshness,
        base_path,
    )
}

fn public_repository_summary_with_candidates(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    candidates: &[CandidateManifest],
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicRepositorySummaryResponse> {
    let selected = &candidates[0];
    let reason = resolve_selection_reason(candidates, selected);

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
    let candidates = resolve_repository_candidates(index_root, host, owner, repo)?;
    public_repository_trust_with_candidates(
        index_root,
        host,
        owner,
        repo,
        &candidates,
        freshness,
        base_path,
    )
}

fn public_repository_trust_with_candidates(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    candidates: &[CandidateManifest],
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicTrustResponse> {
    let selected = &candidates[0];
    let reason = resolve_selection_reason(candidates, selected);

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

pub fn public_repository_profile(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
) -> Result<PublicResearchProfileResponse> {
    public_repository_profile_with_base(index_root, host, owner, repo, freshness, "/")
}

pub fn public_repository_profile_with_base(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicResearchProfileResponse> {
    let candidates = resolve_repository_candidates(index_root, host, owner, repo)?;
    public_repository_profile_with_candidates(
        index_root,
        host,
        owner,
        repo,
        &candidates,
        freshness,
        base_path,
    )
}

fn public_repository_profile_with_candidates(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    candidates: &[CandidateManifest],
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicResearchProfileResponse> {
    let selected = &candidates[0];
    let reason = resolve_selection_reason(candidates, selected);
    let docs = public_research_docs(&selected.manifest);
    let ownership = public_research_ownership(&selected.manifest);
    let synthesis = public_research_synthesis(index_root, selected)?;
    let conflicts = candidates
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
        .collect::<Vec<_>>();

    Ok(PublicResearchProfileResponse {
        api_version: PUBLIC_API_VERSION,
        freshness,
        identity: public_identity(host, owner, repo, selected),
        record: public_research_record(index_root, selected),
        purpose: selected.manifest.repo.description.clone(),
        name: selected.manifest.repo.name.clone(),
        homepage: non_empty_value(selected.manifest.repo.homepage.as_deref()),
        license: non_empty_value(selected.manifest.repo.license.as_deref()),
        visibility: non_empty_value(selected.manifest.repo.visibility.as_deref()),
        project_status: non_empty_value(selected.manifest.repo.status.as_deref()),
        languages: selected.manifest.repo.languages.clone(),
        topics: selected.manifest.repo.topics.clone(),
        execution: public_research_execution(&selected.manifest),
        completeness: public_research_completeness(
            &selected.manifest,
            &docs,
            &ownership,
            conflicts.len(),
        ),
        docs,
        ownership,
        trust: public_research_trust(selected, reason),
        synthesis,
        conflicts,
        links: public_links_with_base(host, owner, repo, PublicLinkKind::Profile, None, base_path)?,
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

pub fn public_repository_batch_profiles_with_base(
    index_root: &Path,
    identities: &[PublicRepositoryIdentity],
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicBatchProfileResponse> {
    normalize_public_base_path(base_path)?;
    validate_batch_identities(identities)?;
    let mut results = Vec::new();
    for identity in identities {
        let requested_identity = PublicRepositoryIdentity {
            host: identity.host.clone(),
            owner: identity.owner.clone(),
            repo: identity.repo.clone(),
            source: identity.source.clone(),
        };
        match public_repository_profile_or_error_with_base_ref(
            index_root,
            &identity.host,
            &identity.owner,
            &identity.repo,
            &freshness,
            base_path,
        ) {
            Ok(profile) => results.push(PublicBatchProfileItem {
                identity: profile.identity.clone(),
                profile: Some(Box::new(profile)),
                error: None,
            }),
            Err(error) => results.push(PublicBatchProfileItem {
                identity: requested_identity,
                profile: None,
                error: Some(error.error),
            }),
        }
    }

    Ok(PublicBatchProfileResponse {
        api_version: PUBLIC_API_VERSION,
        freshness,
        result_count: results.len(),
        results,
    })
}

pub fn public_repository_batch_profiles(
    index_root: &Path,
    identities: &[PublicRepositoryIdentity],
    freshness: PublicFreshness,
) -> Result<PublicBatchProfileResponse> {
    public_repository_batch_profiles_with_base(index_root, identities, freshness, "/")
}

pub fn public_repository_batch_query_with_base(
    index_root: &Path,
    identities: &[PublicRepositoryIdentity],
    paths: &[String],
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicBatchQueryResponse> {
    normalize_public_base_path(base_path)?;
    validate_batch_query_paths(identities, paths)?;
    let mut results = Vec::new();
    for identity in identities {
        for path in paths {
            let requested_identity = PublicRepositoryIdentity {
                host: identity.host.clone(),
                owner: identity.owner.clone(),
                repo: identity.repo.clone(),
                source: identity.source.clone(),
            };
            match public_repository_query_or_error_with_base_ref(
                index_root,
                &identity.host,
                &identity.owner,
                &identity.repo,
                path,
                &freshness,
                base_path,
            ) {
                Ok(query) => results.push(PublicBatchQueryItem {
                    identity: query.identity.clone(),
                    path: path.clone(),
                    query: Some(Box::new(query)),
                    error: None,
                }),
                Err(error) => results.push(PublicBatchQueryItem {
                    identity: requested_identity,
                    path: path.clone(),
                    query: None,
                    error: Some(error.error),
                }),
            }
        }
    }

    Ok(PublicBatchQueryResponse {
        api_version: PUBLIC_API_VERSION,
        freshness,
        repository_count: identities.len(),
        path_count: paths.len(),
        result_count: results.len(),
        results,
    })
}

pub fn public_repository_batch_query(
    index_root: &Path,
    identities: &[PublicRepositoryIdentity],
    paths: &[String],
    freshness: PublicFreshness,
) -> Result<PublicBatchQueryResponse> {
    public_repository_batch_query_with_base(index_root, identities, paths, freshness, "/")
}

fn normalize_search_value(value: &str) -> String {
    value.trim().to_ascii_lowercase()
}

fn contains_normalized(values: &[String], expected: &str) -> bool {
    let expected = normalize_search_value(expected);
    values
        .iter()
        .any(|value| normalize_search_value(value) == expected)
}

fn option_matches_filter(actual: Option<&str>, filters: &[String]) -> bool {
    filters.is_empty()
        || actual
            .map(|value| {
                filters
                    .iter()
                    .any(|filter| normalize_search_value(value) == normalize_search_value(filter))
            })
            .unwrap_or(false)
}

fn profile_matches_filters(
    profile: &PublicResearchProfileResponse,
    options: &PublicProfileSearchOptions,
) -> bool {
    if !options
        .languages
        .iter()
        .all(|language| contains_normalized(&profile.languages, language))
    {
        return false;
    }
    if !options
        .topics
        .iter()
        .all(|topic| contains_normalized(&profile.topics, topic))
    {
        return false;
    }
    if !option_matches_filter(Some(&profile.trust.selected_status), &options.statuses) {
        return false;
    }
    if !option_matches_filter(profile.trust.confidence.as_deref(), &options.confidences) {
        return false;
    }
    if options.require_build && !profile.completeness.has_build {
        return false;
    }
    if options.require_test && !profile.completeness.has_test {
        return false;
    }
    if options.require_docs && !profile.completeness.has_docs {
        return false;
    }
    if options.require_security_contact && !profile.completeness.has_security_contact {
        return false;
    }
    if options.require_license && !profile.completeness.has_license {
        return false;
    }
    true
}

fn profile_query_matches(profile: &PublicResearchProfileResponse, query: &str) -> Vec<String> {
    let query = normalize_search_value(query);
    if query.is_empty() {
        return vec!["all".into()];
    }
    let mut matched = Vec::new();
    let text_fields = [
        (
            "identity",
            format!(
                "{}/{}/{}",
                profile.identity.host, profile.identity.owner, profile.identity.repo
            ),
        ),
        ("name", profile.name.clone()),
        ("purpose", profile.purpose.clone()),
        ("homepage", profile.homepage.clone().unwrap_or_default()),
        ("license", profile.license.clone().unwrap_or_default()),
    ];
    for (field, value) in text_fields {
        if normalize_search_value(&value).contains(&query) {
            matched.push(field.to_string());
        }
    }
    if profile
        .languages
        .iter()
        .any(|language| normalize_search_value(language).contains(&query))
    {
        matched.push("languages".into());
    }
    if profile
        .topics
        .iter()
        .any(|topic| normalize_search_value(topic).contains(&query))
    {
        matched.push("topics".into());
    }
    matched
}

fn completeness_signal_count(completeness: &PublicResearchCompleteness) -> usize {
    [
        completeness.has_build,
        completeness.has_test,
        completeness.has_docs,
        completeness.has_security_contact,
        completeness.has_ownership_signal,
        completeness.has_license,
    ]
    .into_iter()
    .filter(|signal| *signal)
    .count()
}

pub(crate) fn search_ranking_from_profile(
    profile: &PublicResearchProfileResponse,
    matched: &[String],
) -> PublicProfileSearchRanking {
    let completeness_signal_count = completeness_signal_count(&profile.completeness);
    let trust_boost = trust_confidence_boost(profile.trust.confidence.as_deref());
    let mut basis = Vec::new();
    if !matched.is_empty() {
        basis.push("matchedFields".into());
    }
    if completeness_signal_count > 0 {
        basis.push("profileCompleteness".into());
    }
    if trust_boost > 0 {
        basis.push("trustConfidence".into());
    }
    PublicProfileSearchRanking {
        score: matched.len() * 10 + completeness_signal_count + trust_boost,
        matched_field_count: matched.len(),
        completeness_signal_count,
        basis,
    }
}

pub(crate) fn trust_confidence_boost(confidence: Option<&str>) -> usize {
    match confidence.map(|c| c.to_ascii_lowercase()) {
        Some(c) if c == "high" => 3,
        Some(c) if c == "medium" => 1,
        _ => 0,
    }
}

fn search_item_from_profile(
    profile: PublicResearchProfileResponse,
    matched: Vec<String>,
) -> PublicProfileSearchItem {
    let ranking = search_ranking_from_profile(&profile, &matched);
    PublicProfileSearchItem {
        identity: profile.identity,
        name: profile.name,
        purpose: profile.purpose,
        languages: profile.languages,
        topics: profile.topics,
        completeness: profile.completeness,
        trust: profile.trust,
        matched,
        ranking,
        links: profile.links,
    }
}

pub fn public_profile_search_with_base(
    index_root: &Path,
    options: PublicProfileSearchOptions,
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicProfileSearchResponse> {
    normalize_public_base_path(base_path)?;
    let identities = list_index_repository_identities(index_root)?;
    let mut results = Vec::new();
    for identity in &identities {
        let candidates = resolve_repository_candidates(
            index_root,
            &identity.host,
            &identity.owner,
            &identity.repo,
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
        if !profile_matches_filters(&profile, &options) {
            continue;
        }
        let matched = if let Some(query) = options.query.as_deref() {
            profile_query_matches(&profile, query)
        } else {
            vec!["filters".into()]
        };
        if matched.is_empty() {
            continue;
        }
        results.push(search_item_from_profile(profile, matched));
    }
    results.sort_by(|left, right| {
        right
            .ranking
            .score
            .cmp(&left.ranking.score)
            .then_with(|| {
                right
                    .ranking
                    .matched_field_count
                    .cmp(&left.ranking.matched_field_count)
            })
            .then_with(|| left.identity.host.cmp(&right.identity.host))
            .then_with(|| left.identity.owner.cmp(&right.identity.owner))
            .then_with(|| left.identity.repo.cmp(&right.identity.repo))
    });
    let matched_count = results.len();
    if let Some(limit) = options.limit {
        results.truncate(limit);
    }

    Ok(PublicProfileSearchResponse {
        api_version: PUBLIC_API_VERSION,
        freshness,
        query: options.query.clone(),
        filters: PublicProfileSearchAppliedFilters {
            languages: options.languages.clone(),
            topics: options.topics.clone(),
            statuses: options.statuses.clone(),
            confidences: options.confidences.clone(),
            require_build: options.require_build,
            require_test: options.require_test,
            require_docs: options.require_docs,
            require_security_contact: options.require_security_contact,
            require_license: options.require_license,
            limit: options.limit,
        },
        total_repository_count: identities.len(),
        matched_count,
        returned_count: results.len(),
        results,
    })
}

pub fn public_profile_search(
    index_root: &Path,
    options: PublicProfileSearchOptions,
    freshness: PublicFreshness,
) -> Result<PublicProfileSearchResponse> {
    public_profile_search_with_base(index_root, options, freshness, "/")
}

fn compare_item_from_profile(profile: PublicResearchProfileResponse) -> PublicProfileCompareItem {
    PublicProfileCompareItem {
        identity: profile.identity,
        name: profile.name,
        purpose: profile.purpose,
        homepage: profile.homepage,
        license: profile.license,
        languages: profile.languages,
        topics: profile.topics,
        execution: profile.execution,
        docs: profile.docs,
        ownership: profile.ownership,
        completeness: profile.completeness,
        trust: profile.trust,
        links: profile.links,
    }
}

fn shared_profile_values<F>(items: &[PublicProfileCompareItem], select: F) -> Vec<String>
where
    F: Fn(&PublicProfileCompareItem) -> &[String],
{
    let Some((first, rest)) = items.split_first() else {
        return Vec::new();
    };
    let mut shared = select(first)
        .iter()
        .map(|value| normalize_search_value(value))
        .collect::<BTreeSet<_>>();
    for item in rest {
        let values = select(item)
            .iter()
            .map(|value| normalize_search_value(value))
            .collect::<BTreeSet<_>>();
        shared = shared
            .intersection(&values)
            .cloned()
            .collect::<BTreeSet<_>>();
    }
    select(first)
        .iter()
        .filter(|value| shared.contains(&normalize_search_value(value)))
        .cloned()
        .collect()
}

fn compare_text_values<F>(
    items: &[PublicProfileCompareItem],
    select: F,
) -> Vec<PublicProfileCompareTextValue>
where
    F: Fn(&PublicProfileCompareItem) -> Option<String>,
{
    items
        .iter()
        .map(|item| PublicProfileCompareTextValue {
            identity: item.identity.clone(),
            value: select(item),
        })
        .collect()
}

fn compare_bool_values<F>(
    items: &[PublicProfileCompareItem],
    select: F,
) -> Vec<PublicProfileCompareBoolValue>
where
    F: Fn(&PublicProfileCompareItem) -> bool,
{
    items
        .iter()
        .map(|item| PublicProfileCompareBoolValue {
            identity: item.identity.clone(),
            value: select(item),
        })
        .collect()
}

fn compare_signals(items: &[PublicProfileCompareItem]) -> PublicProfileCompareSignals {
    PublicProfileCompareSignals {
        shared_languages: shared_profile_values(items, |item| &item.languages),
        shared_topics: shared_profile_values(items, |item| &item.topics),
        licenses: compare_text_values(items, |item| item.license.clone()),
        selected_statuses: compare_text_values(items, |item| {
            Some(item.trust.selected_status.clone())
        }),
        confidences: compare_text_values(items, |item| item.trust.confidence.clone()),
        has_build: compare_bool_values(items, |item| item.completeness.has_build),
        has_test: compare_bool_values(items, |item| item.completeness.has_test),
        has_docs: compare_bool_values(items, |item| item.completeness.has_docs),
        has_security_contact: compare_bool_values(items, |item| {
            item.completeness.has_security_contact
        }),
        has_license: compare_bool_values(items, |item| item.completeness.has_license),
    }
}

pub fn public_profile_compare_with_base(
    index_root: &Path,
    identities: &[PublicRepositoryIdentity],
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicProfileCompareResponse> {
    normalize_public_base_path(base_path)?;
    if identities.is_empty() {
        bail!("compare requires at least one repository");
    }
    let mut results = Vec::new();
    for identity in identities {
        let profile = public_repository_profile_with_base(
            index_root,
            &identity.host,
            &identity.owner,
            &identity.repo,
            freshness.clone(),
            base_path,
        )?;
        results.push(compare_item_from_profile(profile));
    }
    let signals = compare_signals(&results);
    Ok(PublicProfileCompareResponse {
        api_version: PUBLIC_API_VERSION,
        freshness,
        repository_count: results.len(),
        results,
        signals,
    })
}

pub fn public_profile_compare(
    index_root: &Path,
    identities: &[PublicRepositoryIdentity],
    freshness: PublicFreshness,
) -> Result<PublicProfileCompareResponse> {
    public_profile_compare_with_base(index_root, identities, freshness, "/")
}

fn parse_relation_reference(value: &str) -> Option<PublicRepositoryIdentity> {
    let (host, owner, repo) = repository_reference_identity(value)?;
    Some(PublicRepositoryIdentity {
        host,
        owner,
        repo,
        source: None,
    })
}

fn relation_reference_key(identity: &PublicRepositoryIdentity) -> String {
    format!("{}/{}/{}", identity.host, identity.owner, identity.repo)
}

#[derive(Debug, Clone)]
struct SelectedRelation {
    relationship: &'static str,
    inverse_relationship: &'static str,
    target: String,
    notes: Option<String>,
    trust: Option<PublicRelationTrust>,
}

fn relation_names(kind: RelationKind) -> (&'static str, &'static str) {
    match kind {
        RelationKind::Reference => ("reference", "referenced_by"),
        RelationKind::Alternative => ("alternative", "alternative"),
        RelationKind::Dependency => ("dependency", "depended_on_by"),
        RelationKind::Predecessor => ("predecessor", "successor"),
        RelationKind::Fork => ("fork", "forked_by"),
        RelationKind::Related => ("related", "related"),
    }
}

fn selected_relations(
    index_root: &Path,
    identity: &PublicRepositoryIdentity,
) -> Result<Vec<SelectedRelation>> {
    let scope_root =
        index_repository_scope(index_root, &identity.host, &identity.owner, &identity.repo)?;
    let candidates = resolve_candidates(&scope_root)?;
    let Some(relations) = candidates[0].manifest.relations.as_ref() else {
        return Ok(Vec::new());
    };
    let mut selected = relations
        .references
        .iter()
        .cloned()
        .map(|target| SelectedRelation {
            relationship: "reference",
            inverse_relationship: "referenced_by",
            target,
            notes: None,
            trust: None,
        })
        .collect::<Vec<_>>();
    selected.extend(relations.links.iter().map(|link| {
        let (relationship, inverse_relationship) = relation_names(link.kind);
        SelectedRelation {
            relationship,
            inverse_relationship,
            target: link.target.clone(),
            notes: link.notes.clone(),
            trust: Some(PublicRelationTrust {
                confidence: link.trust.confidence.clone(),
                provenance: link.trust.provenance.clone(),
                notes: link.trust.notes.clone(),
            }),
        }
    }));
    Ok(selected)
}

fn relation_item_with_profile(
    index_root: &Path,
    target: String,
    relation: &SelectedRelation,
    direction: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> PublicRelationItem {
    let identity = parse_relation_reference(&target);
    let mut item = PublicRelationItem {
        relationship: relation.relationship.into(),
        direction: direction.into(),
        target: target.clone(),
        notes: relation.notes.clone(),
        trust: relation.trust.clone(),
        identity: identity.clone(),
        profile: None,
        error: None,
    };
    if let Some(identity) = identity {
        match public_repository_profile_or_error_with_base(
            index_root,
            &identity.host,
            &identity.owner,
            &identity.repo,
            freshness,
            base_path,
        ) {
            Ok(profile) => {
                item.identity = Some(profile.identity.clone());
                item.profile = Some(Box::new(search_item_from_profile(
                    profile,
                    vec!["relation".into()],
                )));
            }
            Err(error) => {
                item.error = Some(error.error);
            }
        }
    }
    item
}

pub fn public_repository_relations_with_base(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> Result<PublicRelationsResponse> {
    normalize_public_base_path(base_path)?;
    let profile = public_repository_profile_with_base(
        index_root,
        host,
        owner,
        repo,
        freshness.clone(),
        base_path,
    )?;
    let selected_identity = PublicRepositoryIdentity {
        host: host.to_string(),
        owner: owner.to_string(),
        repo: repo.to_string(),
        source: None,
    };
    let selected_key = relation_reference_key(&selected_identity);
    let relations = selected_relations(index_root, &selected_identity)?;

    let mut items = Vec::new();
    for relation in relations {
        items.push(relation_item_with_profile(
            index_root,
            relation.target.clone(),
            &relation,
            "outgoing",
            freshness.clone(),
            base_path,
        ));
    }

    for candidate in list_index_repository_identities(index_root)? {
        let candidate_key = relation_reference_key(&candidate);
        if candidate_key == selected_key {
            continue;
        }
        let relations = selected_relations(index_root, &candidate)?;
        for relation in relations {
            let points_to_selected = parse_relation_reference(&relation.target)
                .map(|target| relation_reference_key(&target) == selected_key)
                .unwrap_or(false);
            if !points_to_selected {
                continue;
            }
            items.push(relation_item_with_profile(
                index_root,
                candidate_key.clone(),
                &SelectedRelation {
                    relationship: relation.inverse_relationship,
                    ..relation.clone()
                },
                "incoming",
                freshness.clone(),
                base_path,
            ));
        }
    }
    items.sort_by(|left, right| {
        left.direction
            .cmp(&right.direction)
            .then_with(|| left.relationship.cmp(&right.relationship))
            .then_with(|| left.target.cmp(&right.target))
    });

    Ok(PublicRelationsResponse {
        api_version: PUBLIC_API_VERSION,
        freshness,
        identity: profile.identity,
        relation_count: items.len(),
        references: items,
        links: public_links_with_base(
            host,
            owner,
            repo,
            PublicLinkKind::Relations,
            None,
            base_path,
        )?,
    })
}

pub fn public_repository_relations(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
) -> Result<PublicRelationsResponse> {
    public_repository_relations_with_base(index_root, host, owner, repo, freshness, "/")
}

pub fn public_query_input_snapshot(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
) -> Result<PublicQueryInputSnapshot> {
    let candidates = resolve_repository_candidates(index_root, host, owner, repo)?;
    public_query_input_snapshot_with_candidates(
        index_root,
        host,
        owner,
        repo,
        &candidates,
        freshness,
    )
}

fn public_query_input_snapshot_with_candidates(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    candidates: &[CandidateManifest],
    freshness: PublicFreshness,
) -> Result<PublicQueryInputSnapshot> {
    let selected = &candidates[0];
    let reason = resolve_selection_reason(candidates, selected);

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

pub fn public_repository_profile_or_error(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
) -> std::result::Result<PublicResearchProfileResponse, PublicErrorResponse> {
    public_repository_profile_or_error_with_base(index_root, host, owner, repo, freshness, "/")
}

pub fn public_repository_profile_or_error_with_base(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: PublicFreshness,
    base_path: &str,
) -> std::result::Result<PublicResearchProfileResponse, PublicErrorResponse> {
    public_repository_profile_or_error_with_base_ref(
        index_root, host, owner, repo, &freshness, base_path,
    )
}

pub fn public_repository_profile_or_error_with_base_ref(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    freshness: &PublicFreshness,
    base_path: &str,
) -> std::result::Result<PublicResearchProfileResponse, PublicErrorResponse> {
    public_repository_profile_with_base(index_root, host, owner, repo, freshness.clone(), base_path)
        .map_err(|error| public_error_response(host, owner, repo, None, freshness.clone(), &error))
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
    public_repository_query_or_error_with_base_ref(
        index_root, host, owner, repo, path, &freshness, base_path,
    )
}

pub fn public_repository_query_or_error_with_base_ref(
    index_root: &Path,
    host: &str,
    owner: &str,
    repo: &str,
    path: &str,
    freshness: &PublicFreshness,
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
    .map_err(|error| {
        public_error_response(host, owner, repo, Some(path), freshness.clone(), &error)
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
