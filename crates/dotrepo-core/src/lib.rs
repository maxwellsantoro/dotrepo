use anyhow::{anyhow, Result};
use dotrepo_schema::{parse_manifest, CompatMode, Manifest, RecordMode, RecordStatus, Trust};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Arc;

mod adoption;
mod claims;
mod import;
mod promotion;
mod public;
mod query;
mod render;
mod selection;
mod surfaces;
mod synthesis;
mod util;
mod validation;

pub use adoption::{
    adoption_status_repository, canonical_mirror_path_for_claim_path, native_repository_identity,
    render_dotrepo_ci_workflow, validate_claim_path_matches_native_identity,
    AdoptionRepositoryIdentity, AdoptionStatusItem, AdoptionStatusReport,
};
pub use query::{
    manifest_to_json, query_manifest, query_manifest_value, query_manifest_value_from_json,
};
pub use synthesis::{
    generate_basic_synthesis, get_synthesis, load_synthesis_document, load_synthesis_from_root,
    plan_synthesis_write, validate_synthesis, write_synthesis, LoadedSynthesis,
    SynthesisReadReport, SynthesisWritePlan,
};
pub(crate) use util::display_root;
pub(crate) use util::manifest_path;
pub(crate) use util::relative_to_root;
pub(crate) use util::walk_dir_entries;
pub use util::{
    current_timestamp_rfc3339, display_path, identity_from_index_claim_path,
    index_record_mirror_path, normalize_rfc3339, parse_rfc3339, record_status_name, render_rfc3339,
    repository_identity, resolve_workspace_repository_root, source_digest,
    validate_repository_identity_segments,
};

pub(crate) use surfaces::{
    ensure_native_managed_surface_record, inspect_managed_surface, merge_managed_region,
    render_managed_markdown, render_managed_output, render_readme_body, ManagedOutput,
    ManagedSurface,
};

pub use surfaces::adopt_managed_surface;
pub use surfaces::inspect_surface_states;
pub use surfaces::preview_surfaces;
pub use surfaces::render_readme;

pub(crate) use selection::{
    resolve_candidates, resolve_competing_value, resolve_conflict_reason, resolve_selection_reason,
    selected_record,
};

pub use claims::{
    append_claim_event, inspect_claim_directory, load_claim_directory, parse_claim_event,
    parse_claim_record, resolve_claim_directory, scaffold_claim_directory, ClaimEvent,
    ClaimEventAppendInput, ClaimEventAppendPlan, ClaimEventInspection, ClaimEventKind,
    ClaimEventLinks, ClaimEventMetadata, ClaimHandoffOutcome, ClaimIdentity, ClaimInspectionReport,
    ClaimKind, ClaimMetadata, ClaimRecord, ClaimResolution, ClaimScaffoldInput, ClaimScaffoldPlan,
    ClaimState, ClaimSummary, ClaimTarget, ClaimTargetInspection, ClaimTransition, Claimant,
    LoadedClaimDirectory, LoadedClaimEvent, RecordClaimContext,
};

pub use public::{
    build_public_freshness, build_public_freshness_with_digest, current_public_freshness,
    export_public_index_static, export_public_index_static_with_base, index_snapshot_digest,
    list_index_repository_identities, load_public_query_input_snapshot, public_cache_validators,
    public_error_response, public_export_file_manifest, public_profile_compare,
    public_profile_compare_with_base, public_profile_search, public_profile_search_with_base,
    public_query_input_snapshot, public_repository_batch_profiles,
    public_repository_batch_profiles_with_base, public_repository_batch_query,
    public_repository_batch_query_with_base, public_repository_profile,
    public_repository_profile_or_error, public_repository_profile_or_error_with_base,
    public_repository_profile_with_base, public_repository_query,
    public_repository_query_from_input_or_error_with_base,
    public_repository_query_from_input_with_base, public_repository_query_or_error,
    public_repository_query_or_error_with_base, public_repository_query_with_base,
    public_repository_relations, public_repository_relations_with_base, public_repository_summary,
    public_repository_summary_or_error, public_repository_summary_or_error_with_base,
    public_repository_summary_with_base, public_repository_trust, public_repository_trust_or_error,
    public_repository_trust_or_error_with_base, public_repository_trust_with_base,
    public_snapshot_metadata, PublicBatchProfileItem, PublicBatchProfileResponse,
    PublicBatchQueryItem, PublicBatchQueryResponse, PublicCacheValidators, PublicConflictReport,
    PublicErrorCode, PublicErrorDetail, PublicErrorResponse, PublicExportFileEntry,
    PublicExportFileManifest, PublicFreshness, PublicProfileCompareBoolValue,
    PublicProfileCompareItem, PublicProfileCompareResponse, PublicProfileCompareSignals,
    PublicProfileCompareTextValue, PublicProfileSearchAppliedFilters, PublicProfileSearchItem,
    PublicProfileSearchOptions, PublicProfileSearchResponse, PublicQueryInputConflict,
    PublicQueryInputSelection, PublicQueryInputSnapshot, PublicQueryResponse,
    PublicRecordArtifacts, PublicRelationItem, PublicRelationTrust, PublicRelationsResponse,
    PublicRepositoryFields, PublicRepositoryIdentity, PublicRepositoryInventoryEntry,
    PublicRepositoryInventoryResponse, PublicRepositoryLinks, PublicRepositorySummaryResponse,
    PublicResearchCompleteness, PublicResearchDocs, PublicResearchExecution,
    PublicResearchOwnership, PublicResearchProfileResponse, PublicResearchSynthesis,
    PublicResearchSynthesisArchitecture, PublicResearchSynthesisForAgents, PublicResearchTrust,
    PublicSelectedRecord, PublicSelectionReport, PublicSnapshotMetadata, PublicTrustResponse,
    PUBLIC_BATCH_MAX_IDENTITIES, PUBLIC_BATCH_MAX_PATHS, PUBLIC_BATCH_MAX_QUERY_RESULTS,
};

