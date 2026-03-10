use anyhow::{anyhow, bail, Result};
use dotrepo_schema::{
    parse_manifest, render_manifest, Compat, CompatMode, GitHubCompat, Manifest, Owners, Readme,
    ReadmeCustomSection, Record, RecordMode, RecordStatus, Relations, Repo, Trust,
};
use serde::Serialize;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;
use std::fs;
use std::path::{Path, PathBuf};

const SUPPORTED_SCHEMA: &str = "dotrepo/v0.1";
const GENERATOR_NAME: &str = "dotrepo";
const GENERATOR_VERSION: &str = env!("CARGO_PKG_VERSION");

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

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DoctorFinding {
    pub path: PathBuf,
    pub state: ManagedFileState,
    pub message: String,
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

#[derive(Debug, Clone, Serialize)]
pub struct RecordSummary {
    pub mode: RecordMode,
    pub status: RecordStatus,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub trust: Option<Trust>,
}

#[derive(Debug, Clone, Copy, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SelectionReason {
    OnlyMatchingRecord,
    CanonicalPreferred,
    HigherStatusOverlay,
    EqualAuthorityConflict,
}

#[derive(Debug, Clone, Copy, Serialize)]
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
    manifest: Manifest,
    identity: Option<RepositoryIdentity>,
    rank: u8,
}

pub fn load_manifest_document(root: &Path) -> Result<LoadedManifest> {
    let path = manifest_path(root);
    load_manifest_file(&path)
}

fn load_manifest_file(path: &Path) -> Result<LoadedManifest> {
    let raw = fs::read(&path).map_err(|e| anyhow!("failed to read {}: {}", path.display(), e))?;
    let text = std::str::from_utf8(&raw)
        .map_err(|e| anyhow!("failed to decode {} as UTF-8: {}", path.display(), e))?;
    let manifest = parse_manifest(text)?;
    Ok(LoadedManifest {
        path: path.to_path_buf(),
        raw,
        manifest,
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

fn selected_record(candidate: &CandidateManifest) -> SelectedRecord {
    SelectedRecord {
        manifest_path: candidate.manifest_path.clone(),
        record: record_summary(&candidate.manifest),
    }
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
            record: selected_record(selected),
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
                record: selected_record(candidate),
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
            record: selected_record(selected),
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
                record: selected_record(candidate),
            })
            .collect(),
    })
}

pub fn generate_check_repository(root: &Path) -> Result<GenerateCheckReport> {
    let document = load_manifest_document(root)?;
    validate_manifest(root, &document.manifest)?;
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
    let readme = load_first_existing_file(root, &["README.md"])?;
    let codeowners = load_first_existing_file(root, &[".github/CODEOWNERS", "CODEOWNERS"])?;
    let security = load_first_existing_file(root, &[".github/SECURITY.md", "SECURITY.md"])?;

    let readme_metadata = readme
        .as_ref()
        .map(|file| parse_readme_metadata(&file.contents))
        .unwrap_or_default();
    let codeowners_metadata = codeowners
        .as_ref()
        .map(|file| parse_codeowners_metadata(&file.contents))
        .unwrap_or_default();
    let security_contact = security
        .as_ref()
        .and_then(|file| parse_security_contact(&file.contents))
        .or_else(|| security.as_ref().map(|_| "unknown".into()));

    let mut imported_sources = Vec::new();
    let mut inferred_fields = Vec::new();

    let repo_name = match readme_metadata.title {
        Some(ref title) => {
            note_import(
                &mut imported_sources,
                readme.as_ref().expect("readme exists").path,
            );
            title.clone()
        }
        None => {
            inferred_fields.push("repo.name".into());
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
                readme.as_ref().expect("readme exists").path,
            );
            description.clone()
        }
        None => {
            inferred_fields.push("repo.description".into());
            "Imported repository metadata; review and refine before relying on it.".into()
        }
    };

    if !codeowners_metadata.owners.is_empty() || codeowners_metadata.team.is_some() {
        if let Some(file) = &codeowners {
            note_import(&mut imported_sources, file.path);
        }
    }

    if security_contact.is_some() {
        if let Some(file) = &security {
            note_import(&mut imported_sources, file.path);
        }
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
            generated_at: None,
            trust: Some(Trust {
                confidence: Some(confidence.into()),
                provenance,
                notes: Some(import_notes(mode, &imported_sources, &inferred_fields)),
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
            build: None,
            test: None,
            topics: Vec::new(),
        },
    );
    manifest.owners = build_imported_owners(
        codeowners_metadata.owners,
        codeowners_metadata.team,
        security_contact,
    );
    manifest.readme = match mode {
        ImportMode::Native => Some(Readme {
            title: Some(repo_name),
            tagline: None,
            sections: vec!["overview".into(), "security".into()],
            custom_sections: Default::default(),
        }),
        ImportMode::Overlay => None,
    };
    manifest.compat = match mode {
        ImportMode::Native => Some(Compat {
            github: Some(GitHubCompat {
                codeowners: Some(CompatMode::Skip),
                security: Some(CompatMode::Skip),
                contributing: Some(CompatMode::Skip),
                pull_request_template: Some(CompatMode::Skip),
            }),
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
                &inferred_fields,
                &security,
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
            let target = root.join(path);
            if !target.exists() {
                diagnostics.push(validation_error(
                    "validate_native_paths",
                    format!("referenced path does not exist: {}", target.display()),
                ));
            }
        }
    }

    if let Some(readme) = &manifest.readme {
        for (name, section) in &readme.custom_sections {
            if let Some(path) = &section.path {
                let target = root.join(path);
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
        }
    }

    diagnostics
}

#[derive(Default)]
struct ReadmeMetadata {
    title: Option<String>,
    description: Option<String>,
}

struct ImportedFile {
    path: &'static str,
    contents: String,
}

#[derive(Default)]
struct CodeownersMetadata {
    owners: Vec<String>,
    team: Option<String>,
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
                path: candidate,
                contents,
            }));
        }
    }

    Ok(None)
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

    metadata
}

