//! Import module data types: reports, plans, verification/scoring records,
//! adjudication payloads, and internal parsing/command metadata structs.
use dotrepo_schema::Manifest;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

use crate::RecordSummary;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ImportMode {
    Native,
    Overlay,
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
    pub field_scores: FieldScoreSummary,
    pub verification_passed: bool,
    pub record: RecordSummary,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ImportOptions {
    pub generated_at: Option<String>,
    /// Optional GitHub snapshot facts (fork state + parent) to enable deterministic
    /// overlay relation discovery for the autonomous path without fabricating links.
    pub github: Option<GitHubSnapshotFacts>,
}

/// GitHub-derived facts available at crawl time for conservative relation discovery.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct GitHubSnapshotFacts {
    pub fork: bool,
    pub parent: Option<String>,
    pub repo_name: Option<String>,
    pub description: Option<String>,
    pub topics: Vec<String>,
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
    pub command_candidates: ImportCommandCandidates,
    pub github: Option<GitHubSnapshotFacts>,
}

#[derive(Debug, Clone, Default)]
pub struct ImportCommandCandidates {
    pub candidates: Vec<CommandCandidateSummary>,
    pub selected_build: Option<CommandCandidateSelection>,
    pub selected_test: Option<CommandCandidateSelection>,
}

#[derive(Debug, Clone)]
pub struct CommandCandidateSummary {
    pub source_path: String,
    pub source_tier: CommandSourceTier,
    pub build: Option<String>,
    pub test: Option<String>,
}