pub use import::{
    adjudicate_requests_deterministic, adopt_overlay_record, apply_adjudication_response,
    apply_adjudication_results, apply_adjudication_to_import_plan, autonomous_writeback_eligible,
    build_adjudication_requests, import_preview_repository, import_repository,
    import_repository_with_options, infer_docs_root_from_external_homepage, run_import_escalation,
    score_import_fields, verify_import_plan, write_import_outputs, AdjudicationCandidate,
    AdjudicationModelConfidence, AdjudicationModelResponse, AdjudicationOutcome,
    AdjudicationProvider, AdjudicationProviderResponse, AdjudicationRequest, AdjudicationResult,
    AdjudicationTier, AdjudicationTierProvider, CandidateProvenance, CommandCandidateSelection,
    CommandCandidateSummary, CommandSourceTier, FieldConfidence, FieldScore, FieldScoreReport,
    FieldScoreSummary, GitHubSnapshotFacts, ImportCommandCandidates, ImportEscalationOptions,
    ImportEscalationReport, ImportMode, ImportOptions, ImportPlan, ImportPreviewReport,
    ImportedCommandProvenance, NoopAdjudicationProvider, StubAdjudicationProvider,
    TieredAdjudicationProviders, VerificationCheck, VerificationReport, VerificationSeverity,
};

pub use promotion::{
    analyze_index_promotion, apply_index_promotions, guard_against_unjustified_downgrade,
    promote_to_verified, score_index_record_for_promotion, DowngradeGuardOutcome,
    PromotionAppliedRecord, PromotionApplyReport, PromotionOutcome, PromotionRecordScore,
    PromotionReport, PromotionSummary,
};

pub use validation::{
    validate_index_root, validate_manifest, validate_manifest_diagnostics, validate_repository,
    IndexFinding, IndexFindingSeverity, RepositoryDiagnostic, ValidateReport, ValidationDiagnostic,
    ValidationDiagnosticSeverity,
};

pub(crate) use render::{
    generated_banner, render_contributing, render_contributing_body, render_pull_request_template,
    render_security_body, CommentStyle,
};

#[cfg(test)]
pub(crate) use public::{search_ranking_from_profile, trust_confidence_boost};

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
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub claim_load_warnings: Vec<String>,
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

#[derive(Debug, Clone)]
pub struct LoadedManifest {
    pub path: PathBuf,
    pub raw: Vec<u8>,
    pub manifest: std::sync::Arc<Manifest>,
}

pub fn load_manifest_document(root: &Path) -> Result<LoadedManifest> {
    let path = manifest_path(root);
    load_manifest_file(&path)
}

fn load_manifest_file(path: &Path) -> Result<LoadedManifest> {
    let raw = fs::read(path).map_err(|e| anyhow!("failed to read {}: {}", path.display(), e))?;
    let text = std::str::from_utf8(&raw)
        .map_err(|e| anyhow!("failed to decode {} as UTF-8: {}", path.display(), e))?;
    let manifest = std::sync::Arc::new(parse_manifest(text)?);
    Ok(LoadedManifest {
        path: path.to_path_buf(),
        raw,
        manifest,
    })
}

