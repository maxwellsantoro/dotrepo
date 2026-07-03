use crate::claims::RecordClaimContext;
use crate::{ConflictRelationship, RecordSummary, SelectionReason};
use dotrepo_schema::Manifest;
use serde::{Deserialize, Serialize};
use serde_json::Value;

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
    /// Candidate build commands preserved when no single command could be
    /// honestly chosen as primary (e.g. a genuinely polyglot repository).
    /// See `dotrepo_schema::Repo::build_candidates` and RFC 0020.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub build_candidates: Vec<PublicCommandCandidate>,
    /// Same as `build_candidates`, for `test`.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub test_candidates: Vec<PublicCommandCandidate>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PublicCommandCandidate {
    pub command: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ecosystem: Option<String>,
    pub source: String,
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
    pub snapshot_id: String,
    pub paths: PublicSnapshotPaths,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct PublicSnapshotPaths {
    pub root: String,
    pub inventory: String,
    pub files: String,
    pub query_input_root: String,
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