#[derive(Debug, Clone)]
pub struct CommandCandidateSelection {
    pub command: String,
    pub source_path: String,
    pub source_tier: CommandSourceTier,
    pub provenance: ImportedCommandProvenance,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum VerificationSeverity {
    Pass,
    Warning,
    Failure,
}

#[derive(Debug, Clone)]
pub struct VerificationCheck {
    pub check_id: String,
    pub field: String,
    pub severity: VerificationSeverity,
    pub message: String,
}

#[derive(Debug, Clone)]
pub struct CandidateProvenance {
    pub field: String,
    pub source_path: String,
    pub source_tier: CommandSourceTier,
    pub value: Option<String>,
}

#[derive(Debug, Clone)]
pub struct VerificationReport {
    pub checks: Vec<VerificationCheck>,
    pub candidate_provenance: Vec<CandidateProvenance>,
    pub unresolved_fields: Vec<String>,
    pub absent_fields: Vec<String>,
    pub passed: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FieldConfidence {
    HighConfidencePresent,
    MediumConfidencePresent,
    Suspect,
    HighConfidenceAbsent,
    Unresolved,
}

#[derive(Debug, Clone)]
pub struct FieldScore {
    pub field: String,
    pub confidence: FieldConfidence,
    pub source: Option<String>,
    pub value: Option<String>,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FieldScoreSummary {
    pub high_confidence_present: Vec<String>,
    pub medium_confidence_present: Vec<String>,
    pub suspect: Vec<String>,
    pub high_confidence_absent: Vec<String>,
    pub unresolved: Vec<String>,
    pub eligible_for_auto_publish: bool,
}

#[derive(Debug, Clone)]
pub struct FieldScoreReport {
    pub scores: Vec<FieldScore>,
    pub summary: FieldScoreSummary,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AdjudicationCandidate {
    pub value: String,
    pub source_path: String,
    pub source_tier: CommandSourceTier,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AdjudicationRequest {
    pub field: String,
    pub candidates: Vec<AdjudicationCandidate>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AdjudicationModelConfidence {
    High,
    Medium,
    Low,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AdjudicationModelResponse {
    pub field: String,
    pub value: Option<String>,
    pub confidence: AdjudicationModelConfidence,
    pub reason: String,
    pub source: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AdjudicationResult {
    pub field: String,
    pub outcome: AdjudicationOutcome,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AdjudicationOutcome {
    Resolved {
        value: String,
        confidence: FieldConfidence,
        reason: String,
    },
    Absent {
        reason: String,
    },
    Rejected {
        model_value: String,
        reason: String,
    },
}

#[derive(Default)]
pub(crate) struct ReadmeMetadata {
    pub(crate) title: Option<String>,
    pub(crate) description: Option<String>,
    pub(crate) docs_root: Option<String>,
    pub(crate) docs_getting_started: Option<String>,
}

#[derive(Default)]
pub(crate) struct ReadmeDocsMetadata {
    pub(crate) root: Option<String>,
    pub(crate) getting_started: Option<String>,
}

pub(crate) struct ImportedFile {
    pub(crate) path: String,
    pub(crate) contents: String,
}

#[derive(Default)]
pub(crate) struct CodeownersMetadata {
    pub(crate) owners: Vec<String>,
    pub(crate) team: Option<String>,
    pub(crate) note: Option<String>,
}

#[derive(Debug, Clone)]
pub(crate) struct CodeownersRule {
    pub(crate) pattern: String,
    pub(crate) owners: Vec<String>,
    pub(crate) teams: Vec<String>,
}

#[derive(Default)]
pub(crate) struct SecurityImportMetadata {
    pub(crate) contact: Option<String>,
    pub(crate) note: Option<String>,
}

#[derive(Default)]
pub(crate) struct ImportedCommandMetadata {
    pub(crate) build: Option<ImportedCommandSelection>,
    pub(crate) test: Option<ImportedCommandSelection>,
    pub(crate) candidates: Vec<ImportedCommandCandidate>,
    pub(crate) inferred_fields: Vec<String>,
    pub(crate) notes: Vec<String>,
    pub(crate) evidence_bullets: Vec<String>,
}

#[derive(Default)]
pub(crate) struct ImportedToolchainMetadata {
    pub(crate) min: Option<String>,
    pub(crate) ecosystem: Option<String>,
    pub(crate) source_path: Option<String>,
    pub(crate) notes: Vec<String>,
    pub(crate) evidence_bullets: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ImportedCommandProvenance {
    Imported,
    Inferred,
}

#[derive(Debug, Clone)]
pub(crate) struct ImportedCommandSelection {
    pub(crate) command: String,
    pub(crate) source_path: String,
    pub(crate) source_tier: CommandSourceTier,
    pub(crate) provenance: ImportedCommandProvenance,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CommandSourceTier {
    GitHubApi,
    Workflow,
    TaskScript,
    ContribDoc,
    Manifest,
    EcosystemDefault,
}

pub(crate) struct ImportSources<'a> {
    pub(crate) readme: Option<&'a ImportedFile>,
    pub(crate) cargo_toml: Option<&'a ImportedFile>,
    pub(crate) rust_toolchain_toml: Option<&'a ImportedFile>,
    pub(crate) rust_toolchain: Option<&'a ImportedFile>,
    pub(crate) package_json: Option<&'a ImportedFile>,
    pub(crate) pyproject_toml: Option<&'a ImportedFile>,
    pub(crate) setup_py: Option<&'a ImportedFile>,
    pub(crate) setup_cfg: Option<&'a ImportedFile>,
    pub(crate) go_mod: Option<&'a ImportedFile>,
    pub(crate) pom_xml: Option<&'a ImportedFile>,
    pub(crate) maven_wrapper: bool,
    pub(crate) build_gradle: Option<&'a ImportedFile>,
    pub(crate) gradle_wrapper: bool,
    pub(crate) composer_json: Option<&'a ImportedFile>,
    pub(crate) csproj: Option<&'a ImportedFile>,
    pub(crate) solution: Option<&'a ImportedFile>,
    pub(crate) mix_exs: Option<&'a ImportedFile>,
    pub(crate) rebar_config: Option<&'a ImportedFile>,
    pub(crate) cmake_presets_json: Option<&'a ImportedFile>,
    pub(crate) makefile: Option<&'a ImportedFile>,
    pub(crate) justfile: Option<&'a ImportedFile>,
    pub(crate) rakefile: Option<&'a ImportedFile>,
    pub(crate) contributing: Option<&'a ImportedFile>,
    pub(crate) workflow_files: &'a [ImportedFile],
}

#[derive(Debug, Clone)]
pub(crate) struct ImportedCommandCandidate {
    pub(crate) source_path: String,
    pub(crate) source_tier: CommandSourceTier,
    pub(crate) build: Option<String>,
    pub(crate) test: Option<String>,
}