pub fn load_manifest_from_root(root: &Path) -> Result<Arc<Manifest>> {
    Ok(Arc::clone(&load_manifest_document(root)?.manifest))
}

pub fn record_summary(manifest: &Manifest) -> RecordSummary {
    RecordSummary {
        mode: manifest.record.mode.clone(),
        status: manifest.record.status.clone(),
        source: manifest.record.source.clone(),
        trust: manifest.record.trust.clone(),
    }
}

/// Resolve a dot-path against the best matching record under `root`.
///
/// # Examples
///
/// ```no_run
/// use dotrepo_core::query_repository;
/// use std::path::Path;
///
/// let report = query_repository(Path::new("examples/native-minimal"), "repo.name")?;
/// assert_eq!(report.path, "repo.name");
/// # Ok::<(), anyhow::Error>(())
/// ```
pub fn query_repository(root: &Path, path: &str) -> Result<QueryReport> {
    let candidates = resolve_candidates(root)?;
    let selected = candidates.first().ok_or_else(|| {
        anyhow!(
            "no repository record candidates found under {}",
            root.display()
        )
    })?;
    let value = query_manifest_value(&selected.manifest, path)?;
    let reason = resolve_selection_reason(&candidates, selected);
    Ok(QueryReport {
        root: display_root(root)?,
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
                value: resolve_competing_value(candidate, path),
                record: selected_record(root, candidate),
            })
            .collect(),
    })
}

/// Return the selected record, selection reason, and competing records for `root`.
///
/// # Examples
///
/// ```no_run
/// use dotrepo_core::trust_repository;
/// use std::path::Path;
///
/// let report = trust_repository(Path::new("examples/native-minimal"))?;
/// assert!(!report.manifest_path.is_empty());
/// # Ok::<(), anyhow::Error>(())
/// ```
pub fn trust_repository(root: &Path) -> Result<TrustReport> {
    let candidates = resolve_candidates(root)?;
    let selected = candidates.first().ok_or_else(|| {
        anyhow!(
            "no repository record candidates found under {}",
            root.display()
        )
    })?;
    let reason = resolve_selection_reason(&candidates, selected);
    let mut claim_load_warnings = Vec::new();
    for candidate in &candidates {
        claim_load_warnings.extend(crate::claims::claim_directory_load_warnings(
            root, candidate,
        ));
    }
    claim_load_warnings.sort();
    claim_load_warnings.dedup();
    Ok(TrustReport {
        root: display_root(root)?,
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
        claim_load_warnings,
    })
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
        root: display_root(root)?,
        checked: rendered_outputs.len(),
        stale,
        outputs: rendered_outputs,
    })
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

fn generate_check_output(
    root: &Path,
    path: PathBuf,
    expected: String,
) -> Result<GenerateCheckOutput> {
    let (current, missing) = match fs::read_to_string(&path) {
        Ok(content) => (content, false),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => (String::new(), true),
        Err(e) => return Err(anyhow!("failed to read {}: {}", path.display(), e)),
    };
    let relative = display_path(root, &path)?;
    let is_stale = current != expected;
    Ok(GenerateCheckOutput {
        path: relative,
        state: if missing {
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
        ManagedFileState::PartiallyManaged => {
            let current = status.current.as_deref().ok_or_else(|| {
                anyhow!(
                    "partially managed file {} is missing current contents",
                    status.path.display()
                )
            })?;
            merge_managed_region(&status.path, surface, current, &body)?
        }
        ManagedFileState::Unmanaged => status.current.clone().ok_or_else(|| {
            anyhow!(
                "unmanaged file {} is missing current contents",
                status.path.display()
            )
        })?,
        _ => full_expected,
    };
    let current = status.current.clone();
    let stale = match status.state {
        ManagedFileState::Missing => true,
        ManagedFileState::FullyGenerated | ManagedFileState::PartiallyManaged => {
            match current.as_deref() {
                None => true,
                Some(current) => current != expected,
            }
        }
        ManagedFileState::Unmanaged => false,
        ManagedFileState::MalformedManaged | ManagedFileState::Unsupported => true,
    };

    Ok(GenerateCheckOutput {
        path: display_path(root, &status.path)?,
        state: status.state,
        stale,
        expected,
        current: if stale { current } else { None },
        message: status.message,
    })
}

#[cfg(test)]
#[path = "facade_tests/mod.rs"]
mod tests;
