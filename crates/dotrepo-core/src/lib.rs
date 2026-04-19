use anyhow::{anyhow, bail, Result};
use dotrepo_schema::{
    parse_manifest, parse_synthesis_document, render_manifest, render_synthesis_document,
    validate_synthesis_document, Compat, CompatMode, Docs, GitHubCompat, Manifest, Owners, Readme,
    ReadmeCustomSection, Record, RecordMode, RecordStatus, Relations, Repo, SynthesisDocument,
    Trust,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;
use std::fs;
use std::path::{Component, Path, PathBuf};
use time::format_description::well_known::Rfc3339;
use time::{Duration, OffsetDateTime};

const SUPPORTED_SCHEMA: &str = "dotrepo/v0.1";
const IMPORT_README_CANDIDATES: &[&str] = &[
    "README.md",
    "README.MD",
    "readme.md",
    "README.mdx",
    "README.markdown",
    "README",
];
const SUPPORTED_CLAIM_SCHEMA: &str = "dotrepo-claim/v0";
const SUPPORTED_CLAIM_EVENT_SCHEMA: &str = "dotrepo-claim-event/v0";
const GENERATOR_NAME: &str = "dotrepo";
const GENERATOR_VERSION: &str = env!("CARGO_PKG_VERSION");
const PUBLIC_API_VERSION: &str = "v0";
const PUBLIC_STATIC_STRATEGY: &str = "static_summary_and_trust";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ManagedFileState {
    Missing,
    FullyGenerated,
    PartiallyManaged,
    Unmanaged,
    MalformedManaged,
    Unsupported,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DoctorSurface {
    Readme,
    Security,
    Contributing,
    Codeowners,
    PullRequestTemplate,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DoctorOwnershipHonesty {
    Honest,
    LossyFullGeneration,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DoctorRecommendedMode {
    Generate,
    PartiallyManaged,
    Skip,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DoctorRendererCoverage {
    Structured,
    StubOnly,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DoctorFinding {
    pub path: PathBuf,
    pub surface: DoctorSurface,
    pub state: ManagedFileState,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub declared_mode: Option<CompatMode>,
    pub supports_managed_regions: bool,
    pub supports_full_generation: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ownership_honesty: Option<DoctorOwnershipHonesty>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub recommended_mode: Option<DoctorRecommendedMode>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub would_drop_unmanaged_content: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub renderer_coverage: Option<DoctorRendererCoverage>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub advice: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DoctorReport {
    pub mode: RecordMode,
    pub status: RecordStatus,
    pub findings: Vec<DoctorFinding>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SurfacePreview {
    #[serde(flatten)]
    pub finding: DoctorFinding,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub current: Option<String>,
    pub proposed: String,
    pub full_replacement: bool,
    pub preserves_unmanaged_content: bool,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SurfacePreviewReport {
    pub root: String,
    pub previews: Vec<SurfacePreview>,
}

#[derive(Debug, Clone)]
pub struct ManagedSurfaceAdoptionPlan {
    pub surface: DoctorSurface,
    pub path: PathBuf,
    pub contents: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidationDiagnostic {
    pub severity: ValidationDiagnosticSeverity,
    pub source: &'static str,
    pub message: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ValidationDiagnosticSeverity {
    Error,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IndexFinding {
    pub path: PathBuf,
    pub severity: IndexFindingSeverity,
    pub message: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IndexFindingSeverity {
    Warning,
    Error,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ImportMode {
    Native,
    Overlay,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RepositoryDiagnostic {
    pub severity: &'static str,
    pub source: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub manifest_path: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecordSummary {
    pub mode: RecordMode,
    pub status: RecordStatus,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub trust: Option<Trust>,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SelectionReason {
    OnlyMatchingRecord,
    CanonicalPreferred,
    HigherStatusOverlay,
    EqualAuthorityConflict,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConflictRelationship {
    Superseded,
    Parallel,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SelectedRecord {
    pub manifest_path: String,
    pub record: RecordSummary,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub claim: Option<RecordClaimContext>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SelectionReport {
    pub reason: SelectionReason,
    pub record: SelectedRecord,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ConflictReport {
    pub relationship: ConflictRelationship,
    pub reason: SelectionReason,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<Value>,
    pub record: SelectedRecord,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ValidateReport {
    pub valid: bool,
    pub root: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub manifest_path: Option<String>,
    pub diagnostics: Vec<RepositoryDiagnostic>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub record: Option<RecordSummary>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct QueryReport {
    pub root: String,
    pub manifest_path: String,
    pub path: String,
    pub value: Value,
    pub selection: SelectionReport,
    pub conflicts: Vec<ConflictReport>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TrustReport {
    pub root: String,
    pub manifest_path: String,
    pub selection: SelectionReport,
    pub conflicts: Vec<ConflictReport>,
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

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct RecordClaimContext {
    pub id: String,
    pub state: ClaimState,
    pub handoff: ClaimHandoffOutcome,
    pub claim_path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub latest_event: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub review_path: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimRecord {
    pub schema: String,
    pub claim: ClaimMetadata,
    pub identity: ClaimIdentity,
    pub claimant: Claimant,
    pub target: ClaimTarget,
    #[serde(default)]
    pub resolution: Option<ClaimResolution>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimMetadata {
    pub id: String,
    pub kind: ClaimKind,
    pub state: ClaimState,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ClaimKind {
    MaintainerAuthority,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ClaimState {
    Draft,
    Submitted,
    InReview,
    Accepted,
    Rejected,
    Withdrawn,
    Disputed,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimIdentity {
    pub host: String,
    pub owner: String,
    pub repo: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Claimant {
    pub display_name: String,
    pub asserted_role: String,
    #[serde(default)]
    pub contact: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimTarget {
    #[serde(default)]
    pub index_paths: Vec<String>,
    #[serde(default)]
    pub record_sources: Vec<String>,
    #[serde(default)]
    pub canonical_repo_url: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimResolution {
    #[serde(default)]
    pub canonical_record_path: Option<String>,
    #[serde(default)]
    pub canonical_mirror_path: Option<String>,
    #[serde(default)]
    pub result_event: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimEvent {
    pub schema: String,
    pub event: ClaimEventMetadata,
    #[serde(default)]
    pub transition: Option<ClaimTransition>,
    pub summary: ClaimSummary,
    #[serde(default)]
    pub links: Option<ClaimEventLinks>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimEventMetadata {
    pub sequence: u32,
    pub kind: ClaimEventKind,
    pub timestamp: String,
    pub actor: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ClaimEventKind {
    Submitted,
    ReviewStarted,
    Accepted,
    Rejected,
    Withdrawn,
    Disputed,
    Corrected,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimTransition {
    pub from: ClaimState,
    pub to: ClaimState,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimSummary {
    pub text: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ClaimEventLinks {
    #[serde(default)]
    pub claim: Option<String>,
    #[serde(default)]
    pub review_notes: Option<String>,
    #[serde(default)]
    pub canonical_record_path: Option<String>,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct LoadedClaimEvent {
    pub path: String,
    pub event: ClaimEvent,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct LoadedClaimDirectory {
    pub claim_path: String,
    pub claim: ClaimRecord,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub review_path: Option<String>,
    pub events: Vec<LoadedClaimEvent>,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ClaimHandoffOutcome {
    PendingCanonical,
    Superseded,
    Parallel,
    Rejected,
    Withdrawn,
    Disputed,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct ClaimInspectionReport {
    pub claim_path: String,
    pub state: ClaimState,
    pub kind: ClaimKind,
    pub identity: ClaimIdentity,
    pub claimant: Claimant,
    pub target: ClaimTargetInspection,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub resolution: Option<ClaimResolution>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub review_path: Option<String>,
    pub events: Vec<ClaimEventInspection>,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct ClaimTargetInspection {
    pub index_paths: Vec<String>,
    pub record_sources: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub canonical_repo_url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub handoff: Option<ClaimHandoffOutcome>,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct ClaimEventInspection {
    pub path: String,
    pub sequence: u32,
    pub kind: ClaimEventKind,
    pub timestamp: String,
    pub actor: String,
    pub summary: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub from: Option<ClaimState>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub to: Option<ClaimState>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ClaimScaffoldInput {
    pub host: String,
    pub owner: String,
    pub repo: String,
    pub claim_id: String,
    pub claimant_display_name: String,
    pub asserted_role: String,
    pub contact: Option<String>,
    pub record_sources: Vec<String>,
    pub canonical_repo_url: Option<String>,
    pub create_review_md: bool,
    pub timestamp: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ClaimScaffoldPlan {
    pub claim_dir: PathBuf,
    pub claim_path: PathBuf,
    pub claim_text: String,
    pub review_path: Option<PathBuf>,
    pub review_text: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ClaimEventAppendInput {
    pub kind: ClaimEventKind,
    pub actor: String,
    pub summary: String,
    pub timestamp: String,
    pub corrected_state: Option<ClaimState>,
    pub canonical_record_path: Option<String>,
    pub canonical_mirror_path: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ClaimEventAppendPlan {
    pub claim_dir: PathBuf,
    pub claim_path: PathBuf,
    pub claim_text: String,
    pub event_path: PathBuf,
    pub event_text: String,
    pub next_state: ClaimState,
}

#[derive(Debug, Clone, Serialize)]
pub struct GenerateCheckOutput {
    pub path: String,
    pub state: ManagedFileState,
    pub stale: bool,
    pub expected: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub current: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GenerateCheckReport {
    pub root: String,
    pub checked: usize,
    pub stale: Vec<String>,
    pub outputs: Vec<GenerateCheckOutput>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ImportPreviewReport {
    pub root: String,
    pub mode: &'static str,
    pub manifest_path: String,
    pub manifest: Manifest,
    pub manifest_text: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub evidence_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub evidence_text: Option<String>,
    pub imported_sources: Vec<String>,
    pub inferred_fields: Vec<String>,
    pub record: RecordSummary,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ImportOptions {
    pub generated_at: Option<String>,
}

#[derive(Debug, Clone)]
pub struct ImportPlan {
    pub manifest_path: PathBuf,
    pub manifest: Manifest,
    pub manifest_text: String,
    pub evidence_path: Option<PathBuf>,
    pub evidence_text: Option<String>,
    pub imported_sources: Vec<String>,
    pub inferred_fields: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct LoadedManifest {
    pub path: PathBuf,
    pub raw: Vec<u8>,
    pub manifest: Manifest,
}

#[derive(Debug, Clone)]
pub struct LoadedSynthesis {
    pub path: PathBuf,
    pub raw: Vec<u8>,
    pub synthesis: SynthesisDocument,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SynthesisReadReport {
    pub root: String,
    pub synthesis_path: String,
    pub synthesis: SynthesisDocument,
}

#[derive(Debug, Clone)]
pub struct SynthesisWritePlan {
    pub synthesis_path: PathBuf,
    pub synthesis: SynthesisDocument,
    pub synthesis_text: String,
}

#[derive(Debug, Clone, Copy)]
enum ManagedSurface {
    Readme,
    Security,
    Contributing,
}

#[derive(Debug, Clone)]
struct ManagedOutput {
    path: PathBuf,
    contents: String,
}

#[derive(Debug, Clone)]
struct ManagedSurfaceStatus {
    path: PathBuf,
    state: ManagedFileState,
    current: Option<String>,
    message: Option<String>,
}

#[derive(Debug, Clone)]
struct ManagedRegion {
    id: String,
    content_start: usize,
    content_end: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct RepositoryIdentity {
    host: String,
    owner: String,
    repo: String,
}

#[derive(Debug, Clone)]
struct CandidateManifest {
    manifest_path: String,
    path: PathBuf,
    manifest: Manifest,
    identity: Option<RepositoryIdentity>,
    rank: u8,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct ClaimDirectoryIdentity {
    host: String,
    owner: String,
    repo: String,
    claim_id: String,
}

pub fn load_manifest_document(root: &Path) -> Result<LoadedManifest> {
    let path = manifest_path(root);
    load_manifest_file(&path)
}

fn render_rfc3339(label: &str, timestamp: OffsetDateTime) -> Result<String> {
    timestamp
        .format(&Rfc3339)
        .map_err(|err| anyhow!("failed to render {label}: {err}"))
}

fn parse_rfc3339(label: &str, value: &str) -> Result<OffsetDateTime> {
    OffsetDateTime::parse(value, &Rfc3339)
        .map_err(|err| anyhow!("failed to parse {label} as RFC3339: {err}"))
}

fn normalize_rfc3339(label: &str, value: &str) -> Result<String> {
    render_rfc3339(label, parse_rfc3339(label, value)?)
}

pub fn current_timestamp_rfc3339() -> Result<String> {
    render_rfc3339("current timestamp", OffsetDateTime::now_utc())
}

fn synthesis_path(root: &Path) -> PathBuf {
    root.join("synthesis.toml")
}

pub fn parse_claim_record(input: &str) -> Result<ClaimRecord> {
    let claim = toml::from_str::<ClaimRecord>(input)
        .map_err(|e| anyhow!("failed to parse claim record: {}", e))?;
    validate_claim_record(&claim)?;
    Ok(claim)
}

pub fn parse_claim_event(input: &str) -> Result<ClaimEvent> {
    let event = toml::from_str::<ClaimEvent>(input)
        .map_err(|e| anyhow!("failed to parse claim event: {}", e))?;
    validate_claim_event(&event)?;
    Ok(event)
}

pub fn load_claim_directory(root: &Path, claim_dir: &Path) -> Result<LoadedClaimDirectory> {
    let claim_path = claim_dir.join("claim.toml");
    if !claim_path.is_file() {
        bail!(
            "claim directory is missing claim.toml: {}",
            claim_path.display()
        );
    }

    let claim_text = fs::read_to_string(&claim_path)
        .map_err(|e| anyhow!("failed to read {}: {}", claim_path.display(), e))?;
    let claim =
        parse_claim_record(&claim_text).map_err(|e| anyhow!("{}: {}", claim_path.display(), e))?;

    let review_path = claim_dir.join("review.md");
    let review = review_path
        .is_file()
        .then(|| display_path(root, &review_path));

    let events_dir = claim_dir.join("events");
    let mut event_paths = Vec::new();
    if events_dir.is_dir() {
        for entry in fs::read_dir(&events_dir)
            .map_err(|e| anyhow!("failed to read {}: {}", events_dir.display(), e))?
        {
            let entry =
                entry.map_err(|e| anyhow!("failed to inspect {}: {}", events_dir.display(), e))?;
            let path = entry.path();
            if path.extension().and_then(|ext| ext.to_str()) == Some("toml") {
                event_paths.push(path);
            }
        }
        event_paths.sort();
    }

    let mut events = Vec::new();
    for path in event_paths {
        let text = fs::read_to_string(&path)
            .map_err(|e| anyhow!("failed to read {}: {}", path.display(), e))?;
        let event = parse_claim_event(&text).map_err(|e| anyhow!("{}: {}", path.display(), e))?;
        events.push(LoadedClaimEvent {
            path: display_path(root, &path),
            event,
        });
    }

    Ok(LoadedClaimDirectory {
        claim_path: display_path(root, &claim_path),
        claim,
        review_path: review,
        events,
    })
}

pub fn inspect_claim_directory(root: &Path, claim_dir: &Path) -> Result<ClaimInspectionReport> {
    let loaded = load_claim_directory(root, claim_dir)?;
    Ok(claim_inspection_report(&loaded))
}

pub fn scaffold_claim_directory(
    root: &Path,
    input: &ClaimScaffoldInput,
) -> Result<ClaimScaffoldPlan> {
    require_path_segment("identity.host", &input.host)?;
    require_path_segment("identity.owner", &input.owner)?;
    require_path_segment("identity.repo", &input.repo)?;
    require_path_segment("claim.id", &input.claim_id)?;
    require_non_empty("claimant.display_name", &input.claimant_display_name)?;
    require_non_empty("claimant.asserted_role", &input.asserted_role)?;
    require_non_empty("claim.created_at", &input.timestamp)?;

    let repo_dir = root
        .join("repos")
        .join(&input.host)
        .join(&input.owner)
        .join(&input.repo);
    let record_path = repo_dir.join("record.toml");
    if !record_path.is_file() {
        bail!(
            "no index record found at {}; claims can only be scaffolded for existing index repositories",
            record_path.display()
        );
    }

    let claim_dir = repo_dir.join("claims").join(&input.claim_id);
    let claim_path = claim_dir.join("claim.toml");
    let review_path = input.create_review_md.then(|| claim_dir.join("review.md"));
    let record_source_values = input
        .record_sources
        .iter()
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
        .collect::<Vec<_>>();
    let contact = input
        .contact
        .as_ref()
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned);
    let canonical_repo_url = input
        .canonical_repo_url
        .as_ref()
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned);
    let claim = ClaimRecord {
        schema: SUPPORTED_CLAIM_SCHEMA.into(),
        claim: ClaimMetadata {
            id: format!(
                "{}/{}/{}/{}",
                input.host, input.owner, input.repo, input.claim_id
            ),
            kind: ClaimKind::MaintainerAuthority,
            state: ClaimState::Draft,
            created_at: input.timestamp.clone(),
            updated_at: input.timestamp.clone(),
        },
        identity: ClaimIdentity {
            host: input.host.clone(),
            owner: input.owner.clone(),
            repo: input.repo.clone(),
        },
        claimant: Claimant {
            display_name: input.claimant_display_name.clone(),
            asserted_role: input.asserted_role.clone(),
            contact,
        },
        target: ClaimTarget {
            index_paths: vec![format!(
                "repos/{}/{}/{}/record.toml",
                input.host, input.owner, input.repo
            )],
            record_sources: record_source_values,
            canonical_repo_url,
        },
        resolution: None,
    };
    validate_claim_record(&claim)?;
    let claim_text =
        toml::to_string_pretty(&claim).map_err(|e| anyhow!("failed to render claim.toml: {e}"))?;
    let review_text = review_path
        .as_ref()
        .map(|_| render_claim_review_template(&claim));

    Ok(ClaimScaffoldPlan {
        claim_dir,
        claim_path,
        claim_text,
        review_path,
        review_text,
    })
}

pub fn append_claim_event(
    root: &Path,
    claim_dir: &Path,
    input: &ClaimEventAppendInput,
) -> Result<ClaimEventAppendPlan> {
    require_non_empty("event.actor", &input.actor)?;
    require_non_empty("summary.text", &input.summary)?;
    require_non_empty("event.timestamp", &input.timestamp)?;

    let loaded = load_claim_directory(root, claim_dir)?;
    let next_sequence = loaded
        .events
        .last()
        .map(|event| event.event.event.sequence + 1)
        .unwrap_or(1);
    let current_state = loaded.claim.claim.state.clone();
    let next_state = next_claim_state(
        &current_state,
        &input.kind,
        !loaded.events.is_empty(),
        input.corrected_state.as_ref(),
    )?;
    let transition = event_transition_for(&current_state, &next_state, &input.kind);
    let canonical_record_path = input
        .canonical_record_path
        .as_ref()
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned);
    let canonical_mirror_path = input
        .canonical_mirror_path
        .as_ref()
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned);
    let records_canonical_handoff =
        canonical_record_path.is_some() || canonical_mirror_path.is_some();
    if records_canonical_handoff && next_state != ClaimState::Accepted {
        bail!("canonical handoff links are only valid when the resulting claim state is accepted");
    }
    let review_notes_link = if loaded.review_path.is_some()
        && matches!(
            input.kind,
            ClaimEventKind::Accepted | ClaimEventKind::Corrected
        ) {
        Some("../review.md".into())
    } else {
        None
    };
    let links = if review_notes_link.is_some() || canonical_record_path.is_some() {
        Some(ClaimEventLinks {
            claim: Some("../claim.toml".into()),
            review_notes: review_notes_link,
            canonical_record_path: canonical_record_path.clone(),
        })
    } else {
        None
    };
    let event = ClaimEvent {
        schema: SUPPORTED_CLAIM_EVENT_SCHEMA.into(),
        event: ClaimEventMetadata {
            sequence: next_sequence,
            kind: input.kind.clone(),
            timestamp: input.timestamp.clone(),
            actor: input.actor.clone(),
        },
        transition,
        summary: ClaimSummary {
            text: input.summary.clone(),
        },
        links,
    };
    validate_claim_event(&event)?;

    let mut updated_claim = loaded.claim.clone();
    updated_claim.claim.updated_at = input.timestamp.clone();
    updated_claim.claim.state = next_state.clone();
    let result_event = format!(
        "events/{next_sequence:04}-{}.toml",
        claim_event_kind_slug(&input.kind)
    );
    updated_claim.resolution = update_claim_resolution(
        &loaded.claim,
        &input.kind,
        &next_state,
        canonical_record_path.clone(),
        canonical_mirror_path.clone(),
        &result_event,
    )?;
    validate_claim_record(&updated_claim)?;

    let event_label = claim_event_kind_slug(&input.kind);
    let event_file_name = format!("{next_sequence:04}-{event_label}.toml");
    let event_path = claim_dir.join("events").join(&event_file_name);
    let event_text =
        toml::to_string_pretty(&event).map_err(|e| anyhow!("failed to render claim event: {e}"))?;
    let claim_text = toml::to_string_pretty(&updated_claim)
        .map_err(|e| anyhow!("failed to render updated claim.toml: {e}"))?;

    let mut simulated_events = loaded.events.clone();
    simulated_events.push(LoadedClaimEvent {
        path: display_path(root, &event_path),
        event: event.clone(),
    });
    let relative_claim = PathBuf::from(&loaded.claim_path);
    let history_findings =
        validate_claim_event_history(&relative_claim, &updated_claim, &simulated_events);
    if let Some(finding) = history_findings.first() {
        bail!("{}", finding.message);
    }
    let resolution_findings =
        validate_claim_resolution_consistency(&relative_claim, &updated_claim);
    if let Some(finding) = resolution_findings.first() {
        bail!("{}", finding.message);
    }

    Ok(ClaimEventAppendPlan {
        claim_dir: claim_dir.to_path_buf(),
        claim_path: claim_dir.join("claim.toml"),
        claim_text,
        event_path,
        event_text,
        next_state,
    })
}

fn load_manifest_file(path: &Path) -> Result<LoadedManifest> {
    let raw = fs::read(path).map_err(|e| anyhow!("failed to read {}: {}", path.display(), e))?;
    let text = std::str::from_utf8(&raw)
        .map_err(|e| anyhow!("failed to decode {} as UTF-8: {}", path.display(), e))?;
    let manifest = parse_manifest(text)?;
    Ok(LoadedManifest {
        path: path.to_path_buf(),
        raw,
        manifest,
    })
}

pub fn load_synthesis_document(root: &Path) -> Result<LoadedSynthesis> {
    let path = synthesis_path(root);
    let raw = fs::read(&path).map_err(|e| anyhow!("failed to read {}: {}", path.display(), e))?;
    let text = std::str::from_utf8(&raw)
        .map_err(|e| anyhow!("failed to decode {} as UTF-8: {}", path.display(), e))?;
    let synthesis = parse_synthesis_document(text)?;
    Ok(LoadedSynthesis {
        path,
        raw,
        synthesis,
    })
}

pub fn load_synthesis_from_root(root: &Path) -> Result<SynthesisDocument> {
    Ok(load_synthesis_document(root)?.synthesis)
}

pub fn get_synthesis(root: &Path) -> Result<SynthesisReadReport> {
    let loaded = load_synthesis_document(root)?;
    Ok(SynthesisReadReport {
        root: root.display().to_string(),
        synthesis_path: display_path(root, &loaded.path),
        synthesis: loaded.synthesis,
    })
}

fn contains_unsafe_shell_like_value(value: &str) -> bool {
    value.contains('\n')
        || value.contains('\r')
        || value.contains('\0')
        || value.contains("`")
        || value.contains("$(")
        || value.contains("${")
}

fn validate_synthesis_command(field: &str, value: &str) -> Result<()> {
    if contains_unsafe_shell_like_value(value) {
        bail!("{field} contains an unsafe shell-like value");
    }
    Ok(())
}

pub fn validate_synthesis(manifest: &Manifest, synthesis: &SynthesisDocument) -> Result<()> {
    validate_synthesis_document(synthesis).map_err(|err| anyhow!("{err}"))?;
    parse_rfc3339("synthesis.generated_at", &synthesis.synthesis.generated_at)?;
    validate_synthesis_command(
        "synthesis.for_agents.how_to_build",
        &synthesis.synthesis.for_agents.how_to_build,
    )?;
    validate_synthesis_command(
        "synthesis.for_agents.how_to_test",
        &synthesis.synthesis.for_agents.how_to_test,
    )?;

    if let Some(build) = manifest.repo.build.as_deref() {
        if !build.trim().is_empty()
            && build.trim() != synthesis.synthesis.for_agents.how_to_build.trim()
        {
            bail!("synthesis.for_agents.how_to_build conflicts with factual repo.build");
        }
    }
    if let Some(test) = manifest.repo.test.as_deref() {
        if !test.trim().is_empty()
            && test.trim() != synthesis.synthesis.for_agents.how_to_test.trim()
        {
            bail!("synthesis.for_agents.how_to_test conflicts with factual repo.test");
        }
    }

    Ok(())
}

pub fn write_synthesis(root: &Path, synthesis: &SynthesisDocument) -> Result<SynthesisWritePlan> {
    let manifest = load_manifest_from_root(root)?;
    validate_synthesis(&manifest, synthesis)?;
    let synthesis_text = render_synthesis_document(synthesis)?;
    Ok(SynthesisWritePlan {
        synthesis_path: synthesis_path(root),
        synthesis: synthesis.clone(),
        synthesis_text,
    })
}

pub fn load_manifest_from_root(root: &Path) -> Result<Manifest> {
    Ok(load_manifest_document(root)?.manifest)
}

pub fn display_path(root: &Path, path: &Path) -> String {
    path.strip_prefix(root)
        .unwrap_or(path)
        .display()
        .to_string()
}

pub fn record_summary(manifest: &Manifest) -> RecordSummary {
    RecordSummary {
        mode: manifest.record.mode.clone(),
        status: manifest.record.status.clone(),
        source: manifest.record.source.clone(),
        trust: manifest.record.trust.clone(),
    }
}

fn selected_record(root: &Path, candidate: &CandidateManifest) -> SelectedRecord {
    SelectedRecord {
        manifest_path: candidate.manifest_path.clone(),
        record: record_summary(&candidate.manifest),
        claim: candidate_claim_context(root, candidate),
    }
}

fn public_selected_record(
    display_root: &Path,
    candidate: &CandidateManifest,
) -> PublicSelectedRecord {
    PublicSelectedRecord {
        manifest_path: display_path(display_root, &candidate.path),
        record: record_summary(&candidate.manifest),
        claim: candidate_claim_context(display_root, candidate),
        artifacts: public_record_artifacts(display_root, candidate),
    }
}

fn public_record_artifacts(
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

fn resolve_selection_reason(
    candidates: &[CandidateManifest],
    selected: &CandidateManifest,
) -> SelectionReason {
    if candidates.len() == 1 {
        return SelectionReason::OnlyMatchingRecord;
    }

    if candidates.iter().any(|candidate| {
        candidate.manifest_path != selected.manifest_path && candidate.rank == selected.rank
    }) {
        return SelectionReason::EqualAuthorityConflict;
    }

    if matches!(selected.manifest.record.status, RecordStatus::Canonical) {
        SelectionReason::CanonicalPreferred
    } else {
        SelectionReason::HigherStatusOverlay
    }
}

fn claim_inspection_report(loaded: &LoadedClaimDirectory) -> ClaimInspectionReport {
    ClaimInspectionReport {
        claim_path: loaded.claim_path.clone(),
        state: loaded.claim.claim.state.clone(),
        kind: loaded.claim.claim.kind.clone(),
        identity: loaded.claim.identity.clone(),
        claimant: loaded.claim.claimant.clone(),
        target: ClaimTargetInspection {
            index_paths: loaded.claim.target.index_paths.clone(),
            record_sources: loaded.claim.target.record_sources.clone(),
            canonical_repo_url: loaded.claim.target.canonical_repo_url.clone(),
            handoff: derived_claim_handoff(&loaded.claim),
        },
        resolution: loaded.claim.resolution.clone(),
        review_path: loaded.review_path.clone(),
        events: loaded
            .events
            .iter()
            .map(|loaded_event| ClaimEventInspection {
                path: loaded_event.path.clone(),
                sequence: loaded_event.event.event.sequence,
                kind: loaded_event.event.event.kind.clone(),
                timestamp: loaded_event.event.event.timestamp.clone(),
                actor: loaded_event.event.event.actor.clone(),
                summary: loaded_event.event.summary.text.clone(),
                from: loaded_event
                    .event
                    .transition
                    .as_ref()
                    .map(|transition| transition.from.clone()),
                to: loaded_event
                    .event
                    .transition
                    .as_ref()
                    .map(|transition| transition.to.clone()),
            })
            .collect(),
    }
}

fn derived_claim_handoff(claim: &ClaimRecord) -> Option<ClaimHandoffOutcome> {
    match claim.claim.state {
        ClaimState::Draft | ClaimState::Submitted | ClaimState::InReview => None,
        ClaimState::Accepted => {
            let has_canonical_link = claim
                .resolution
                .as_ref()
                .map(|resolution| {
                    resolution.canonical_record_path.is_some()
                        || resolution.canonical_mirror_path.is_some()
                })
                .unwrap_or(false);
            Some(if has_canonical_link {
                ClaimHandoffOutcome::Superseded
            } else {
                ClaimHandoffOutcome::PendingCanonical
            })
        }
        ClaimState::Rejected => Some(ClaimHandoffOutcome::Rejected),
        ClaimState::Withdrawn => Some(ClaimHandoffOutcome::Withdrawn),
        ClaimState::Disputed => Some(ClaimHandoffOutcome::Disputed),
    }
}

fn render_claim_review_template(claim: &ClaimRecord) -> String {
    format!(
        "# Claim review\n\n- Claim: `{}`\n- Repository: `{}/{}/{}`\n- Status: `{:?}`\n- Reviewer:\n- Decision:\n- Notes:\n",
        claim.claim.id,
        claim.identity.host,
        claim.identity.owner,
        claim.identity.repo,
        claim.claim.state
    )
}

fn next_claim_state(
    current: &ClaimState,
    kind: &ClaimEventKind,
    has_events: bool,
    corrected_state: Option<&ClaimState>,
) -> Result<ClaimState> {
    match kind {
        ClaimEventKind::Submitted => {
            if *current != ClaimState::Draft || has_events {
                bail!("submitted events are only valid for draft claims without prior history");
            }
            Ok(ClaimState::Submitted)
        }
        ClaimEventKind::ReviewStarted => {
            if *current != ClaimState::Submitted {
                bail!("review_started events are only valid for submitted claims");
            }
            Ok(ClaimState::InReview)
        }
        ClaimEventKind::Accepted => {
            if !matches!(current, ClaimState::Submitted | ClaimState::InReview) {
                bail!("accepted events are only valid for submitted or in_review claims");
            }
            Ok(ClaimState::Accepted)
        }
        ClaimEventKind::Rejected => {
            if !matches!(current, ClaimState::Submitted | ClaimState::InReview) {
                bail!("rejected events are only valid for submitted or in_review claims");
            }
            Ok(ClaimState::Rejected)
        }
        ClaimEventKind::Withdrawn => {
            if !matches!(
                current,
                ClaimState::Draft | ClaimState::Submitted | ClaimState::InReview
            ) {
                bail!("withdrawn events are only valid before terminal review outcomes");
            }
            Ok(ClaimState::Withdrawn)
        }
        ClaimEventKind::Disputed => {
            if !matches!(current, ClaimState::Submitted | ClaimState::InReview) {
                bail!("disputed events are only valid for submitted or in_review claims");
            }
            Ok(ClaimState::Disputed)
        }
        ClaimEventKind::Corrected => {
            if !has_events {
                bail!("corrected events require prior claim history");
            }
            if let Some(state) = corrected_state {
                if *state == ClaimState::Draft {
                    bail!("corrected events must not reset a claim back to draft");
                }
                Ok(state.clone())
            } else {
                Ok(current.clone())
            }
        }
    }
}

fn event_transition_for(
    current: &ClaimState,
    next: &ClaimState,
    kind: &ClaimEventKind,
) -> Option<ClaimTransition> {
    if matches!(kind, ClaimEventKind::Corrected) {
        return None;
    }

    Some(ClaimTransition {
        from: current.clone(),
        to: next.clone(),
    })
}

fn claim_event_kind_slug(kind: &ClaimEventKind) -> &'static str {
    match kind {
        ClaimEventKind::Submitted => "submitted",
        ClaimEventKind::ReviewStarted => "review-started",
        ClaimEventKind::Accepted => "accepted",
        ClaimEventKind::Rejected => "rejected",
        ClaimEventKind::Withdrawn => "withdrawn",
        ClaimEventKind::Disputed => "disputed",
        ClaimEventKind::Corrected => "corrected",
    }
}

fn update_claim_resolution(
    existing: &ClaimRecord,
    kind: &ClaimEventKind,
    next_state: &ClaimState,
    canonical_record_path: Option<String>,
    canonical_mirror_path: Option<String>,
    result_event: &str,
) -> Result<Option<ClaimResolution>> {
    if *next_state != ClaimState::Accepted {
        return Ok(None);
    }

    let provided_links = canonical_record_path.is_some() || canonical_mirror_path.is_some();
    match kind {
        ClaimEventKind::Accepted => {
            if !provided_links {
                return Ok(None);
            }
            Ok(Some(ClaimResolution {
                canonical_record_path,
                canonical_mirror_path,
                result_event: Some(result_event.into()),
            }))
        }
        ClaimEventKind::Corrected => {
            if !provided_links {
                return Ok(existing.resolution.clone());
            }
            let mut resolution = existing.resolution.clone().unwrap_or(ClaimResolution {
                canonical_record_path: None,
                canonical_mirror_path: None,
                result_event: None,
            });
            resolution.canonical_record_path = canonical_record_path;
            resolution.canonical_mirror_path = canonical_mirror_path;
            resolution.result_event = Some(result_event.into());
            Ok(Some(resolution))
        }
        _ => Ok(existing.resolution.clone()),
    }
}

fn candidate_claim_context(
    root: &Path,
    candidate: &CandidateManifest,
) -> Option<RecordClaimContext> {
    let handoff_root = match candidate.path.parent() {
        Some(parent) => parent.join("claims"),
        None => return None,
    };
    if !handoff_root.is_dir() {
        return None;
    }

    let mut claim_dirs = fs::read_dir(&handoff_root)
        .ok()?
        .filter_map(|entry| entry.ok())
        .filter_map(|entry| {
            entry
                .file_type()
                .ok()
                .filter(|ty| ty.is_dir())
                .map(|_| entry.path())
        })
        .collect::<Vec<_>>();
    claim_dirs.sort();

    let manifest_path = candidate.manifest_path.as_str();
    let mut matching = claim_dirs
        .into_iter()
        .filter_map(|claim_dir| load_claim_directory(root, &claim_dir).ok())
        .filter_map(|loaded| {
            let handoff = derived_claim_handoff(&loaded.claim)?;
            if matches!(
                handoff,
                ClaimHandoffOutcome::Rejected | ClaimHandoffOutcome::Withdrawn
            ) {
                return None;
            }
            if !claim_matches_candidate(&loaded.claim, manifest_path, candidate) {
                return None;
            }
            Some((loaded, handoff))
        })
        .collect::<Vec<_>>();

    matching.sort_by(|left, right| {
        right
            .0
            .claim
            .claim
            .updated_at
            .cmp(&left.0.claim.claim.updated_at)
            .then_with(|| left.0.claim_path.cmp(&right.0.claim_path))
    });

    let (loaded, handoff) = matching.into_iter().next()?;
    Some(RecordClaimContext {
        id: loaded.claim.claim.id,
        state: loaded.claim.claim.state,
        handoff,
        claim_path: loaded.claim_path,
        latest_event: loaded.events.last().map(|event| event.path.clone()),
        review_path: loaded.review_path,
    })
}

fn claim_matches_candidate(
    claim: &ClaimRecord,
    manifest_path: &str,
    candidate: &CandidateManifest,
) -> bool {
    if claim
        .target
        .index_paths
        .iter()
        .any(|path| path == manifest_path)
    {
        return true;
    }

    if claim
        .resolution
        .as_ref()
        .and_then(|resolution| resolution.canonical_mirror_path.as_deref())
        .is_some_and(|path| path == manifest_path)
    {
        return true;
    }

    if claim
        .resolution
        .as_ref()
        .and_then(|resolution| resolution.canonical_record_path.as_deref())
        .is_some_and(|path| path == manifest_path)
    {
        return true;
    }

    if candidate
        .manifest
        .record
        .source
        .as_deref()
        .is_some_and(|source| {
            claim
                .target
                .record_sources
                .iter()
                .any(|record_source| record_source == source)
        })
    {
        return true;
    }

    candidate.identity.as_ref().is_some_and(|identity| {
        claim.identity.host == identity.host
            && claim.identity.owner == identity.owner
            && claim.identity.repo == identity.repo
    })
}

fn validate_claim_record(claim: &ClaimRecord) -> Result<()> {
    if claim.schema != SUPPORTED_CLAIM_SCHEMA {
        bail!(
            "unsupported claim schema `{}`; expected {}",
            claim.schema,
            SUPPORTED_CLAIM_SCHEMA
        );
    }

    require_non_empty("claim.id", &claim.claim.id)?;
    require_non_empty("claim.created_at", &claim.claim.created_at)?;
    require_non_empty("claim.updated_at", &claim.claim.updated_at)?;
    require_non_empty("identity.host", &claim.identity.host)?;
    require_non_empty("identity.owner", &claim.identity.owner)?;
    require_non_empty("identity.repo", &claim.identity.repo)?;
    require_non_empty("claimant.display_name", &claim.claimant.display_name)?;
    require_non_empty("claimant.asserted_role", &claim.claimant.asserted_role)?;
    if claim.target.index_paths.is_empty()
        && claim.target.record_sources.is_empty()
        && claim.target.canonical_repo_url.is_none()
    {
        bail!(
            "claim.target must include at least one index path, record source, or canonical repo url"
        );
    }
    Ok(())
}

fn validate_claim_event(event: &ClaimEvent) -> Result<()> {
    if event.schema != SUPPORTED_CLAIM_EVENT_SCHEMA {
        bail!(
            "unsupported claim event schema `{}`; expected {}",
            event.schema,
            SUPPORTED_CLAIM_EVENT_SCHEMA
        );
    }

    if event.event.sequence == 0 {
        bail!("event.sequence must be greater than zero");
    }
    require_non_empty("event.timestamp", &event.event.timestamp)?;
    require_non_empty("event.actor", &event.event.actor)?;
    require_non_empty("summary.text", &event.summary.text)?;
    Ok(())
}

fn require_non_empty(field: &str, value: &str) -> Result<()> {
    if value.trim().is_empty() {
        bail!("{field} must not be empty");
    }
    Ok(())
}

fn require_path_segment(field: &str, value: &str) -> Result<()> {
    require_non_empty(field, value)?;
    let path = Path::new(value);
    let mut components = path.components();
    if !matches!(components.next(), Some(Component::Normal(_))) || components.next().is_some() {
        bail!("{field} must be a single path segment");
    }
    Ok(())
}

fn resolve_repository_local_path(root: &Path, value: &str) -> Result<PathBuf> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        bail!("path must not be empty");
    }

    let path = Path::new(trimmed);
    let mut normalized = PathBuf::new();
    for component in path.components() {
        match component {
            Component::Normal(part) => normalized.push(part),
            Component::CurDir => {}
            Component::ParentDir => bail!("path must stay within the repository root"),
            Component::RootDir | Component::Prefix(_) => {
                bail!("path must be relative to the repository root")
            }
        }
    }

    Ok(root.join(normalized))
}

fn resolve_conflict_reason(
    selected_reason: SelectionReason,
    selected: &CandidateManifest,
    competing: &CandidateManifest,
) -> SelectionReason {
    match selected_reason {
        SelectionReason::OnlyMatchingRecord => SelectionReason::OnlyMatchingRecord,
        SelectionReason::CanonicalPreferred | SelectionReason::HigherStatusOverlay => {
            selected_reason
        }
        SelectionReason::EqualAuthorityConflict => {
            if competing.rank == selected.rank {
                SelectionReason::EqualAuthorityConflict
            } else {
                SelectionReason::HigherStatusOverlay
            }
        }
    }
}

fn resolve_competing_value(manifest: &Manifest, path: &str) -> Option<Value> {
    query_manifest_value(manifest, path).ok()
}

fn resolve_candidates(root: &Path) -> Result<Vec<CandidateManifest>> {
    let mut candidates = load_direct_candidates(root)?;
    if !candidates.is_empty() {
        let direct_identities = unique_identities(
            candidates
                .iter()
                .filter_map(|candidate| candidate.identity.clone()),
        );
        if direct_identities.len() > 1 {
            bail!("multiple root candidates describe different repository identities");
        }

        if let Some(identity) = direct_identities.first() {
            for candidate in load_descendant_candidates(root)? {
                if candidate.identity.as_ref() == Some(identity) {
                    candidates.push(candidate);
                }
            }
        }

        sort_candidates(&mut candidates);
        return Ok(candidates);
    }

    let descendants = load_descendant_candidates(root)?;
    if descendants.is_empty() {
        bail!(
            "failed to read {}: no .repo, record.toml, or descendant record.toml candidates found",
            manifest_path(root).display()
        );
    }

    let identities = unique_identities(
        descendants
            .iter()
            .filter_map(|candidate| candidate.identity.clone()),
    );
    let mut candidates = if identities.len() == 1 {
        let identity = &identities[0];
        descendants
            .into_iter()
            .filter(|candidate| candidate.identity.as_ref() == Some(identity))
            .collect::<Vec<_>>()
    } else if identities.is_empty() && descendants.len() == 1 {
        descendants
    } else if identities.is_empty() {
        bail!("multiple candidate overlays were found, but none expose a resolvable repository identity");
    } else {
        bail!("multiple repository identities were found under the query root; point query/trust at one repository scope");
    };

    sort_candidates(&mut candidates);
    Ok(candidates)
}

fn load_direct_candidates(root: &Path) -> Result<Vec<CandidateManifest>> {
    let mut candidates = Vec::new();
    for name in [".repo", "record.toml"] {
        let path = root.join(name);
        if !path.exists() {
            continue;
        }

        let document = load_manifest_file(&path)?;
        validate_manifest(root, &document.manifest)?;
        candidates.push(candidate_from_document(root, &document));
    }
    Ok(candidates)
}

fn load_descendant_candidates(root: &Path) -> Result<Vec<CandidateManifest>> {
    let mut record_dirs = Vec::new();
    collect_record_dirs(root, &mut record_dirs)?;
    record_dirs.sort();

    let root_record = root.join("record.toml");
    let mut candidates = Vec::new();
    for record_dir in record_dirs {
        let path = record_dir.join("record.toml");
        if path == root_record {
            continue;
        }
        let document = load_manifest_file(&path)?;
        validate_manifest(root, &document.manifest)?;
        candidates.push(candidate_from_document(root, &document));
    }
    Ok(candidates)
}

fn candidate_from_document(root: &Path, document: &LoadedManifest) -> CandidateManifest {
    CandidateManifest {
        manifest_path: display_path(root, &document.path),
        path: document.path.clone(),
        rank: precedence_rank(&document.manifest),
        identity: manifest_identity(root, document),
        manifest: document.manifest.clone(),
    }
}

fn precedence_rank(manifest: &Manifest) -> u8 {
    match (&manifest.record.mode, &manifest.record.status) {
        (RecordMode::Native, RecordStatus::Canonical) => 7,
        (_, RecordStatus::Canonical) => 6,
        (_, RecordStatus::Verified) => 5,
        (_, RecordStatus::Reviewed) => 4,
        (_, RecordStatus::Imported) => 3,
        (_, RecordStatus::Inferred) => 2,
        (_, RecordStatus::Draft) => 1,
    }
}

fn manifest_identity(root: &Path, document: &LoadedManifest) -> Option<RepositoryIdentity> {
    document
        .manifest
        .record
        .source
        .as_deref()
        .and_then(repository_identity)
        .map(repository_identity_parts)
        .or_else(|| {
            document
                .manifest
                .repo
                .homepage
                .as_deref()
                .and_then(repository_identity)
                .map(repository_identity_parts)
        })
        .or_else(|| index_manifest_identity(root, &document.path))
}

fn index_manifest_identity(root: &Path, path: &Path) -> Option<RepositoryIdentity> {
    let relative = path.strip_prefix(root).ok()?;
    let segments = relative
        .iter()
        .map(|segment| segment.to_string_lossy().to_string())
        .collect::<Vec<_>>();
    let repos_index = segments.iter().position(|segment| segment == "repos")?;
    let tail = &segments[repos_index + 1..];
    if tail.len() != 4 || tail[3] != "record.toml" {
        return None;
    }
    Some(RepositoryIdentity {
        host: tail[0].clone(),
        owner: tail[1].clone(),
        repo: tail[2].clone(),
    })
}

fn unique_identities(
    identities: impl Iterator<Item = RepositoryIdentity>,
) -> Vec<RepositoryIdentity> {
    let mut unique = Vec::new();
    for identity in identities {
        if !unique.iter().any(|existing| existing == &identity) {
            unique.push(identity);
        }
    }
    unique
}

fn repository_identity_parts(parts: (String, String, String)) -> RepositoryIdentity {
    RepositoryIdentity {
        host: parts.0,
        owner: parts.1,
        repo: parts.2,
    }
}

fn sort_candidates(candidates: &mut [CandidateManifest]) {
    candidates.sort_by(|left, right| {
        right
            .rank
            .cmp(&left.rank)
            .then_with(|| left.manifest_path.cmp(&right.manifest_path))
    });
}

pub fn validate_repository(root: &Path) -> ValidateReport {
    match load_manifest_document(root) {
        Ok(document) => {
            let diagnostics = validate_manifest_diagnostics(root, &document.manifest)
                .into_iter()
                .map(|item| RepositoryDiagnostic {
                    severity: "error",
                    source: item.source.to_string(),
                    message: item.message,
                    manifest_path: Some(display_path(root, &document.path)),
                })
                .collect::<Vec<_>>();

            ValidateReport {
                valid: diagnostics.is_empty(),
                root: root.display().to_string(),
                manifest_path: Some(display_path(root, &document.path)),
                diagnostics,
                record: Some(record_summary(&document.manifest)),
            }
        }
        Err(err) => ValidateReport {
            valid: false,
            root: root.display().to_string(),
            manifest_path: None,
            diagnostics: vec![RepositoryDiagnostic {
                severity: "error",
                source: "load_manifest_document".into(),
                message: err.to_string(),
                manifest_path: None,
            }],
            record: None,
        },
    }
}

pub fn query_repository(root: &Path, path: &str) -> Result<QueryReport> {
    let candidates = resolve_candidates(root)?;
    let selected = &candidates[0];
    let value = query_manifest_value(&selected.manifest, path)?;
    let reason = resolve_selection_reason(&candidates, selected);
    Ok(QueryReport {
        root: root.display().to_string(),
        manifest_path: selected.manifest_path.clone(),
        path: path.to_string(),
        value,
        selection: SelectionReport {
            reason,
            record: selected_record(root, selected),
        },
        conflicts: candidates
            .iter()
            .skip(1)
            .map(|candidate| ConflictReport {
                relationship: if candidate.rank == selected.rank {
                    ConflictRelationship::Parallel
                } else {
                    ConflictRelationship::Superseded
                },
                reason: resolve_conflict_reason(reason, selected, candidate),
                value: resolve_competing_value(&candidate.manifest, path),
                record: selected_record(root, candidate),
            })
            .collect(),
    })
}

pub fn trust_repository(root: &Path) -> Result<TrustReport> {
    let candidates = resolve_candidates(root)?;
    let selected = &candidates[0];
    let reason = resolve_selection_reason(&candidates, selected);
    Ok(TrustReport {
        root: root.display().to_string(),
        manifest_path: selected.manifest_path.clone(),
        selection: SelectionReport {
            reason,
            record: selected_record(root, selected),
        },
        conflicts: candidates
            .iter()
            .skip(1)
            .map(|candidate| ConflictReport {
                relationship: if candidate.rank == selected.rank {
                    ConflictRelationship::Parallel
                } else {
                    ConflictRelationship::Superseded
                },
                reason: resolve_conflict_reason(reason, selected, candidate),
                value: None,
                record: selected_record(root, candidate),
            })
            .collect(),
    })
}

pub fn index_snapshot_digest(index_root: &Path) -> Result<String> {
    let mut files = Vec::new();
    collect_files(index_root, &mut files)?;
    files.sort();

    let mut hasher = Sha256::new();
    for path in files {
        let relative = path.strip_prefix(index_root).unwrap_or(&path);
        hasher.update(relative.to_string_lossy().as_bytes());
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
                value: resolve_competing_value(&candidate.manifest, path),
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
            manifest: selected.manifest.clone(),
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
                manifest: candidate.manifest.clone(),
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
                value: resolve_competing_value(&candidate.manifest, path),
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

pub fn generate_check_repository(root: &Path) -> Result<GenerateCheckReport> {
    let document = load_manifest_document(root)?;
    validate_manifest(root, &document.manifest)?;
    ensure_native_managed_surface_record(&document.manifest, "generate-check")?;
    let mut rendered_outputs = Vec::new();
    let mut stale = Vec::new();

    rendered_outputs.push(generate_check_managed_surface(
        root,
        ManagedSurface::Readme,
        &document.manifest,
        &document.raw,
    )?);

    let digest = source_digest(&document.raw);
    if let Some(compat) = &document.manifest.compat {
        if let Some(github) = &compat.github {
            if matches!(github.codeowners, Some(CompatMode::Generate)) {
                let owners = document
                    .manifest
                    .owners
                    .as_ref()
                    .map(|o| o.maintainers.join(" "))
                    .unwrap_or_else(|| "@maintainers".into());
                rendered_outputs.push(generate_check_output(
                    root,
                    root.join(".github/CODEOWNERS"),
                    format!(
                        "{}\n* {}\n",
                        generated_banner(CommentStyle::Hash, &document.manifest, &digest),
                        owners
                    ),
                )?);
            }
            if matches!(github.security, Some(CompatMode::Generate)) {
                rendered_outputs.push(generate_check_managed_surface(
                    root,
                    ManagedSurface::Security,
                    &document.manifest,
                    &document.raw,
                )?);
            }
            if matches!(github.contributing, Some(CompatMode::Generate)) {
                rendered_outputs.push(generate_check_managed_surface(
                    root,
                    ManagedSurface::Contributing,
                    &document.manifest,
                    &document.raw,
                )?);
            }
            if matches!(github.pull_request_template, Some(CompatMode::Generate)) {
                rendered_outputs.push(generate_check_output(
                    root,
                    root.join(".github/pull_request_template.md"),
                    render_pull_request_template(&document.manifest, &digest),
                )?);
            }
        }
    }

    for output in &rendered_outputs {
        if output.stale {
            stale.push(output.path.clone());
        }
    }

    Ok(GenerateCheckReport {
        root: root.display().to_string(),
        checked: rendered_outputs.len(),
        stale,
        outputs: rendered_outputs,
    })
}

pub fn import_preview_repository(
    root: &Path,
    mode: ImportMode,
    source: Option<&str>,
) -> Result<ImportPreviewReport> {
    let plan = import_repository(root, mode, source)?;
    Ok(ImportPreviewReport {
        root: root.display().to_string(),
        mode: import_mode_name(mode),
        manifest_path: display_path(root, &plan.manifest_path),
        manifest: plan.manifest.clone(),
        manifest_text: plan.manifest_text.clone(),
        evidence_path: plan
            .evidence_path
            .as_ref()
            .map(|path| display_path(root, path)),
        evidence_text: plan.evidence_text.clone(),
        imported_sources: plan.imported_sources.clone(),
        inferred_fields: plan.inferred_fields.clone(),
        record: record_summary(&plan.manifest),
    })
}

pub fn import_repository(
    root: &Path,
    mode: ImportMode,
    source: Option<&str>,
) -> Result<ImportPlan> {
    import_repository_with_options(root, mode, source, &ImportOptions::default())
}

pub fn import_repository_with_options(
    root: &Path,
    mode: ImportMode,
    source: Option<&str>,
    options: &ImportOptions,
) -> Result<ImportPlan> {
    let readme = load_first_existing_file(root, IMPORT_README_CANDIDATES)?;
    let codeowners = load_first_existing_file(root, &[".github/CODEOWNERS", "CODEOWNERS"])?;
    let security = load_first_existing_file(root, &[".github/SECURITY.md", "SECURITY.md"])?;
    let cargo_toml = load_first_existing_file(root, &["Cargo.toml"])?;
    let package_json = load_first_existing_file(root, &["package.json"])?;
    let pyproject_toml = load_first_existing_file(root, &["pyproject.toml"])?;
    let go_mod = load_first_existing_file(root, &["go.mod"])?;
    let workflow_files = load_workflow_import_files(root)?;
    let contributing =
        load_first_existing_file(root, &["CONTRIBUTING.md", ".github/CONTRIBUTING.md"])?;
    let pull_request_template = load_first_existing_file(
        root,
        &[
            ".github/pull_request_template.md",
            ".github/PULL_REQUEST_TEMPLATE.md",
            "pull_request_template.md",
            "PULL_REQUEST_TEMPLATE.md",
        ],
    )?;

    let readme_metadata = readme
        .as_ref()
        .map(|file| parse_readme_metadata(&file.contents))
        .unwrap_or_default();
    let codeowners_metadata = codeowners
        .as_ref()
        .map(|file| parse_codeowners_metadata(&file.contents))
        .unwrap_or_default();
    let parsed_security = security
        .as_ref()
        .map(|file| parse_security_import_metadata(&file.contents))
        .unwrap_or_default();
    let security_contact = parsed_security
        .contact
        .clone()
        .or_else(|| security.as_ref().map(|_| "unknown".into()));
    let security_note = if security.is_some() {
        if parsed_security.contact.is_some() {
            parsed_security.note.clone()
        } else {
            Some(
                "SECURITY.md did not expose a direct mailbox or reporting URL, so `security_contact = \"unknown\"` is intentional."
                    .to_string(),
            )
        }
    } else {
        None
    };
    let imported_commands = infer_imported_commands(
        cargo_toml.as_ref(),
        package_json.as_ref(),
        pyproject_toml.as_ref(),
        go_mod.as_ref(),
        &workflow_files,
    );

    let mut imported_sources = Vec::new();
    let mut inferred_defaults = Vec::new();

    let repo_name = match readme_metadata.title {
        Some(ref title) => {
            note_import(
                &mut imported_sources,
                &readme.as_ref().expect("readme exists").path,
            );
            title.clone()
        }
        None => {
            inferred_defaults.push("repo.name".into());
            root.file_name()
                .and_then(|name| name.to_str())
                .filter(|name| !name.is_empty())
                .unwrap_or("repository")
                .to_string()
        }
    };

    let description = match readme_metadata.description {
        Some(ref description) => {
            note_import(
                &mut imported_sources,
                &readme.as_ref().expect("readme exists").path,
            );
            description.clone()
        }
        None => {
            inferred_defaults.push("repo.description".into());
            "Imported repository metadata; review and refine before relying on it.".into()
        }
    };

    let imported_docs = build_imported_docs(
        readme_metadata.docs_root.clone(),
        readme_metadata.docs_getting_started.clone(),
    );

    if !codeowners_metadata.owners.is_empty() || codeowners_metadata.team.is_some() {
        if let Some(file) = &codeowners {
            note_import(&mut imported_sources, &file.path);
        }
    }

    if security_contact.is_some() {
        if let Some(file) = &security {
            note_import(&mut imported_sources, &file.path);
        }
    }
    if let Some(command) = imported_commands.build.as_ref() {
        if matches!(command.provenance, ImportedCommandProvenance::Imported) {
            note_import(&mut imported_sources, &command.source_path);
        }
    }
    if let Some(command) = imported_commands.test.as_ref() {
        if matches!(command.provenance, ImportedCommandProvenance::Imported) {
            note_import(&mut imported_sources, &command.source_path);
        }
    }

    let mut inferred_fields = inferred_defaults.clone();
    for field in &imported_commands.inferred_fields {
        push_unique(&mut inferred_fields, field.clone());
    }

    let provenance = import_provenance(&imported_sources, &inferred_fields);
    let confidence = if provenance.iter().any(|value| value == "imported") {
        "medium"
    } else {
        "low"
    };

    let status = match mode {
        ImportMode::Native => RecordStatus::Draft,
        ImportMode::Overlay if inferred_fields.is_empty() => RecordStatus::Imported,
        ImportMode::Overlay => RecordStatus::Inferred,
    };
    let generated_at = options
        .generated_at
        .as_deref()
        .map(|value| normalize_rfc3339("record.generated_at", value))
        .transpose()?;

    let mut manifest = Manifest::new(
        Record {
            mode: match mode {
                ImportMode::Native => RecordMode::Native,
                ImportMode::Overlay => RecordMode::Overlay,
            },
            status,
            source: match mode {
                ImportMode::Native => None,
                ImportMode::Overlay => Some(
                    source
                        .map(str::trim)
                        .filter(|value| !value.is_empty())
                        .ok_or_else(|| anyhow!("--source is required for overlay imports"))?
                        .to_string(),
                ),
            },
            generated_at,
            trust: Some(Trust {
                confidence: Some(confidence.into()),
                provenance,
                notes: Some(import_notes(
                    mode,
                    &imported_sources,
                    &inferred_defaults,
                    codeowners_metadata.note.as_deref(),
                    security_note.as_deref(),
                    &imported_commands.notes,
                )),
            }),
        },
        Repo {
            name: repo_name.clone(),
            description,
            homepage: match mode {
                ImportMode::Native => None,
                ImportMode::Overlay => source.map(|value| value.trim().to_string()),
            },
            license: None,
            status: None,
            visibility: None,
            languages: Vec::new(),
            build: imported_commands
                .build
                .as_ref()
                .map(|command| command.command.clone()),
            test: imported_commands
                .test
                .as_ref()
                .map(|command| command.command.clone()),
            topics: Vec::new(),
        },
    );
    manifest.owners = build_imported_owners(
        codeowners_metadata.owners,
        codeowners_metadata.team,
        security_contact.clone(),
    );
    manifest.docs = imported_docs.clone();
    manifest.readme = match mode {
        ImportMode::Native => Some(Readme {
            title: Some(repo_name),
            tagline: None,
            sections: {
                let mut sections = vec!["overview".into()];
                if imported_docs.is_some() {
                    sections.push("docs".into());
                }
                sections.push("security".into());
                sections
            },
            custom_sections: Default::default(),
        }),
        ImportMode::Overlay => None,
    };
    manifest.compat = match mode {
        ImportMode::Native => Some(Compat {
            github: Some(native_import_github_compat(
                &manifest,
                codeowners.as_ref(),
                security.as_ref(),
                contributing.as_ref(),
                pull_request_template.as_ref(),
            )),
        }),
        ImportMode::Overlay => None,
    };
    manifest.relations = match mode {
        ImportMode::Native => None,
        ImportMode::Overlay => Some(Relations {
            references: Vec::new(),
        }),
    };
    validate_manifest(root, &manifest)?;
    let manifest_text = render_manifest(&manifest)?;

    let (evidence_path, evidence_text) = match mode {
        ImportMode::Native => (None, None),
        ImportMode::Overlay => (
            Some(root.join("evidence.md")),
            Some(render_import_evidence(
                &imported_sources,
                &inferred_defaults,
                security_contact.as_deref(),
                codeowners_metadata.note.as_deref(),
                security_note.as_deref(),
                imported_docs.is_some(),
                &imported_commands.evidence_bullets,
            )),
        ),
    };

    Ok(ImportPlan {
        manifest_path: root.join(match mode {
            ImportMode::Native => ".repo",
            ImportMode::Overlay => "record.toml",
        }),
        manifest,
        manifest_text,
        evidence_path,
        evidence_text,
        imported_sources,
        inferred_fields,
    })
}

pub fn validate_manifest(root: &Path, manifest: &Manifest) -> Result<()> {
    let diagnostics = validate_manifest_diagnostics(root, manifest);
    if diagnostics.is_empty() {
        return Ok(());
    }

    bail!(
        "{}",
        diagnostics
            .into_iter()
            .map(|diagnostic| diagnostic.message)
            .collect::<Vec<_>>()
            .join("\n")
    )
}

pub fn validate_manifest_diagnostics(
    root: &Path,
    manifest: &Manifest,
) -> Vec<ValidationDiagnostic> {
    let mut diagnostics = Vec::new();

    if manifest.schema.trim() != SUPPORTED_SCHEMA {
        diagnostics.push(validation_error(
            "validate_manifest",
            format!("unsupported schema: {}", manifest.schema),
        ));
    }

    if let Some(generated_at) = manifest.record.generated_at.as_deref() {
        if let Err(err) = parse_rfc3339("record.generated_at", generated_at) {
            diagnostics.push(validation_error("validate_manifest", err.to_string()));
        }
    }

    if manifest.repo.name.trim().is_empty() {
        diagnostics.push(validation_error(
            "validate_manifest",
            "repo.name must not be empty",
        ));
    }

    diagnostics.extend(validate_readme_sections(manifest));

    if matches!(manifest.record.mode, RecordMode::Native) {
        diagnostics.extend(validate_native_paths(root, manifest));
    }

    if matches!(manifest.record.mode, RecordMode::Overlay) {
        let source = manifest.record.source.as_deref().unwrap_or("").trim();
        if source.is_empty() {
            diagnostics.push(validation_error(
                "validate_manifest",
                "record.source must be set for overlay records",
            ));
        }

        match manifest.record.trust.as_ref() {
            Some(trust) => {
                if trust.provenance.is_empty() {
                    diagnostics.push(validation_error(
                        "validate_manifest",
                        "record.trust.provenance must list at least one provenance entry for overlay records",
                    ));
                }
            }
            None => diagnostics.push(validation_error(
                "validate_manifest",
                "record.trust must be set for overlay records",
            )),
        }
    }

    diagnostics
}

fn validate_native_paths(root: &Path, manifest: &Manifest) -> Vec<ValidationDiagnostic> {
    let mut diagnostics = Vec::new();

    if let Some(docs) = &manifest.docs {
        for path in [
            &docs.root,
            &docs.getting_started,
            &docs.architecture,
            &docs.api,
        ]
        .into_iter()
        .flatten()
        {
            match resolve_repository_local_path(root, path) {
                Ok(target) => {
                    if !target.exists() {
                        diagnostics.push(validation_error(
                            "validate_native_paths",
                            format!("referenced path does not exist: {}", target.display()),
                        ));
                    }
                }
                Err(err) => {
                    diagnostics.push(validation_error(
                        "validate_native_paths",
                        format!("referenced path `{}` is invalid: {}", path, err),
                    ));
                }
            }
        }
    }

    if let Some(readme) = &manifest.readme {
        for (name, section) in &readme.custom_sections {
            if let Some(path) = &section.path {
                match resolve_repository_local_path(root, path) {
                    Ok(target) => {
                        if !target.exists() {
                            diagnostics.push(validation_error(
                                "validate_native_paths",
                                format!(
                                    "custom README section `{}` references a missing path: {}",
                                    name,
                                    target.display()
                                ),
                            ));
                        }
                    }
                    Err(err) => {
                        diagnostics.push(validation_error(
                            "validate_native_paths",
                            format!(
                                "custom README section `{}` uses an invalid path `{}`: {}",
                                name, path, err
                            ),
                        ));
                    }
                }
            }
        }
    }

    diagnostics
}

#[derive(Default)]
struct ReadmeMetadata {
    title: Option<String>,
    description: Option<String>,
    docs_root: Option<String>,
    docs_getting_started: Option<String>,
}

#[derive(Default)]
struct ReadmeDocsMetadata {
    root: Option<String>,
    getting_started: Option<String>,
}

struct ImportedFile {
    path: String,
    contents: String,
}

#[derive(Default)]
struct CodeownersMetadata {
    owners: Vec<String>,
    team: Option<String>,
    note: Option<String>,
}

#[derive(Debug, Clone)]
struct CodeownersRule {
    pattern: String,
    owners: Vec<String>,
    teams: Vec<String>,
}

#[derive(Default)]
struct SecurityImportMetadata {
    contact: Option<String>,
    note: Option<String>,
}

#[derive(Default)]
struct ImportedCommandMetadata {
    build: Option<ImportedCommandSelection>,
    test: Option<ImportedCommandSelection>,
    inferred_fields: Vec<String>,
    notes: Vec<String>,
    evidence_bullets: Vec<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ImportedCommandProvenance {
    Imported,
    Inferred,
}

#[derive(Debug, Clone)]
struct ImportedCommandSelection {
    command: String,
    source_path: String,
    provenance: ImportedCommandProvenance,
}

#[derive(Debug, Clone)]
struct ImportedCommandCandidate {
    source_path: String,
    build: Option<String>,
    test: Option<String>,
}

fn load_first_existing_file(
    root: &Path,
    candidates: &[&'static str],
) -> Result<Option<ImportedFile>> {
    for candidate in candidates {
        let path = root.join(candidate);
        if path.exists() {
            let contents = fs::read_to_string(&path)
                .map_err(|err| anyhow!("failed to read {}: {}", path.display(), err))?;
            return Ok(Some(ImportedFile {
                path: candidate.to_string(),
                contents,
            }));
        }
    }

    Ok(None)
}

fn load_workflow_import_files(root: &Path) -> Result<Vec<ImportedFile>> {
    let workflows_root = root.join(".github").join("workflows");
    if !workflows_root.is_dir() {
        return Ok(Vec::new());
    }

    let mut files = fs::read_dir(&workflows_root)
        .map_err(|err| anyhow!("failed to read {}: {}", workflows_root.display(), err))?
        .filter_map(|entry| entry.ok())
        .filter_map(|entry| {
            let path = entry.path();
            let file_name = path.file_name()?.to_str()?;
            let lower = file_name.to_ascii_lowercase();
            if !path.is_file() || !(lower.ends_with(".yml") || lower.ends_with(".yaml")) {
                return None;
            }
            Some((file_name.to_string(), path))
        })
        .collect::<Vec<_>>();
    files.sort_by(|left, right| left.0.cmp(&right.0));

    let mut imported = Vec::new();
    for (file_name, path) in files {
        let contents = fs::read_to_string(&path)
            .map_err(|err| anyhow!("failed to read {}: {}", path.display(), err))?;
        imported.push(ImportedFile {
            path: format!(".github/workflows/{}", file_name),
            contents,
        });
    }

    Ok(imported)
}

fn infer_imported_commands(
    cargo_toml: Option<&ImportedFile>,
    package_json: Option<&ImportedFile>,
    pyproject_toml: Option<&ImportedFile>,
    go_mod: Option<&ImportedFile>,
    workflow_files: &[ImportedFile],
) -> ImportedCommandMetadata {
    let mut manifest_candidates = Vec::new();
    if let Some(candidate) = cargo_toml.and_then(infer_cargo_manifest_commands) {
        manifest_candidates.push(candidate);
    }
    if let Some(candidate) = package_json.and_then(infer_package_json_commands) {
        manifest_candidates.push(candidate);
    }
    if let Some(candidate) = pyproject_toml.and_then(infer_pyproject_commands) {
        manifest_candidates.push(candidate);
    }
    if let Some(candidate) = go_mod.and_then(infer_go_module_commands) {
        manifest_candidates.push(candidate);
    }
    let workflow_candidates = workflow_files
        .iter()
        .filter_map(infer_workflow_commands)
        .collect::<Vec<_>>();

    let mut metadata = ImportedCommandMetadata::default();
    metadata.build = resolve_command_field(
        &manifest_candidates,
        &workflow_candidates,
        "repo.build",
        true,
        &mut metadata.notes,
        &mut metadata.evidence_bullets,
        &mut metadata.inferred_fields,
    );
    metadata.test = resolve_command_field(
        &manifest_candidates,
        &workflow_candidates,
        "repo.test",
        false,
        &mut metadata.notes,
        &mut metadata.evidence_bullets,
        &mut metadata.inferred_fields,
    );
    metadata
}

fn infer_cargo_manifest_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let parsed: toml::Value = toml::from_str(&file.contents).ok()?;
    let has_workspace = parsed
        .get("workspace")
        .and_then(toml::Value::as_table)
        .is_some();
    let has_package = parsed
        .get("package")
        .and_then(toml::Value::as_table)
        .is_some();
    if !has_workspace && !has_package {
        return None;
    }

    let (build, test) = if has_workspace {
        ("cargo build --workspace", "cargo test --workspace")
    } else {
        ("cargo build", "cargo test")
    };

    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        build: Some(build.into()),
        test: Some(test.into()),
    })
}

fn infer_package_json_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let parsed: serde_json::Value = serde_json::from_str(&file.contents).ok()?;
    let scripts = parsed
        .get("scripts")
        .and_then(serde_json::Value::as_object)?;
    let runner = detect_node_package_runner(
        parsed
            .get("packageManager")
            .and_then(serde_json::Value::as_str),
    );

    let build = scripts
        .get("build")
        .and_then(serde_json::Value::as_str)
        .filter(|value| !value.trim().is_empty())
        .map(|_| runner.build_command());
    let test = scripts
        .get("test")
        .and_then(serde_json::Value::as_str)
        .filter(|value| !value.trim().is_empty())
        .filter(|value| !is_placeholder_package_json_test_script(value))
        .map(|_| runner.test_command());

    if build.is_none() && test.is_none() {
        return None;
    }

    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        build,
        test,
    })
}

fn infer_pyproject_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let parsed: toml::Value = toml::from_str(&file.contents).ok()?;
    let build = parsed
        .get("build-system")
        .and_then(toml::Value::as_table)
        .map(|_| "python -m build".to_string());
    let test = parsed
        .get("tool")
        .and_then(toml::Value::as_table)
        .and_then(|tool| tool.get("pytest"))
        .map(|_| "python -m pytest".to_string());

    if build.is_none() && test.is_none() {
        return None;
    }

    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        build,
        test,
    })
}

fn infer_go_module_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let has_module = file
        .contents
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .any(|line| line.starts_with("module "));
    if !has_module {
        return None;
    }

    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        build: Some("go build ./...".into()),
        test: Some("go test ./...".into()),
    })
}

fn infer_workflow_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let run_commands = extract_workflow_run_commands(&file.contents);
    let build = first_matching_workflow_command(&run_commands, true);
    let test = first_matching_workflow_command(&run_commands, false);
    if build.is_none() && test.is_none() {
        return None;
    }

    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        build,
        test,
    })
}

fn extract_workflow_run_commands(contents: &str) -> Vec<String> {
    let mut commands = Vec::new();
    let mut run_block_indent = None;

    for line in contents.lines() {
        let indent = line.chars().take_while(|ch| ch.is_whitespace()).count();
        let trimmed = line.trim();

        if let Some(block_indent) = run_block_indent {
            if !trimmed.is_empty() && indent > block_indent {
                commands.push(trimmed.to_string());
                continue;
            }
            run_block_indent = None;
        }

        let run_line = trimmed
            .strip_prefix("- run:")
            .or_else(|| trimmed.strip_prefix("run:"));
        if let Some(rest) = run_line {
            let rest = rest.trim();
            if matches!(rest, "|" | "|-" | ">" | ">-") {
                run_block_indent = Some(indent);
            } else if !rest.is_empty() {
                commands.push(rest.to_string());
            }
        }
    }

    commands
}

fn first_matching_workflow_command(commands: &[String], select_build: bool) -> Option<String> {
    commands.iter().find_map(|command| {
        let trimmed = command.trim();
        if trimmed.is_empty() {
            return None;
        }

        if select_build {
            for prefix in [
                "cargo build",
                "go build",
                "python -m build",
                "npm run build",
                "pnpm build",
                "yarn build",
                "bun run build",
            ] {
                if trimmed.starts_with(prefix) {
                    return Some(trimmed.to_string());
                }
            }
        } else {
            for prefix in [
                "cargo test",
                "go test",
                "python -m pytest",
                "pytest",
                "npm test",
                "npm run test",
                "pnpm test",
                "yarn test",
                "bun run test",
            ] {
                if trimmed.starts_with(prefix) {
                    return Some(trimmed.to_string());
                }
            }
        }

        None
    })
}

enum UniqueCommandResolution {
    None,
    Unique {
        command: String,
        source_path: String,
    },
    Conflict {
        source_paths: Vec<String>,
    },
}

fn resolve_command_field(
    manifest_candidates: &[ImportedCommandCandidate],
    workflow_candidates: &[ImportedCommandCandidate],
    field: &'static str,
    select_build: bool,
    notes: &mut Vec<String>,
    evidence_bullets: &mut Vec<String>,
    inferred_fields: &mut Vec<String>,
) -> Option<ImportedCommandSelection> {
    let manifest_resolution = resolve_unique_command_candidate(manifest_candidates, select_build);
    let workflow_resolution = resolve_unique_command_candidate(workflow_candidates, select_build);

    let manifest_unique = match &manifest_resolution {
        UniqueCommandResolution::Unique {
            command,
            source_path,
        } => Some((command.clone(), source_path.clone())),
        _ => None,
    };
    let workflow_unique = match &workflow_resolution {
        UniqueCommandResolution::Unique {
            command,
            source_path,
        } => Some((command.clone(), source_path.clone())),
        _ => None,
    };

    let mut conflict_paths = Vec::new();
    if let UniqueCommandResolution::Conflict { source_paths } = &manifest_resolution {
        for path in source_paths {
            push_unique(&mut conflict_paths, path.clone());
        }
        if let Some((_, path)) = &workflow_unique {
            push_unique(&mut conflict_paths, path.clone());
        }
    }
    if let UniqueCommandResolution::Conflict { source_paths } = &workflow_resolution {
        for path in source_paths {
            push_unique(&mut conflict_paths, path.clone());
        }
        if let Some((_, path)) = &manifest_unique {
            push_unique(&mut conflict_paths, path.clone());
        }
    }
    if let (Some((manifest_command, manifest_path)), Some((workflow_command, workflow_path))) =
        (&manifest_unique, &workflow_unique)
    {
        if manifest_command != workflow_command {
            push_unique(&mut conflict_paths, manifest_path.clone());
            push_unique(&mut conflict_paths, workflow_path.clone());
        }
    }

    if !conflict_paths.is_empty() {
        let kind = if select_build { "build" } else { "test" };
        let note = format!(
            "Left `{}` unset because {} suggested conflicting {} commands.",
            field,
            human_join(&conflict_paths),
            kind
        );
        notes.push(note.clone());
        evidence_bullets.push(note);
        return None;
    }

    if let Some((command, source_path)) = manifest_unique {
        let selection = ImportedCommandSelection {
            command,
            source_path,
            provenance: ImportedCommandProvenance::Imported,
        };
        note_selected_command(field, &selection, notes, evidence_bullets);
        return Some(selection);
    }

    if let Some((command, source_path)) = workflow_unique {
        let selection = ImportedCommandSelection {
            command,
            source_path,
            provenance: ImportedCommandProvenance::Inferred,
        };
        inferred_fields.push(field.into());
        note_selected_command(field, &selection, notes, evidence_bullets);
        return Some(selection);
    }

    None
}

fn note_selected_command(
    field: &'static str,
    selection: &ImportedCommandSelection,
    notes: &mut Vec<String>,
    evidence_bullets: &mut Vec<String>,
) {
    match selection.provenance {
        ImportedCommandProvenance::Imported => {
            notes.push(format!(
                "Imported `{}` from `{}`.",
                field, selection.source_path
            ));
            evidence_bullets.push(format!(
                "Imported {} from {} as `{}`.",
                field, selection.source_path, selection.command
            ));
        }
        ImportedCommandProvenance::Inferred => {
            notes.push(format!(
                "Inferred `{}` from `{}`.",
                field, selection.source_path
            ));
            evidence_bullets.push(format!(
                "Inferred {} from {} as `{}`.",
                field, selection.source_path, selection.command
            ));
        }
    }
}

fn resolve_unique_command_candidate(
    candidates: &[ImportedCommandCandidate],
    select_build: bool,
) -> UniqueCommandResolution {
    let mut present = Vec::new();
    for candidate in candidates {
        let command = if select_build {
            candidate.build.as_deref()
        } else {
            candidate.test.as_deref()
        };
        if let Some(command) = command.filter(|value| !value.trim().is_empty()) {
            present.push((command.to_string(), candidate.source_path.clone()));
        }
    }

    if present.is_empty() {
        return UniqueCommandResolution::None;
    }

    let mut unique_commands = Vec::new();
    for (command, path) in &present {
        if !unique_commands
            .iter()
            .any(|(existing, _): &(String, String)| existing == command)
        {
            unique_commands.push((command.clone(), path.clone()));
        }
    }

    if unique_commands.len() == 1 {
        let (command, path) = unique_commands.remove(0);
        return UniqueCommandResolution::Unique {
            command,
            source_path: path,
        };
    }

    let mut source_paths = Vec::new();
    for (_, path) in &present {
        push_unique(&mut source_paths, path.clone());
    }
    UniqueCommandResolution::Conflict { source_paths }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum NodePackageRunner {
    Npm,
    Pnpm,
    Yarn,
    Bun,
}

impl NodePackageRunner {
    fn build_command(self) -> String {
        match self {
            Self::Npm => "npm run build".into(),
            Self::Pnpm => "pnpm build".into(),
            Self::Yarn => "yarn build".into(),
            Self::Bun => "bun run build".into(),
        }
    }

    fn test_command(self) -> String {
        match self {
            Self::Npm => "npm test".into(),
            Self::Pnpm => "pnpm test".into(),
            Self::Yarn => "yarn test".into(),
            Self::Bun => "bun run test".into(),
        }
    }
}

fn detect_node_package_runner(package_manager: Option<&str>) -> NodePackageRunner {
    match package_manager
        .filter(|value| !value.trim().is_empty())
        .map(|value| value.to_ascii_lowercase())
    {
        Some(value) if value.starts_with("pnpm@") || value == "pnpm" => NodePackageRunner::Pnpm,
        Some(value) if value.starts_with("yarn@") || value == "yarn" => NodePackageRunner::Yarn,
        Some(value) if value.starts_with("bun@") || value == "bun" => NodePackageRunner::Bun,
        _ => NodePackageRunner::Npm,
    }
}

fn is_placeholder_package_json_test_script(script: &str) -> bool {
    script.to_ascii_lowercase().contains("no test specified")
}

fn parse_readme_metadata(contents: &str) -> ReadmeMetadata {
    let mut metadata = ReadmeMetadata::default();
    let lines = contents.lines().collect::<Vec<_>>();
    let mut in_code_block = false;
    let mut idx = 0;

    while idx < lines.len() {
        let trimmed = lines[idx].trim();
        if trimmed.starts_with("```") {
            in_code_block = !in_code_block;
            idx += 1;
            continue;
        }
        if in_code_block {
            idx += 1;
            continue;
        }

        if metadata.title.is_none() {
            if let Some(title) = parse_readme_title_line(trimmed) {
                metadata.title = Some(title);
                idx += 1;
                continue;
            }
            if let Some(title) = parse_setext_heading(&lines, idx) {
                metadata.title = Some(title);
                idx += 2;
                continue;
            }
        }

        if metadata.description.is_none() {
            if let Some((description, next_idx)) = parse_readme_description(&lines, idx) {
                metadata.description = Some(description);
                idx = next_idx;
                if metadata.title.is_some() {
                    break;
                }
                continue;
            }
        }

        if metadata.title.is_some() && metadata.description.is_some() {
            break;
        }

        idx += 1;
    }

    let docs = parse_readme_docs_metadata(&lines);
    metadata.docs_root = docs.root;
    metadata.docs_getting_started = docs.getting_started;

    metadata
}

fn parse_readme_title_line(line: &str) -> Option<String> {
    if line.starts_with('#') {
        let title = strip_badge_run(line.trim_start_matches('#').trim());
        return normalize_readme_text(title);
    }

    parse_html_heading(line)
}

fn parse_setext_heading(lines: &[&str], idx: usize) -> Option<String> {
    let line = lines.get(idx)?.trim();
    let underline = lines.get(idx + 1)?.trim();
    if line.is_empty() || !is_setext_underline(underline) {
        return None;
    }

    normalize_readme_text(line)
}

fn is_setext_underline(line: &str) -> bool {
    line.len() >= 3 && line.chars().all(|ch| ch == '=' || ch == '-')
}

fn parse_html_heading(line: &str) -> Option<String> {
    let trimmed = line.trim();
    let lower = trimmed.to_ascii_lowercase();
    if !["<h1", "<h2", "<h3", "<h4", "<h5", "<h6"]
        .iter()
        .any(|needle| lower.contains(needle))
    {
        return None;
    }

    normalize_readme_text(trimmed)
}

fn parse_readme_description(lines: &[&str], start: usize) -> Option<(String, usize)> {
    let mut parts = Vec::new();
    let mut idx = start;

    while idx < lines.len() {
        let trimmed = lines[idx].trim();
        if trimmed.starts_with("```") {
            break;
        }
        if trimmed.is_empty() {
            if parts.is_empty() {
                idx += 1;
                continue;
            }
            break;
        }
        if parse_readme_title_line(trimmed).is_some() || parse_setext_heading(lines, idx).is_some()
        {
            if parts.is_empty() {
                return None;
            }
            break;
        }

        let normalized = match normalize_description_line(trimmed) {
            Some(normalized) => normalized,
            None => {
                if parts.is_empty() {
                    idx += 1;
                    continue;
                }
                break;
            }
        };

        parts.push(normalized);
        idx += 1;
    }

    if parts.is_empty() {
        None
    } else {
        Some((parts.join(" "), idx))
    }
}

fn normalize_description_line(line: &str) -> Option<String> {
    if line.is_empty()
        || line.starts_with('#')
        || line.starts_with("![")
        || line.starts_with("[![")
        || is_markdown_reference_definition(line)
        || line.starts_with("<!--")
        || line == "---"
        || line.starts_with("- ")
        || line.starts_with("* ")
        || starts_with_ordered_list_item(line)
        || is_probable_readme_nav_line(line)
        || is_probable_docs_signal_line(line)
    {
        return None;
    }

    let description = line.trim_start_matches('>').trim();
    normalize_readme_text(description).filter(|value| value.chars().any(|ch| ch.is_alphanumeric()))
}

fn normalize_readme_text(line: &str) -> Option<String> {
    let linked = rewrite_markdown_links(line);
    let stripped = replace_common_html_entities(&strip_html_tags(&linked));
    let collapsed = stripped.split_whitespace().collect::<Vec<_>>().join(" ");
    let cleaned = strip_wrapping_emphasis(collapsed.trim().trim_matches('`').trim());
    if cleaned.is_empty() {
        None
    } else {
        Some(cleaned.to_string())
    }
}

fn strip_badge_run(line: &str) -> &str {
    line.find("[![")
        .map(|idx| line[..idx].trim_end())
        .unwrap_or(line)
}

fn is_markdown_reference_definition(line: &str) -> bool {
    let trimmed = line.trim();
    trimmed.starts_with('[') && trimmed.contains("]:")
}

fn replace_common_html_entities(line: &str) -> String {
    line.replace("&emsp;", " ")
        .replace("&ensp;", " ")
        .replace("&nbsp;", " ")
        .replace("&amp;", "&")
}

fn strip_wrapping_emphasis(mut line: &str) -> &str {
    loop {
        let trimmed = line.trim();
        if trimmed.len() >= 4
            && ((trimmed.starts_with("**") && trimmed.ends_with("**"))
                || (trimmed.starts_with("__") && trimmed.ends_with("__")))
        {
            line = &trimmed[2..trimmed.len() - 2];
            continue;
        }
        if trimmed.len() >= 2
            && ((trimmed.starts_with('*') && trimmed.ends_with('*'))
                || (trimmed.starts_with('_') && trimmed.ends_with('_')))
        {
            line = &trimmed[1..trimmed.len() - 1];
            continue;
        }
        return trimmed;
    }
}

fn strip_html_tags(line: &str) -> String {
    let mut out = String::new();
    let mut in_tag = false;

    for ch in line.chars() {
        match ch {
            '<' => in_tag = true,
            '>' => in_tag = false,
            _ if !in_tag => out.push(ch),
            _ => {}
        }
    }

    out
}

fn parse_readme_docs_metadata(lines: &[&str]) -> ReadmeDocsMetadata {
    let mut docs = ReadmeDocsMetadata::default();
    let mut in_code_block = false;

    for line in lines {
        let trimmed = line.trim();
        if trimmed.starts_with("```") {
            in_code_block = !in_code_block;
            continue;
        }
        if in_code_block {
            continue;
        }

        let signal = parse_readme_docs_signal(trimmed);
        if docs.root.is_none() {
            docs.root = signal.root;
        }
        if docs.getting_started.is_none() {
            docs.getting_started = signal.getting_started;
        }

        if docs.root.is_some() && docs.getting_started.is_some() {
            break;
        }
    }

    docs
}

fn parse_readme_docs_signal(line: &str) -> ReadmeDocsMetadata {
    let mut docs = ReadmeDocsMetadata::default();
    let lower_line = strip_html_tags(line).to_ascii_lowercase();

    for (label, url) in extract_markdown_links(line) {
        let lower_label = label.to_ascii_lowercase();
        let lower_url = url.to_ascii_lowercase();

        let is_getting_started = lower_label.contains("getting started")
            || lower_label.contains("quickstart")
            || lower_line.starts_with("getting started:")
            || lower_line.starts_with("quickstart:")
            || lower_url.contains("getting-started")
            || lower_url.contains("quickstart");

        if docs.getting_started.is_none() && is_getting_started {
            docs.getting_started = Some(url.clone());
        }

        let is_docs_root = !is_getting_started
            && (lower_label == "docs"
                || lower_label == "documentation"
                || lower_label.contains("reference")
                || lower_line.starts_with("docs:")
                || lower_line.starts_with("documentation:")
                || lower_line.starts_with("documentation ")
                || lower_url == "./docs/"
                || lower_url == "docs/"
                || lower_url.ends_with("/docs/")
                || lower_url.ends_with("/docs"));

        if docs.root.is_none() && is_docs_root {
            docs.root = Some(url);
        }
    }

    docs
}

fn extract_markdown_links(line: &str) -> Vec<(String, String)> {
    let mut links = Vec::new();
    let mut idx = 0;

    while idx < line.len() {
        let next_idx = match line[idx..].find(['[', '!']) {
            Some(rel) => idx + rel,
            None => break,
        };
        let is_image = line[next_idx..].starts_with("![");
        let link_start = if is_image { next_idx + 1 } else { next_idx };

        if let Some((end, label, url)) = parse_markdown_link_at(line, link_start) {
            if !is_image {
                if let Some(label) = normalize_readme_text(&label).filter(|_| !url.is_empty()) {
                    links.push((label, url));
                }
            }
            idx = end;
            continue;
        }

        idx = next_idx + 1;
    }

    links
}

fn rewrite_markdown_links(line: &str) -> String {
    let mut out = String::new();
    let mut idx = 0;

    while idx < line.len() {
        let remainder = &line[idx..];

        if remainder.starts_with("![") {
            if let Some((end, _, _)) = parse_markdown_link_at(line, idx + 1) {
                idx = end;
                continue;
            }
        }

        if remainder.starts_with('[') {
            if let Some((end, label, _)) = parse_markdown_link_at(line, idx) {
                out.push_str(&label);
                idx = end;
                continue;
            }
        }

        let ch = remainder
            .chars()
            .next()
            .expect("rewrite_markdown_links only advances within non-empty remainder");
        out.push(ch);
        idx += ch.len_utf8();
    }

    out
}

fn parse_markdown_link_at(line: &str, start: usize) -> Option<(usize, String, String)> {
    let bytes = line.as_bytes();
    if bytes.get(start).copied()? != b'[' {
        return None;
    }

    let close_label_rel = line[start + 1..].find(']')?;
    let close_label = start + 1 + close_label_rel;
    if bytes.get(close_label + 1).copied()? != b'(' {
        return None;
    }

    let url_start = close_label + 2;
    let mut idx = url_start;
    let mut depth = 1usize;
    while idx < bytes.len() {
        match bytes[idx] {
            b'(' => depth += 1,
            b')' => {
                depth -= 1;
                if depth == 0 {
                    let label = line[start + 1..close_label].to_string();
                    let url = line[url_start..idx].trim().to_string();
                    return Some((idx + 1, label, url));
                }
            }
            _ => {}
        }
        idx += 1;
    }

    None
}

fn is_probable_readme_nav_line(line: &str) -> bool {
    if extract_markdown_links(line).len() < 2 {
        return false;
    }

    let lowered = strip_html_tags(line).to_ascii_lowercase();
    lowered.contains("docs")
        || lowered.contains("getting started")
        || lowered.contains("quickstart")
        || lowered.contains("api")
        || lowered.contains("guide")
        || lowered.contains("reference")
}

fn is_probable_docs_signal_line(line: &str) -> bool {
    let lowered = strip_html_tags(line)
        .trim_start_matches('*')
        .trim_start_matches('_')
        .trim()
        .to_ascii_lowercase();
    lowered.starts_with("docs:")
        || lowered.starts_with("documentation:")
        || lowered.starts_with("getting started:")
        || lowered.starts_with("quickstart:")
}

fn starts_with_ordered_list_item(line: &str) -> bool {
    let digits = line.chars().take_while(|ch| ch.is_ascii_digit()).count();
    digits > 0
        && line
            .chars()
            .nth(digits)
            .is_some_and(|ch| matches!(ch, '.' | ')'))
}

fn parse_codeowners_metadata(contents: &str) -> CodeownersMetadata {
    let mut owners = Vec::new();
    let mut rules = Vec::new();

    for line in contents.lines() {
        let trimmed = line.split('#').next().unwrap_or("").trim();
        if trimmed.is_empty() {
            continue;
        }

        let mut tokens = trimmed.split_whitespace();
        let Some(pattern) = tokens.next() else {
            continue;
        };
        let mut rule_owners = Vec::new();
        let mut rule_teams = Vec::new();
        for token in tokens {
            let cleaned = trim_contact_token(token);
            if cleaned.starts_with('@') || looks_like_email(cleaned) {
                push_unique(&mut owners, cleaned.to_string());
                push_unique(&mut rule_owners, cleaned.to_string());
            }
            if is_team_handle(cleaned) {
                push_unique(&mut rule_teams, cleaned.to_string());
            }
        }

        if !rule_owners.is_empty() {
            rules.push(CodeownersRule {
                pattern: pattern.to_string(),
                owners: rule_owners,
                teams: rule_teams,
            });
        }
    }

    let all_teams = collect_codeowners_teams(&rules);
    let repo_wide_rules = rules
        .iter()
        .filter(|rule| is_repo_wide_codeowners_pattern(&rule.pattern))
        .cloned()
        .collect::<Vec<_>>();
    let repo_wide_teams = collect_codeowners_teams(&repo_wide_rules);
    let team = if repo_wide_teams.len() == 1 {
        Some(repo_wide_teams[0].clone())
    } else {
        match all_teams.as_slice() {
            [only] => Some(only.clone()),
            _ => None,
        }
    };

    CodeownersMetadata {
        owners,
        team: team.clone(),
        note: codeowners_import_note(&rules, team.as_deref()),
    }
}

fn collect_codeowners_teams(rules: &[CodeownersRule]) -> Vec<String> {
    let mut teams = Vec::new();
    for rule in rules {
        for team in &rule.teams {
            push_unique(&mut teams, team.clone());
        }
    }
    teams
}

fn is_repo_wide_codeowners_pattern(pattern: &str) -> bool {
    matches!(pattern.trim(), "*" | "/*" | "**" | "/**" | "**/*" | "/**/*")
}

fn codeowners_import_note(rules: &[CodeownersRule], selected_team: Option<&str>) -> Option<String> {
    if rules.len() <= 1 {
        return None;
    }

    let repo_wide_rules = rules
        .iter()
        .filter(|rule| is_repo_wide_codeowners_pattern(&rule.pattern))
        .cloned()
        .collect::<Vec<_>>();
    let repo_wide_teams = collect_codeowners_teams(&repo_wide_rules);
    let all_teams = collect_codeowners_teams(rules);

    if let Some(team) = selected_team {
        if repo_wide_teams.len() == 1 && all_teams.len() > 1 {
            return Some(format!(
                "Maintainer information was imported from broad CODEOWNERS patterns; `owners.team` prefers `{}` from the repo-wide rule, and `owners.maintainers` preserves narrower owner candidates.",
                team
            ));
        }

        if rules
            .iter()
            .any(|rule| !is_repo_wide_codeowners_pattern(&rule.pattern) && !rule.owners.is_empty())
        {
            return Some(format!(
                "Maintainer information was imported from CODEOWNERS; `owners.team` is `{}` because it is the clearest imported team signal, but `owners.maintainers` still preserves narrower owner candidates.",
                team
            ));
        }
    }

    if all_teams.len() > 1 {
        return Some(
            "Maintainer information was imported from broad CODEOWNERS patterns with multiple team owners, so `owners.team` was left unset and `owners.maintainers` preserves the competing owner candidates."
                .to_string(),
        );
    }

    None
}

fn parse_security_contact(contents: &str) -> Option<String> {
    find_mailto_or_email(contents).or_else(|| find_first_url(contents))
}

fn parse_security_import_metadata(contents: &str) -> SecurityImportMetadata {
    match parse_security_contact(contents) {
        Some(contact) if looks_like_email(&contact) => SecurityImportMetadata {
            contact: Some(contact),
            note: None,
        },
        Some(contact) => SecurityImportMetadata {
            contact: Some(contact),
            note: Some(
                "SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL."
                    .to_string(),
            ),
        },
        None => SecurityImportMetadata::default(),
    }
}

fn find_mailto_or_email(contents: &str) -> Option<String> {
    let rewritten = rewrite_markdown_links(contents);

    for destination in security_link_destinations(contents) {
        if let Some(email) = extract_email_candidate(&destination) {
            return Some(email);
        }
    }

    for token in rewritten.split_whitespace() {
        if let Some(email) = extract_email_candidate(token) {
            return Some(email);
        }
    }

    None
}

fn find_first_url(contents: &str) -> Option<String> {
    if let Some(url) = find_best_security_url(contents) {
        return Some(url);
    }

    let rewritten = rewrite_markdown_links(contents);

    for destination in security_link_destinations(contents) {
        if let Some(url) = extract_url_candidate(&destination) {
            return Some(url);
        }
    }

    for token in rewritten.split_whitespace() {
        if let Some(url) = extract_url_candidate(token) {
            return Some(url);
        }
    }

    None
}

fn find_best_security_url(contents: &str) -> Option<String> {
    let mut current_heading = String::new();
    let mut best: Option<(i32, String)> = None;

    for line in contents.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }

        if let Some(heading) = markdown_heading_text(trimmed) {
            current_heading = heading;
            continue;
        }

        for url in security_urls_in_line(trimmed) {
            let score = security_reporting_score(&current_heading, trimmed, &url);
            if score <= 0 {
                continue;
            }
            match &best {
                Some((best_score, _)) if *best_score >= score => {}
                _ => best = Some((score, url)),
            }
        }
    }

    best.map(|(_, url)| url)
}

fn markdown_heading_text(line: &str) -> Option<String> {
    let trimmed = line.trim_start();
    let hashes = trimmed.chars().take_while(|ch| *ch == '#').count();
    if hashes == 0 {
        return None;
    }

    let text = trimmed[hashes..].trim();
    (!text.is_empty()).then(|| text.to_ascii_lowercase())
}

fn security_urls_in_line(line: &str) -> Vec<String> {
    let rewritten = rewrite_markdown_links(line);
    let mut urls = Vec::new();

    for (label, destination) in extract_markdown_links(line) {
        if let Some(url) = extract_url_candidate(&label) {
            push_unique(&mut urls, url);
        }
        if let Some(url) = extract_url_candidate(&destination) {
            push_unique(&mut urls, url);
        }
    }

    for destination in markdown_reference_destinations(line) {
        if let Some(url) = extract_url_candidate(&destination) {
            push_unique(&mut urls, url);
        }
    }

    for destination in html_href_destinations(line) {
        if let Some(url) = extract_url_candidate(&destination) {
            push_unique(&mut urls, url);
        }
    }

    for token in rewritten.split_whitespace() {
        if let Some(url) = extract_url_candidate(token) {
            push_unique(&mut urls, url);
        }
    }

    urls
}

fn security_reporting_score(heading: &str, line: &str, url: &str) -> i32 {
    let heading_lower = heading.to_ascii_lowercase();
    let line_lower = line.to_ascii_lowercase();
    let url_lower = url.to_ascii_lowercase();
    let mut score = 0;

    if heading_lower.contains("report") || heading_lower.contains("disclosure") {
        score += 6;
    }
    if [
        "report",
        "contact",
        "disclosure",
        "response center",
        "vulnerability",
    ]
    .iter()
    .any(|needle| line_lower.contains(needle))
    {
        score += 4;
    }
    if ["report", "create-report", "contact", "submit"]
        .iter()
        .any(|needle| url_lower.contains(needle))
    {
        score += 3;
    }

    if [
        "definition",
        "faq",
        "bounty",
        "policy",
        "preferred languages",
    ]
    .iter()
    .any(|needle| heading_lower.contains(needle) || line_lower.contains(needle))
    {
        score -= 4;
    }
    if ["definition", "faq", "bounty", "policy"]
        .iter()
        .any(|needle| url_lower.contains(needle))
    {
        score -= 3;
    }
    if ["aka.ms/", "bit.ly/", "t.co/", "goo.gl/", "tinyurl.com/"]
        .iter()
        .any(|needle| url_lower.contains(needle))
    {
        score -= 2;
    }

    score
}

fn extract_email_candidate(token: &str) -> Option<String> {
    if let Some(address) = extract_mailto_address(token) {
        return Some(address);
    }

    let cleaned = trim_contact_token(token);
    looks_like_email(cleaned).then(|| cleaned.to_string())
}

fn extract_mailto_address(token: &str) -> Option<String> {
    let cleaned = trim_contact_token(token);
    if cleaned.len() < 7 || !cleaned[..7].eq_ignore_ascii_case("mailto:") {
        return None;
    }

    let value = cleaned[7..]
        .split(['?', '#'])
        .next()
        .map(trim_contact_token)
        .unwrap_or("");
    looks_like_email(value).then(|| value.to_string())
}

fn extract_url_candidate(token: &str) -> Option<String> {
    let cleaned = trim_contact_token(token);
    if cleaned.starts_with("https://") || cleaned.starts_with("http://") {
        Some(cleaned.to_string())
    } else {
        None
    }
}

fn security_link_destinations(contents: &str) -> Vec<String> {
    let mut destinations = Vec::new();

    for destination in markdown_link_destinations(contents) {
        push_unique(&mut destinations, destination);
    }
    for destination in markdown_reference_destinations(contents) {
        push_unique(&mut destinations, destination);
    }
    for destination in html_href_destinations(contents) {
        push_unique(&mut destinations, destination);
    }

    destinations
}

fn markdown_link_destinations(contents: &str) -> Vec<String> {
    extract_markdown_links(contents)
        .into_iter()
        .map(|(_, url)| url)
        .collect()
}

fn markdown_reference_destinations(contents: &str) -> Vec<String> {
    let mut destinations = Vec::new();

    for line in contents.lines() {
        let trimmed = line.trim();
        if !trimmed.starts_with('[') {
            continue;
        }
        let Some(split_idx) = trimmed.find("]:") else {
            continue;
        };
        if let Some(destination) = extract_link_destination(&trimmed[split_idx + 2..]) {
            destinations.push(destination);
        }
    }

    destinations
}

fn html_href_destinations(contents: &str) -> Vec<String> {
    let mut destinations = Vec::new();
    let lower = contents.to_ascii_lowercase();
    let bytes = contents.as_bytes();
    let mut idx = 0;

    while let Some(rel) = lower[idx..].find("href=") {
        let mut start = idx + rel + 5;
        while start < bytes.len() && bytes[start].is_ascii_whitespace() {
            start += 1;
        }
        if start >= bytes.len() {
            break;
        }

        let (raw_start, raw_end) = match bytes[start] {
            b'"' | b'\'' => {
                let quote = bytes[start] as char;
                let raw_start = start + 1;
                let Some(rel_end) = contents[raw_start..].find(quote) else {
                    break;
                };
                (raw_start, raw_start + rel_end)
            }
            _ => {
                let raw_start = start;
                let raw_end = contents[raw_start..]
                    .find(|ch: char| ch.is_whitespace() || ch == '>')
                    .map(|rel_end| raw_start + rel_end)
                    .unwrap_or(contents.len());
                (raw_start, raw_end)
            }
        };

        if let Some(destination) = extract_link_destination(&contents[raw_start..raw_end]) {
            destinations.push(destination);
        }

        idx = raw_end;
    }

    destinations
}

fn extract_link_destination(raw: &str) -> Option<String> {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return None;
    }

    let destination = if let Some(stripped) = trimmed.strip_prefix('<') {
        stripped.split('>').next().unwrap_or("")
    } else {
        trimmed.split_whitespace().next().unwrap_or("")
    };
    let cleaned = trim_contact_token(destination);
    (!cleaned.is_empty()).then(|| cleaned.to_string())
}

fn is_team_handle(token: &str) -> bool {
    token.starts_with('@') && token[1..].contains('/')
}

fn trim_contact_token(token: &str) -> &str {
    token.trim_matches(|ch: char| {
        matches!(
            ch,
            '<' | '>' | '(' | ')' | '[' | ']' | '{' | '}' | ',' | ';' | ':' | '.' | '"' | '\''
        )
    })
}

fn looks_like_email(token: &str) -> bool {
    let mut parts = token.split('@');
    let local = parts.next().unwrap_or("");
    let domain = parts.next().unwrap_or("");
    !local.is_empty()
        && !domain.is_empty()
        && parts.next().is_none()
        && token
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '.' | '_' | '%' | '+' | '-' | '@'))
        && domain.contains('.')
        && !token.starts_with("http://")
        && !token.starts_with("https://")
}

fn push_unique(values: &mut Vec<String>, value: String) {
    if !values.iter().any(|existing| existing == &value) {
        values.push(value);
    }
}

fn note_import(imported_sources: &mut Vec<String>, path: &str) {
    push_unique(imported_sources, path.to_string());
}

fn import_mode_name(mode: ImportMode) -> &'static str {
    match mode {
        ImportMode::Native => "native",
        ImportMode::Overlay => "overlay",
    }
}

fn import_provenance(imported_sources: &[String], inferred_fields: &[String]) -> Vec<String> {
    let mut provenance = Vec::new();
    if !imported_sources.is_empty() {
        provenance.push("imported".into());
    }
    if !inferred_fields.is_empty() {
        provenance.push("inferred".into());
    }
    if provenance.is_empty() {
        provenance.push("inferred".into());
    }
    provenance
}

fn import_notes(
    mode: ImportMode,
    imported_sources: &[String],
    inferred_fields: &[String],
    codeowners_note: Option<&str>,
    security_note: Option<&str>,
    command_notes: &[String],
) -> String {
    let mut notes = if imported_sources.is_empty() {
        "Bootstrapped from inferred defaults because no README.md, CODEOWNERS, or SECURITY.md content was imported."
            .to_string()
    } else {
        format!("Bootstrapped from {}.", human_join(imported_sources))
    };

    if !inferred_fields.is_empty() {
        notes.push_str(&format!(
            " Filled {} with inferred defaults.",
            human_join(inferred_fields)
        ));
    }

    if let Some(codeowners_note) = codeowners_note {
        notes.push(' ');
        notes.push_str(codeowners_note);
    }

    if let Some(security_note) = security_note {
        notes.push(' ');
        notes.push_str(security_note);
    }

    for command_note in command_notes {
        notes.push(' ');
        notes.push_str(command_note);
    }

    if matches!(mode, ImportMode::Overlay) {
        notes.push_str(
            " This is an overlay bootstrap, not a maintainer-controlled canonical record.",
        );
    }

    notes
}

fn build_imported_owners(
    maintainers: Vec<String>,
    team: Option<String>,
    security_contact: Option<String>,
) -> Option<Owners> {
    if maintainers.is_empty() && team.is_none() && security_contact.is_none() {
        None
    } else {
        Some(Owners {
            maintainers,
            team,
            security_contact,
        })
    }
}

fn build_imported_docs(root: Option<String>, getting_started: Option<String>) -> Option<Docs> {
    if root.is_none() && getting_started.is_none() {
        None
    } else {
        Some(Docs {
            root,
            getting_started,
            architecture: None,
            api: None,
        })
    }
}

fn native_import_github_compat(
    manifest: &Manifest,
    codeowners: Option<&ImportedFile>,
    security: Option<&ImportedFile>,
    contributing: Option<&ImportedFile>,
    pull_request_template: Option<&ImportedFile>,
) -> GitHubCompat {
    GitHubCompat {
        codeowners: Some(
            if codeowners.is_some_and(|file| {
                imported_surface_matches_generated(
                    &file.contents,
                    &render_codeowners_body_for_import(manifest),
                )
            }) {
                CompatMode::Generate
            } else {
                CompatMode::Skip
            },
        ),
        security: Some(
            if security.is_some_and(|file| {
                imported_surface_matches_generated(&file.contents, &render_security_body(manifest))
            }) {
                CompatMode::Generate
            } else {
                CompatMode::Skip
            },
        ),
        contributing: Some(
            if contributing.is_some_and(|file| {
                imported_surface_matches_generated(
                    &file.contents,
                    &render_contributing_body(manifest),
                )
            }) {
                CompatMode::Generate
            } else {
                CompatMode::Skip
            },
        ),
        pull_request_template: Some(
            if pull_request_template.is_some_and(|file| {
                imported_surface_matches_generated(
                    &file.contents,
                    &render_pull_request_template_body(manifest),
                )
            }) {
                CompatMode::Generate
            } else {
                CompatMode::Skip
            },
        ),
    }
}

fn render_codeowners_body_for_import(manifest: &Manifest) -> String {
    let owners = manifest
        .owners
        .as_ref()
        .map(|owners| owners.maintainers.join(" "))
        .unwrap_or_else(|| "@maintainers".into());
    format!("* {}\n", owners)
}

fn imported_surface_matches_generated(current: &str, expected: &str) -> bool {
    normalize_import_surface(current) == normalize_import_surface(expected)
}

fn normalize_import_surface(contents: &str) -> String {
    let without_banner = strip_generated_banner(contents).unwrap_or(contents);
    without_banner.replace("\r\n", "\n").trim().to_string()
}

fn strip_generated_banner(contents: &str) -> Option<&str> {
    let stripped = contents.strip_prefix('\u{feff}').unwrap_or(contents);
    let line_end = stripped.find('\n')?;
    let (first_line, rest) = stripped.split_at(line_end);
    if is_banner_line(first_line) {
        Some(rest.trim_start_matches('\n'))
    } else {
        None
    }
}

fn render_import_evidence(
    imported_sources: &[String],
    inferred_fields: &[String],
    security_contact: Option<&str>,
    codeowners_note: Option<&str>,
    security_note: Option<&str>,
    imported_docs: bool,
    command_evidence_bullets: &[String],
) -> String {
    let mut bullets = Vec::new();

    if imported_sources.is_empty() {
        bullets.push(
            "No README.md, CODEOWNERS, or SECURITY.md content was imported; this record needs manual completion."
                .to_string(),
        );
    }

    if let Some(readme_path) = imported_sources
        .iter()
        .find(|path| is_imported_readme_path(path))
    {
        bullets.push(readme_import_evidence_bullet(
            inferred_fields,
            imported_docs,
            readme_path,
        ));
    }
    if imported_sources
        .iter()
        .any(|path| path == ".github/CODEOWNERS" || path == "CODEOWNERS")
    {
        let mut bullet = "Imported maintainer candidates from CODEOWNERS.".to_string();
        if let Some(codeowners_note) = codeowners_note {
            bullet.push(' ');
            bullet.push_str(codeowners_note);
        }
        bullets.push(bullet);
    }
    if imported_sources
        .iter()
        .any(|path| path == ".github/SECURITY.md" || path == "SECURITY.md")
    {
        if security_contact.is_some_and(|contact| contact != "unknown") {
            let mut bullet =
                "Imported the security reporting channel from SECURITY.md.".to_string();
            if let Some(security_note) = security_note {
                bullet.push(' ');
                bullet.push_str(security_note);
            }
            bullets.push(bullet);
        } else {
            bullets.push(
                "Imported SECURITY.md, but no explicit contact channel was parsed, so security_contact = \"unknown\" is intentional."
                    .to_string(),
            );
        }
    }

    if !inferred_fields.is_empty() {
        bullets.push(format!(
            "Inferred fallback values for {} because the imported files did not provide enough structured metadata.",
            human_join(inferred_fields)
        ));
    }

    bullets.extend(command_evidence_bullets.iter().cloned());
    bullets.push("This is an overlay record, not a maintainer-controlled canonical record.".into());

    let mut out = String::from("# Evidence\n\n");
    for bullet in bullets {
        out.push_str("- ");
        out.push_str(&bullet);
        out.push('\n');
    }
    out
}

fn is_imported_readme_path(path: &str) -> bool {
    IMPORT_README_CANDIDATES.contains(&path)
}

fn readme_import_evidence_bullet(
    inferred_fields: &[String],
    imported_docs: bool,
    readme_path: &str,
) -> String {
    let imported_name = !inferred_fields.iter().any(|field| field == "repo.name");
    let imported_description = !inferred_fields
        .iter()
        .any(|field| field == "repo.description");

    match (imported_name, imported_description, imported_docs) {
        (true, true, true) => {
            format!(
                "Imported repository name, description, and docs entry points from {}.",
                readme_path
            )
        }
        (true, false, true) => format!(
            "Imported repository name and docs entry points from {}.",
            readme_path
        ),
        (false, true, true) => format!(
            "Imported repository description and docs entry points from {}.",
            readme_path
        ),
        (false, false, true) => format!(
            "Imported repository metadata and docs entry points from {}.",
            readme_path
        ),
        (true, true, false) => {
            format!(
                "Imported repository name and description from {}.",
                readme_path
            )
        }
        (true, false, false) => format!("Imported repository name from {}.", readme_path),
        (false, true, false) => {
            format!("Imported repository description from {}.", readme_path)
        }
        (false, false, false) => {
            format!("Imported repository metadata from {}.", readme_path)
        }
    }
}

fn human_join(values: &[String]) -> String {
    match values {
        [] => String::new(),
        [only] => format!("`{}`", only),
        [first, second] => format!("`{}` and `{}`", first, second),
        _ => {
            let last = values.last().expect("non-empty");
            let leading = values[..values.len() - 1]
                .iter()
                .map(|value| format!("`{}`", value))
                .collect::<Vec<_>>()
                .join(", ");
            format!("{}, and `{}`", leading, last)
        }
    }
}

pub fn query_manifest_value(manifest: &Manifest, key: &str) -> Result<Value> {
    let document = serde_json::to_value(manifest)?;
    let canonical_key = normalize_query_path(key);
    let value = query_value(&document, &canonical_key).or_else(|_| {
        if canonical_key != key {
            query_value(&document, key)
        } else {
            bail!("query path not found: {}", key)
        }
    })?;
    Ok(value.clone())
}

pub fn query_manifest(manifest: &Manifest, key: &str) -> Result<String> {
    Ok(serde_json::to_string_pretty(&query_manifest_value(
        manifest, key,
    )?)?)
}

fn render_readme_body(root: &Path, manifest: &Manifest) -> Result<String> {
    let mut out = String::new();

    let title = manifest
        .readme
        .as_ref()
        .and_then(|r| r.title.clone())
        .unwrap_or_else(|| manifest.repo.name.clone());
    out.push_str(&format!("# {}\n\n", title));

    if let Some(tagline) = manifest.readme.as_ref().and_then(|r| r.tagline.clone()) {
        out.push_str(&format!("> {}\n\n", tagline));
    }

    let sections = manifest
        .readme
        .as_ref()
        .map(|r| r.sections.clone())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| {
            vec![
                "overview".into(),
                "docs".into(),
                "contributing".into(),
                "security".into(),
            ]
        });

    for section in sections {
        match section.as_str() {
            "overview" => {
                out.push_str("## Overview\n\n");
                out.push_str(&format!("{}\n\n", manifest.repo.description));
            }
            "docs" => {
                out.push_str("## Documentation\n\n");
                if let Some(docs) = &manifest.docs {
                    if let Some(path) = &docs.getting_started {
                        out.push_str(&format!("- Getting started: `{}`\n", path));
                    }
                    if let Some(path) = &docs.architecture {
                        out.push_str(&format!("- Architecture: `{}`\n", path));
                    }
                    if let Some(path) = &docs.api {
                        out.push_str(&format!("- API: `{}`\n", path));
                    }
                }
                out.push('\n');
            }
            "contributing" => {
                out.push_str("## Contributing\n\n");
                out.push_str("See project contribution guidance and repository policies.\n\n");
            }
            "security" => {
                out.push_str("## Security\n\n");
                if let Some(contact) = manifest
                    .owners
                    .as_ref()
                    .and_then(|o| o.security_contact.clone())
                {
                    out.push_str(&format!("Report vulnerabilities to {}.\n\n", contact));
                } else {
                    out.push_str("Report vulnerabilities to the listed maintainers.\n\n");
                }
            }
            _ => {
                out.push_str(&format!("## {}\n\n", section_heading(&section)));
                if let Some(custom) = manifest
                    .readme
                    .as_ref()
                    .and_then(|readme| readme.custom_sections.get(&section))
                {
                    out.push_str(&render_custom_section(root, &section, custom)?);
                    out.push_str("\n\n");
                } else {
                    out.push_str("_section reserved_\n\n");
                }
            }
        }
    }

    Ok(out)
}

pub fn render_readme(root: &Path, manifest: &Manifest, source_bytes: &[u8]) -> Result<String> {
    let digest = source_digest(source_bytes);
    Ok(render_managed_markdown(
        generated_banner(CommentStyle::Html, manifest, &digest),
        &render_readme_body(root, manifest)?,
    ))
}

pub fn managed_outputs(
    root: &Path,
    manifest: &Manifest,
    source_bytes: &[u8],
) -> Result<Vec<(PathBuf, String)>> {
    ensure_native_managed_surface_record(manifest, "generate")?;
    let mut outputs = Vec::new();
    if let Some(output) =
        render_managed_output(root, ManagedSurface::Readme, manifest, source_bytes)?
    {
        outputs.push(output);
    }

    let digest = source_digest(source_bytes);
    if let Some(compat) = &manifest.compat {
        if let Some(github) = &compat.github {
            if matches!(github.codeowners, Some(CompatMode::Generate)) {
                let owners = manifest
                    .owners
                    .as_ref()
                    .map(|o| o.maintainers.join(" "))
                    .unwrap_or_else(|| "@maintainers".into());
                outputs.push(ManagedOutput {
                    path: root.join(".github/CODEOWNERS"),
                    contents: format!(
                        "{}\n* {}\n",
                        generated_banner(CommentStyle::Hash, manifest, &digest),
                        owners
                    ),
                });
            }
            if matches!(github.security, Some(CompatMode::Generate)) {
                if let Some(output) =
                    render_managed_output(root, ManagedSurface::Security, manifest, source_bytes)?
                {
                    outputs.push(output);
                }
            }
            if matches!(github.contributing, Some(CompatMode::Generate)) {
                if let Some(output) = render_managed_output(
                    root,
                    ManagedSurface::Contributing,
                    manifest,
                    source_bytes,
                )? {
                    outputs.push(output);
                }
            }
            if matches!(github.pull_request_template, Some(CompatMode::Generate)) {
                outputs.push(ManagedOutput {
                    path: root.join(".github/pull_request_template.md"),
                    contents: render_pull_request_template(manifest, &digest),
                });
            }
        }
    }

    Ok(outputs
        .into_iter()
        .map(|output| (output.path, output.contents))
        .collect())
}

fn ensure_native_managed_surface_record(manifest: &Manifest, action: &str) -> Result<()> {
    if manifest.record.mode == RecordMode::Overlay {
        bail!(
            "{} is only supported for native records; found record.mode = \"overlay\"",
            action
        );
    }

    Ok(())
}

pub fn github_outputs(manifest: &Manifest, source_bytes: &[u8]) -> Vec<(PathBuf, String)> {
    let mut outputs = Vec::new();
    let digest = source_digest(source_bytes);
    if let Some(compat) = &manifest.compat {
        if let Some(github) = &compat.github {
            if matches!(github.codeowners, Some(CompatMode::Generate)) {
                let owners = manifest
                    .owners
                    .as_ref()
                    .map(|o| o.maintainers.join(" "))
                    .unwrap_or_else(|| "@maintainers".into());
                outputs.push((
                    PathBuf::from(".github/CODEOWNERS"),
                    format!(
                        "{}\n* {}\n",
                        generated_banner(CommentStyle::Hash, manifest, &digest),
                        owners
                    ),
                ));
            }
            if matches!(github.security, Some(CompatMode::Generate)) {
                outputs.push((
                    PathBuf::from(".github/SECURITY.md"),
                    render_managed_markdown(
                        generated_banner(CommentStyle::Html, manifest, &digest),
                        &render_security_body(manifest),
                    ),
                ));
            }
            if matches!(github.contributing, Some(CompatMode::Generate)) {
                outputs.push((
                    PathBuf::from("CONTRIBUTING.md"),
                    render_contributing(manifest, &digest),
                ));
            }
            if matches!(github.pull_request_template, Some(CompatMode::Generate)) {
                outputs.push((
                    PathBuf::from(".github/pull_request_template.md"),
                    render_pull_request_template(manifest, &digest),
                ));
            }
        }
    }
    outputs
}

pub fn inspect_surface_states(root: &Path) -> Result<Vec<DoctorFinding>> {
    let mut findings = Vec::new();
    let loaded_manifest = load_doctor_manifest(root)?;

    for surface in [
        ManagedSurface::Readme,
        ManagedSurface::Security,
        ManagedSurface::Contributing,
    ] {
        let status = inspect_managed_surface(root, surface)?;
        if status.state == ManagedFileState::Missing {
            continue;
        }
        findings.push(build_managed_surface_doctor_finding(
            root,
            surface,
            status,
            loaded_manifest.as_ref(),
        )?);
    }

    for relative in [
        "CODEOWNERS",
        ".github/CODEOWNERS",
        "PULL_REQUEST_TEMPLATE.md",
        ".github/PULL_REQUEST_TEMPLATE.md",
        "pull_request_template.md",
        ".github/pull_request_template.md",
    ] {
        let path = root.join(relative);
        if !path.exists() {
            continue;
        }
        match fs::read_to_string(&path) {
            Ok(contents) => {
                if !is_dotrepo_generated(&contents) {
                    findings.push(build_unsupported_surface_doctor_finding(
                        relative,
                        ManagedFileState::Unsupported,
                        "conventional surface exists outside the managed-region contract for this file; keep it unmanaged or convert it to a fully generated dotrepo surface".into(),
                        loaded_manifest.as_ref(),
                    ));
                }
            }
            Err(err) => findings.push(build_unsupported_surface_doctor_finding(
                relative,
                ManagedFileState::Unsupported,
                format!("could not be read during doctor scan: {}", err),
                loaded_manifest.as_ref(),
            )),
        }
    }

    Ok(findings)
}

pub fn preview_surfaces(root: &Path, surfaces: &[DoctorSurface]) -> Result<SurfacePreviewReport> {
    let loaded_manifest = load_manifest_document(root)?;
    validate_manifest(root, &loaded_manifest.manifest)?;
    ensure_native_managed_surface_record(&loaded_manifest.manifest, "preview")?;

    let targets = if surfaces.is_empty() {
        all_doctor_surfaces().to_vec()
    } else {
        surfaces.to_vec()
    };

    let previews = targets
        .iter()
        .copied()
        .map(|surface| preview_surface(root, &loaded_manifest, surface))
        .collect::<Result<Vec<_>>>()?;

    Ok(SurfacePreviewReport {
        root: root.display().to_string(),
        previews,
    })
}

pub fn adopt_managed_surface(
    root: &Path,
    surface: DoctorSurface,
) -> Result<ManagedSurfaceAdoptionPlan> {
    let loaded_manifest = load_manifest_document(root)?;
    validate_manifest(root, &loaded_manifest.manifest)?;
    ensure_native_managed_surface_record(&loaded_manifest.manifest, "manage")?;

    let managed_surface = managed_surface_for_adoption(surface)?;
    ensure_surface_adoption_is_enabled(surface, &loaded_manifest.manifest)?;
    let status = inspect_managed_surface(root, managed_surface)?;
    let body = match managed_surface {
        ManagedSurface::Readme => render_readme_body(root, &loaded_manifest.manifest)?,
        ManagedSurface::Security => render_security_body(&loaded_manifest.manifest),
        ManagedSurface::Contributing => render_contributing_body(&loaded_manifest.manifest),
    };

    let contents = match status.state {
        ManagedFileState::Unmanaged => adopt_unmanaged_surface(
            managed_surface,
            status
                .current
                .as_deref()
                .expect("unmanaged file retains current contents"),
            &body,
        ),
        ManagedFileState::Missing => {
            bail!(
                "{} is missing; `manage --adopt` only converts existing files into managed-region files",
                display_path(root, &status.path)
            )
        }
        ManagedFileState::PartiallyManaged => {
            bail!(
                "{} already contains valid managed-region markers for this surface",
                display_path(root, &status.path)
            )
        }
        ManagedFileState::FullyGenerated => {
            bail!(
                "{} is already fully generated by dotrepo; `manage --adopt` is only for existing unmanaged Markdown surfaces",
                display_path(root, &status.path)
            )
        }
        ManagedFileState::MalformedManaged | ManagedFileState::Unsupported => bail!(
            "{}",
            status
                .message
                .unwrap_or_else(|| default_state_message(status.state))
        ),
    };

    Ok(ManagedSurfaceAdoptionPlan {
        surface,
        path: status.path,
        contents,
    })
}

fn all_doctor_surfaces() -> &'static [DoctorSurface] {
    &[
        DoctorSurface::Readme,
        DoctorSurface::Security,
        DoctorSurface::Contributing,
        DoctorSurface::Codeowners,
        DoctorSurface::PullRequestTemplate,
    ]
}

fn load_doctor_manifest(root: &Path) -> Result<Option<LoadedManifest>> {
    let path = manifest_path(root);
    if !path.exists() {
        return Ok(None);
    }
    load_manifest_file(&path).map(Some)
}

fn build_managed_surface_doctor_finding(
    root: &Path,
    surface: ManagedSurface,
    status: ManagedSurfaceStatus,
    loaded_manifest: Option<&LoadedManifest>,
) -> Result<DoctorFinding> {
    let doctor_surface = doctor_surface_for_managed(surface);
    let mut finding = base_doctor_finding(
        relative_or_absolute(root, &status.path),
        doctor_surface,
        status.state,
        status
            .message
            .unwrap_or_else(|| default_state_message(status.state)),
    );

    if let Some(loaded_manifest) = loaded_manifest {
        apply_doctor_surface_manifest_metadata(
            root,
            &mut finding,
            loaded_manifest,
            status.current.as_deref(),
        )?;
    }

    Ok(finding)
}

fn build_unsupported_surface_doctor_finding(
    relative: &str,
    state: ManagedFileState,
    message: String,
    loaded_manifest: Option<&LoadedManifest>,
) -> DoctorFinding {
    let mut finding = base_doctor_finding(
        PathBuf::from(relative),
        doctor_surface_for_unsupported_path(relative),
        state,
        message,
    );

    if let Some(loaded_manifest) = loaded_manifest {
        apply_all_or_nothing_surface_manifest_metadata(&mut finding, &loaded_manifest.manifest);
    }

    finding
}

fn ensure_surface_adoption_is_enabled(surface: DoctorSurface, manifest: &Manifest) -> Result<()> {
    match surface {
        DoctorSurface::Readme => Ok(()),
        DoctorSurface::Security | DoctorSurface::Contributing => {
            if declared_mode_for_surface(manifest, surface) == Some(CompatMode::Generate) {
                Ok(())
            } else {
                bail!(
                    "{} adoption requires compat.github.{} = \"generate\" first",
                    doctor_surface_cli_name(surface),
                    doctor_surface_cli_name(surface)
                )
            }
        }
        DoctorSurface::Codeowners | DoctorSurface::PullRequestTemplate => bail!(
            "{} does not support managed-region adoption",
            doctor_surface_cli_name(surface)
        ),
    }
}

fn preview_surface(
    root: &Path,
    loaded_manifest: &LoadedManifest,
    surface: DoctorSurface,
) -> Result<SurfacePreview> {
    let manifest = &loaded_manifest.manifest;
    match surface {
        DoctorSurface::Readme | DoctorSurface::Security | DoctorSurface::Contributing => {
            let managed_surface = managed_surface_for_doctor(surface);
            let status = inspect_managed_surface(root, managed_surface)?;
            let finding = build_managed_surface_doctor_finding(
                root,
                managed_surface,
                status.clone(),
                Some(loaded_manifest),
            )?;
            let proposed = expected_preview_output_for_managed_surface(
                root,
                surface,
                manifest,
                &loaded_manifest.raw,
                &status,
            )?;
            Ok(SurfacePreview {
                finding,
                current: status.current,
                proposed,
                full_replacement: matches!(
                    status.state,
                    ManagedFileState::Unmanaged
                        | ManagedFileState::MalformedManaged
                        | ManagedFileState::Unsupported
                ),
                preserves_unmanaged_content: status.state == ManagedFileState::PartiallyManaged,
            })
        }
        DoctorSurface::Codeowners | DoctorSurface::PullRequestTemplate => {
            let status = inspect_all_or_nothing_surface(root, surface)?;
            let mut finding = base_doctor_finding(
                relative_or_absolute(root, &status.path),
                surface,
                status.state,
                status
                    .message
                    .clone()
                    .unwrap_or_else(|| default_state_message(status.state)),
            );
            apply_all_or_nothing_surface_manifest_metadata(&mut finding, manifest);
            Ok(SurfacePreview {
                finding,
                current: status.current,
                proposed: expected_generated_surface_contents(
                    root,
                    surface,
                    manifest,
                    &loaded_manifest.raw,
                )?,
                full_replacement: status.state == ManagedFileState::Unsupported,
                preserves_unmanaged_content: false,
            })
        }
    }
}

fn base_doctor_finding(
    path: PathBuf,
    surface: DoctorSurface,
    state: ManagedFileState,
    message: String,
) -> DoctorFinding {
    DoctorFinding {
        path,
        surface,
        state,
        message,
        declared_mode: None,
        supports_managed_regions: surface_supports_managed_regions(surface),
        supports_full_generation: surface_supports_full_generation(surface),
        ownership_honesty: None,
        recommended_mode: None,
        would_drop_unmanaged_content: None,
        renderer_coverage: Some(surface_renderer_coverage(surface)),
        advice: Vec::new(),
    }
}

fn apply_doctor_surface_manifest_metadata(
    root: &Path,
    finding: &mut DoctorFinding,
    loaded_manifest: &LoadedManifest,
    current: Option<&str>,
) -> Result<()> {
    let manifest = &loaded_manifest.manifest;
    finding.declared_mode = declared_mode_for_surface(manifest, finding.surface);

    match finding.surface {
        DoctorSurface::Readme => {
            if finding.state == ManagedFileState::PartiallyManaged {
                finding.ownership_honesty = Some(DoctorOwnershipHonesty::Honest);
                finding.recommended_mode = Some(DoctorRecommendedMode::PartiallyManaged);
                finding.would_drop_unmanaged_content = Some(false);
            } else if finding.state == ManagedFileState::FullyGenerated {
                finding.ownership_honesty = Some(DoctorOwnershipHonesty::Honest);
                finding.recommended_mode = Some(DoctorRecommendedMode::Generate);
                finding.would_drop_unmanaged_content = Some(false);
            }
        }
        DoctorSurface::Security | DoctorSurface::Contributing => {
            if finding.declared_mode == Some(CompatMode::Generate) {
                match finding.state {
                    ManagedFileState::FullyGenerated => {
                        finding.ownership_honesty = Some(DoctorOwnershipHonesty::Honest);
                        finding.recommended_mode = Some(DoctorRecommendedMode::Generate);
                        finding.would_drop_unmanaged_content = Some(false);
                    }
                    ManagedFileState::PartiallyManaged => {
                        finding.ownership_honesty = Some(DoctorOwnershipHonesty::Honest);
                        finding.recommended_mode = Some(DoctorRecommendedMode::PartiallyManaged);
                        finding.would_drop_unmanaged_content = Some(false);
                    }
                    ManagedFileState::Unmanaged => {
                        let expected = expected_generated_surface_contents(
                            root,
                            finding.surface,
                            manifest,
                            &loaded_manifest.raw,
                        )?;
                        if current != Some(expected.as_str()) {
                            finding.ownership_honesty =
                                Some(DoctorOwnershipHonesty::LossyFullGeneration);
                            finding.recommended_mode =
                                Some(DoctorRecommendedMode::PartiallyManaged);
                            finding.would_drop_unmanaged_content = Some(true);
                            finding.message = format!(
                                "{} is declared as fully generated, but the current renderer can only reproduce a minimal dotrepo-owned block from this manifest. Regenerating would replace repository-specific prose. Prefer `partially_managed` or `skip` unless the generated stub is the full file you want.",
                                finding.path.display()
                            );
                            finding.advice = vec![
                                format!(
                                    "Run `dotrepo preview --surface {}` before changing compat mode.",
                                    doctor_surface_cli_name(finding.surface)
                                ),
                                "Use managed regions to preserve repository-specific prose outside the dotrepo-owned block.".into(),
                            ];
                        }
                    }
                    ManagedFileState::Missing
                    | ManagedFileState::MalformedManaged
                    | ManagedFileState::Unsupported => {}
                }
            }
        }
        DoctorSurface::Codeowners | DoctorSurface::PullRequestTemplate => {}
    }

    Ok(())
}

fn apply_all_or_nothing_surface_manifest_metadata(
    finding: &mut DoctorFinding,
    manifest: &Manifest,
) {
    finding.declared_mode = declared_mode_for_surface(manifest, finding.surface);

    if finding.declared_mode != Some(CompatMode::Generate) {
        return;
    }

    match finding.state {
        ManagedFileState::Missing | ManagedFileState::FullyGenerated => {
            finding.ownership_honesty = Some(DoctorOwnershipHonesty::Honest);
            finding.recommended_mode = Some(DoctorRecommendedMode::Generate);
            finding.would_drop_unmanaged_content = Some(false);
        }
        ManagedFileState::Unsupported => {
            finding.ownership_honesty = Some(DoctorOwnershipHonesty::LossyFullGeneration);
            finding.recommended_mode = Some(DoctorRecommendedMode::Skip);
            finding.would_drop_unmanaged_content = Some(true);
            finding.message = format!(
                "{} is declared as fully generated, but partial management is not supported for this surface. dotrepo can only fully replace it or leave it unmanaged. Prefer `skip` unless the generated template is the entire file you want.",
                finding.path.display()
            );
            finding.advice = vec![
                format!(
                    "Run `dotrepo preview --surface {}` before enabling full generation.",
                    doctor_surface_cli_name(finding.surface)
                ),
                "Keep this surface unmanaged if the checked-in file contains richer policy or workflow content than the current template can express.".into(),
            ];
        }
        ManagedFileState::PartiallyManaged
        | ManagedFileState::Unmanaged
        | ManagedFileState::MalformedManaged => {}
    }
}

fn doctor_surface_for_managed(surface: ManagedSurface) -> DoctorSurface {
    match surface {
        ManagedSurface::Readme => DoctorSurface::Readme,
        ManagedSurface::Security => DoctorSurface::Security,
        ManagedSurface::Contributing => DoctorSurface::Contributing,
    }
}

fn managed_surface_for_doctor(surface: DoctorSurface) -> ManagedSurface {
    match surface {
        DoctorSurface::Readme => ManagedSurface::Readme,
        DoctorSurface::Security => ManagedSurface::Security,
        DoctorSurface::Contributing => ManagedSurface::Contributing,
        DoctorSurface::Codeowners | DoctorSurface::PullRequestTemplate => {
            panic!("no managed-surface equivalent for {:?}", surface)
        }
    }
}

fn managed_surface_for_adoption(surface: DoctorSurface) -> Result<ManagedSurface> {
    match surface {
        DoctorSurface::Readme => Ok(ManagedSurface::Readme),
        DoctorSurface::Security => Ok(ManagedSurface::Security),
        DoctorSurface::Contributing => Ok(ManagedSurface::Contributing),
        DoctorSurface::Codeowners | DoctorSurface::PullRequestTemplate => bail!(
            "partial management is not supported for `{}`; `manage --adopt` is available only for readme, security, and contributing",
            doctor_surface_cli_name(surface)
        ),
    }
}

fn doctor_surface_for_unsupported_path(relative: &str) -> DoctorSurface {
    if relative.to_ascii_lowercase().contains("codeowners") {
        DoctorSurface::Codeowners
    } else {
        DoctorSurface::PullRequestTemplate
    }
}

fn doctor_surface_cli_name(surface: DoctorSurface) -> &'static str {
    match surface {
        DoctorSurface::Readme => "readme",
        DoctorSurface::Security => "security",
        DoctorSurface::Contributing => "contributing",
        DoctorSurface::Codeowners => "codeowners",
        DoctorSurface::PullRequestTemplate => "pull_request_template",
    }
}

fn surface_supports_managed_regions(surface: DoctorSurface) -> bool {
    matches!(
        surface,
        DoctorSurface::Readme | DoctorSurface::Security | DoctorSurface::Contributing
    )
}

fn surface_supports_full_generation(_surface: DoctorSurface) -> bool {
    true
}

fn surface_renderer_coverage(surface: DoctorSurface) -> DoctorRendererCoverage {
    match surface {
        DoctorSurface::Readme | DoctorSurface::Codeowners => DoctorRendererCoverage::Structured,
        DoctorSurface::Security
        | DoctorSurface::Contributing
        | DoctorSurface::PullRequestTemplate => DoctorRendererCoverage::StubOnly,
    }
}

fn declared_mode_for_surface(manifest: &Manifest, surface: DoctorSurface) -> Option<CompatMode> {
    let github = manifest
        .compat
        .as_ref()
        .and_then(|compat| compat.github.as_ref());
    match surface {
        DoctorSurface::Readme => None,
        DoctorSurface::Security => github.and_then(|github| github.security.clone()),
        DoctorSurface::Contributing => github.and_then(|github| github.contributing.clone()),
        DoctorSurface::Codeowners => github.and_then(|github| github.codeowners.clone()),
        DoctorSurface::PullRequestTemplate => {
            github.and_then(|github| github.pull_request_template.clone())
        }
    }
}

fn expected_generated_surface_contents(
    root: &Path,
    surface: DoctorSurface,
    manifest: &Manifest,
    source_bytes: &[u8],
) -> Result<String> {
    let digest = source_digest(source_bytes);
    match surface {
        DoctorSurface::Readme => render_readme(root, manifest, source_bytes),
        DoctorSurface::Security => Ok(render_managed_markdown(
            generated_banner(CommentStyle::Html, manifest, &digest),
            &render_security_body(manifest),
        )),
        DoctorSurface::Contributing => Ok(render_contributing(manifest, &digest)),
        DoctorSurface::Codeowners => {
            let owners = manifest
                .owners
                .as_ref()
                .map(|owners| owners.maintainers.join(" "))
                .unwrap_or_else(|| "@maintainers".into());
            Ok(format!(
                "{}\n* {}\n",
                generated_banner(CommentStyle::Hash, manifest, &digest),
                owners
            ))
        }
        DoctorSurface::PullRequestTemplate => Ok(render_pull_request_template(manifest, &digest)),
    }
}

fn expected_preview_output_for_managed_surface(
    root: &Path,
    surface: DoctorSurface,
    manifest: &Manifest,
    source_bytes: &[u8],
    status: &ManagedSurfaceStatus,
) -> Result<String> {
    let full_expected = expected_generated_surface_contents(root, surface, manifest, source_bytes)?;
    match status.state {
        ManagedFileState::PartiallyManaged => {
            let body = match surface {
                DoctorSurface::Readme => render_readme_body(root, manifest)?,
                DoctorSurface::Security => render_security_body(manifest),
                DoctorSurface::Contributing => render_contributing_body(manifest),
                DoctorSurface::Codeowners | DoctorSurface::PullRequestTemplate => {
                    bail!("surface does not support managed-region preview bodies")
                }
            };
            merge_managed_region(
                &status.path,
                managed_surface_for_doctor(surface),
                status
                    .current
                    .as_deref()
                    .expect("partially managed file retains current contents"),
                &body,
            )
        }
        _ => Ok(full_expected),
    }
}

fn inspect_all_or_nothing_surface(
    root: &Path,
    surface: DoctorSurface,
) -> Result<ManagedSurfaceStatus> {
    let candidate_paths = all_or_nothing_surface_paths(surface)
        .iter()
        .map(|relative| root.join(relative))
        .filter(|path| path.exists())
        .collect::<Vec<_>>();

    if candidate_paths.len() > 1 {
        let paths = candidate_paths
            .iter()
            .map(|path| display_path(root, path))
            .collect::<Vec<_>>()
            .join(", ");
        return Ok(ManagedSurfaceStatus {
            path: candidate_paths[0].clone(),
            state: ManagedFileState::Unsupported,
            current: None,
            message: Some(format!(
                "multiple candidate files exist for this surface ({paths}); keep one authoritative path before enabling sync"
            )),
        });
    }

    let Some(path) = candidate_paths.first() else {
        return Ok(ManagedSurfaceStatus {
            path: root.join(all_or_nothing_surface_paths(surface)[0]),
            state: ManagedFileState::Missing,
            current: None,
            message: Some("managed surface is missing".into()),
        });
    };

    let current = fs::read_to_string(path)
        .map_err(|err| anyhow!("failed to read {}: {}", path.display(), err))?;
    if is_dotrepo_generated(&current) {
        return Ok(ManagedSurfaceStatus {
            path: path.clone(),
            state: ManagedFileState::FullyGenerated,
            current: Some(current),
            message: Some("fully generated by dotrepo".into()),
        });
    }

    Ok(ManagedSurfaceStatus {
        path: path.clone(),
        state: ManagedFileState::Unsupported,
        current: Some(current),
        message: Some(
            "conventional surface exists outside the managed-region contract for this file; keep it unmanaged or convert it to a fully generated dotrepo surface".into(),
        ),
    })
}

fn all_or_nothing_surface_paths(surface: DoctorSurface) -> &'static [&'static str] {
    match surface {
        DoctorSurface::Codeowners => &[".github/CODEOWNERS", "CODEOWNERS"],
        DoctorSurface::PullRequestTemplate => &[
            ".github/pull_request_template.md",
            ".github/PULL_REQUEST_TEMPLATE.md",
            "pull_request_template.md",
            "PULL_REQUEST_TEMPLATE.md",
        ],
        DoctorSurface::Readme | DoctorSurface::Security | DoctorSurface::Contributing => {
            panic!(
                "surface does not use all-or-nothing path resolution: {:?}",
                surface
            )
        }
    }
}

pub fn validate_index_root(index_root: &Path) -> Result<Vec<IndexFinding>> {
    let repos_root = index_root.join("repos");
    if !repos_root.exists() {
        bail!(
            "index root does not contain a repos/ directory: {}",
            repos_root.display()
        );
    }

    let mut record_dirs = Vec::new();
    collect_record_dirs(&repos_root, &mut record_dirs)?;
    record_dirs.sort();
    let mut claim_dirs = Vec::new();
    collect_claim_dirs(&repos_root, &mut claim_dirs)?;
    claim_dirs.sort();

    let mut findings = Vec::new();
    for record_dir in record_dirs {
        let display_path = record_dir
            .strip_prefix(index_root)
            .unwrap_or(&record_dir)
            .join("record.toml");
        let synthesis_display_path = record_dir
            .strip_prefix(index_root)
            .unwrap_or(&record_dir)
            .join("synthesis.toml");

        let document = match load_manifest_document(&record_dir) {
            Ok(document) => document,
            Err(err) => {
                findings.push(index_error(display_path, err.to_string()));
                continue;
            }
        };

        for diagnostic in validate_manifest_diagnostics(&record_dir, &document.manifest) {
            findings.push(index_error(
                display_path.clone(),
                format!("[{}] {}", diagnostic.source, diagnostic.message),
            ));
        }

        let synthesis_file = record_dir.join("synthesis.toml");
        if synthesis_file.is_file() {
            match load_synthesis_document(&record_dir) {
                Ok(synthesis) => {
                    if let Err(err) = validate_synthesis(&document.manifest, &synthesis.synthesis) {
                        findings.push(index_error(synthesis_display_path.clone(), err.to_string()));
                    }
                }
                Err(err) => {
                    findings.push(index_error(synthesis_display_path.clone(), err.to_string()))
                }
            }
        }

        findings.extend(validate_index_entry(
            index_root,
            &record_dir,
            &document.manifest,
        ));
    }

    for claim_dir in claim_dirs {
        findings.extend(validate_claim_directory(index_root, &claim_dir));
    }

    Ok(findings)
}

pub fn source_digest(source_bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(source_bytes);
    format!("{:x}", hasher.finalize())
}

fn validate_readme_sections(manifest: &Manifest) -> Vec<ValidationDiagnostic> {
    let mut diagnostics = Vec::new();
    if let Some(readme) = &manifest.readme {
        for (name, section) in &readme.custom_sections {
            let has_content = section
                .content
                .as_deref()
                .map(|value| !value.trim().is_empty())
                .unwrap_or(false);
            let has_path = section
                .path
                .as_deref()
                .map(|value| !value.trim().is_empty())
                .unwrap_or(false);

            match (has_content, has_path) {
                (false, false) => {
                    diagnostics.push(validation_error(
                        "validate_readme_sections",
                        format!(
                            "custom README section `{}` must declare either `content` or `path`",
                            name
                        ),
                    ));
                }
                (true, true) => {
                    diagnostics.push(validation_error(
                        "validate_readme_sections",
                        format!(
                            "custom README section `{}` must not declare both `content` and `path`",
                            name
                        ),
                    ));
                }
                _ => {}
            }
        }
    }

    diagnostics
}

fn validate_index_entry(
    index_root: &Path,
    record_dir: &Path,
    manifest: &Manifest,
) -> Vec<IndexFinding> {
    let mut findings = Vec::new();
    let relative_record = record_dir
        .strip_prefix(index_root)
        .unwrap_or(record_dir)
        .join("record.toml");

    let relative = match record_dir.strip_prefix(index_root.join("repos")) {
        Ok(relative) => relative,
        Err(_) => {
            findings.push(IndexFinding {
                path: relative_record,
                severity: IndexFindingSeverity::Error,
                message:
                    "index records must live under index_root/repos/<host>/<owner>/<repo>/record.toml"
                        .into(),
            });
            return findings;
        }
    };

    let segments = relative
        .iter()
        .map(|segment| segment.to_string_lossy().to_string())
        .collect::<Vec<_>>();
    if segments.len() != 3 {
        findings.push(IndexFinding {
            path: relative_record.clone(),
            severity: IndexFindingSeverity::Error,
            message: "index path must be exactly repos/<host>/<owner>/<repo>/record.toml".into(),
        });
        return findings;
    }

    if manifest.record.mode != RecordMode::Overlay {
        findings.push(index_error(
            relative_record.clone(),
            "v0.1 index entries must use record.mode = \"overlay\"",
        ));
    }

    let evidence_path = record_dir.join("evidence.md");
    let evidence = match fs::read_to_string(&evidence_path) {
        Ok(contents) => {
            if contents.trim().is_empty() {
                findings.push(index_error(
                    relative_record.clone(),
                    "evidence.md must not be empty",
                ));
            }
            Some(contents)
        }
        Err(_) => {
            findings.push(index_error(
                relative_record.clone(),
                "index entries must include a sibling evidence.md file",
            ));
            None
        }
    };

    let expected = (
        segments[0].clone(),
        segments[1].clone(),
        segments[2].clone(),
    );

    match repository_identity(manifest.record.source.as_deref().unwrap_or_default()) {
        Some(identity) if identity == expected => {}
        Some(identity) => findings.push(index_error(
            relative_record.clone(),
            format!(
                "record.source resolves to {}/{}/{}, but index path is {}/{}/{}",
                identity.0, identity.1, identity.2, expected.0, expected.1, expected.2
            ),
        )),
        None => findings.push(index_error(
            relative_record.clone(),
            "record.source must be an absolute repository URL with host/owner/repo segments",
        )),
    }

    if let Some(homepage) = &manifest.repo.homepage {
        if let Some(identity) = repository_identity(homepage) {
            if identity != expected {
                findings.push(index_error(
                    relative_record.clone(),
                    format!(
                        "repo.homepage resolves to {}/{}/{}, but index path is {}/{}/{}",
                        identity.0, identity.1, identity.2, expected.0, expected.1, expected.2
                    ),
                ));
            }
        }
    }

    findings.extend(lint_index_entry(
        relative_record,
        manifest,
        evidence.as_deref().unwrap_or(""),
    ));

    findings
}

fn validate_claim_directory(index_root: &Path, claim_dir: &Path) -> Vec<IndexFinding> {
    let mut findings = Vec::new();
    let claim_path = claim_dir.join("claim.toml");
    let relative_claim = claim_path
        .strip_prefix(index_root)
        .unwrap_or(&claim_path)
        .to_path_buf();

    let directory_identity = match claim_directory_identity(index_root, claim_dir) {
        Ok(identity) => identity,
        Err(message) => {
            findings.push(index_error(relative_claim, message.to_string()));
            return findings;
        }
    };

    let loaded = match load_claim_directory(index_root, claim_dir) {
        Ok(loaded) => loaded,
        Err(err) => {
            findings.push(index_error(relative_claim, err.to_string()));
            return findings;
        }
    };

    findings.extend(validate_claim_identity_alignment(
        &relative_claim,
        &directory_identity,
        &loaded.claim,
    ));
    findings.extend(validate_claim_event_history(
        &relative_claim,
        &loaded.claim,
        &loaded.events,
    ));
    findings.extend(validate_claim_resolution_consistency(
        &relative_claim,
        &loaded.claim,
    ));

    findings
}

fn manifest_path(root: &Path) -> PathBuf {
    let canonical = root.join(".repo");
    if canonical.exists() {
        canonical
    } else {
        root.join("record.toml")
    }
}

fn normalize_query_path(key: &str) -> String {
    match key {
        "" | "." => ".".into(),
        "trust" => "record.trust".into(),
        _ if key.starts_with("trust.") => format!("record.{}", key),
        _ => key.into(),
    }
}

fn query_value<'a>(value: &'a Value, key: &str) -> Result<&'a Value> {
    if key.is_empty() || key == "." {
        return Ok(value);
    }

    let mut current = value;
    for segment in key.split('.') {
        current = match current {
            Value::Object(map) => map
                .get(segment)
                .ok_or_else(|| anyhow!("query path not found: {}", key))?,
            Value::Array(items) => {
                let index = segment
                    .parse::<usize>()
                    .map_err(|_| anyhow!("query path not found: {}", key))?;
                items
                    .get(index)
                    .ok_or_else(|| anyhow!("query path not found: {}", key))?
            }
            _ => bail!("query path not found: {}", key),
        };
    }

    Ok(current)
}

fn render_custom_section(
    root: &Path,
    section_name: &str,
    custom: &ReadmeCustomSection,
) -> Result<String> {
    if let Some(content) = &custom.content {
        return Ok(content.trim().to_string());
    }

    if let Some(path) = &custom.path {
        let target = resolve_repository_local_path(root, path).map_err(|err| {
            anyhow!(
                "custom README section `{}` uses an invalid path `{}`: {}",
                section_name,
                path,
                err
            )
        })?;
        return fs::read_to_string(&target)
            .map(|content| content.trim().to_string())
            .map_err(|err| {
                anyhow!(
                    "failed to read custom README section `{}` from {}: {}",
                    section_name,
                    target.display(),
                    err
                )
            });
    }

    bail!(
        "custom README section `{}` must declare either `content` or `path`",
        section_name
    )
}

fn section_heading(input: &str) -> String {
    input
        .split(['-', '_', ' '])
        .filter(|segment| !segment.is_empty())
        .map(capitalize)
        .collect::<Vec<_>>()
        .join(" ")
}

fn capitalize(input: &str) -> String {
    let mut chars = input.chars();
    match chars.next() {
        None => String::new(),
        Some(first) => first.to_uppercase().collect::<String>() + chars.as_str(),
    }
}

fn generated_banner(style: CommentStyle, manifest: &Manifest, digest: &str) -> String {
    let body = format!(
        "generated by {} {} | schema: {} | source: sha256:{}",
        GENERATOR_NAME, GENERATOR_VERSION, manifest.schema, digest
    );
    match style {
        CommentStyle::Html => format!("<!-- {} -->", body),
        CommentStyle::Hash => format!("# {}", body),
    }
}

fn render_contributing(manifest: &Manifest, digest: &str) -> String {
    render_managed_markdown(
        generated_banner(CommentStyle::Html, manifest, digest),
        &render_contributing_body(manifest),
    )
}

fn render_contributing_body(manifest: &Manifest) -> String {
    let mut out = String::new();
    out.push_str("# Contributing\n\n");
    out.push_str(&format!(
        "Thanks for contributing to {}.\n\n",
        manifest.repo.name
    ));
    out.push_str("## Before you open a change\n\n");
    out.push_str("- Review the repository documentation and policies.\n");
    if let Some(build) = &manifest.repo.build {
        out.push_str(&format!("- Run `{}` before submitting changes.\n", build));
    }
    if let Some(test) = &manifest.repo.test {
        out.push_str(&format!("- Run `{}` before submitting changes.\n", test));
    }
    out.push('\n');
    out.push_str("## Security\n\n");
    if let Some(contact) = manifest
        .owners
        .as_ref()
        .and_then(|owners| owners.security_contact.as_ref())
    {
        out.push_str(&format!(
            "Report suspected vulnerabilities to {} instead of opening a public issue.\n",
            contact
        ));
    } else {
        out.push_str(
            "Report suspected vulnerabilities privately to the maintainers instead of opening a public issue.\n",
        );
    }
    out
}

fn render_security_body(manifest: &Manifest) -> String {
    let contact = manifest
        .owners
        .as_ref()
        .and_then(|o| o.security_contact.clone())
        .unwrap_or_else(|| "the maintainers".into());
    format!(
        "# Security\n\nPlease report vulnerabilities to {}.\n",
        contact
    )
}

fn render_pull_request_template(manifest: &Manifest, digest: &str) -> String {
    let mut out = String::new();
    out.push_str(&generated_banner(CommentStyle::Html, manifest, digest));
    out.push('\n');
    out.push_str(&render_pull_request_template_body(manifest));
    out
}

fn render_pull_request_template_body(manifest: &Manifest) -> String {
    let mut out = String::new();
    out.push_str("## Summary\n\n");
    out.push_str("- Describe the user-visible change.\n\n");
    out.push_str("## Validation\n\n");
    if let Some(build) = &manifest.repo.build {
        out.push_str(&format!("- [ ] `{}`\n", build));
    }
    if let Some(test) = &manifest.repo.test {
        out.push_str(&format!("- [ ] `{}`\n", test));
    }
    if manifest.repo.build.is_none() && manifest.repo.test.is_none() {
        out.push_str("- [ ] Describe how you validated this change.\n");
    }
    out.push('\n');
    out.push_str("## Checklist\n\n");
    out.push_str("- [ ] Documentation updated where needed.\n");
    out.push_str("- [ ] Ownership, policy, and security impacts considered.\n");
    out
}

fn is_dotrepo_generated(contents: &str) -> bool {
    contents.lines().next().map(is_banner_line).unwrap_or(false)
}

fn render_managed_output(
    root: &Path,
    surface: ManagedSurface,
    manifest: &Manifest,
    source_bytes: &[u8],
) -> Result<Option<ManagedOutput>> {
    let digest = source_digest(source_bytes);
    let status = inspect_managed_surface(root, surface)?;
    let full_contents = match surface {
        ManagedSurface::Readme => render_readme(root, manifest, source_bytes)?,
        ManagedSurface::Security => render_managed_markdown(
            generated_banner(CommentStyle::Html, manifest, &digest),
            &render_security_body(manifest),
        ),
        ManagedSurface::Contributing => render_contributing(manifest, &digest),
    };

    let body = match surface {
        ManagedSurface::Readme => render_readme_body(root, manifest)?,
        ManagedSurface::Security => render_security_body(manifest),
        ManagedSurface::Contributing => render_contributing_body(manifest),
    };

    let output_path = status.path;
    let contents = match status.state {
        ManagedFileState::Missing | ManagedFileState::FullyGenerated => full_contents,
        ManagedFileState::PartiallyManaged => {
            let current = status
                .current
                .as_deref()
                .expect("partially managed file retains current contents");
            merge_managed_region(&output_path, surface, current, &body)?
        }
        ManagedFileState::Unmanaged => return Ok(None),
        ManagedFileState::MalformedManaged | ManagedFileState::Unsupported => {
            bail!(
                "{}",
                status
                    .message
                    .unwrap_or_else(|| default_state_message(status.state))
            );
        }
    };

    Ok(Some(ManagedOutput {
        path: output_path,
        contents,
    }))
}

fn render_managed_markdown(banner: String, body: &str) -> String {
    let mut out = String::new();
    out.push_str(&banner);
    out.push('\n');
    out.push_str(body);
    out
}

fn inspect_managed_surface(root: &Path, surface: ManagedSurface) -> Result<ManagedSurfaceStatus> {
    let candidate_paths = managed_surface_paths(surface)
        .iter()
        .map(|relative| root.join(relative))
        .filter(|path| path.exists())
        .collect::<Vec<_>>();

    if candidate_paths.len() > 1 {
        let paths = candidate_paths
            .iter()
            .map(|path| display_path(root, path))
            .collect::<Vec<_>>()
            .join(", ");
        return Ok(ManagedSurfaceStatus {
            path: candidate_paths[0].clone(),
            state: ManagedFileState::Unsupported,
            current: None,
            message: Some(format!(
                "multiple candidate files exist for this surface ({paths}); keep one authoritative path before enabling sync"
            )),
        });
    }

    let Some(path) = candidate_paths.first() else {
        return Ok(ManagedSurfaceStatus {
            path: root.join(managed_surface_paths(surface)[0]),
            state: ManagedFileState::Missing,
            current: None,
            message: Some("managed surface is missing".into()),
        });
    };

    let current = fs::read_to_string(path)
        .map_err(|err| anyhow!("failed to read {}: {}", path.display(), err))?;
    if contains_managed_region_markers(&current) {
        return classify_marker_managed_surface(root, path, surface, current);
    }
    if is_dotrepo_generated(&current) {
        return Ok(ManagedSurfaceStatus {
            path: path.clone(),
            state: ManagedFileState::FullyGenerated,
            current: Some(current),
            message: Some("fully generated by dotrepo".into()),
        });
    }
    Ok(ManagedSurfaceStatus {
        path: path.clone(),
        state: ManagedFileState::Unmanaged,
        current: Some(current),
        message: Some(
            "file exists outside dotrepo management; unmanaged prose is preserved and does not fail generate --check by itself"
                .into(),
        ),
    })
}

fn classify_marker_managed_surface(
    root: &Path,
    path: &Path,
    surface: ManagedSurface,
    current: String,
) -> Result<ManagedSurfaceStatus> {
    match parse_managed_regions(path, &current) {
        Ok(regions) => {
            let required = managed_region_id(surface);
            if regions.len() != 1 || regions[0].id != required {
                let found = regions
                    .iter()
                    .map(|region| region.id.as_str())
                    .collect::<Vec<_>>()
                    .join(", ");
                return Ok(ManagedSurfaceStatus {
                    path: path.to_path_buf(),
                    state: ManagedFileState::Unsupported,
                    current: Some(current),
                    message: Some(format!(
                        "{} uses unsupported managed-region ids for this surface; expected only `{}`, found [{}]",
                        display_path(root, path),
                        required,
                        found
                    )),
                });
            }
            Ok(ManagedSurfaceStatus {
                path: path.to_path_buf(),
                state: ManagedFileState::PartiallyManaged,
                current: Some(current),
                message: Some(
                    "managed regions are valid; unmanaged content outside the markers is preserved"
                        .into(),
                ),
            })
        }
        Err(err) => Ok(ManagedSurfaceStatus {
            path: path.to_path_buf(),
            state: ManagedFileState::MalformedManaged,
            current: Some(current),
            message: Some(err.to_string()),
        }),
    }
}

fn managed_surface_paths(surface: ManagedSurface) -> &'static [&'static str] {
    match surface {
        ManagedSurface::Readme => &["README.md"],
        ManagedSurface::Security => &[".github/SECURITY.md", "SECURITY.md"],
        ManagedSurface::Contributing => &["CONTRIBUTING.md", ".github/CONTRIBUTING.md"],
    }
}

fn managed_region_id(surface: ManagedSurface) -> &'static str {
    match surface {
        ManagedSurface::Readme => "readme.body",
        ManagedSurface::Security => "security.body",
        ManagedSurface::Contributing => "contributing.body",
    }
}

fn contains_managed_region_markers(contents: &str) -> bool {
    contents.lines().any(|line| {
        let trimmed = line.trim();
        parse_managed_marker(trimmed, "begin").is_some()
            || parse_managed_marker(trimmed, "end").is_some()
    })
}

fn merge_managed_region(
    path: &Path,
    surface: ManagedSurface,
    current: &str,
    body: &str,
) -> Result<String> {
    let regions = parse_managed_regions(path, current)?;
    let region = regions
        .iter()
        .find(|region| region.id == managed_region_id(surface))
        .ok_or_else(|| {
            anyhow!(
                "{} contains managed-region markers, but not the required `{}` region",
                path.display(),
                managed_region_id(surface)
            )
        })?;

    let mut out = String::with_capacity(current.len() + body.len());
    out.push_str(&current[..region.content_start]);
    out.push_str(&ensure_trailing_newline(body));
    out.push_str(&current[region.content_end..]);
    Ok(out)
}

fn adopt_unmanaged_surface(surface: ManagedSurface, current: &str, body: &str) -> String {
    let mut out = String::new();
    let trimmed_current = current.trim_end_matches('\n');
    if !trimmed_current.is_empty() {
        out.push_str(trimmed_current);
        out.push_str("\n\n");
    }
    out.push_str(&managed_region_block(surface, body));
    out
}

fn managed_region_block(surface: ManagedSurface, body: &str) -> String {
    format!(
        "<!-- dotrepo:begin id={} -->\n{}<!-- dotrepo:end id={} -->\n",
        managed_region_id(surface),
        ensure_trailing_newline(body),
        managed_region_id(surface)
    )
}

fn parse_managed_regions(path: &Path, contents: &str) -> Result<Vec<ManagedRegion>> {
    let mut regions = Vec::new();
    let mut seen = BTreeSet::new();
    let mut active: Option<(String, usize, usize)> = None;
    let mut offset = 0;

    for line in contents.split_inclusive('\n') {
        let line_start = offset;
        let line_end = offset + line.len();
        offset = line_end;

        let trimmed = line.trim();
        if let Some(id) = parse_managed_marker(trimmed, "begin") {
            if active.is_some() {
                bail!(
                    "{} contains nested or overlapping managed regions; close the current region before opening `{}`",
                    path.display(),
                    id
                );
            }
            if !seen.insert(id.to_string()) {
                bail!(
                    "{} declares the managed region `{}` more than once",
                    path.display(),
                    id
                );
            }
            active = Some((id.to_string(), line_start, line_end));
            continue;
        }

        if let Some(id) = parse_managed_marker(trimmed, "end") {
            let (active_id, _begin_start, begin_end) = active.take().ok_or_else(|| {
                anyhow!(
                    "{} closes managed region `{}` without a matching begin marker",
                    path.display(),
                    id
                )
            })?;
            if active_id != id {
                bail!(
                    "{} closes managed region `{}`, but the open region is `{}`",
                    path.display(),
                    id,
                    active_id
                );
            }
            regions.push(ManagedRegion {
                id: active_id,
                content_start: begin_end,
                content_end: line_start,
            });
        }
    }

    if let Some((id, _, _)) = active {
        bail!(
            "{} opens managed region `{}` without a matching end marker",
            path.display(),
            id
        );
    }

    Ok(regions)
}

fn parse_managed_marker(line: &str, kind: &str) -> Option<String> {
    let body = line.strip_prefix("<!--")?.strip_suffix("-->")?.trim();
    let body = body.strip_prefix("dotrepo:")?;
    let body = body.trim_start();
    let body = body.strip_prefix(kind)?.trim_start();
    let body = body.strip_prefix("id")?.trim_start();
    let body = body.strip_prefix('=')?.trim();

    if body.is_empty() || body.split_whitespace().count() != 1 {
        None
    } else {
        Some(body.to_string())
    }
}

fn ensure_trailing_newline(body: &str) -> String {
    if body.ends_with('\n') {
        body.to_string()
    } else {
        format!("{body}\n")
    }
}

fn relative_or_absolute(root: &Path, path: &Path) -> PathBuf {
    path.strip_prefix(root)
        .map(PathBuf::from)
        .unwrap_or_else(|_| path.to_path_buf())
}

fn default_state_message(state: ManagedFileState) -> String {
    match state {
        ManagedFileState::Missing => "managed surface is missing".into(),
        ManagedFileState::FullyGenerated => "fully generated by dotrepo".into(),
        ManagedFileState::PartiallyManaged => {
            "managed regions are valid; unmanaged content outside the markers is preserved".into()
        }
        ManagedFileState::Unmanaged => {
            "file exists outside dotrepo management; unmanaged prose is preserved and does not fail generate --check by itself".into()
        }
        ManagedFileState::MalformedManaged => {
            "managed-region markers are malformed and must be fixed before sync can proceed".into()
        }
        ManagedFileState::Unsupported => {
            "file is in an unsupported managed-sync state for this surface".into()
        }
    }
}

fn generate_check_output(
    root: &Path,
    path: PathBuf,
    expected: String,
) -> Result<GenerateCheckOutput> {
    let current = fs::read_to_string(&path).unwrap_or_default();
    let relative = display_path(root, &path);
    let is_stale = current != expected;
    Ok(GenerateCheckOutput {
        path: relative,
        state: if current.is_empty() && !path.exists() {
            ManagedFileState::Missing
        } else {
            ManagedFileState::FullyGenerated
        },
        stale: is_stale,
        expected,
        current: if is_stale { Some(current) } else { None },
        message: None,
    })
}

fn generate_check_managed_surface(
    root: &Path,
    surface: ManagedSurface,
    manifest: &Manifest,
    source_bytes: &[u8],
) -> Result<GenerateCheckOutput> {
    let digest = source_digest(source_bytes);
    let status = inspect_managed_surface(root, surface)?;
    let body = match surface {
        ManagedSurface::Readme => render_readme_body(root, manifest)?,
        ManagedSurface::Security => render_security_body(manifest),
        ManagedSurface::Contributing => render_contributing_body(manifest),
    };
    let full_expected = match surface {
        ManagedSurface::Readme => render_readme(root, manifest, source_bytes)?,
        ManagedSurface::Security => render_managed_markdown(
            generated_banner(CommentStyle::Html, manifest, &digest),
            &body,
        ),
        ManagedSurface::Contributing => render_managed_markdown(
            generated_banner(CommentStyle::Html, manifest, &digest),
            &body,
        ),
    };
    let expected = match status.state {
        ManagedFileState::PartiallyManaged => merge_managed_region(
            &status.path,
            surface,
            status
                .current
                .as_deref()
                .expect("partially managed file retains current contents"),
            &body,
        )?,
        ManagedFileState::Unmanaged => status
            .current
            .clone()
            .expect("unmanaged file retains current contents"),
        _ => full_expected,
    };
    let current = status.current.clone();
    let stale = match status.state {
        ManagedFileState::Missing => true,
        ManagedFileState::FullyGenerated | ManagedFileState::PartiallyManaged => {
            current.as_deref().unwrap_or_default() != expected
        }
        ManagedFileState::Unmanaged => false,
        ManagedFileState::MalformedManaged | ManagedFileState::Unsupported => true,
    };

    Ok(GenerateCheckOutput {
        path: display_path(root, &status.path),
        state: status.state,
        stale,
        expected,
        current: if stale { current } else { None },
        message: status.message,
    })
}

fn is_banner_line(line: &str) -> bool {
    let trimmed = line.trim_start();
    trimmed.starts_with("<!-- generated by dotrepo")
        || trimmed.starts_with("# generated by dotrepo")
}

fn collect_record_dirs(root: &Path, out: &mut Vec<PathBuf>) -> Result<()> {
    for entry in
        fs::read_dir(root).map_err(|err| anyhow!("failed to read {}: {}", root.display(), err))?
    {
        let entry = entry?;
        let path = entry.path();
        let file_type = entry.file_type()?;
        if file_type.is_dir() {
            collect_record_dirs(&path, out)?;
        } else if file_type.is_file()
            && path.file_name().and_then(|name| name.to_str()) == Some("record.toml")
        {
            if let Some(parent) = path.parent() {
                out.push(parent.to_path_buf());
            }
        }
    }
    Ok(())
}

fn collect_files(root: &Path, out: &mut Vec<PathBuf>) -> Result<()> {
    for entry in
        fs::read_dir(root).map_err(|err| anyhow!("failed to read {}: {}", root.display(), err))?
    {
        let entry = entry?;
        let path = entry.path();
        let file_type = entry.file_type()?;
        if file_type.is_dir() {
            collect_files(&path, out)?;
        } else if file_type.is_file() {
            out.push(path);
        }
    }
    Ok(())
}

fn collect_claim_dirs(root: &Path, out: &mut Vec<PathBuf>) -> Result<()> {
    for entry in
        fs::read_dir(root).map_err(|err| anyhow!("failed to read {}: {}", root.display(), err))?
    {
        let entry = entry?;
        let path = entry.path();
        let file_type = entry.file_type()?;
        if file_type.is_dir() {
            if path.file_name().and_then(|name| name.to_str()) == Some("claims") {
                for claim_entry in fs::read_dir(&path)
                    .map_err(|err| anyhow!("failed to read {}: {}", path.display(), err))?
                {
                    let claim_entry = claim_entry?;
                    if claim_entry.file_type()?.is_dir() {
                        out.push(claim_entry.path());
                    }
                }
            } else {
                collect_claim_dirs(&path, out)?;
            }
        }
    }
    Ok(())
}

fn claim_directory_identity(index_root: &Path, claim_dir: &Path) -> Result<ClaimDirectoryIdentity> {
    let relative = claim_dir.strip_prefix(index_root).map_err(|_| {
        anyhow!(
            "claim directories must live under index_root/repos/<host>/<owner>/<repo>/claims/<id>/"
        )
    })?;
    let segments = relative
        .iter()
        .map(|segment| segment.to_string_lossy().to_string())
        .collect::<Vec<_>>();
    if segments.len() != 6
        || segments[0] != "repos"
        || segments[4] != "claims"
        || segments[5].trim().is_empty()
    {
        bail!("claim directories must live under repos/<host>/<owner>/<repo>/claims/<claim-id>/");
    }

    Ok(ClaimDirectoryIdentity {
        host: segments[1].clone(),
        owner: segments[2].clone(),
        repo: segments[3].clone(),
        claim_id: segments[5].clone(),
    })
}

fn validate_claim_identity_alignment(
    relative_claim: &Path,
    expected: &ClaimDirectoryIdentity,
    claim: &ClaimRecord,
) -> Vec<IndexFinding> {
    let mut findings = Vec::new();

    if claim.identity.host != expected.host
        || claim.identity.owner != expected.owner
        || claim.identity.repo != expected.repo
    {
        findings.push(index_error(
            relative_claim.to_path_buf(),
            format!(
                "claim.identity resolves to {}/{}/{}, but claim path is repos/{}/{}/{}/claims/{}/claim.toml",
                claim.identity.host,
                claim.identity.owner,
                claim.identity.repo,
                expected.host,
                expected.owner,
                expected.repo,
                expected.claim_id
            ),
        ));
    }

    if claim.claim.id.trim().is_empty() {
        findings.push(index_error(
            relative_claim.to_path_buf(),
            "claim.id must not be empty",
        ));
    } else {
        let expected_prefix = format!("{}/{}/{}/", expected.host, expected.owner, expected.repo);
        if !claim.claim.id.starts_with(&expected_prefix) {
            findings.push(index_error(
                relative_claim.to_path_buf(),
                format!(
                    "claim.id must start with {expected_prefix} to match the containing repository identity"
                ),
            ));
        }
    }

    for index_path in &claim.target.index_paths {
        match parse_index_record_identity(index_path) {
            Some(identity)
                if identity.host == expected.host
                    && identity.owner == expected.owner
                    && identity.repo == expected.repo => {}
            Some(identity) => findings.push(index_error(
                relative_claim.to_path_buf(),
                format!(
                    "target.index_paths includes {}, which resolves to {}/{}/{}, but claim path is repos/{}/{}/{}",
                    index_path, identity.host, identity.owner, identity.repo, expected.host, expected.owner, expected.repo
                ),
            )),
            None => findings.push(index_error(
                relative_claim.to_path_buf(),
                format!(
                    "target.index_paths includes `{}`; expected repos/<host>/<owner>/<repo>/record.toml",
                    index_path
                ),
            )),
        }
    }

    for record_source in &claim.target.record_sources {
        match repository_identity(record_source) {
            Some((host, owner, repo))
                if host == expected.host && owner == expected.owner && repo == expected.repo => {}
            Some((host, owner, repo)) => findings.push(index_error(
                relative_claim.to_path_buf(),
                format!(
                    "target.record_sources includes {}, which resolves to {}/{}/{}, but claim path is repos/{}/{}/{}",
                    record_source, host, owner, repo, expected.host, expected.owner, expected.repo
                ),
            )),
            None => findings.push(index_error(
                relative_claim.to_path_buf(),
                format!(
                    "target.record_sources includes `{}`; expected an absolute repository URL",
                    record_source
                ),
            )),
        }
    }

    if let Some(canonical_repo_url) = &claim.target.canonical_repo_url {
        match repository_identity(canonical_repo_url) {
            Some((host, owner, repo))
                if host == expected.host && owner == expected.owner && repo == expected.repo => {}
            Some((host, owner, repo)) => findings.push(index_error(
                relative_claim.to_path_buf(),
                format!(
                    "target.canonical_repo_url resolves to {}/{}/{}, but claim path is repos/{}/{}/{}",
                    host, owner, repo, expected.host, expected.owner, expected.repo
                ),
            )),
            None => findings.push(index_error(
                relative_claim.to_path_buf(),
                format!(
                    "target.canonical_repo_url `{}` must be an absolute repository URL",
                    canonical_repo_url
                ),
            )),
        }
    }

    findings
}

fn validate_claim_event_history(
    relative_claim: &Path,
    claim: &ClaimRecord,
    events: &[LoadedClaimEvent],
) -> Vec<IndexFinding> {
    let mut findings = Vec::new();

    if events.is_empty() {
        if claim.claim.state != ClaimState::Draft {
            findings.push(index_error(
                relative_claim.to_path_buf(),
                "non-draft claims must include at least one event in events/",
            ));
        }
        return findings;
    }

    let mut expected_sequence = 1_u32;
    for loaded in events {
        let event = &loaded.event;
        if event.event.sequence != expected_sequence {
            findings.push(index_error(
                relative_claim.to_path_buf(),
                format!(
                    "claim events must use contiguous sequence numbers starting at 1; expected {}, found {} in {}",
                    expected_sequence, event.event.sequence, loaded.path
                ),
            ));
            expected_sequence = event.event.sequence.saturating_add(1);
        } else {
            expected_sequence += 1;
        }

        let requires_transition = !matches!(event.event.kind, ClaimEventKind::Corrected);
        if requires_transition && event.transition.is_none() {
            findings.push(index_error(
                relative_claim.to_path_buf(),
                format!(
                    "{} must include a transition block for event kind {:?}",
                    loaded.path, event.event.kind
                ),
            ));
        }
        if let Some(transition) = &event.transition {
            if transition.from == transition.to {
                findings.push(index_error(
                    relative_claim.to_path_buf(),
                    format!(
                        "{} has a transition where from and to are both {:?}",
                        loaded.path, transition.to
                    ),
                ));
            }
            if !transition_matches_event_kind(transition.to.clone(), &event.event.kind) {
                findings.push(index_error(
                    relative_claim.to_path_buf(),
                    format!(
                        "{} transitions to {:?}, which does not match event kind {:?}",
                        loaded.path, transition.to, event.event.kind
                    ),
                ));
            }
        }
    }

    if let Some(last) = events.last() {
        let terminal_state = last
            .event
            .transition
            .as_ref()
            .map(|transition| transition.to.clone())
            .unwrap_or_else(|| claim.claim.state.clone());
        if terminal_state != claim.claim.state {
            findings.push(index_error(
                relative_claim.to_path_buf(),
                format!(
                    "claim.state is {:?}, but the last event in {} resolves to {:?}",
                    claim.claim.state, last.path, terminal_state
                ),
            ));
        }
    }

    findings
}

fn validate_claim_resolution_consistency(
    relative_claim: &Path,
    claim: &ClaimRecord,
) -> Vec<IndexFinding> {
    let mut findings = Vec::new();
    let resolution = claim.resolution.as_ref();
    let has_canonical_link = resolution
        .map(|resolution| {
            resolution.canonical_record_path.is_some() || resolution.canonical_mirror_path.is_some()
        })
        .unwrap_or(false);

    match claim.claim.state {
        ClaimState::Rejected | ClaimState::Withdrawn => {
            if has_canonical_link {
                findings.push(index_error(
                    relative_claim.to_path_buf(),
                    "rejected or withdrawn claims must not record canonical handoff links",
                ));
            }
        }
        ClaimState::Disputed => {
            if has_canonical_link {
                findings.push(index_error(
                    relative_claim.to_path_buf(),
                    "disputed claims must not record completed canonical handoff links",
                ));
            }
        }
        ClaimState::Accepted => {
            if let Some(resolution) = resolution {
                if resolution.result_event.is_none() {
                    findings.push(index_error(
                        relative_claim.to_path_buf(),
                        "accepted claims with a resolution block must include resolution.result_event",
                    ));
                }
                if let Some(canonical_mirror_path) = &resolution.canonical_mirror_path {
                    if parse_index_record_identity(canonical_mirror_path).is_none() {
                        findings.push(index_error(
                            relative_claim.to_path_buf(),
                            format!(
                                "resolution.canonical_mirror_path `{}` must match repos/<host>/<owner>/<repo>/record.toml",
                                canonical_mirror_path
                            ),
                        ));
                    }
                }
            }
        }
        _ => {}
    }

    findings
}

fn transition_matches_event_kind(target: ClaimState, kind: &ClaimEventKind) -> bool {
    if matches!(kind, ClaimEventKind::Corrected) {
        return true;
    }
    matches!(
        (target, kind),
        (ClaimState::Submitted, ClaimEventKind::Submitted)
            | (ClaimState::InReview, ClaimEventKind::ReviewStarted)
            | (ClaimState::Accepted, ClaimEventKind::Accepted)
            | (ClaimState::Rejected, ClaimEventKind::Rejected)
            | (ClaimState::Withdrawn, ClaimEventKind::Withdrawn)
            | (ClaimState::Disputed, ClaimEventKind::Disputed)
    )
}

fn parse_index_record_identity(path: &str) -> Option<RepositoryIdentity> {
    let segments = Path::new(path)
        .iter()
        .map(|segment| segment.to_string_lossy().to_string())
        .collect::<Vec<_>>();
    if segments.len() != 5
        || segments[0] != "repos"
        || segments[4] != "record.toml"
        || segments[1].trim().is_empty()
        || segments[2].trim().is_empty()
        || segments[3].trim().is_empty()
    {
        return None;
    }

    Some(RepositoryIdentity {
        host: segments[1].clone(),
        owner: segments[2].clone(),
        repo: segments[3].clone(),
    })
}

fn repository_identity(url: &str) -> Option<(String, String, String)> {
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

fn lint_index_entry(path: PathBuf, manifest: &Manifest, evidence: &str) -> Vec<IndexFinding> {
    let mut findings = Vec::new();
    let evidence_lower = evidence.to_lowercase();

    if let Some(confidence) = manifest
        .record
        .trust
        .as_ref()
        .and_then(|trust| trust.confidence.as_deref())
    {
        if !matches!(confidence, "low" | "medium" | "high") {
            findings.push(index_warning(
                path.clone(),
                format!(
                    "record.trust.confidence uses non-reference vocabulary `{}`; preserve it, but prefer low/medium/high in the public index",
                    confidence
                ),
            ));
        }
    }

    if let Some(trust) = &manifest.record.trust {
        for provenance in &trust.provenance {
            if !matches!(
                provenance.as_str(),
                "declared" | "imported" | "inferred" | "verified"
            ) {
                findings.push(index_warning(
                    path.clone(),
                    format!(
                        "record.trust.provenance includes non-reference value `{}`; preserve it, but prefer declared/imported/inferred/verified in the public index",
                        provenance
                    ),
                ));
            }
        }
    }

    for expected in expected_provenance_for_status(&manifest.record.status) {
        let has_expected = manifest
            .record
            .trust
            .as_ref()
            .map(|trust| trust.provenance.iter().any(|value| value == expected))
            .unwrap_or(false);
        if !has_expected {
            findings.push(index_warning(
                path.clone(),
                format!(
                    "record.status = {:?} should usually be accompanied by `{}` in record.trust.provenance",
                    manifest.record.status, expected
                ),
            ));
        }
    }

    for keyword in manifest
        .record
        .trust
        .as_ref()
        .map(|trust| trust.provenance.clone())
        .unwrap_or_default()
    {
        if matches!(
            keyword.as_str(),
            "declared" | "imported" | "inferred" | "verified"
        ) && !evidence_mentions(&evidence_lower, &keyword)
        {
            findings.push(index_warning(
                path.clone(),
                format!(
                    "evidence.md should mention `{}` so the trust story is visible to reviewers",
                    keyword
                ),
            ));
        }
    }

    if manifest.repo.build.is_some() && !evidence_mentions(&evidence_lower, "build") {
        findings.push(index_warning(
            path.clone(),
            "evidence.md should explain where the build command came from",
        ));
    }

    if manifest.repo.test.is_some() && !evidence_mentions(&evidence_lower, "test") {
        findings.push(index_warning(
            path.clone(),
            "evidence.md should explain where the test command came from",
        ));
    }

    if manifest
        .owners
        .as_ref()
        .and_then(|owners| owners.security_contact.as_deref())
        == Some("unknown")
        && !evidence_mentions(&evidence_lower, "unknown")
    {
        findings.push(index_warning(
            path,
            "evidence.md should explain why security_contact = \"unknown\" is intentional",
        ));
    }

    findings
}

fn expected_provenance_for_status(
    status: &dotrepo_schema::RecordStatus,
) -> &'static [&'static str] {
    match status {
        dotrepo_schema::RecordStatus::Imported => &["imported"],
        dotrepo_schema::RecordStatus::Inferred => &["inferred"],
        dotrepo_schema::RecordStatus::Verified => &["verified"],
        dotrepo_schema::RecordStatus::Canonical => &["declared"],
        _ => &[],
    }
}

fn validation_error(source: &'static str, message: impl Into<String>) -> ValidationDiagnostic {
    ValidationDiagnostic {
        severity: ValidationDiagnosticSeverity::Error,
        source,
        message: message.into(),
    }
}

fn evidence_mentions(evidence_lower: &str, keyword: &str) -> bool {
    evidence_lower.contains(&keyword.to_lowercase())
}

fn index_error(path: PathBuf, message: impl Into<String>) -> IndexFinding {
    IndexFinding {
        path,
        severity: IndexFindingSeverity::Error,
        message: message.into(),
    }
}

fn index_warning(path: PathBuf, message: impl Into<String>) -> IndexFinding {
    IndexFinding {
        path,
        severity: IndexFindingSeverity::Warning,
        message: message.into(),
    }
}

enum CommentStyle {
    Html,
    Hash,
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn query_manifest_walks_dynamic_paths() {
        let manifest = parse_manifest(
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[record.trust]
confidence = "high"
provenance = ["declared", "verified"]

[repo]
name = "orbit"
description = "Fast local-first sync engine"
languages = ["rust"]

[x.example]
internal_id = "orbit-prod"
"#,
        )
        .expect("manifest parses");

        assert_eq!(
            query_manifest(&manifest, "x.example.internal_id").expect("query succeeds"),
            "\"orbit-prod\""
        );
        assert_eq!(
            query_manifest(&manifest, "trust.provenance").expect("legacy trust alias works"),
            "[\n  \"declared\",\n  \"verified\"\n]"
        );
        assert_eq!(
            query_manifest_value(&manifest, "repo.name").expect("value query succeeds"),
            Value::String("orbit".into())
        );
    }

    #[test]
    fn query_repository_serializes_selection_and_conflicts() {
        let root = temp_dir("query-report");
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[record.trust]
confidence = "high"
provenance = ["declared"]

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
        )
        .expect("manifest written");

        let report = query_repository(&root, "repo.name").expect("query report");
        let json = serde_json::to_value(report).expect("report serializes");
        assert_eq!(
            json["selection"]["reason"],
            Value::String("only_matching_record".into())
        );
        assert_eq!(
            json["selection"]["record"]["record"]["status"],
            Value::String("canonical".into())
        );
        assert_eq!(json["conflicts"], Value::Array(Vec::new()));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn trust_repository_serializes_selection_and_conflicts() {
        let root = temp_dir("trust-report");
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://example.com/orbit"

[record.trust]
confidence = "medium"
provenance = ["imported", "verified"]

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
        )
        .expect("manifest written");

        let report = trust_repository(&root).expect("trust report");
        let json = serde_json::to_value(report).expect("report serializes");
        assert_eq!(
            json["selection"]["reason"],
            Value::String("only_matching_record".into())
        );
        assert_eq!(
            json["selection"]["record"]["record"]["mode"],
            Value::String("overlay".into())
        );
        assert_eq!(json["conflicts"], Value::Array(Vec::new()));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn query_repository_prefers_canonical_over_matching_overlay() {
        let root = temp_dir("query-canonical-preferred");
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[record.trust]
confidence = "high"
provenance = ["declared"]

[repo]
name = "orbit"
description = "Fast local-first sync engine"
homepage = "https://github.com/example/orbit"
build = "cargo build --workspace"
"#,
        )
        .expect("canonical manifest written");
        let overlay_dir = root.join("repos/github.com/example/orbit");
        fs::create_dir_all(&overlay_dir).expect("overlay dir created");
        let claim_dir = overlay_dir.join("claims/2026-03-10-maintainer-claim-01");
        fs::create_dir_all(claim_dir.join("events")).expect("claim dir created");
        fs::write(
            overlay_dir.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["imported", "verified"]

[repo]
name = "orbit"
description = "Curated overlay"
build = "cargo test"
"#,
        )
        .expect("overlay manifest written");
        fs::write(
            claim_dir.join("claim.toml"),
            r#"
schema = "dotrepo-claim/v0"

[claim]
id = "github.com/example/orbit/2026-03-10-maintainer-claim-01"
kind = "maintainer_authority"
state = "accepted"
created_at = "2026-03-10T14:30:00Z"
updated_at = "2026-03-12T09:15:00Z"

[identity]
host = "github.com"
owner = "example"
repo = "orbit"

[claimant]
display_name = "Orbit maintainers"
asserted_role = "maintainer"

[target]
index_paths = ["repos/github.com/example/orbit/record.toml"]
record_sources = ["https://github.com/example/orbit"]
canonical_repo_url = "https://github.com/example/orbit"

[resolution]
canonical_record_path = ".repo"
canonical_mirror_path = "repos/github.com/example/orbit/record.toml"
result_event = "events/0002-accepted.toml"
"#,
        )
        .expect("claim written");
        fs::write(
            claim_dir.join("events/0001-submitted.toml"),
            r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 1
kind = "submitted"
timestamp = "2026-03-10T14:30:00Z"
actor = "claimant"

[transition]
from = "draft"
to = "submitted"

[summary]
text = "Submitted claim."
"#,
        )
        .expect("submitted event written");
        fs::write(
            claim_dir.join("events/0002-accepted.toml"),
            r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 2
kind = "accepted"
timestamp = "2026-03-12T09:15:00Z"
actor = "index-reviewer"

[transition]
from = "submitted"
to = "accepted"

[summary]
text = "Accepted claim."
"#,
        )
        .expect("accepted event written");

        let report = query_repository(&root, "repo.build").expect("query report");
        let json = serde_json::to_value(report).expect("query report serializes");
        assert_eq!(
            json["selection"]["reason"],
            Value::String("canonical_preferred".into())
        );
        assert_eq!(
            json["value"],
            Value::String("cargo build --workspace".into())
        );
        assert_eq!(
            json["conflicts"][0]["relationship"],
            Value::String("superseded".into())
        );
        assert_eq!(
            json["conflicts"][0]["reason"],
            Value::String("canonical_preferred".into())
        );
        assert_eq!(
            json["conflicts"][0]["value"],
            Value::String("cargo test".into())
        );
        assert_eq!(
            json["conflicts"][0]["record"]["claim"]["state"],
            Value::String("accepted".into())
        );
        assert_eq!(
            json["conflicts"][0]["record"]["claim"]["handoff"],
            Value::String("superseded".into())
        );

        let trust = trust_repository(&root).expect("trust report");
        let trust_json = serde_json::to_value(trust).expect("trust report serializes");
        assert_eq!(
            trust_json["selection"]["reason"],
            Value::String("canonical_preferred".into())
        );
        assert_eq!(
            trust_json["conflicts"][0]["relationship"],
            Value::String("superseded".into())
        );
        assert_eq!(trust_json["conflicts"][0].get("value"), None);
        assert_eq!(
            trust_json["conflicts"][0]["record"]["claim"]["id"],
            Value::String("github.com/example/orbit/2026-03-10-maintainer-claim-01".into())
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn query_repository_prefers_higher_status_overlay() {
        let root = temp_dir("query-higher-status-overlay");
        let imported_dir = root.join("imported");
        let reviewed_dir = root.join("reviewed");
        fs::create_dir_all(&imported_dir).expect("imported dir created");
        fs::create_dir_all(&reviewed_dir).expect("reviewed dir created");
        fs::write(
            imported_dir.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "low"
provenance = ["imported"]

[repo]
name = "orbit"
description = "Imported overlay"
build = "cargo build"
"#,
        )
        .expect("imported overlay written");
        fs::write(
            reviewed_dir.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["imported", "verified"]

[repo]
name = "orbit"
description = "Reviewed overlay"
build = "cargo build --locked"
"#,
        )
        .expect("reviewed overlay written");

        let report = query_repository(&root, "repo.build").expect("query report");
        let json = serde_json::to_value(report).expect("query report serializes");
        assert_eq!(
            json["selection"]["reason"],
            Value::String("higher_status_overlay".into())
        );
        assert_eq!(json["value"], Value::String("cargo build --locked".into()));
        assert_eq!(
            json["conflicts"][0]["relationship"],
            Value::String("superseded".into())
        );
        assert_eq!(
            json["conflicts"][0]["reason"],
            Value::String("higher_status_overlay".into())
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn query_repository_surfaces_equal_authority_overlay_conflicts() {
        let root = temp_dir("query-equal-authority-overlay");
        let first_dir = root.join("a");
        let second_dir = root.join("b");
        fs::create_dir_all(&first_dir).expect("first dir created");
        fs::create_dir_all(&second_dir).expect("second dir created");
        fs::write(
            first_dir.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["imported", "verified"]

[repo]
name = "orbit"
description = "First reviewed overlay"
build = "cargo build"
"#,
        )
        .expect("first overlay written");
        fs::write(
            second_dir.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["imported", "verified"]

[repo]
name = "orbit"
description = "Second reviewed overlay"
build = "cargo test"
"#,
        )
        .expect("second overlay written");

        let report = query_repository(&root, "repo.build").expect("query report");
        let json = serde_json::to_value(report).expect("query report serializes");
        assert_eq!(
            json["selection"]["reason"],
            Value::String("equal_authority_conflict".into())
        );
        assert_eq!(
            json["selection"]["record"]["manifestPath"],
            Value::String("a/record.toml".into())
        );
        assert_eq!(
            json["conflicts"][0]["relationship"],
            Value::String("parallel".into())
        );
        assert_eq!(
            json["conflicts"][0]["reason"],
            Value::String("equal_authority_conflict".into())
        );
        assert_eq!(
            json["conflicts"][0]["value"],
            Value::String("cargo test".into())
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn trust_repository_omits_rejected_claim_context_from_normal_visibility() {
        let root = temp_dir("query-rejected-claim");
        fs::write(
            root.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["imported", "verified"]

[repo]
name = "orbit"
description = "Reviewed overlay"
"#,
        )
        .expect("record written");
        let claim_dir = root.join("claims/2026-03-10-maintainer-claim-01");
        fs::create_dir_all(claim_dir.join("events")).expect("claim dir created");
        fs::write(
            claim_dir.join("claim.toml"),
            r#"
schema = "dotrepo-claim/v0"

[claim]
id = "github.com/example/orbit/2026-03-10-maintainer-claim-01"
kind = "maintainer_authority"
state = "rejected"
created_at = "2026-03-10T14:30:00Z"
updated_at = "2026-03-10T15:00:00Z"

[identity]
host = "github.com"
owner = "example"
repo = "orbit"

[claimant]
display_name = "Orbit maintainers"
asserted_role = "maintainer"

[target]
record_sources = ["https://github.com/example/orbit"]
"#,
        )
        .expect("claim written");
        fs::write(
            claim_dir.join("events/0001-submitted.toml"),
            r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 1
kind = "submitted"
timestamp = "2026-03-10T14:30:00Z"
actor = "claimant"

[transition]
from = "draft"
to = "submitted"

[summary]
text = "Submitted claim."
"#,
        )
        .expect("submitted event written");
        fs::write(
            claim_dir.join("events/0002-rejected.toml"),
            r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 2
kind = "rejected"
timestamp = "2026-03-10T15:00:00Z"
actor = "index-reviewer"

[transition]
from = "submitted"
to = "rejected"

[summary]
text = "Rejected claim."
"#,
        )
        .expect("rejected event written");

        let report = trust_repository(&root).expect("trust report");
        let json = serde_json::to_value(report).expect("trust report serializes");
        assert_eq!(
            json["selection"]["record"].get("claim"),
            None,
            "rejected claims should stay in dedicated claim inspection, not normal trust visibility"
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn public_repository_summary_includes_freshness_links_and_artifacts() {
        let root = temp_dir("public-summary");
        let record_dir = root.join("repos/github.com/example/orbit");
        fs::create_dir_all(&record_dir).expect("record dir created");
        fs::write(
            record_dir.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["imported", "verified"]
notes = "Reviewed overlay."

[repo]
name = "orbit"
description = "Reviewed overlay"
homepage = "https://github.com/example/orbit"

[owners]
team = "@example/orbit-team"
security_contact = "security@example.com"

[docs]
root = "https://example.com/orbit/docs"
getting_started = "https://example.com/orbit/docs/start"
"#,
        )
        .expect("record written");
        fs::write(
            record_dir.join("evidence.md"),
            "# Evidence\n\n- imported from the upstream repository\n",
        )
        .expect("evidence written");

        let response = public_repository_summary(
            &root,
            "github.com",
            "example",
            "orbit",
            sample_public_freshness(),
        )
        .expect("public summary builds");
        let json = serde_json::to_value(response).expect("summary serializes");
        assert_eq!(json["apiVersion"], Value::String("v0".into()));
        assert_eq!(
            json["freshness"]["generatedAt"],
            Value::String("2026-03-10T18:30:00Z".into())
        );
        assert_eq!(
            json["freshness"]["snapshotDigest"],
            Value::String("snapshot-123".into())
        );
        assert_eq!(
            json["repository"]["gettingStarted"],
            Value::String("https://example.com/orbit/docs/start".into())
        );
        assert_eq!(
            json["selection"]["record"]["artifacts"]["evidencePath"],
            Value::String("repos/github.com/example/orbit/evidence.md".into())
        );
        assert_eq!(
            json["links"]["self"],
            Value::String("/v0/repos/github.com/example/orbit/index.json".into())
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn public_repository_query_preserves_competing_values() {
        let root = temp_dir("public-query");
        let record_dir = root.join("repos/github.com/example/orbit");
        let alt_dir = record_dir.join("alt");
        fs::create_dir_all(&alt_dir).expect("alt dir created");
        fs::write(
            record_dir.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Selected description"
"#,
        )
        .expect("selected record written");
        fs::write(
            alt_dir.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Competing description"
"#,
        )
        .expect("competing record written");

        let response = public_repository_query(
            &root,
            "github.com",
            "example",
            "orbit",
            "repo.description",
            sample_public_freshness(),
        )
        .expect("public query builds");
        let json = serde_json::to_value(response).expect("query serializes");
        assert_eq!(
            json["selection"]["reason"],
            Value::String("equal_authority_conflict".into())
        );
        assert_eq!(json["value"], Value::String("Competing description".into()));
        assert_eq!(
            json["conflicts"][0]["relationship"],
            Value::String("parallel".into())
        );
        assert_eq!(
            json["conflicts"][0]["value"],
            Value::String("Selected description".into())
        );
        assert_eq!(
            json["links"]["self"],
            Value::String("/v0/repos/github.com/example/orbit/query?path=repo.description".into())
        );
        assert_eq!(
            json["links"]["repository"],
            Value::String("/v0/repos/github.com/example/orbit/index.json".into())
        );
        assert_eq!(
            json["links"]["trust"],
            Value::String("/v0/repos/github.com/example/orbit/trust.json".into())
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn public_repository_query_rejects_dot_segments_in_identity() {
        let response = public_repository_query_or_error(
            Path::new("."),
            "github.com",
            "..",
            "orbit",
            "repo.description",
            sample_public_freshness(),
        )
        .expect_err("invalid identity rejected");

        assert_eq!(
            response.error.code,
            PublicErrorCode::InvalidRepositoryIdentity
        );
        assert_eq!(
            response.error.message,
            "invalid repository identity: owner must be a single path segment"
        );
    }

    #[test]
    fn public_repository_summary_omits_rejected_claim_context() {
        let root = temp_dir("public-rejected-claim");
        let record_dir = root.join("repos/github.com/example/orbit");
        fs::create_dir_all(&record_dir).expect("record dir created");
        fs::write(
            record_dir.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["imported", "verified"]

[repo]
name = "orbit"
description = "Reviewed overlay"
"#,
        )
        .expect("record written");
        fs::write(record_dir.join("evidence.md"), "# Evidence\n").expect("evidence written");
        let claim_dir = record_dir.join("claims/2026-03-10-maintainer-claim-01");
        fs::create_dir_all(claim_dir.join("events")).expect("claim dir created");
        fs::write(
            claim_dir.join("claim.toml"),
            r#"
schema = "dotrepo-claim/v0"

[claim]
id = "github.com/example/orbit/2026-03-10-maintainer-claim-01"
kind = "maintainer_authority"
state = "rejected"
created_at = "2026-03-10T14:30:00Z"
updated_at = "2026-03-10T15:00:00Z"

[identity]
host = "github.com"
owner = "example"
repo = "orbit"

[claimant]
display_name = "Orbit maintainers"
asserted_role = "maintainer"

[target]
record_sources = ["https://github.com/example/orbit"]
"#,
        )
        .expect("claim written");
        fs::write(
            claim_dir.join("events/0001-submitted.toml"),
            r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 1
kind = "submitted"
timestamp = "2026-03-10T14:30:00Z"
actor = "claimant"

[transition]
from = "draft"
to = "submitted"

[summary]
text = "Submitted claim."
"#,
        )
        .expect("submitted event written");
        fs::write(
            claim_dir.join("events/0002-rejected.toml"),
            r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 2
kind = "rejected"
timestamp = "2026-03-10T15:00:00Z"
actor = "index-reviewer"

[transition]
from = "submitted"
to = "rejected"

[summary]
text = "Rejected claim."
"#,
        )
        .expect("rejected event written");

        let response = public_repository_summary(
            &root,
            "github.com",
            "example",
            "orbit",
            sample_public_freshness(),
        )
        .expect("public summary builds");
        let json = serde_json::to_value(response).expect("summary serializes");
        assert_eq!(
            json["selection"]["record"].get("claim"),
            None,
            "rejected claims should stay out of ordinary public repository responses"
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn export_public_index_static_emits_meta_summary_trust_and_query_input_files() {
        let root = temp_dir("public-export");
        let record_dir = root.join("repos/github.com/example/orbit");
        fs::create_dir_all(&record_dir).expect("record dir created");
        fs::write(
            record_dir.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Reviewed overlay"
"#,
        )
        .expect("record written");
        fs::write(record_dir.join("evidence.md"), "# Evidence\n").expect("evidence written");

        let out = root.join("public");
        let outputs =
            export_public_index_static(&root, &out, sample_public_freshness()).expect("export");
        let rendered = outputs
            .iter()
            .map(|(path, contents)| {
                (
                    path.strip_prefix(&root).unwrap().display().to_string(),
                    contents.clone(),
                )
            })
            .collect::<Vec<_>>();

        assert!(rendered
            .iter()
            .any(|(path, _)| path == "public/v0/meta.json"));
        assert!(rendered
            .iter()
            .any(|(path, _)| path == "public/v0/repos/index.json"));
        assert!(rendered
            .iter()
            .any(|(path, _)| path == "public/v0/repos/github.com/example/orbit/index.json"));
        assert!(rendered
            .iter()
            .any(|(path, _)| path == "public/v0/repos/github.com/example/orbit/trust.json"));
        assert!(rendered
            .iter()
            .any(|(path, _)| path == "public/query-input/github.com/example/orbit.json"));
        assert!(rendered.iter().any(|(path, contents)| {
            path == "public/v0/repos/index.json"
                && contents.contains("\"repositoryCount\": 1")
                && contents.contains("\"repo\": \"orbit\"")
        }));
        assert!(rendered.iter().any(|(path, contents)| {
            path == "public/v0/meta.json"
                && contents.contains("\"strategy\": \"static_summary_and_trust\"")
        }));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn public_query_input_snapshot_matches_direct_query_semantics() {
        let root = temp_dir("public-query-input");
        let record_dir = root.join("repos/github.com/example/orbit");
        let alt_dir = record_dir.join("alt");
        fs::create_dir_all(&alt_dir).expect("record dirs created");
        fs::write(
            record_dir.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Selected description"
"#,
        )
        .expect("selected record written");
        fs::write(record_dir.join("evidence.md"), "# Evidence\n").expect("evidence written");
        fs::write(
            alt_dir.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Competing description"
"#,
        )
        .expect("competing record written");

        let freshness = sample_public_freshness();
        let snapshot =
            public_query_input_snapshot(&root, "github.com", "example", "orbit", freshness.clone())
                .expect("query input snapshot builds");
        let round_tripped = serde_json::from_str::<PublicQueryInputSnapshot>(
            &serde_json::to_string(&snapshot).expect("snapshot serializes"),
        )
        .expect("snapshot round trips");

        let direct = public_repository_query_with_base(
            &root,
            "github.com",
            "example",
            "orbit",
            "repo.description",
            freshness.clone(),
            "/dotrepo",
        )
        .expect("direct query succeeds");
        let via_snapshot = public_repository_query_from_input_with_base(
            &round_tripped,
            "repo.description",
            freshness,
            "/dotrepo",
        )
        .expect("snapshot query succeeds");

        assert_eq!(
            serde_json::to_value(via_snapshot).expect("snapshot response serializes"),
            serde_json::to_value(direct).expect("direct response serializes")
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn scaffold_claim_directory_renders_valid_draft_claim() {
        let root = temp_dir("claim-scaffold");
        let repo_dir = root.join("repos/github.com/acme/widget");
        fs::create_dir_all(&repo_dir).expect("repo dir created");
        fs::write(repo_dir.join("record.toml"), "schema = \"dotrepo/v0.1\"\n")
            .expect("record written");

        let plan = scaffold_claim_directory(
            &root,
            &ClaimScaffoldInput {
                host: "github.com".into(),
                owner: "acme".into(),
                repo: "widget".into(),
                claim_id: "2026-03-10-maintainer-claim-02".into(),
                claimant_display_name: "Acme maintainers".into(),
                asserted_role: "maintainer".into(),
                contact: Some("maintainers@acme.dev".into()),
                record_sources: vec!["https://github.com/acme/widget".into()],
                canonical_repo_url: Some("https://github.com/acme/widget".into()),
                create_review_md: true,
                timestamp: "2026-03-10T18:00:00Z".into(),
            },
        )
        .expect("claim plan");

        assert_eq!(
            display_path(&root, &plan.claim_path),
            "repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-02/claim.toml"
        );
        let claim = parse_claim_record(&plan.claim_text).expect("claim parses");
        assert_eq!(claim.claim.state, ClaimState::Draft);
        assert_eq!(
            claim.claim.id,
            "github.com/acme/widget/2026-03-10-maintainer-claim-02"
        );
        assert_eq!(
            claim.target.index_paths,
            vec!["repos/github.com/acme/widget/record.toml"]
        );
        assert!(plan
            .review_text
            .as_ref()
            .expect("review template")
            .contains("# Claim review"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn scaffold_claim_directory_requires_existing_index_record() {
        let root = temp_dir("claim-scaffold-missing-record");
        let err = scaffold_claim_directory(
            &root,
            &ClaimScaffoldInput {
                host: "github.com".into(),
                owner: "acme".into(),
                repo: "widget".into(),
                claim_id: "2026-03-10-maintainer-claim-02".into(),
                claimant_display_name: "Acme maintainers".into(),
                asserted_role: "maintainer".into(),
                contact: None,
                record_sources: Vec::new(),
                canonical_repo_url: None,
                create_review_md: false,
                timestamp: "2026-03-10T18:00:00Z".into(),
            },
        )
        .expect_err("missing record should fail");

        assert!(err.to_string().contains("no index record found"));
        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn append_claim_event_advances_draft_claim_to_submitted() {
        let root = temp_dir("claim-event-submit");
        let repo_dir = root.join("repos/github.com/acme/widget");
        fs::create_dir_all(&repo_dir).expect("repo dir created");
        fs::write(repo_dir.join("record.toml"), "schema = \"dotrepo/v0.1\"\n")
            .expect("record written");
        let scaffold = scaffold_claim_directory(
            &root,
            &ClaimScaffoldInput {
                host: "github.com".into(),
                owner: "acme".into(),
                repo: "widget".into(),
                claim_id: "2026-03-10-maintainer-claim-04".into(),
                claimant_display_name: "Acme maintainers".into(),
                asserted_role: "maintainer".into(),
                contact: None,
                record_sources: vec!["https://github.com/acme/widget".into()],
                canonical_repo_url: None,
                create_review_md: true,
                timestamp: "2026-03-10T18:00:00Z".into(),
            },
        )
        .expect("claim scaffold");
        fs::create_dir_all(scaffold.claim_dir.join("events")).expect("events dir created");
        fs::write(&scaffold.claim_path, scaffold.claim_text).expect("claim written");
        fs::write(
            scaffold.review_path.as_ref().expect("review path"),
            scaffold.review_text.as_ref().expect("review text"),
        )
        .expect("review written");

        let plan = append_claim_event(
            &root,
            &scaffold.claim_dir,
            &ClaimEventAppendInput {
                kind: ClaimEventKind::Submitted,
                actor: "claimant".into(),
                summary: "Submitted maintainer claim.".into(),
                timestamp: "2026-03-10T18:05:00Z".into(),
                corrected_state: None,
                canonical_record_path: None,
                canonical_mirror_path: None,
            },
        )
        .expect("submit event");

        assert_eq!(
            display_path(&root, &plan.event_path),
            "repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-04/events/0001-submitted.toml"
        );
        let updated_claim = parse_claim_record(&plan.claim_text).expect("updated claim parses");
        assert_eq!(updated_claim.claim.state, ClaimState::Submitted);
        let event = parse_claim_event(&plan.event_text).expect("event parses");
        assert_eq!(event.event.sequence, 1);
        assert_eq!(
            event.transition.expect("transition").to,
            ClaimState::Submitted
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn append_claim_event_rejects_invalid_acceptance_from_draft() {
        let root = temp_dir("claim-event-invalid");
        let repo_dir = root.join("repos/github.com/acme/widget");
        fs::create_dir_all(&repo_dir).expect("repo dir created");
        fs::write(repo_dir.join("record.toml"), "schema = \"dotrepo/v0.1\"\n")
            .expect("record written");
        let scaffold = scaffold_claim_directory(
            &root,
            &ClaimScaffoldInput {
                host: "github.com".into(),
                owner: "acme".into(),
                repo: "widget".into(),
                claim_id: "2026-03-10-maintainer-claim-05".into(),
                claimant_display_name: "Acme maintainers".into(),
                asserted_role: "maintainer".into(),
                contact: None,
                record_sources: vec!["https://github.com/acme/widget".into()],
                canonical_repo_url: None,
                create_review_md: false,
                timestamp: "2026-03-10T18:00:00Z".into(),
            },
        )
        .expect("claim scaffold");
        fs::create_dir_all(scaffold.claim_dir.join("events")).expect("events dir created");
        fs::write(&scaffold.claim_path, scaffold.claim_text).expect("claim written");

        let err = append_claim_event(
            &root,
            &scaffold.claim_dir,
            &ClaimEventAppendInput {
                kind: ClaimEventKind::Accepted,
                actor: "index-reviewer".into(),
                summary: "Accepted maintainer claim.".into(),
                timestamp: "2026-03-10T18:05:00Z".into(),
                corrected_state: None,
                canonical_record_path: None,
                canonical_mirror_path: None,
            },
        )
        .expect_err("draft claim should not accept");

        assert!(err
            .to_string()
            .contains("accepted events are only valid for submitted or in_review claims"));
        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn append_claim_event_records_canonical_links_for_accepted_handoff() {
        let root = temp_dir("claim-event-accepted-handoff");
        let repo_dir = root.join("repos/github.com/acme/widget");
        fs::create_dir_all(&repo_dir).expect("repo dir created");
        fs::write(repo_dir.join("record.toml"), "schema = \"dotrepo/v0.1\"\n")
            .expect("record written");
        let scaffold = scaffold_claim_directory(
            &root,
            &ClaimScaffoldInput {
                host: "github.com".into(),
                owner: "acme".into(),
                repo: "widget".into(),
                claim_id: "2026-03-10-maintainer-claim-06".into(),
                claimant_display_name: "Acme maintainers".into(),
                asserted_role: "maintainer".into(),
                contact: None,
                record_sources: vec!["https://github.com/acme/widget".into()],
                canonical_repo_url: Some("https://github.com/acme/widget".into()),
                create_review_md: false,
                timestamp: "2026-03-10T18:00:00Z".into(),
            },
        )
        .expect("claim scaffold");
        fs::create_dir_all(scaffold.claim_dir.join("events")).expect("events dir created");
        fs::write(&scaffold.claim_path, scaffold.claim_text).expect("claim written");

        let submitted = append_claim_event(
            &root,
            &scaffold.claim_dir,
            &ClaimEventAppendInput {
                kind: ClaimEventKind::Submitted,
                actor: "claimant".into(),
                summary: "Submitted maintainer claim.".into(),
                timestamp: "2026-03-10T18:05:00Z".into(),
                corrected_state: None,
                canonical_record_path: None,
                canonical_mirror_path: None,
            },
        )
        .expect("submitted event");
        fs::write(&submitted.event_path, submitted.event_text).expect("submitted event written");
        fs::write(&submitted.claim_path, submitted.claim_text).expect("submitted claim written");

        let accepted = append_claim_event(
            &root,
            &scaffold.claim_dir,
            &ClaimEventAppendInput {
                kind: ClaimEventKind::Accepted,
                actor: "index-reviewer".into(),
                summary: "Accepted maintainer claim after review.".into(),
                timestamp: "2026-03-10T18:10:00Z".into(),
                corrected_state: None,
                canonical_record_path: Some(".repo".into()),
                canonical_mirror_path: Some("repos/github.com/acme/widget/record.toml".into()),
            },
        )
        .expect("accepted event");

        let updated_claim = parse_claim_record(&accepted.claim_text).expect("updated claim parses");
        let resolution = updated_claim.resolution.expect("resolution recorded");
        assert_eq!(updated_claim.claim.state, ClaimState::Accepted);
        assert_eq!(resolution.canonical_record_path.as_deref(), Some(".repo"));
        assert_eq!(
            resolution.canonical_mirror_path.as_deref(),
            Some("repos/github.com/acme/widget/record.toml")
        );
        assert_eq!(
            resolution.result_event.as_deref(),
            Some("events/0002-accepted.toml")
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn append_claim_event_allows_corrected_handoff_adjustments() {
        let root = temp_dir("claim-event-corrected-handoff");
        let repo_dir = root.join("repos/github.com/acme/widget");
        fs::create_dir_all(&repo_dir).expect("repo dir created");
        fs::write(repo_dir.join("record.toml"), "schema = \"dotrepo/v0.1\"\n")
            .expect("record written");
        let scaffold = scaffold_claim_directory(
            &root,
            &ClaimScaffoldInput {
                host: "github.com".into(),
                owner: "acme".into(),
                repo: "widget".into(),
                claim_id: "2026-03-10-maintainer-claim-07".into(),
                claimant_display_name: "Acme maintainers".into(),
                asserted_role: "maintainer".into(),
                contact: None,
                record_sources: vec!["https://github.com/acme/widget".into()],
                canonical_repo_url: Some("https://github.com/acme/widget".into()),
                create_review_md: false,
                timestamp: "2026-03-10T18:00:00Z".into(),
            },
        )
        .expect("claim scaffold");
        fs::create_dir_all(scaffold.claim_dir.join("events")).expect("events dir created");
        fs::write(&scaffold.claim_path, scaffold.claim_text).expect("claim written");

        let submitted = append_claim_event(
            &root,
            &scaffold.claim_dir,
            &ClaimEventAppendInput {
                kind: ClaimEventKind::Submitted,
                actor: "claimant".into(),
                summary: "Submitted maintainer claim.".into(),
                timestamp: "2026-03-10T18:05:00Z".into(),
                corrected_state: None,
                canonical_record_path: None,
                canonical_mirror_path: None,
            },
        )
        .expect("submitted event");
        fs::write(&submitted.event_path, submitted.event_text).expect("submitted event written");
        fs::write(&submitted.claim_path, submitted.claim_text).expect("submitted claim written");

        let accepted = append_claim_event(
            &root,
            &scaffold.claim_dir,
            &ClaimEventAppendInput {
                kind: ClaimEventKind::Accepted,
                actor: "index-reviewer".into(),
                summary: "Accepted maintainer claim without canonical links yet.".into(),
                timestamp: "2026-03-10T18:10:00Z".into(),
                corrected_state: None,
                canonical_record_path: None,
                canonical_mirror_path: None,
            },
        )
        .expect("accepted event");
        fs::write(&accepted.event_path, accepted.event_text).expect("accepted event written");
        fs::write(&accepted.claim_path, accepted.claim_text).expect("accepted claim written");

        let corrected = append_claim_event(
            &root,
            &scaffold.claim_dir,
            &ClaimEventAppendInput {
                kind: ClaimEventKind::Corrected,
                actor: "index-reviewer".into(),
                summary: "Linked accepted claim to canonical artifacts.".into(),
                timestamp: "2026-03-10T18:15:00Z".into(),
                corrected_state: None,
                canonical_record_path: Some(".repo".into()),
                canonical_mirror_path: Some("repos/github.com/acme/widget/record.toml".into()),
            },
        )
        .expect("corrected event");

        let updated_claim =
            parse_claim_record(&corrected.claim_text).expect("updated claim parses");
        let resolution = updated_claim.resolution.expect("resolution recorded");
        assert_eq!(updated_claim.claim.state, ClaimState::Accepted);
        assert_eq!(
            resolution.result_event.as_deref(),
            Some("events/0003-corrected.toml")
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn append_claim_event_rejects_canonical_links_for_non_accepted_states() {
        let root = temp_dir("claim-event-invalid-handoff");
        let repo_dir = root.join("repos/github.com/acme/widget");
        fs::create_dir_all(&repo_dir).expect("repo dir created");
        fs::write(repo_dir.join("record.toml"), "schema = \"dotrepo/v0.1\"\n")
            .expect("record written");
        let scaffold = scaffold_claim_directory(
            &root,
            &ClaimScaffoldInput {
                host: "github.com".into(),
                owner: "acme".into(),
                repo: "widget".into(),
                claim_id: "2026-03-10-maintainer-claim-08".into(),
                claimant_display_name: "Acme maintainers".into(),
                asserted_role: "maintainer".into(),
                contact: None,
                record_sources: vec!["https://github.com/acme/widget".into()],
                canonical_repo_url: None,
                create_review_md: false,
                timestamp: "2026-03-10T18:00:00Z".into(),
            },
        )
        .expect("claim scaffold");
        fs::create_dir_all(scaffold.claim_dir.join("events")).expect("events dir created");
        fs::write(&scaffold.claim_path, scaffold.claim_text).expect("claim written");
        let submitted = append_claim_event(
            &root,
            &scaffold.claim_dir,
            &ClaimEventAppendInput {
                kind: ClaimEventKind::Submitted,
                actor: "claimant".into(),
                summary: "Submitted maintainer claim.".into(),
                timestamp: "2026-03-10T18:05:00Z".into(),
                corrected_state: None,
                canonical_record_path: None,
                canonical_mirror_path: None,
            },
        )
        .expect("submitted event");
        fs::write(&submitted.event_path, submitted.event_text).expect("event written");
        fs::write(&submitted.claim_path, submitted.claim_text).expect("claim written");

        let err = append_claim_event(
            &root,
            &scaffold.claim_dir,
            &ClaimEventAppendInput {
                kind: ClaimEventKind::Rejected,
                actor: "index-reviewer".into(),
                summary: "Rejected maintainer claim.".into(),
                timestamp: "2026-03-10T18:10:00Z".into(),
                corrected_state: None,
                canonical_record_path: Some(".repo".into()),
                canonical_mirror_path: None,
            },
        )
        .expect_err("non-accepted states should reject canonical links");

        assert!(err.to_string().contains(
            "canonical handoff links are only valid when the resulting claim state is accepted"
        ));
        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn parse_claim_record_rejects_unknown_schema() {
        let err = parse_claim_record(
            r#"
schema = "dotrepo-claim/v9"

[claim]
id = "github.com/acme/widget/2026-03-10-maintainer-claim-01"
kind = "maintainer_authority"
state = "submitted"
created_at = "2026-03-10T14:30:00Z"
updated_at = "2026-03-10T14:30:00Z"

[identity]
host = "github.com"
owner = "acme"
repo = "widget"

[claimant]
display_name = "Acme maintainers"
asserted_role = "maintainer"

[target]
record_sources = ["https://github.com/acme/widget"]
"#,
        )
        .expect_err("claim schema should fail");

        assert!(
            err.to_string().contains("unsupported claim schema"),
            "unexpected error: {err}"
        );
    }

    #[test]
    fn parse_claim_event_rejects_zero_sequence() {
        let err = parse_claim_event(
            r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 0
kind = "submitted"
timestamp = "2026-03-10T14:30:00Z"
actor = "claimant"

[summary]
text = "Submitted claim."
"#,
        )
        .expect_err("zero sequence should fail");

        assert!(
            err.to_string()
                .contains("event.sequence must be greater than zero"),
            "unexpected error: {err}"
        );
    }

    #[test]
    fn load_claim_directory_reads_claim_and_events() {
        let root = temp_dir("claim-directory");
        let claim_dir =
            root.join("repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01");
        fs::create_dir_all(claim_dir.join("events")).expect("claim events dir created");
        fs::write(
            claim_dir.join("claim.toml"),
            r#"
schema = "dotrepo-claim/v0"

[claim]
id = "github.com/acme/widget/2026-03-10-maintainer-claim-01"
kind = "maintainer_authority"
state = "accepted"
created_at = "2026-03-10T14:30:00Z"
updated_at = "2026-03-12T09:15:00Z"

[identity]
host = "github.com"
owner = "acme"
repo = "widget"

[claimant]
display_name = "Acme maintainers"
asserted_role = "maintainer"
contact = "maintainers@acme.dev"

[target]
index_paths = ["repos/github.com/acme/widget/record.toml"]
record_sources = ["https://github.com/acme/widget"]
canonical_repo_url = "https://github.com/acme/widget"

[resolution]
canonical_record_path = ".repo"
canonical_mirror_path = "repos/github.com/acme/widget/record.toml"
result_event = "events/0002-accepted.toml"
"#,
        )
        .expect("claim written");
        fs::write(claim_dir.join("review.md"), "Reviewed.").expect("review written");
        fs::write(
            claim_dir.join("events/0001-submitted.toml"),
            r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 1
kind = "submitted"
timestamp = "2026-03-10T14:30:00Z"
actor = "claimant"

[transition]
from = "draft"
to = "submitted"

[summary]
text = "Submitted maintainer claim."
"#,
        )
        .expect("submitted event written");
        fs::write(
            claim_dir.join("events/0002-accepted.toml"),
            r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 2
kind = "accepted"
timestamp = "2026-03-12T09:15:00Z"
actor = "index-reviewer"

[transition]
from = "in_review"
to = "accepted"

[summary]
text = "Accepted maintainer claim."

[links]
claim = "../claim.toml"
review_notes = "../review.md"
canonical_record_path = ".repo"
"#,
        )
        .expect("accepted event written");

        let loaded = load_claim_directory(&root, &claim_dir).expect("claim directory loads");
        assert_eq!(
            loaded.claim.claim.state,
            ClaimState::Accepted,
            "current state should parse"
        );
        assert_eq!(loaded.events.len(), 2, "events should be loaded");
        assert_eq!(
            loaded.events[0].event.event.kind,
            ClaimEventKind::Submitted,
            "events should be ordered by filename"
        );
        assert_eq!(
            loaded.review_path.as_deref(),
            Some("repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01/review.md")
        );

        let json = serde_json::to_value(&loaded).expect("claim directory serializes");
        assert_eq!(
            json["claim"]["claim"]["state"],
            Value::String("accepted".into())
        );
        assert_eq!(
            json["events"][1]["event"]["event"]["kind"],
            Value::String("accepted".into())
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn render_readme_renders_custom_sections() {
        let root = temp_dir("custom-readme");
        let manifest = parse_manifest(
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"

[readme]
sections = ["overview", "quickstart"]

[readme.custom_sections.quickstart]
content = "Run `cargo build`."
"#,
        )
        .expect("manifest parses");

        let rendered =
            render_readme(&root, &manifest, b"schema = \"dotrepo/v0.1\"").expect("readme renders");

        assert!(rendered.contains("## Quickstart"));
        assert!(rendered.contains("Run `cargo build`."));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn render_readme_rejects_custom_sections_outside_repository_root() {
        let sandbox = temp_dir("custom-readme-escape");
        let root = sandbox.join("repo");
        fs::create_dir_all(&root).expect("repo dir created");
        fs::write(sandbox.join("secret.txt"), "do not read").expect("secret written");
        let manifest = parse_manifest(
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"

[readme]
sections = ["overview", "quickstart"]

[readme.custom_sections.quickstart]
path = "../secret.txt"
"#,
        )
        .expect("manifest parses");

        let err = render_readme(&root, &manifest, b"schema = \"dotrepo/v0.1\"")
            .expect_err("escape path rejected");
        assert!(err
            .to_string()
            .contains("path must stay within the repository root"));

        fs::remove_dir_all(sandbox).expect("temp dir removed");
    }

    #[test]
    fn validate_manifest_rejects_custom_sections_outside_repository_root() {
        let sandbox = temp_dir("custom-readme-validate-escape");
        let root = sandbox.join("repo");
        fs::create_dir_all(&root).expect("repo dir created");
        fs::write(sandbox.join("secret.txt"), "do not read").expect("secret written");
        let manifest = parse_manifest(
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"

[readme]
sections = ["quickstart"]

[readme.custom_sections.quickstart]
path = "../secret.txt"
"#,
        )
        .expect("manifest parses");

        let diagnostics = validate_manifest_diagnostics(&root, &manifest);
        assert!(diagnostics.iter().any(|diagnostic| diagnostic
            .message
            .contains("custom README section `quickstart` uses an invalid path")));

        fs::remove_dir_all(sandbox).expect("temp dir removed");
    }

    #[test]
    fn parse_readme_docs_metadata_extracts_docs_and_getting_started_links() {
        let signal = parse_readme_docs_signal(
            "[Docs](./docs/) · [Getting Started](./docs/getting-started.md) · [API](./docs/api.md)",
        );
        assert_eq!(signal.root.as_deref(), Some("./docs/"));
        assert_eq!(
            signal.getting_started.as_deref(),
            Some("./docs/getting-started.md")
        );

        let links = extract_markdown_links(
            "[Docs](./docs/) · [Getting Started](./docs/getting-started.md) · [API](./docs/api.md)",
        );
        assert_eq!(
            links,
            vec![
                ("Docs".to_string(), "./docs/".to_string()),
                (
                    "Getting Started".to_string(),
                    "./docs/getting-started.md".to_string()
                ),
                ("API".to_string(), "./docs/api.md".to_string())
            ]
        );

        let metadata = parse_readme_metadata(
            r#"# Tidelift

[Docs](./docs/) · [Getting Started](./docs/getting-started.md) · [API](./docs/api.md)

Policy-aware release orchestration for multi-service deploys.
"#,
        );
        assert_eq!(metadata.docs_root.as_deref(), Some("./docs/"));
        assert_eq!(
            metadata.docs_getting_started.as_deref(),
            Some("./docs/getting-started.md")
        );
        assert_eq!(
            metadata.description.as_deref(),
            Some("Policy-aware release orchestration for multi-service deploys.")
        );
    }

    #[test]
    fn parse_readme_metadata_skips_reference_definitions_and_trailing_badges() {
        let metadata = parse_readme_metadata(
            r#"# Serde &emsp; [![Build Status]][actions] [![Latest Version]][crates.io]

[Build Status]: https://img.shields.io/github/actions/workflow/status/serde-rs/serde/ci.yml?branch=master
[actions]: https://github.com/serde-rs/serde/actions?query=branch%3Amaster
[Latest Version]: https://img.shields.io/crates/v/serde.svg
[crates.io]: https://crates.io/crates/serde

**Serde is a framework for *ser*ializing and *de*serializing Rust data structures efficiently and generically.**
"#,
        );
        assert_eq!(metadata.title.as_deref(), Some("Serde"));
        assert_eq!(
            metadata.description.as_deref(),
            Some("Serde is a framework for *ser*ializing and *de*serializing Rust data structures efficiently and generically.")
        );
    }

    #[test]
    fn parse_readme_metadata_preserves_unicode_text_around_markdown_links() {
        let metadata = parse_readme_metadata(
            r#"# Café

Café sécurité pour les dépôts [guides](./docs/guides.md) et l’équipe.
"#,
        );
        assert_eq!(metadata.title.as_deref(), Some("Café"));
        assert_eq!(
            metadata.description.as_deref(),
            Some("Café sécurité pour les dépôts guides et l’équipe.")
        );
    }

    #[test]
    fn import_repository_accepts_readme_variants_and_preserves_their_paths() {
        let root = temp_dir("import-readme-variant");
        fs::write(
            root.join("README.mdx"),
            "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
        )
        .expect("README variant written");

        let plan = import_repository(
            &root,
            ImportMode::Overlay,
            Some("https://github.com/example/orbit"),
        )
        .expect("import succeeds");

        assert!(plan
            .imported_sources
            .iter()
            .any(|path| path == "README.mdx"));
        assert_eq!(plan.manifest.repo.name, "Orbit");
        assert_eq!(
            plan.manifest.repo.description,
            "Policy-aware release orchestration for multi-service deploys."
        );
        assert!(plan.evidence_text.as_deref().is_some_and(
            |text| text.contains("Imported repository name and description from README.mdx.")
        ));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn import_repository_imports_cargo_workspace_build_and_test_commands() {
        let root = temp_dir("import-cargo-commands");
        fs::write(
            root.join("README.md"),
            "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
        )
        .expect("README written");
        fs::write(
            root.join("Cargo.toml"),
            "[workspace]\nmembers = [\"crates/orbit\"]\n",
        )
        .expect("Cargo.toml written");

        let plan = import_repository(
            &root,
            ImportMode::Overlay,
            Some("https://github.com/example/orbit"),
        )
        .expect("import succeeds");

        assert_eq!(
            plan.manifest.repo.build.as_deref(),
            Some("cargo build --workspace")
        );
        assert_eq!(
            plan.manifest.repo.test.as_deref(),
            Some("cargo test --workspace")
        );
        assert!(plan
            .imported_sources
            .iter()
            .any(|path| path == "Cargo.toml"));
        assert!(plan
            .manifest
            .record
            .trust
            .as_ref()
            .and_then(|trust| trust.notes.as_deref())
            .is_some_and(|text| text.contains("Imported `repo.build` from `Cargo.toml`.")));
        assert!(plan.evidence_text.as_deref().is_some_and(|text| text
            .contains("Imported repo.build from Cargo.toml as `cargo build --workspace`.")));
        assert!(plan
            .evidence_text
            .as_deref()
            .is_some_and(|text| text
                .contains("Imported repo.test from Cargo.toml as `cargo test --workspace`.")));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn import_repository_imports_package_json_commands_with_runner_detection() {
        let root = temp_dir("import-package-json-commands");
        fs::write(
            root.join("README.md"),
            "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
        )
        .expect("README written");
        fs::write(
            root.join("package.json"),
            r#"{
  "name": "orbit",
  "packageManager": "pnpm@9.1.0",
  "scripts": {
    "build": "vite build",
    "test": "vitest run"
  }
}
"#,
        )
        .expect("package.json written");

        let plan = import_repository(
            &root,
            ImportMode::Overlay,
            Some("https://github.com/example/orbit"),
        )
        .expect("import succeeds");

        assert_eq!(plan.manifest.repo.build.as_deref(), Some("pnpm build"));
        assert_eq!(plan.manifest.repo.test.as_deref(), Some("pnpm test"));
        assert!(plan
            .imported_sources
            .iter()
            .any(|path| path == "package.json"));
        assert!(plan.evidence_text.as_deref().is_some_and(
            |text| text.contains("Imported repo.test from package.json as `pnpm test`.")
        ));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn import_repository_imports_pyproject_build_and_test_defaults() {
        let root = temp_dir("import-pyproject-commands");
        fs::write(
            root.join("README.md"),
            "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
        )
        .expect("README written");
        fs::write(
            root.join("pyproject.toml"),
            r#"[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
"#,
        )
        .expect("pyproject written");

        let plan = import_repository(
            &root,
            ImportMode::Overlay,
            Some("https://github.com/example/orbit"),
        )
        .expect("import succeeds");

        assert_eq!(plan.manifest.repo.build.as_deref(), Some("python -m build"));
        assert_eq!(plan.manifest.repo.test.as_deref(), Some("python -m pytest"));
        assert!(plan
            .imported_sources
            .iter()
            .any(|path| path == "pyproject.toml"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn import_repository_imports_go_module_build_and_test_defaults() {
        let root = temp_dir("import-go-mod-commands");
        fs::write(
            root.join("README.md"),
            "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
        )
        .expect("README written");
        fs::write(
            root.join("go.mod"),
            "module github.com/example/orbit\n\ngo 1.24\n",
        )
        .expect("go.mod written");

        let plan = import_repository(
            &root,
            ImportMode::Overlay,
            Some("https://github.com/example/orbit"),
        )
        .expect("import succeeds");

        assert_eq!(plan.manifest.repo.build.as_deref(), Some("go build ./..."));
        assert_eq!(plan.manifest.repo.test.as_deref(), Some("go test ./..."));
        assert!(plan.imported_sources.iter().any(|path| path == "go.mod"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn import_repository_leaves_conflicting_manifest_commands_unset() {
        let root = temp_dir("import-conflicting-commands");
        fs::write(
            root.join("README.md"),
            "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
        )
        .expect("README written");
        fs::write(
            root.join("Cargo.toml"),
            "[workspace]\nmembers = [\"crates/orbit\"]\n",
        )
        .expect("Cargo.toml written");
        fs::write(
            root.join("package.json"),
            r#"{
  "name": "orbit",
  "scripts": {
    "build": "vite build",
    "test": "vitest run"
  }
}
"#,
        )
        .expect("package.json written");

        let plan = import_repository(
            &root,
            ImportMode::Overlay,
            Some("https://github.com/example/orbit"),
        )
        .expect("import succeeds");

        assert_eq!(plan.manifest.repo.build, None);
        assert_eq!(plan.manifest.repo.test, None);
        assert!(!plan
            .imported_sources
            .iter()
            .any(|path| path == "Cargo.toml"));
        assert!(!plan
            .imported_sources
            .iter()
            .any(|path| path == "package.json"));
        assert!(plan
            .manifest
            .record
            .trust
            .as_ref()
            .and_then(|trust| trust.notes.as_deref())
            .is_some_and(|text| text.contains("Left `repo.build` unset because")));
        assert!(plan
            .evidence_text
            .as_deref()
            .is_some_and(|text| text.contains("conflicting build commands")));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn import_repository_falls_back_to_workflow_commands_when_manifests_are_absent() {
        let root = temp_dir("import-workflow-commands");
        fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir created");
        fs::write(
            root.join("README.md"),
            "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
        )
        .expect("README written");
        fs::write(
            root.join(".github/workflows/ci.yml"),
            r#"name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cargo build --workspace
      - run: cargo test --workspace
"#,
        )
        .expect("workflow written");

        let plan = import_repository(
            &root,
            ImportMode::Overlay,
            Some("https://github.com/example/orbit"),
        )
        .expect("import succeeds");

        assert_eq!(
            plan.manifest.repo.build.as_deref(),
            Some("cargo build --workspace")
        );
        assert_eq!(
            plan.manifest.repo.test.as_deref(),
            Some("cargo test --workspace")
        );
        assert_eq!(
            plan.inferred_fields,
            vec!["repo.build".to_string(), "repo.test".to_string()]
        );
        assert_eq!(plan.manifest.record.status, RecordStatus::Inferred);
        assert!(!plan
            .imported_sources
            .iter()
            .any(|path| path == ".github/workflows/ci.yml"));
        assert!(plan
            .manifest
            .record
            .trust
            .as_ref()
            .and_then(|trust| trust.notes.as_deref())
            .is_some_and(
                |text| text.contains("Inferred `repo.build` from `.github/workflows/ci.yml`.")
            ));
        assert!(plan
            .evidence_text
            .as_deref()
            .is_some_and(|text| text.contains(
                "Inferred repo.build from .github/workflows/ci.yml as `cargo build --workspace`."
            )));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn import_repository_keeps_manifest_commands_imported_when_workflow_agrees() {
        let root = temp_dir("import-manifest-workflow-agree");
        fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir created");
        fs::write(
            root.join("README.md"),
            "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
        )
        .expect("README written");
        fs::write(
            root.join("Cargo.toml"),
            "[workspace]\nmembers = [\"crates/orbit\"]\n",
        )
        .expect("Cargo.toml written");
        fs::write(
            root.join(".github/workflows/ci.yml"),
            r#"name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: cargo build --workspace
      - run: cargo test --workspace
"#,
        )
        .expect("workflow written");

        let plan = import_repository(
            &root,
            ImportMode::Overlay,
            Some("https://github.com/example/orbit"),
        )
        .expect("import succeeds");

        assert_eq!(
            plan.manifest.repo.build.as_deref(),
            Some("cargo build --workspace")
        );
        assert_eq!(
            plan.manifest.repo.test.as_deref(),
            Some("cargo test --workspace")
        );
        assert!(plan.inferred_fields.is_empty());
        assert!(plan
            .imported_sources
            .iter()
            .any(|path| path == "Cargo.toml"));
        assert!(!plan
            .imported_sources
            .iter()
            .any(|path| path == ".github/workflows/ci.yml"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn import_repository_leaves_commands_unset_when_manifest_and_workflow_conflict() {
        let root = temp_dir("import-manifest-workflow-conflict");
        fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir created");
        fs::write(
            root.join("README.md"),
            "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
        )
        .expect("README written");
        fs::write(
            root.join("Cargo.toml"),
            "[workspace]\nmembers = [\"crates/orbit\"]\n",
        )
        .expect("Cargo.toml written");
        fs::write(
            root.join(".github/workflows/ci.yml"),
            r#"name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: cargo build
      - run: cargo test
"#,
        )
        .expect("workflow written");

        let plan = import_repository(
            &root,
            ImportMode::Overlay,
            Some("https://github.com/example/orbit"),
        )
        .expect("import succeeds");

        assert_eq!(plan.manifest.repo.build, None);
        assert_eq!(plan.manifest.repo.test, None);
        assert!(plan.inferred_fields.is_empty());
        assert!(!plan
            .imported_sources
            .iter()
            .any(|path| path == "Cargo.toml"));
        assert!(plan
            .manifest
            .record
            .trust
            .as_ref()
            .and_then(|trust| trust.notes.as_deref())
            .is_some_and(|text| text.contains(
                "`Cargo.toml` and `.github/workflows/ci.yml` suggested conflicting build commands"
            )));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn import_repository_leaves_commands_unset_when_workflows_conflict() {
        let root = temp_dir("import-workflow-conflict");
        fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir created");
        fs::write(
            root.join("README.md"),
            "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
        )
        .expect("README written");
        fs::write(
            root.join(".github/workflows/ci.yml"),
            r#"name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: cargo build --workspace
      - run: cargo test --workspace
"#,
        )
        .expect("ci workflow written");
        fs::write(
            root.join(".github/workflows/release.yml"),
            r#"name: Release
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: cargo build
      - run: cargo test
"#,
        )
        .expect("release workflow written");

        let plan = import_repository(
            &root,
            ImportMode::Overlay,
            Some("https://github.com/example/orbit"),
        )
        .expect("import succeeds");

        assert_eq!(plan.manifest.repo.build, None);
        assert_eq!(plan.manifest.repo.test, None);
        assert!(plan.inferred_fields.is_empty());
        assert!(!plan
            .imported_sources
            .iter()
            .any(|path| path.starts_with(".github/workflows/")));
        assert!(plan
            .manifest
            .record
            .trust
            .as_ref()
            .and_then(|trust| trust.notes.as_deref())
            .is_some_and(|text| text.contains(
                "`.github/workflows/ci.yml` and `.github/workflows/release.yml` suggested conflicting build commands"
            )));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn managed_outputs_preserve_unmanaged_readme_content_outside_markers() {
        let root = temp_dir("managed-readme");
        let manifest = parse_manifest(
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
        )
        .expect("manifest parses");
        fs::write(
            root.join("README.md"),
            r#"# Local README

This introduction stays.

<!-- dotrepo:begin id=readme.body -->
Old managed section
<!-- dotrepo:end id=readme.body -->

This footer stays too.
"#,
        )
        .expect("README written");

        let outputs = managed_outputs(&root, &manifest, b"schema = \"dotrepo/v0.1\"")
            .expect("managed outputs render");
        let readme = outputs
            .iter()
            .find(|(path, _)| path == &root.join("README.md"))
            .expect("README output present")
            .1
            .clone();

        assert!(readme.contains("# Local README"));
        assert!(readme.contains("This introduction stays."));
        assert!(readme.contains("<!-- dotrepo:begin id=readme.body -->"));
        assert!(readme.contains("## Overview"));
        assert!(readme.contains("Fast local-first sync engine"));
        assert!(readme.contains("This footer stays too."));
        assert!(!readme.contains("Old managed section"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn managed_outputs_do_not_overwrite_unmanaged_readme_without_markers() {
        let root = temp_dir("unmanaged-readme-skip");
        let manifest = parse_manifest(
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
        )
        .expect("manifest parses");
        fs::write(root.join("README.md"), "# Keep my hand-written README\n")
            .expect("README written");

        let outputs = managed_outputs(&root, &manifest, b"schema = \"dotrepo/v0.1\"")
            .expect("managed outputs render");
        assert!(!outputs
            .iter()
            .any(|(path, _)| path == &root.join("README.md")));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn adopt_managed_surface_preserves_unmanaged_readme_prose() {
        let root = temp_dir("adopt-readme");
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
        )
        .expect(".repo written");
        fs::write(
            root.join("README.md"),
            "# Local README\n\nThis introduction stays.\n",
        )
        .expect("README written");

        let plan = adopt_managed_surface(&root, DoctorSurface::Readme).expect("adoption succeeds");
        assert_eq!(plan.path, root.join("README.md"));
        assert!(plan.contents.contains("# Local README"));
        assert!(plan.contents.contains("This introduction stays."));
        assert!(plan
            .contents
            .contains("<!-- dotrepo:begin id=readme.body -->"));
        assert!(plan.contents.contains("## Overview"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn adopt_managed_surface_refuses_missing_supported_file() {
        let root = temp_dir("adopt-missing");
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"

[owners]
security_contact = "security@example.com"

[compat.github]
security = "generate"
"#,
        )
        .expect(".repo written");

        let err =
            adopt_managed_surface(&root, DoctorSurface::Security).expect_err("missing should fail");
        assert!(err
            .to_string()
            .contains("manage --adopt` only converts existing files"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn managed_outputs_preserve_unmanaged_security_content_outside_markers() {
        let root = temp_dir("managed-security");
        let manifest = parse_manifest(
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"

[owners]
security_contact = "security@example.com"

[compat.github]
security = "generate"
"#,
        )
        .expect("manifest parses");
        fs::create_dir_all(root.join(".github")).expect(".github dir created");
        fs::write(
            root.join(".github/SECURITY.md"),
            r#"Intro stays.

<!-- dotrepo:begin id=security.body -->
old security block
<!-- dotrepo:end id=security.body -->

Footer stays.
"#,
        )
        .expect("SECURITY written");

        let outputs = managed_outputs(&root, &manifest, b"schema = \"dotrepo/v0.1\"")
            .expect("managed outputs render");
        let security = outputs
            .iter()
            .find(|(path, _)| path == &root.join(".github/SECURITY.md"))
            .expect("SECURITY output present")
            .1
            .clone();

        assert!(security.contains("Intro stays."));
        assert!(security.contains("# Security"));
        assert!(security.contains("Please report vulnerabilities to security@example.com."));
        assert!(security.contains("Footer stays."));
        assert!(!security.contains("old security block"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn managed_outputs_preserve_unmanaged_contributing_content_outside_markers() {
        let root = temp_dir("managed-contributing");
        let manifest = parse_manifest(
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
build = "cargo build"
test = "cargo test"

[owners]
security_contact = "security@example.com"

[compat.github]
contributing = "generate"
"#,
        )
        .expect("manifest parses");
        fs::write(
            root.join("CONTRIBUTING.md"),
            r#"Local preface.

<!-- dotrepo:begin id=contributing.body -->
old contributing block
<!-- dotrepo:end id=contributing.body -->

Local footer.
"#,
        )
        .expect("CONTRIBUTING written");

        let outputs = managed_outputs(&root, &manifest, b"schema = \"dotrepo/v0.1\"")
            .expect("managed outputs render");
        let contributing = outputs
            .iter()
            .find(|(path, _)| path == &root.join("CONTRIBUTING.md"))
            .expect("CONTRIBUTING output present")
            .1
            .clone();

        assert!(contributing.contains("Local preface."));
        assert!(contributing.contains("# Contributing"));
        assert!(contributing.contains("Run `cargo build` before submitting changes."));
        assert!(contributing.contains("Run `cargo test` before submitting changes."));
        assert!(contributing.contains("Local footer."));
        assert!(!contributing.contains("old contributing block"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn managed_outputs_fail_on_malformed_nested_regions() {
        let root = temp_dir("managed-malformed");
        let manifest = parse_manifest(
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
        )
        .expect("manifest parses");
        fs::write(
            root.join("README.md"),
            r#"<!-- dotrepo:begin id=readme.body -->
<!-- dotrepo:begin id=security.body -->
bad nesting
<!-- dotrepo:end id=security.body -->
<!-- dotrepo:end id=readme.body -->
"#,
        )
        .expect("README written");

        let err = managed_outputs(&root, &manifest, b"schema = \"dotrepo/v0.1\"")
            .expect_err("nested regions should fail");
        assert!(err
            .to_string()
            .contains("nested or overlapping managed regions"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn managed_outputs_accept_whitespace_variation_in_markers() {
        let root = temp_dir("managed-whitespace");
        let manifest = parse_manifest(
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
        )
        .expect("manifest parses");
        fs::write(
            root.join("README.md"),
            r#"Local preface.

<!--   dotrepo:begin   id = readme.body   -->
stale managed content
<!--dotrepo:end id = readme.body-->

Local footer.
"#,
        )
        .expect("README written");

        let outputs = managed_outputs(&root, &manifest, b"schema = \"dotrepo/v0.1\"")
            .expect("managed outputs render");
        let readme = outputs
            .iter()
            .find(|(path, _)| path == &root.join("README.md"))
            .expect("README output present")
            .1
            .clone();

        assert!(readme.contains("Local preface."));
        assert!(readme.contains("## Overview"));
        assert!(readme.contains("Local footer."));
        assert!(!readme.contains("stale managed content"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn managed_outputs_reject_overlay_records() {
        let root = temp_dir("overlay-managed-outputs");
        let manifest = parse_manifest(
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["imported"]

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
        )
        .expect("manifest parses");

        let err = managed_outputs(&root, &manifest, b"schema = \"dotrepo/v0.1\"")
            .expect_err("overlay records should not render managed outputs");
        assert!(err
            .to_string()
            .contains("generate is only supported for native records"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn parse_managed_marker_rejects_extra_tokens() {
        assert_eq!(
            parse_managed_marker("<!-- dotrepo:begin id=readme.body -->", "begin").as_deref(),
            Some("readme.body")
        );
        assert_eq!(
            parse_managed_marker("<!-- dotrepo:begin id = readme.body -->", "begin").as_deref(),
            Some("readme.body")
        );
        assert_eq!(
            parse_managed_marker("<!-- dotrepo:begin id=readme.body trailing -->", "begin"),
            None
        );
        assert_eq!(
            parse_managed_marker("<!-- dotrepo:begin -->", "begin"),
            None
        );
    }

    #[test]
    fn generate_check_repository_detects_drift_inside_managed_regions() {
        let root = temp_dir("managed-stale");
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
        )
        .expect("manifest written");
        fs::write(
            root.join("README.md"),
            r#"Preface.

<!-- dotrepo:begin id=readme.body -->
stale managed content
<!-- dotrepo:end id=readme.body -->
"#,
        )
        .expect("README written");

        let report = generate_check_repository(&root).expect("generate check succeeds");
        assert!(report.stale.iter().any(|path| path == "README.md"));
        let readme = report
            .outputs
            .iter()
            .find(|output| output.path == "README.md")
            .expect("README output present");
        assert!(readme.stale);
        assert!(readme.expected.contains("## Overview"));
        assert!(readme
            .current
            .as_ref()
            .expect("current content included")
            .contains("stale managed content"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn generate_check_repository_does_not_flag_unmanaged_readme() {
        let root = temp_dir("unmanaged-generate-check");
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
        )
        .expect("manifest written");
        fs::write(root.join("README.md"), "# Keep my hand-written README\n")
            .expect("README written");

        let report = generate_check_repository(&root).expect("generate check succeeds");
        let readme = report
            .outputs
            .iter()
            .find(|output| output.path == "README.md")
            .expect("README output present");
        assert_eq!(readme.state, ManagedFileState::Unmanaged);
        assert!(!readme.stale);
        assert!(report.stale.is_empty());

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn generate_check_repository_rejects_overlay_records() {
        let root = temp_dir("overlay-generate-check");
        fs::write(
            root.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/orbit"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
        )
        .expect("record written");

        let err = generate_check_repository(&root)
            .expect_err("overlay records should not run generate-check");
        assert!(err
            .to_string()
            .contains("generate-check is only supported for native records"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn inspect_surface_states_reports_supported_and_unsupported_surfaces() {
        let root = temp_dir("doctor");
        fs::write(root.join("README.md"), "# Existing README\n").expect("README written");
        fs::create_dir_all(root.join(".github")).expect(".github created");
        fs::write(root.join(".github/CODEOWNERS"), "* @alice\n").expect("CODEOWNERS written");

        let findings = inspect_surface_states(&root).expect("doctor findings");
        assert_eq!(findings.len(), 2);
        assert_eq!(findings[0].path, PathBuf::from("README.md"));
        assert_eq!(findings[0].state, ManagedFileState::Unmanaged);
        assert_eq!(findings[1].path, PathBuf::from(".github/CODEOWNERS"));
        assert_eq!(findings[1].state, ManagedFileState::Unsupported);

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn inspect_surface_states_reports_partially_managed_and_malformed_files() {
        let root = temp_dir("doctor-partial");
        fs::create_dir_all(root.join(".github")).expect(".github created");
        fs::write(
            root.join("README.md"),
            r#"Intro

<!-- dotrepo:begin id=readme.body -->
managed
<!-- dotrepo:end id=readme.body -->
"#,
        )
        .expect("README written");
        fs::write(
            root.join(".github/SECURITY.md"),
            r#"<!-- dotrepo:begin id=security.body -->
broken
"#,
        )
        .expect("SECURITY written");

        let findings = inspect_surface_states(&root).expect("doctor findings");
        assert_eq!(findings[0].path, PathBuf::from("README.md"));
        assert_eq!(findings[0].state, ManagedFileState::PartiallyManaged);
        assert_eq!(findings[1].path, PathBuf::from(".github/SECURITY.md"));
        assert_eq!(findings[1].state, ManagedFileState::MalformedManaged);

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn inspect_surface_states_treats_partially_managed_readme_as_honest() {
        let root = temp_dir("doctor-partial-readme");
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "reviewed"

[repo]
name = "example"
description = "Example project"

[readme]
title = "Example"
"#,
        )
        .expect(".repo written");
        fs::write(
            root.join("README.md"),
            r#"Project-specific introduction.

<!-- dotrepo:begin id=readme.body -->
managed
<!-- dotrepo:end id=readme.body -->

Repository-specific footer.
"#,
        )
        .expect("README written");

        let findings = inspect_surface_states(&root).expect("doctor findings");
        let readme = findings
            .iter()
            .find(|finding| finding.surface == DoctorSurface::Readme)
            .expect("readme finding present");

        assert_eq!(readme.state, ManagedFileState::PartiallyManaged);
        assert_eq!(
            readme.ownership_honesty,
            Some(DoctorOwnershipHonesty::Honest)
        );
        assert_eq!(
            readme.recommended_mode,
            Some(DoctorRecommendedMode::PartiallyManaged)
        );
        assert_eq!(readme.would_drop_unmanaged_content, Some(false));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn inspect_surface_states_flags_lossy_contributing_generation() {
        let root = temp_dir("doctor-lossy-contributing");
        fs::create_dir_all(root.join(".github")).expect(".github created");
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "reviewed"

[repo]
name = "example"
description = "Example project"
build = "cargo build --locked"
test = "cargo nextest run --locked"

[owners]
maintainers = ["@alice"]
security_contact = "security@example.com"

[compat.github]
contributing = "generate"
"#,
        )
        .expect(".repo written");
        fs::write(
            root.join("CONTRIBUTING.md"),
            r#"# Contributing

Read this repository-specific guide before opening a pull request.

## Local workflow

- Use the internal bootstrap script.
- Coordinate releases in the maintainer chat before tagging.
"#,
        )
        .expect("CONTRIBUTING written");

        let findings = inspect_surface_states(&root).expect("doctor findings");
        let contributing = findings
            .iter()
            .find(|finding| finding.surface == DoctorSurface::Contributing)
            .expect("contributing finding present");

        assert_eq!(contributing.state, ManagedFileState::Unmanaged);
        assert_eq!(contributing.declared_mode, Some(CompatMode::Generate));
        assert_eq!(
            contributing.ownership_honesty,
            Some(DoctorOwnershipHonesty::LossyFullGeneration)
        );
        assert_eq!(
            contributing.recommended_mode,
            Some(DoctorRecommendedMode::PartiallyManaged)
        );
        assert_eq!(contributing.would_drop_unmanaged_content, Some(true));
        assert_eq!(
            contributing.renderer_coverage,
            Some(DoctorRendererCoverage::StubOnly)
        );
        assert!(contributing.supports_managed_regions);
        assert!(contributing.message.contains("declared as fully generated"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn inspect_surface_states_treats_partially_managed_security_as_honest() {
        let root = temp_dir("doctor-partial-security");
        fs::create_dir_all(root.join(".github")).expect(".github created");
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "reviewed"

[repo]
name = "example"
description = "Example project"

[owners]
maintainers = ["@alice"]
security_contact = "security@example.com"

[compat.github]
security = "generate"
"#,
        )
        .expect(".repo written");
        fs::write(
            root.join(".github/SECURITY.md"),
            r#"Project-specific introduction.

<!-- dotrepo:begin id=security.body -->
managed
<!-- dotrepo:end id=security.body -->

Repository-specific disclosure notes.
"#,
        )
        .expect("SECURITY written");

        let findings = inspect_surface_states(&root).expect("doctor findings");
        let security = findings
            .iter()
            .find(|finding| finding.surface == DoctorSurface::Security)
            .expect("security finding present");

        assert_eq!(security.state, ManagedFileState::PartiallyManaged);
        assert_eq!(security.declared_mode, Some(CompatMode::Generate));
        assert_eq!(
            security.ownership_honesty,
            Some(DoctorOwnershipHonesty::Honest)
        );
        assert_eq!(
            security.recommended_mode,
            Some(DoctorRecommendedMode::PartiallyManaged)
        );
        assert_eq!(security.would_drop_unmanaged_content, Some(false));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn inspect_surface_states_flags_lossy_pull_request_template_generation() {
        let root = temp_dir("doctor-lossy-pr-template");
        fs::create_dir_all(root.join(".github")).expect(".github created");
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "reviewed"

[repo]
name = "example"
description = "Example project"
test = "cargo nextest run --locked"

[compat.github]
pull_request_template = "generate"
"#,
        )
        .expect(".repo written");
        fs::write(
            root.join(".github/pull_request_template.md"),
            r#"## Type of change

- [ ] Feature
- [ ] Fix

## Repo-specific checks

- [ ] Mention the rollout plan.
"#,
        )
        .expect("PR template written");

        let findings = inspect_surface_states(&root).expect("doctor findings");
        let pr_template = findings
            .iter()
            .find(|finding| finding.surface == DoctorSurface::PullRequestTemplate)
            .expect("PR template finding present");

        assert_eq!(pr_template.state, ManagedFileState::Unsupported);
        assert_eq!(pr_template.declared_mode, Some(CompatMode::Generate));
        assert_eq!(
            pr_template.ownership_honesty,
            Some(DoctorOwnershipHonesty::LossyFullGeneration)
        );
        assert_eq!(
            pr_template.recommended_mode,
            Some(DoctorRecommendedMode::Skip)
        );
        assert_eq!(pr_template.would_drop_unmanaged_content, Some(true));
        assert!(!pr_template.supports_managed_regions);
        assert!(pr_template
            .message
            .contains("partial management is not supported"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn load_manifest_from_root_falls_back_to_record_toml() {
        let root = temp_dir("overlay");
        fs::write(
            root.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://example.com/repo"

[record.trust]
confidence = "medium"
provenance = ["imported"]

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
        )
        .expect("record written");

        let manifest = load_manifest_from_root(&root).expect("manifest loads from record.toml");
        assert_eq!(manifest.repo.name, "orbit");

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn load_manifest_document_returns_path_and_raw_bytes() {
        let root = temp_dir("document");
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
        )
        .expect("manifest written");

        let document = load_manifest_document(&root).expect("document loads");
        assert_eq!(document.path, root.join(".repo"));
        assert!(!document.raw.is_empty());
        assert_eq!(document.manifest.repo.name, "orbit");

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn github_outputs_generate_remaining_compat_files() {
        let manifest = parse_manifest(
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
build = "cargo build"
test = "cargo test"

[owners]
security_contact = "security@example.com"

[compat.github]
codeowners = "skip"
security = "skip"
contributing = "generate"
pull_request_template = "generate"
"#,
        )
        .expect("manifest parses");

        let outputs = github_outputs(&manifest, b"schema = \"dotrepo/v0.1\"");
        assert!(outputs
            .iter()
            .any(|(path, _)| path == Path::new("CONTRIBUTING.md")));
        assert!(outputs
            .iter()
            .any(|(path, _)| path == Path::new(".github/pull_request_template.md")));
    }

    #[test]
    fn import_repository_bootstraps_native_manifest_from_conventional_files() {
        let root = temp_dir("import-native");
        fs::write(
            root.join("README.md"),
            "# Orbit\n\nFast local-first sync engine.\n",
        )
        .expect("README written");
        fs::create_dir_all(root.join(".github")).expect(".github created");
        fs::write(root.join(".github/CODEOWNERS"), "* @orbit-maintainer\n")
            .expect("CODEOWNERS written");
        fs::write(
            root.join(".github/SECURITY.md"),
            "Report vulnerabilities to security@example.com.\n",
        )
        .expect("SECURITY written");

        let plan =
            import_repository(&root, ImportMode::Native, None).expect("native import succeeds");

        assert_eq!(plan.manifest.record.mode, RecordMode::Native);
        assert_eq!(plan.manifest.record.status, RecordStatus::Draft);
        assert_eq!(plan.manifest.repo.name, "Orbit");
        assert_eq!(
            plan.manifest.repo.description,
            "Fast local-first sync engine."
        );
        assert_eq!(
            plan.manifest
                .owners
                .as_ref()
                .expect("owners imported")
                .maintainers,
            vec!["@orbit-maintainer"]
        );
        assert_eq!(
            plan.manifest
                .owners
                .as_ref()
                .and_then(|owners| owners.security_contact.as_deref()),
            Some("security@example.com")
        );
        assert_eq!(plan.imported_sources.len(), 3);
        assert!(plan.evidence_text.is_none());
        let github = plan
            .manifest
            .compat
            .as_ref()
            .and_then(|compat| compat.github.as_ref())
            .expect("github compat present");
        assert_eq!(github.codeowners, Some(CompatMode::Generate));
        assert_eq!(github.security, Some(CompatMode::Skip));
        assert_eq!(github.contributing, Some(CompatMode::Skip));
        assert_eq!(github.pull_request_template, Some(CompatMode::Skip));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn import_repository_enables_generate_only_for_reproducible_surfaces() {
        let root = temp_dir("import-native-reproducible");
        fs::write(
            root.join("README.md"),
            "# Orbit\n\nFast local-first sync engine.\n",
        )
        .expect("README written");
        fs::create_dir_all(root.join(".github")).expect(".github created");
        fs::write(root.join(".github/CODEOWNERS"), "* @orbit-maintainer\n")
            .expect("CODEOWNERS written");
        fs::write(
            root.join(".github/SECURITY.md"),
            "# Security\n\nPlease report vulnerabilities to security@example.com.\n",
        )
        .expect("SECURITY written");
        fs::write(
            root.join("CONTRIBUTING.md"),
            "# Contributing\n\nThanks for contributing to Orbit.\n\n## Before you open a change\n\n- Review the repository documentation and policies.\n\n## Security\n\nReport suspected vulnerabilities to security@example.com instead of opening a public issue.\n",
        )
        .expect("CONTRIBUTING written");
        fs::write(
            root.join(".github/pull_request_template.md"),
            "## Summary\n\n- Describe the user-visible change.\n\n## Validation\n\n- [ ] Describe how you validated this change.\n\n## Checklist\n\n- [ ] Documentation updated where needed.\n- [ ] Ownership, policy, and security impacts considered.\n",
        )
        .expect("PR template written");

        let plan =
            import_repository(&root, ImportMode::Native, None).expect("native import succeeds");

        let github = plan
            .manifest
            .compat
            .as_ref()
            .and_then(|compat| compat.github.as_ref())
            .expect("github compat present");
        assert_eq!(github.codeowners, Some(CompatMode::Generate));
        assert_eq!(github.security, Some(CompatMode::Generate));
        assert_eq!(github.contributing, Some(CompatMode::Generate));
        assert_eq!(github.pull_request_template, Some(CompatMode::Generate));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn import_repository_keeps_richer_surfaces_at_skip() {
        let root = temp_dir("import-native-rich");
        fs::write(
            root.join("README.md"),
            "# Orbit\n\nFast local-first sync engine.\n",
        )
        .expect("README written");
        fs::create_dir_all(root.join(".github")).expect(".github created");
        fs::write(
            root.join(".github/CODEOWNERS"),
            "* @orbit-maintainer\n/docs/ @docs-team\n",
        )
        .expect("CODEOWNERS written");
        fs::write(
            root.join(".github/SECURITY.md"),
            "# Security\n\nReport vulnerabilities to security@example.com.\n\nSee docs/security.md for the full disclosure policy.\n",
        )
        .expect("SECURITY written");
        fs::write(
            root.join("CONTRIBUTING.md"),
            "# Contributing\n\nUse the repository-specific release checklist before opening a change.\n",
        )
        .expect("CONTRIBUTING written");
        fs::write(
            root.join(".github/pull_request_template.md"),
            "## Type of change\n\n- [ ] Feature\n- [ ] Fix\n",
        )
        .expect("PR template written");

        let plan =
            import_repository(&root, ImportMode::Native, None).expect("native import succeeds");

        let github = plan
            .manifest
            .compat
            .as_ref()
            .and_then(|compat| compat.github.as_ref())
            .expect("github compat present");
        assert_eq!(github.codeowners, Some(CompatMode::Skip));
        assert_eq!(github.security, Some(CompatMode::Skip));
        assert_eq!(github.contributing, Some(CompatMode::Skip));
        assert_eq!(github.pull_request_template, Some(CompatMode::Skip));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn import_repository_marks_overlay_fallbacks_as_inferred() {
        let root = temp_dir("import-overlay");

        let plan = import_repository(
            &root,
            ImportMode::Overlay,
            Some("https://github.com/example/project"),
        )
        .expect("overlay import succeeds");

        assert_eq!(plan.manifest.record.mode, RecordMode::Overlay);
        assert_eq!(plan.manifest.record.status, RecordStatus::Inferred);
        assert_eq!(
            plan.manifest
                .record
                .trust
                .as_ref()
                .expect("trust present")
                .provenance,
            vec!["inferred"]
        );
        assert!(plan
            .evidence_text
            .as_deref()
            .expect("evidence present")
            .contains("Inferred fallback values"));
        assert!(plan
            .inferred_fields
            .iter()
            .any(|field| field == "repo.name"));
        assert!(plan.manifest.compat.is_none());

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn parse_codeowners_metadata_prefers_repo_wide_team_over_narrower_team_rules() {
        let metadata = parse_codeowners_metadata(
            "* @maintainer @org/release-team security@example.com\n/docs/ @org/docs-team\n*.rs @maintainer\n",
        );

        assert_eq!(
            metadata.owners,
            vec![
                "@maintainer",
                "@org/release-team",
                "security@example.com",
                "@org/docs-team",
            ]
        );
        assert_eq!(metadata.team.as_deref(), Some("@org/release-team"));
        assert!(metadata.note.as_deref().is_some_and(
            |note| note.contains("prefers `@org/release-team` from the repo-wide rule")
        ));
    }

    #[test]
    fn parse_codeowners_metadata_keeps_team_unset_when_broad_ownership_is_ambiguous() {
        let metadata = parse_codeowners_metadata(
            "* @org/platform-team @org/release-team @alice\n/docs/ @org/docs-team\n/services/payments/ @org/payments-team\n",
        );

        assert_eq!(
            metadata.owners,
            vec![
                "@org/platform-team",
                "@org/release-team",
                "@alice",
                "@org/docs-team",
                "@org/payments-team",
            ]
        );
        assert_eq!(metadata.team, None);
        assert!(metadata
            .note
            .as_deref()
            .is_some_and(|note| note.contains("`owners.team` was left unset")));
    }

    #[test]
    fn parse_security_contact_supports_reference_links_html_anchors_and_mailto_queries() {
        assert_eq!(
            parse_security_contact(
                "Please report vulnerabilities through our [security mailbox][security-mailbox].\n\n[security-mailbox]: mailto:security@example.com\n",
            )
            .as_deref(),
            Some("security@example.com")
        );
        assert_eq!(
            parse_security_contact(
                "For responsible disclosure, contact <a href=\"mailto:security@example.com\">the security team</a>.\n",
            )
            .as_deref(),
            Some("security@example.com")
        );
        assert_eq!(
            parse_security_contact(
                "Report vulnerabilities through our [security desk](mailto:security@example.com?subject=Security%20Report).\n",
            )
            .as_deref(),
            Some("security@example.com")
        );
        assert_eq!(
            parse_security_contact(
                "Please report it to us at [https://msrc.microsoft.com/create-report](https://aka.ms/security.md/msrc/create-report).\n",
            )
            .as_deref(),
            Some("https://msrc.microsoft.com/create-report")
        );
        assert_eq!(
            parse_security_contact(
                "If you believe you have found a security vulnerability that meets [Microsoft's definition of a security vulnerability](https://aka.ms/security.md/definition), please report it to us as described below.\n\n## Reporting Security Issues\nPlease report it to us at [https://msrc.microsoft.com/create-report](https://aka.ms/security.md/msrc/create-report).\n",
            )
            .as_deref(),
            Some("https://msrc.microsoft.com/create-report")
        );
    }

    #[test]
    fn parse_security_import_metadata_marks_policy_urls_as_partial_security_channels() {
        let metadata = parse_security_import_metadata(
            "Please use https://example.com/security for coordinated disclosure.\n",
        );

        assert_eq!(
            metadata.contact.as_deref(),
            Some("https://example.com/security")
        );
        assert!(metadata.note.as_deref().is_some_and(
            |note| note.contains("policy or reporting URL rather than a direct mailbox")
        ));
    }

    #[test]
    fn parse_security_contact_prefers_reporting_url_over_redirect_destination() {
        assert_eq!(
            parse_security_contact(
                "Please report vulnerabilities via [https://msrc.microsoft.com/create-report](https://aka.ms/security.md/msrc/create-report).\n",
            )
            .as_deref(),
            Some("https://msrc.microsoft.com/create-report")
        );
    }

    #[test]
    fn parse_security_contact_preserves_unicode_context_around_links() {
        assert_eq!(
            parse_security_contact(
                "Pour un signalement sécurité, utilisez [security@example.com](mailto:security@example.com?subject=Rapport%20sécurité).\n",
            )
            .as_deref(),
            Some("security@example.com")
        );
    }

    #[test]
    fn validate_manifest_diagnostics_accumulates_multiple_errors() {
        let root = temp_dir("validate-many");
        let manifest = parse_manifest(
            r#"
schema = "dotrepo/v9.9"

[record]
mode = "overlay"
status = "imported"

[repo]
name = "   "
description = "Broken overlay"
"#,
        )
        .expect("manifest parses");

        let diagnostics = validate_manifest_diagnostics(&root, &manifest);
        assert!(diagnostics.len() >= 3);
        assert!(diagnostics
            .iter()
            .any(|diagnostic| diagnostic.message.contains("unsupported schema")));
        assert!(diagnostics
            .iter()
            .any(|diagnostic| diagnostic.message.contains("repo.name must not be empty")));
        assert!(diagnostics
            .iter()
            .any(|diagnostic| diagnostic.message.contains("record.source must be set")));
        assert!(diagnostics
            .iter()
            .any(|diagnostic| diagnostic.message.contains("record.trust must be set")));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn validate_index_root_accepts_seed_overlay_layout() {
        let root = temp_dir("index");
        let record_dir = root.join("repos/github.com/BurntSushi/ripgrep");
        fs::create_dir_all(&record_dir).expect("record dir created");
        fs::write(
            record_dir.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://github.com/BurntSushi/ripgrep"

[record.trust]
confidence = "medium"
provenance = ["imported"]

[repo]
name = "ripgrep"
description = "Line-oriented search tool"
homepage = "https://github.com/BurntSushi/ripgrep"
"#,
        )
        .expect("record written");
        fs::write(
            record_dir.join("evidence.md"),
            "# Evidence\n\n- imported from the upstream repository homepage.\n",
        )
        .expect("evidence written");

        let findings = validate_index_root(&root).expect("index validates");
        assert!(findings.is_empty());

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn validate_index_root_reports_path_mismatches_and_missing_evidence() {
        let root = temp_dir("index-bad");
        let record_dir = root.join("repos/github.com/ripgrep/ripgrep");
        fs::create_dir_all(&record_dir).expect("record dir created");
        fs::write(
            record_dir.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://github.com/BurntSushi/ripgrep"

[record.trust]
confidence = "medium"
provenance = ["imported"]

[repo]
name = "ripgrep"
description = "Line-oriented search tool"
homepage = "https://github.com/BurntSushi/ripgrep"
"#,
        )
        .expect("record written");

        let findings = validate_index_root(&root).expect("index validates");
        let error_count = findings
            .iter()
            .filter(|finding| finding.severity == IndexFindingSeverity::Error)
            .count();
        assert_eq!(error_count, 3);
        assert!(findings
            .iter()
            .any(|finding| finding.message.contains("evidence.md")));
        assert!(findings
            .iter()
            .any(|finding| finding.message.contains("record.source resolves")));
        assert!(findings
            .iter()
            .any(|finding| finding.message.contains("repo.homepage resolves")));
        assert!(findings
            .iter()
            .any(|finding| finding.severity == IndexFindingSeverity::Warning));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn validate_index_root_emits_quality_warnings_for_non_reference_vocab() {
        let root = temp_dir("index-warn");
        let record_dir = root.join("repos/github.com/sharkdp/bat");
        fs::create_dir_all(&record_dir).expect("record dir created");
        fs::write(
            record_dir.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://github.com/sharkdp/bat"

[record.trust]
confidence = "very-high"
provenance = ["imported", "maintainer-reviewed"]

[repo]
name = "bat"
description = "A cat clone with wings"
homepage = "https://github.com/sharkdp/bat"
build = "cargo build --locked"
test = "cargo test --locked"

[owners]
security_contact = "unknown"
"#,
        )
        .expect("record written");
        fs::write(
            record_dir.join("evidence.md"),
            "# Evidence\n\n- Imported from the upstream repository.\n",
        )
        .expect("evidence written");

        let findings = validate_index_root(&root).expect("index validates");
        assert!(findings
            .iter()
            .all(|finding| finding.severity == IndexFindingSeverity::Warning));
        assert!(findings.iter().any(|finding| {
            finding
                .message
                .contains("record.trust.confidence uses non-reference vocabulary")
        }));
        assert!(findings.iter().any(|finding| {
            finding
                .message
                .contains("record.trust.provenance includes non-reference value")
        }));
        assert!(findings
            .iter()
            .any(|finding| finding.message.contains("build command")));
        assert!(findings
            .iter()
            .any(|finding| finding.message.contains("test command")));
        assert!(findings
            .iter()
            .any(|finding| finding.message.contains("security_contact = \"unknown\"")));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn validate_index_root_accepts_well_formed_claim_directory() {
        let root = temp_dir("index-claims-ok");
        let record_dir = root.join("repos/github.com/acme/widget");
        let claim_dir = record_dir.join("claims/2026-03-10-maintainer-claim-01");
        fs::create_dir_all(claim_dir.join("events")).expect("claim events dir created");
        fs::write(
            record_dir.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/acme/widget"

[record.trust]
confidence = "medium"
provenance = ["imported", "verified"]

[repo]
name = "widget"
description = "Reviewed overlay"
"#,
        )
        .expect("record written");
        fs::write(
            record_dir.join("evidence.md"),
            "Imported from README and validated against repository surfaces.\n",
        )
        .expect("evidence written");
        fs::write(
            claim_dir.join("claim.toml"),
            r#"
schema = "dotrepo-claim/v0"

[claim]
id = "github.com/acme/widget/2026-03-10-maintainer-claim-01"
kind = "maintainer_authority"
state = "accepted"
created_at = "2026-03-10T14:30:00Z"
updated_at = "2026-03-12T09:15:00Z"

[identity]
host = "github.com"
owner = "acme"
repo = "widget"

[claimant]
display_name = "Acme maintainers"
asserted_role = "maintainer"
contact = "maintainers@acme.dev"

[target]
index_paths = ["repos/github.com/acme/widget/record.toml"]
record_sources = ["https://github.com/acme/widget"]
canonical_repo_url = "https://github.com/acme/widget"

[resolution]
canonical_record_path = ".repo"
canonical_mirror_path = "repos/github.com/acme/widget/record.toml"
result_event = "events/0002-accepted.toml"
"#,
        )
        .expect("claim written");
        fs::write(claim_dir.join("review.md"), "Reviewed.").expect("review written");
        fs::write(
            claim_dir.join("events/0001-submitted.toml"),
            r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 1
kind = "submitted"
timestamp = "2026-03-10T14:30:00Z"
actor = "claimant"

[transition]
from = "draft"
to = "submitted"

[summary]
text = "Submitted claim."
"#,
        )
        .expect("submitted event written");
        fs::write(
            claim_dir.join("events/0002-accepted.toml"),
            r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 2
kind = "accepted"
timestamp = "2026-03-12T09:15:00Z"
actor = "index-reviewer"

[transition]
from = "submitted"
to = "accepted"

[summary]
text = "Accepted claim."

[links]
claim = "../claim.toml"
review_notes = "../review.md"
canonical_record_path = ".repo"
"#,
        )
        .expect("accepted event written");

        let findings = validate_index_root(&root).expect("index validates");
        assert!(
            findings
                .iter()
                .all(|finding| finding.severity != IndexFindingSeverity::Error),
            "unexpected findings: {findings:#?}"
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn validate_index_root_reports_claim_identity_mismatch() {
        let root = temp_dir("index-claims-identity");
        let record_dir = root.join("repos/github.com/acme/widget");
        let claim_dir = record_dir.join("claims/2026-03-10-maintainer-claim-01");
        fs::create_dir_all(claim_dir.join("events")).expect("claim events dir created");
        fs::write(
            claim_dir.join("claim.toml"),
            r#"
schema = "dotrepo-claim/v0"

[claim]
id = "github.com/acme/widget/2026-03-10-maintainer-claim-01"
kind = "maintainer_authority"
state = "submitted"
created_at = "2026-03-10T14:30:00Z"
updated_at = "2026-03-10T14:30:00Z"

[identity]
host = "github.com"
owner = "acme"
repo = "other-widget"

[claimant]
display_name = "Acme maintainers"
asserted_role = "maintainer"

[target]
record_sources = ["https://github.com/acme/widget"]
"#,
        )
        .expect("claim written");
        fs::write(
            claim_dir.join("events/0001-submitted.toml"),
            r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 1
kind = "submitted"
timestamp = "2026-03-10T14:30:00Z"
actor = "claimant"

[transition]
from = "draft"
to = "submitted"

[summary]
text = "Submitted claim."
"#,
        )
        .expect("submitted event written");

        let findings = validate_index_root(&root).expect("index validates");
        assert!(
            findings.iter().any(|finding| finding
                .message
                .contains("claim.identity resolves to github.com/acme/other-widget")),
            "expected claim identity mismatch, found: {findings:#?}"
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn validate_index_root_reports_claim_event_history_errors() {
        let root = temp_dir("index-claims-history");
        let record_dir = root.join("repos/github.com/acme/widget");
        let claim_dir = record_dir.join("claims/2026-03-10-maintainer-claim-01");
        fs::create_dir_all(claim_dir.join("events")).expect("claim events dir created");
        fs::write(
            claim_dir.join("claim.toml"),
            r#"
schema = "dotrepo-claim/v0"

[claim]
id = "github.com/acme/widget/2026-03-10-maintainer-claim-01"
kind = "maintainer_authority"
state = "accepted"
created_at = "2026-03-10T14:30:00Z"
updated_at = "2026-03-12T09:15:00Z"

[identity]
host = "github.com"
owner = "acme"
repo = "widget"

[claimant]
display_name = "Acme maintainers"
asserted_role = "maintainer"

[target]
record_sources = ["https://github.com/acme/widget"]
"#,
        )
        .expect("claim written");
        fs::write(
            claim_dir.join("events/0002-submitted.toml"),
            r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 2
kind = "submitted"
timestamp = "2026-03-10T14:30:00Z"
actor = "claimant"

[transition]
from = "draft"
to = "submitted"

[summary]
text = "Submitted claim."
"#,
        )
        .expect("submitted event written");

        let findings = validate_index_root(&root).expect("index validates");
        assert!(
            findings.iter().any(|finding| finding
                .message
                .contains("claim events must use contiguous sequence numbers starting at 1")),
            "expected sequence error, found: {findings:#?}"
        );
        assert!(
            findings
                .iter()
                .any(|finding| finding.message.contains("claim.state is Accepted")),
            "expected claim state mismatch, found: {findings:#?}"
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    fn temp_dir(label: &str) -> PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock works")
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "dotrepo-{}-{}-{}",
            label,
            std::process::id(),
            unique
        ));
        fs::create_dir_all(&path).expect("temp dir created");
        path
    }

    fn sample_public_freshness() -> PublicFreshness {
        PublicFreshness {
            generated_at: "2026-03-10T18:30:00Z".into(),
            snapshot_digest: "snapshot-123".into(),
            stale_after: Some("2026-03-11T18:30:00Z".into()),
        }
    }
}