fn parse_readme_title_line(line: &str) -> Option<String> {
    if line.starts_with('#') {
        let title = line.trim_start_matches('#').trim();
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
    if !matches!(
        lower.as_bytes().get(0..3),
        Some(prefix)
            if prefix == b"<h1"
                || prefix == b"<h2"
                || prefix == b"<h3"
                || prefix == b"<h4"
                || prefix == b"<h5"
                || prefix == b"<h6"
    ) {
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
        || line.starts_with("<!--")
        || line == "---"
        || line.starts_with("- ")
        || line.starts_with("* ")
        || starts_with_ordered_list_item(line)
    {
        return None;
    }

    let description = line.trim_start_matches('>').trim();
    normalize_readme_text(description).filter(|value| value.chars().any(|ch| ch.is_alphanumeric()))
}

fn normalize_readme_text(line: &str) -> Option<String> {
    let stripped = strip_html_tags(line);
    let collapsed = stripped.split_whitespace().collect::<Vec<_>>().join(" ");
    let cleaned = collapsed.trim().trim_matches('`').trim();
    if cleaned.is_empty() {
        None
    } else {
        Some(cleaned.to_string())
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
    let mut teams = Vec::new();

    for line in contents.lines() {
        let trimmed = line.split('#').next().unwrap_or("").trim();
        if trimmed.is_empty() {
            continue;
        }

        let mut tokens = trimmed.split_whitespace();
        let _pattern = tokens.next();
        for token in tokens {
            let cleaned = trim_contact_token(token);
            if cleaned.starts_with('@') || looks_like_email(cleaned) {
                push_unique(&mut owners, cleaned.to_string());
                if is_team_handle(cleaned) {
                    push_unique(&mut teams, cleaned.to_string());
                }
            }
        }
    }

    CodeownersMetadata {
        owners,
        team: match teams.as_slice() {
            [only] => Some(only.clone()),
            _ => None,
        },
    }
}

fn parse_security_contact(contents: &str) -> Option<String> {
    find_mailto_or_email(contents).or_else(|| find_first_url(contents))
}

fn find_mailto_or_email(contents: &str) -> Option<String> {
    for token in contents.split_whitespace() {
        let cleaned = trim_contact_token(token);
        if let Some(value) = cleaned.strip_prefix("mailto:") {
            let value = trim_contact_token(value);
            if looks_like_email(value) {
                return Some(value.to_string());
            }
        }
        if looks_like_email(cleaned) {
            return Some(cleaned.to_string());
        }
    }

    for destination in markdown_link_destinations(contents) {
        let cleaned = trim_contact_token(&destination);
        if let Some(value) = cleaned.strip_prefix("mailto:") {
            let value = trim_contact_token(value);
            if looks_like_email(value) {
                return Some(value.to_string());
            }
        }
        if looks_like_email(cleaned) {
            return Some(cleaned.to_string());
        }
    }

    None
}

fn find_first_url(contents: &str) -> Option<String> {
    for token in contents.split_whitespace() {
        let cleaned = trim_contact_token(token);
        if cleaned.starts_with("https://") || cleaned.starts_with("http://") {
            return Some(cleaned.to_string());
        }
    }

    for destination in markdown_link_destinations(contents) {
        let cleaned = trim_contact_token(&destination);
        if cleaned.starts_with("https://") || cleaned.starts_with("http://") {
            return Some(cleaned.to_string());
        }
    }

    None
}

fn markdown_link_destinations(contents: &str) -> Vec<String> {
    let mut destinations = Vec::new();
    let mut rest = contents;

    while let Some(start) = rest.find("](") {
        let after = &rest[start + 2..];
        let Some(end) = after.find(')') else {
            break;
        };
        let destination = after[..end].trim();
        if !destination.is_empty() {
            destinations.push(destination.to_string());
        }
        rest = &after[end + 1..];
    }

    destinations
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

fn note_import(imported_sources: &mut Vec<String>, path: &'static str) {
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

fn render_import_evidence(
    imported_sources: &[String],
    inferred_fields: &[String],
    security: &Option<ImportedFile>,
) -> String {
    let mut bullets = Vec::new();

    if imported_sources.is_empty() {
        bullets.push(
            "No README.md, CODEOWNERS, or SECURITY.md content was imported; this record needs manual completion."
                .to_string(),
        );
    }

    if imported_sources.iter().any(|path| path == "README.md") {
        bullets.push(readme_import_evidence_bullet(inferred_fields));
    }
    if imported_sources
        .iter()
        .any(|path| path == ".github/CODEOWNERS" || path == "CODEOWNERS")
    {
        bullets.push("Imported maintainer handles from CODEOWNERS.".to_string());
    }
    if imported_sources
        .iter()
        .any(|path| path == ".github/SECURITY.md" || path == "SECURITY.md")
    {
        if security
            .as_ref()
            .and_then(|file| parse_security_contact(&file.contents))
            .is_some()
        {
            bullets.push("Imported the security contact from SECURITY.md.".to_string());
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

    bullets.push("This is an overlay record, not a maintainer-controlled canonical record.".into());

    let mut out = String::from("# Evidence\n\n");
    for bullet in bullets {
        out.push_str("- ");
        out.push_str(&bullet);
        out.push('\n');
    }
    out
}

fn readme_import_evidence_bullet(inferred_fields: &[String]) -> String {
    let imported_name = !inferred_fields.iter().any(|field| field == "repo.name");
    let imported_description = !inferred_fields
        .iter()
        .any(|field| field == "repo.description");

    match (imported_name, imported_description) {
        (true, true) => "Imported repository name and description from README.md.".to_string(),
        (true, false) => "Imported repository name from README.md.".to_string(),
        (false, true) => "Imported repository description from README.md.".to_string(),
        (false, false) => "Imported repository metadata from README.md.".to_string(),
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

pub fn inspect_surface_states(root: &Path) -> Result<Vec<DoctorFinding>> {
    let mut findings = Vec::new();

    for surface in [
        ManagedSurface::Readme,
        ManagedSurface::Security,
        ManagedSurface::Contributing,
    ] {
        let status = inspect_managed_surface(root, surface)?;
        if status.state == ManagedFileState::Missing {
            continue;
        }
        findings.push(DoctorFinding {
            path: relative_or_absolute(root, &status.path),
            state: status.state,
            message: status
                .message
                .unwrap_or_else(|| default_state_message(status.state)),
        });
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
                    findings.push(DoctorFinding {
                        path: PathBuf::from(relative),
                        state: ManagedFileState::Unsupported,
                        message: "conventional surface exists outside the managed-region contract for this file; keep it unmanaged or convert it to a fully generated dotrepo surface".into(),
                    });
                }
            }
            Err(err) => findings.push(DoctorFinding {
                path: PathBuf::from(relative),
                state: ManagedFileState::Unsupported,
                message: format!("could not be read during doctor scan: {}", err),
            }),
        }
    }

    Ok(findings)
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

    let mut findings = Vec::new();
    for record_dir in record_dirs {
        let display_path = record_dir
            .strip_prefix(index_root)
            .unwrap_or(&record_dir)
            .join("record.toml");

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

        findings.extend(validate_index_entry(
            index_root,
            &record_dir,
            &document.manifest,
        ));
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
        let target = root.join(path);
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
        trimmed.starts_with("<!-- dotrepo:begin id=") || trimmed.starts_with("<!-- dotrepo:end id=")
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
    let prefix = format!("<!-- dotrepo:{} id=", kind);
    let value = line.strip_prefix(&prefix)?.strip_suffix(" -->")?;
    if value.is_empty() {
        None
    } else {
        Some(value.to_string())
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
    fn inspect_surface_states_reports_supported_and_unsupported_surfaces() {
        let root = temp_dir("doctor");
        fs::write(root.join("README.md"), "# Existing README\n").expect("README written");
        fs::create_dir_all(root.join(".github")).expect(".github created");
        fs::write(
            root.join(".github/CODEOWNERS"),
            "* @alice\n",
        )
        .expect("CODEOWNERS written");

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

        fs::remove_dir_all(root).expect("temp dir removed");
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
}
