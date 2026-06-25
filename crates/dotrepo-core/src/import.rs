use anyhow::{anyhow, bail, Result};
use dotrepo_schema::{
    render_manifest, Compat, CompatMode, Docs, GitHubCompat, Manifest, Owners, Readme,
    ReadmeCustomSection, Record, RecordMode, RecordStatus, Relations, Repo, Trust,
};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};

use crate::claims::resolve_repository_local_path;
use crate::render::{
    render_contributing_body, render_pull_request_template_body, render_security_body,
};
use crate::surfaces::{is_banner_line, render_managed_markdown, ManagedSurface};
use crate::util::{display_path, normalize_rfc3339, source_digest};
use crate::validate_manifest;
use crate::validation::SUPPORTED_SCHEMA;
use crate::{record_summary, RecordSummary};

pub(crate) const IMPORT_README_CANDIDATES: &[&str] = &[
    "README.md",
    "README.MD",
    "readme.md",
    "README.mdx",
    "README.markdown",
    "README",
];
pub(crate) const GENERATOR_NAME: &str = "dotrepo";
pub(crate) const GENERATOR_VERSION: &str = env!("CARGO_PKG_VERSION");

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
    pub command_candidates: ImportCommandCandidates,
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

#[derive(Debug, Clone)]
pub struct FieldScoreSummary {
    pub high_confidence_present: Vec<String>,
    pub medium_confidence_present: Vec<String>,
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
    let makefile = load_first_existing_file(root, &["GNUmakefile", "Makefile", "makefile"])?;
    let justfile = load_first_existing_file(root, &["justfile", "Justfile"])?;
    let security_issue_template = load_first_existing_file(
        root,
        &[
            ".github/ISSUE_TEMPLATE/security.md",
            ".github/ISSUE_TEMPLATE/SECURITY.md",
            ".github/ISSUE_TEMPLATE/security.yml",
        ],
    )?;
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
    let contributing_security = contributing
        .as_ref()
        .and_then(|file| parse_contributing_security(&file.contents));
    let template_security = security_issue_template
        .as_ref()
        .and_then(|file| parse_issue_template_security(&file.contents));
    let has_contributing_security = contributing_security.is_some();
    let has_template_security = template_security.is_some();

    let security_contact = parsed_security
        .contact
        .clone()
        .or(contributing_security)
        .or(template_security)
        .or_else(|| {
            if security.is_some() {
                Some("unknown".into())
            } else {
                None
            }
        });
    let security_note = if security.is_some() {
        if parsed_security.contact.is_some() {
            parsed_security.note.clone()
        } else if has_contributing_security {
            Some(
                "SECURITY.md did not expose a direct mailbox or reporting URL. `security_contact` was extracted from CONTRIBUTING.md instead."
                    .to_string(),
            )
        } else if has_template_security {
            Some(
                "SECURITY.md did not expose a direct mailbox or reporting URL. `security_contact` was extracted from an issue template instead."
                    .to_string(),
            )
        } else {
            Some(
                "SECURITY.md did not expose a direct mailbox or reporting URL, so `security_contact = \"unknown\"` is intentional."
                    .to_string(),
            )
        }
    } else if has_contributing_security {
        Some(
            "`security_contact` was extracted from CONTRIBUTING.md (no SECURITY.md found)."
                .to_string(),
        )
    } else if has_template_security {
        Some(
            "`security_contact` was extracted from an issue template (no SECURITY.md found)."
                .to_string(),
        )
    } else {
        None
    };
    let imported_commands = infer_imported_commands(&ImportSources {
        cargo_toml: cargo_toml.as_ref(),
        package_json: package_json.as_ref(),
        pyproject_toml: pyproject_toml.as_ref(),
        go_mod: go_mod.as_ref(),
        makefile: makefile.as_ref(),
        justfile: justfile.as_ref(),
        contributing: contributing.as_ref(),
        workflow_files: &workflow_files,
    });

    let mut imported_sources = Vec::new();
    let mut inferred_defaults = Vec::new();

    let dir_name = root
        .file_name()
        .and_then(|name| name.to_str())
        .filter(|name| !name.is_empty())
        .unwrap_or("repository")
        .to_string();

    let repo_name = match readme_metadata.title {
        Some(ref title) => {
            if let Some(r) = &readme {
                note_import(&mut imported_sources, &r.path);
            }
            match clean_project_name(title, &dir_name) {
                Some(cleaned) => cleaned,
                None => {
                    inferred_defaults.push("repo.name".into());
                    dir_name.clone()
                }
            }
        }
        None => {
            inferred_defaults.push("repo.name".into());
            dir_name.clone()
        }
    };

    let description = match readme_metadata.description {
        Some(ref description) => {
            if let Some(r) = &readme {
                note_import(&mut imported_sources, &r.path);
            }
            match clean_project_description(description) {
                Some(cleaned) => cleaned,
                None => {
                    inferred_defaults.push("repo.description".into());
                    "Imported repository metadata; review and refine before relying on it.".into()
                }
            }
        }
        None => {
            inferred_defaults.push("repo.description".into());
            "Imported repository metadata; review and refine before relying on it.".into()
        }
    };

    let imported_docs = build_imported_docs(
        readme_metadata
            .docs_root
            .as_deref()
            .filter(|url| is_quality_url(url))
            .map(str::to_string),
        readme_metadata
            .docs_getting_started
            .as_deref()
            .filter(|url| is_quality_url(url))
            .map(str::to_string),
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
        if has_contributing_security {
            if let Some(file) = &contributing {
                note_import(&mut imported_sources, &file.path);
            }
        }
        if has_template_security {
            if let Some(file) = &security_issue_template {
                note_import(&mut imported_sources, &file.path);
            }
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
        command_candidates: ImportCommandCandidates {
            candidates: imported_commands
                .candidates
                .iter()
                .map(|c| CommandCandidateSummary {
                    source_path: c.source_path.clone(),
                    source_tier: c.source_tier,
                    build: c.build.clone(),
                    test: c.test.clone(),
                })
                .collect(),
            selected_build: imported_commands
                .build
                .as_ref()
                .map(|s| CommandCandidateSelection {
                    command: s.command.clone(),
                    source_path: s.source_path.clone(),
                    provenance: s.provenance.clone(),
                }),
            selected_test: imported_commands
                .test
                .as_ref()
                .map(|s| CommandCandidateSelection {
                    command: s.command.clone(),
                    source_path: s.source_path.clone(),
                    provenance: s.provenance.clone(),
                }),
        },
    })
}

pub fn verify_import_plan(root: &Path, plan: &ImportPlan, source_url: &str) -> VerificationReport {
    let mut checks = Vec::new();
    let mut candidate_provenance = Vec::new();
    let mut unresolved_fields = Vec::new();
    let mut absent_fields = Vec::new();

    // Identity consistency: source URL matches record.source
    if let Some(ref source) = plan.manifest.record.source {
        if source != source_url {
            checks.push(VerificationCheck {
                check_id: "identity/source-mismatch".into(),
                field: "record.source".into(),
                severity: VerificationSeverity::Failure,
                message: format!(
                    "record.source ({}) does not match crawl source ({})",
                    source, source_url
                ),
            });
        } else {
            checks.push(VerificationCheck {
                check_id: "identity/source-match".into(),
                field: "record.source".into(),
                severity: VerificationSeverity::Pass,
                message: "record.source matches crawl source".into(),
            });
        }
    }

    // Source-file existence: imported_sources paths exist under root
    for source_path in &plan.imported_sources {
        let full_path = root.join(source_path);
        if !full_path.exists() {
            checks.push(VerificationCheck {
                check_id: format!("source-exists/{}", source_path),
                field: "imported_sources".into(),
                severity: VerificationSeverity::Failure,
                message: format!("imported source file does not exist: {}", source_path),
            });
        }
    }

    // Candidate provenance for build/test
    for candidate in &plan.command_candidates.candidates {
        candidate_provenance.push(CandidateProvenance {
            field: "repo.build".into(),
            source_path: candidate.source_path.clone(),
            source_tier: candidate.source_tier,
            value: candidate.build.clone(),
        });
        candidate_provenance.push(CandidateProvenance {
            field: "repo.test".into(),
            source_path: candidate.source_path.clone(),
            source_tier: candidate.source_tier,
            value: candidate.test.clone(),
        });
    }

    // Field completeness: check build/test resolution
    if plan.manifest.repo.build.is_none() {
        let has_candidates = plan
            .command_candidates
            .candidates
            .iter()
            .any(|c| c.build.is_some());
        if has_candidates {
            unresolved_fields.push("repo.build".into());
        } else {
            absent_fields.push("repo.build".into());
        }
    }
    if plan.manifest.repo.test.is_none() {
        let has_candidates = plan
            .command_candidates
            .candidates
            .iter()
            .any(|c| c.test.is_some());
        if has_candidates {
            unresolved_fields.push("repo.test".into());
        } else {
            absent_fields.push("repo.test".into());
        }
    }

    // URL quality checks
    if let Some(ref homepage) = plan.manifest.repo.homepage {
        if !is_quality_url(homepage) {
            checks.push(VerificationCheck {
                check_id: "url-quality/homepage".into(),
                field: "repo.homepage".into(),
                severity: VerificationSeverity::Warning,
                message: format!("homepage URL failed quality check: {}", homepage),
            });
        }
    }
    if let Some(ref docs) = &plan.manifest.docs {
        if let Some(ref root) = docs.root {
            if !is_quality_url(root) {
                checks.push(VerificationCheck {
                    check_id: "url-quality/docs.root".into(),
                    field: "docs.root".into(),
                    severity: VerificationSeverity::Warning,
                    message: format!("docs.root URL failed quality check: {}", root),
                });
            }
        }
        if let Some(ref gs) = docs.getting_started {
            if !is_quality_url(gs) {
                checks.push(VerificationCheck {
                    check_id: "url-quality/docs.getting_started".into(),
                    field: "docs.getting_started".into(),
                    severity: VerificationSeverity::Warning,
                    message: format!("docs.getting_started URL failed quality check: {}", gs),
                });
            }
        }
    }

    let passed = checks
        .iter()
        .all(|c| c.severity != VerificationSeverity::Failure);

    VerificationReport {
        checks,
        candidate_provenance,
        unresolved_fields,
        absent_fields,
        passed,
    }
}

struct ReservedImportOutput {
    path: PathBuf,
    contents: String,
    file: std::fs::File,
}

pub fn write_import_outputs(
    outputs: Vec<(PathBuf, String)>,
    force: bool,
    force_hint: &str,
) -> Result<()> {
    use std::fs::OpenOptions;
    use std::io::{ErrorKind, Write};

    if force {
        for (path, contents) in outputs {
            if let Some(parent) = path.parent() {
                fs::create_dir_all(parent)?;
            }
            fs::write(path, contents)?;
        }
        return Ok(());
    }

    let mut reserved: Vec<ReservedImportOutput> = Vec::new();
    for (path, contents) in outputs {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }

        let file = match OpenOptions::new().write(true).create_new(true).open(&path) {
            Ok(file) => file,
            Err(err) => {
                for reserved in reserved {
                    let _ = fs::remove_file(reserved.path);
                }
                return Err(match err.kind() {
                    ErrorKind::AlreadyExists => anyhow::anyhow!(
                        "{} already exists; rerun with {} to overwrite imported artifacts",
                        path.display(),
                        force_hint
                    ),
                    _ => err.into(),
                });
            }
        };

        reserved.push(ReservedImportOutput {
            path,
            contents,
            file,
        });
    }

    for reserved in &mut reserved {
        reserved
            .file
            .write_all(reserved.contents.as_bytes())
            .and_then(|_| reserved.file.flush())?;
    }

    Ok(())
}

pub fn score_import_fields(
    plan: &ImportPlan,
    verification: &VerificationReport,
) -> FieldScoreReport {
    let mut scores = Vec::new();

    // repo.name
    let name_has_readme_source = plan
        .imported_sources
        .iter()
        .any(|s| s.eq_ignore_ascii_case("readme.md"));
    scores.push(FieldScore {
        field: "repo.name".into(),
        confidence: if name_has_readme_source {
            FieldConfidence::HighConfidencePresent
        } else {
            FieldConfidence::MediumConfidencePresent
        },
        source: plan.imported_sources.first().cloned(),
        value: Some(plan.manifest.repo.name.clone()),
        reason: if name_has_readme_source {
            "extracted from README heading with post-cleaners".into()
        } else {
            "fell back to directory name or GitHub API".into()
        },
    });

    // repo.description
    scores.push(FieldScore {
        field: "repo.description".into(),
        confidence: if name_has_readme_source {
            FieldConfidence::HighConfidencePresent
        } else {
            FieldConfidence::MediumConfidencePresent
        },
        source: plan.imported_sources.first().cloned(),
        value: Some(plan.manifest.repo.description.clone()),
        reason: if name_has_readme_source {
            "extracted from README paragraph with post-cleaners".into()
        } else {
            "fell back to GitHub API or inferred".into()
        },
    });

    // repo.homepage
    if let Some(ref homepage) = plan.manifest.repo.homepage {
        scores.push(FieldScore {
            field: "repo.homepage".into(),
            confidence: if is_quality_url(homepage) {
                FieldConfidence::HighConfidencePresent
            } else {
                FieldConfidence::MediumConfidencePresent
            },
            source: None,
            value: Some(homepage.clone()),
            reason: "set and passes quality check".into(),
        });
    } else {
        scores.push(FieldScore {
            field: "repo.homepage".into(),
            confidence: FieldConfidence::HighConfidenceAbsent,
            source: None,
            value: None,
            reason: "no homepage detected".into(),
        });
    }

    // repo.build
    let build_unresolved = verification
        .unresolved_fields
        .contains(&"repo.build".to_string());
    let build_absent = verification
        .absent_fields
        .contains(&"repo.build".to_string());
    if let Some(ref build) = plan.manifest.repo.build {
        let is_manifest = plan
            .command_candidates
            .selected_build
            .as_ref()
            .map(|s| matches!(s.provenance, ImportedCommandProvenance::Imported))
            .unwrap_or(false);
        scores.push(FieldScore {
            field: "repo.build".into(),
            confidence: if is_manifest {
                FieldConfidence::HighConfidencePresent
            } else {
                FieldConfidence::MediumConfidencePresent
            },
            source: plan
                .command_candidates
                .selected_build
                .as_ref()
                .map(|s| s.source_path.clone()),
            value: Some(build.clone()),
            reason: if is_manifest {
                "from manifest source".into()
            } else {
                "from workflow fallback".into()
            },
        });
    } else if build_unresolved {
        scores.push(FieldScore {
            field: "repo.build".into(),
            confidence: FieldConfidence::Unresolved,
            source: None,
            value: None,
            reason: "conflicting candidates, no clear winner".into(),
        });
    } else if build_absent {
        scores.push(FieldScore {
            field: "repo.build".into(),
            confidence: FieldConfidence::HighConfidenceAbsent,
            source: None,
            value: None,
            reason: "no build command sources found".into(),
        });
    }

    // repo.test
    let test_unresolved = verification
        .unresolved_fields
        .contains(&"repo.test".to_string());
    let test_absent = verification
        .absent_fields
        .contains(&"repo.test".to_string());
    if let Some(ref test) = plan.manifest.repo.test {
        let is_manifest = plan
            .command_candidates
            .selected_test
            .as_ref()
            .map(|s| matches!(s.provenance, ImportedCommandProvenance::Imported))
            .unwrap_or(false);
        scores.push(FieldScore {
            field: "repo.test".into(),
            confidence: if is_manifest {
                FieldConfidence::HighConfidencePresent
            } else {
                FieldConfidence::MediumConfidencePresent
            },
            source: plan
                .command_candidates
                .selected_test
                .as_ref()
                .map(|s| s.source_path.clone()),
            value: Some(test.clone()),
            reason: if is_manifest {
                "from manifest source".into()
            } else {
                "from workflow fallback".into()
            },
        });
    } else if test_unresolved {
        scores.push(FieldScore {
            field: "repo.test".into(),
            confidence: FieldConfidence::Unresolved,
            source: None,
            value: None,
            reason: "conflicting candidates, no clear winner".into(),
        });
    } else if test_absent {
        scores.push(FieldScore {
            field: "repo.test".into(),
            confidence: FieldConfidence::HighConfidenceAbsent,
            source: None,
            value: None,
            reason: "no test command sources found".into(),
        });
    }

    // owners.security_contact
    let owners = plan.manifest.owners.as_ref();
    let security = owners.and_then(|o| o.security_contact.as_deref());
    if let Some(contact) = security {
        if contact == "unknown" {
            scores.push(FieldScore {
                field: "owners.security_contact".into(),
                confidence: FieldConfidence::HighConfidenceAbsent,
                source: None,
                value: Some(contact.into()),
                reason: "explicitly unknown".into(),
            });
        } else if contact.contains('@') {
            scores.push(FieldScore {
                field: "owners.security_contact".into(),
                confidence: FieldConfidence::HighConfidencePresent,
                source: plan.imported_sources.first().cloned(),
                value: Some(contact.into()),
                reason: "direct email or mailing list".into(),
            });
        } else if is_actionable_security_url(contact) {
            scores.push(FieldScore {
                field: "owners.security_contact".into(),
                confidence: FieldConfidence::HighConfidencePresent,
                source: plan.imported_sources.first().cloned(),
                value: Some(contact.into()),
                reason: "actionable security reporting URL".into(),
            });
        } else {
            scores.push(FieldScore {
                field: "owners.security_contact".into(),
                confidence: FieldConfidence::MediumConfidencePresent,
                source: plan.imported_sources.first().cloned(),
                value: Some(contact.into()),
                reason: "policy URL or non-email contact".into(),
            });
        }
    } else {
        scores.push(FieldScore {
            field: "owners.security_contact".into(),
            confidence: FieldConfidence::HighConfidenceAbsent,
            source: None,
            value: None,
            reason: "no SECURITY.md or security contact sources found".into(),
        });
    }

    // owners.team
    let team = owners.and_then(|o| o.team.as_deref());
    if let Some(team_val) = team {
        scores.push(FieldScore {
            field: "owners.team".into(),
            confidence: FieldConfidence::HighConfidencePresent,
            source: plan
                .imported_sources
                .iter()
                .find(|s| s.eq_ignore_ascii_case("codeowners"))
                .cloned(),
            value: Some(team_val.into()),
            reason: "clear CODEOWNERS team".into(),
        });
    } else {
        scores.push(FieldScore {
            field: "owners.team".into(),
            confidence: FieldConfidence::HighConfidenceAbsent,
            source: None,
            value: None,
            reason: "no single clear team in CODEOWNERS".into(),
        });
    }

    // docs.root
    if let Some(ref docs) = &plan.manifest.docs {
        if let Some(ref root) = docs.root {
            scores.push(FieldScore {
                field: "docs.root".into(),
                confidence: if is_quality_url(root) {
                    FieldConfidence::HighConfidencePresent
                } else {
                    FieldConfidence::MediumConfidencePresent
                },
                source: None,
                value: Some(root.clone()),
                reason: "docs URL present".into(),
            });
        } else {
            scores.push(FieldScore {
                field: "docs.root".into(),
                confidence: FieldConfidence::HighConfidenceAbsent,
                source: None,
                value: None,
                reason: "no docs site detected".into(),
            });
        }
    } else {
        scores.push(FieldScore {
            field: "docs.root".into(),
            confidence: FieldConfidence::HighConfidenceAbsent,
            source: None,
            value: None,
            reason: "no docs detected".into(),
        });
    }

    // docs.getting_started
    if let Some(ref docs) = &plan.manifest.docs {
        if let Some(ref gs) = docs.getting_started {
            scores.push(FieldScore {
                field: "docs.getting_started".into(),
                confidence: if is_quality_url(gs) {
                    FieldConfidence::HighConfidencePresent
                } else {
                    FieldConfidence::MediumConfidencePresent
                },
                source: None,
                value: Some(gs.clone()),
                reason: "getting started URL present".into(),
            });
        } else {
            scores.push(FieldScore {
                field: "docs.getting_started".into(),
                confidence: FieldConfidence::HighConfidenceAbsent,
                source: None,
                value: None,
                reason: "no getting started link detected".into(),
            });
        }
    } else {
        scores.push(FieldScore {
            field: "docs.getting_started".into(),
            confidence: FieldConfidence::HighConfidenceAbsent,
            source: None,
            value: None,
            reason: "no docs detected".into(),
        });
    }

    let high_confidence_present: Vec<_> = scores
        .iter()
        .filter(|s| s.confidence == FieldConfidence::HighConfidencePresent)
        .map(|s| s.field.clone())
        .collect();
    let medium_confidence_present: Vec<_> = scores
        .iter()
        .filter(|s| s.confidence == FieldConfidence::MediumConfidencePresent)
        .map(|s| s.field.clone())
        .collect();
    let high_confidence_absent: Vec<_> = scores
        .iter()
        .filter(|s| s.confidence == FieldConfidence::HighConfidenceAbsent)
        .map(|s| s.field.clone())
        .collect();
    let unresolved: Vec<_> = scores
        .iter()
        .filter(|s| s.confidence == FieldConfidence::Unresolved)
        .map(|s| s.field.clone())
        .collect();

    let eligible_for_auto_publish = unresolved.is_empty() && medium_confidence_present.is_empty();

    FieldScoreReport {
        scores,
        summary: FieldScoreSummary {
            high_confidence_present,
            medium_confidence_present,
            high_confidence_absent,
            unresolved,
            eligible_for_auto_publish,
        },
    }
}

pub fn build_adjudication_requests(
    report: &FieldScoreReport,
    plan: &ImportPlan,
) -> Vec<AdjudicationRequest> {
    let unresolved_fields: Vec<&str> = report
        .scores
        .iter()
        .filter(|s| s.confidence == FieldConfidence::Unresolved)
        .map(|s| s.field.as_str())
        .collect();

    if unresolved_fields.is_empty() {
        return Vec::new();
    }

    let mut requests = Vec::new();

    for field in &unresolved_fields {
        let is_build = *field == "repo.build";
        let is_test = *field == "repo.test";

        if !is_build && !is_test {
            continue;
        }

        let mut candidates = Vec::new();
        for candidate in &plan.command_candidates.candidates {
            let value = if is_build {
                candidate.build.as_ref()
            } else {
                candidate.test.as_ref()
            };
            if let Some(value) = value {
                candidates.push(AdjudicationCandidate {
                    value: value.clone(),
                    source_path: candidate.source_path.clone(),
                    source_tier: candidate.source_tier,
                });
            }
        }

        if !candidates.is_empty() {
            requests.push(AdjudicationRequest {
                field: field.to_string(),
                candidates,
            });
        }
    }

    requests
}

pub fn apply_adjudication_response(
    response: &AdjudicationModelResponse,
    request: &AdjudicationRequest,
) -> AdjudicationResult {
    let candidate_values: Vec<&str> = request
        .candidates
        .iter()
        .map(|c| c.value.as_str())
        .collect();

    match &response.value {
        Some(value) => {
            if candidate_values.iter().any(|c| *c == value) {
                AdjudicationResult {
                    field: response.field.clone(),
                    outcome: AdjudicationOutcome::Resolved {
                        value: value.clone(),
                        confidence: FieldConfidence::MediumConfidencePresent,
                        reason: response.reason.clone(),
                    },
                }
            } else {
                AdjudicationResult {
                    field: response.field.clone(),
                    outcome: AdjudicationOutcome::Rejected {
                        model_value: value.clone(),
                        reason: format!(
                            "model proposed value not in candidate set: {:?}",
                            candidate_values
                        ),
                    },
                }
            }
        }
        None => AdjudicationResult {
            field: response.field.clone(),
            outcome: AdjudicationOutcome::Absent {
                reason: response.reason.clone(),
            },
        },
    }
}

pub fn apply_adjudication_results(report: &mut FieldScoreReport, results: &[AdjudicationResult]) {
    for result in results {
        let Some(score) = report.scores.iter_mut().find(|s| s.field == result.field) else {
            continue;
        };
        match &result.outcome {
            AdjudicationOutcome::Resolved {
                value,
                confidence,
                reason,
            } => {
                score.confidence = confidence.clone();
                score.value = Some(value.clone());
                score.reason = format!("adjudicated: {}", reason);
            }
            AdjudicationOutcome::Absent { reason } => {
                score.confidence = FieldConfidence::HighConfidenceAbsent;
                score.value = None;
                score.reason = format!("adjudicated absent: {}", reason);
            }
            AdjudicationOutcome::Rejected { .. } => {
                // Leave as unresolved — model couldn't help
            }
        }
    }

    // Recompute summary
    let mut high_confidence_present = Vec::new();
    let mut medium_confidence_present = Vec::new();
    let mut high_confidence_absent = Vec::new();
    let mut unresolved = Vec::new();
    for score in &report.scores {
        match score.confidence {
            FieldConfidence::HighConfidencePresent => {
                high_confidence_present.push(score.field.clone())
            }
            FieldConfidence::MediumConfidencePresent => {
                medium_confidence_present.push(score.field.clone())
            }
            FieldConfidence::HighConfidenceAbsent => {
                high_confidence_absent.push(score.field.clone())
            }
            FieldConfidence::Unresolved => unresolved.push(score.field.clone()),
        }
    }
    report.summary.high_confidence_present = high_confidence_present;
    report.summary.medium_confidence_present = medium_confidence_present;
    report.summary.high_confidence_absent = high_confidence_absent;
    report.summary.unresolved = unresolved;
    report.summary.eligible_for_auto_publish =
        report.summary.unresolved.is_empty() && report.summary.medium_confidence_present.is_empty();
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
struct CodeownersRule {
    pattern: String,
    owners: Vec<String>,
    teams: Vec<String>,
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

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ImportedCommandProvenance {
    Imported,
    Inferred,
}

#[derive(Debug, Clone)]
pub(crate) struct ImportedCommandSelection {
    pub(crate) command: String,
    pub(crate) source_path: String,
    pub(crate) provenance: ImportedCommandProvenance,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CommandSourceTier {
    Workflow,
    TaskScript,
    ContribDoc,
    Manifest,
}

pub(crate) struct ImportSources<'a> {
    pub(crate) cargo_toml: Option<&'a ImportedFile>,
    pub(crate) package_json: Option<&'a ImportedFile>,
    pub(crate) pyproject_toml: Option<&'a ImportedFile>,
    pub(crate) go_mod: Option<&'a ImportedFile>,
    pub(crate) makefile: Option<&'a ImportedFile>,
    pub(crate) justfile: Option<&'a ImportedFile>,
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

pub(crate) fn infer_imported_commands(sources: &ImportSources) -> ImportedCommandMetadata {
    let mut candidates = Vec::new();
    // Manifest tier
    if let Some(candidate) = sources.cargo_toml.and_then(infer_cargo_manifest_commands) {
        candidates.push(candidate);
    }
    if let Some(candidate) = sources.package_json.and_then(infer_package_json_commands) {
        candidates.push(candidate);
    }
    if let Some(candidate) = sources.pyproject_toml.and_then(infer_pyproject_commands) {
        candidates.push(candidate);
    }
    if let Some(candidate) = sources.go_mod.and_then(infer_go_module_commands) {
        candidates.push(candidate);
    }
    // ContribDoc tier
    if let Some(candidate) = sources.contributing.and_then(infer_contributing_commands) {
        candidates.push(candidate);
    }
    // TaskScript tier
    if let Some(candidate) = sources.makefile.and_then(infer_makefile_commands) {
        candidates.push(candidate);
    }
    if let Some(candidate) = sources.justfile.and_then(infer_justfile_commands) {
        candidates.push(candidate);
    }
    // Workflow tier
    candidates.extend(
        sources
            .workflow_files
            .iter()
            .filter_map(infer_workflow_commands),
    );

    let mut metadata = ImportedCommandMetadata::default();
    metadata.build = resolve_command_field(
        &candidates,
        "repo.build",
        true,
        &mut metadata.notes,
        &mut metadata.evidence_bullets,
        &mut metadata.inferred_fields,
    );
    metadata.test = resolve_command_field(
        &candidates,
        "repo.test",
        false,
        &mut metadata.notes,
        &mut metadata.evidence_bullets,
        &mut metadata.inferred_fields,
    );
    metadata.candidates = candidates;
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
        source_tier: CommandSourceTier::Manifest,
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
        source_tier: CommandSourceTier::Manifest,
        build,
        test,
    })
}

pub(crate) fn infer_pyproject_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let parsed: toml::Value = toml::from_str(&file.contents).ok()?;
    let has_build_system = parsed
        .get("build-system")
        .and_then(toml::Value::as_table)
        .is_some();
    let build = has_build_system.then(|| "python -m build".to_string());

    let test = infer_pyproject_test_command(&parsed);

    if build.is_none() && test.is_none() {
        return None;
    }

    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::Manifest,
        build,
        test,
    })
}

fn infer_pyproject_test_command(parsed: &toml::Value) -> Option<String> {
    let tool = parsed.get("tool").and_then(toml::Value::as_table);
    if let Some(tool_table) = tool {
        if tool_table.contains_key("pytest") {
            return Some("python -m pytest".to_string());
        }
        if tool_table.contains_key("tox") || tool_table.contains_key("tox-gh-actions") {
            return Some("tox".to_string());
        }
        if tool_table.contains_key("nox") {
            return Some("nox".to_string());
        }
    }

    let project = parsed.get("project").and_then(toml::Value::as_table);
    if let Some(project_table) = project {
        if let Some(scripts) = project_table.get("scripts").and_then(toml::Value::as_table) {
            if scripts.contains_key("test") {
                return Some("python -m pytest".to_string());
            }
        }
        if let Some(optional_deps) = project_table
            .get("optional-dependencies")
            .and_then(toml::Value::as_table)
        {
            if optional_deps.contains_key("test") || optional_deps.contains_key("testing") {
                return Some("python -m pytest".to_string());
            }
        }
    }

    if parsed
        .get("build-system")
        .and_then(toml::Value::as_table)
        .is_some()
    {
        return Some("python -m pytest".to_string());
    }

    None
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
        source_tier: CommandSourceTier::Manifest,
        build: Some("go build ./...".into()),
        test: Some("go test ./...".into()),
    })
}

fn infer_makefile_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let mut has_build = false;
    let mut has_test = false;
    for line in file.contents.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with("build:") || trimmed.starts_with("all:") {
            has_build = true;
        }
        if trimmed.starts_with("test:") || trimmed.starts_with("check:") {
            has_test = true;
        }
    }
    if !has_build && !has_test {
        return None;
    }
    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::TaskScript,
        build: if has_build {
            Some("make build".into())
        } else {
            None
        },
        test: if has_test {
            Some("make test".into())
        } else {
            None
        },
    })
}

fn infer_justfile_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let mut has_build = false;
    let mut has_test = false;
    for line in file.contents.lines() {
        let trimmed = line.trim();
        // Skip ':=' assignments (variables) and '[' (settings/aliases)
        if trimmed.contains(":=") || trimmed.starts_with('[') {
            continue;
        }
        // Recipes: "name:" or "name arg:" — split on first ':' and check the lhs
        if let Some(colon_pos) = trimmed.find(':') {
            let lhs = trimmed[..colon_pos].trim();
            // lhs must be a valid recipe identifier (no spaces, no '=')
            if lhs.contains(' ') || lhs.contains('=') || lhs.is_empty() {
                continue;
            }
            // The first word of lhs is the recipe name (may have args after it)
            let name = lhs.split_whitespace().next().unwrap_or(lhs);
            if name == "build" || name == "all" {
                has_build = true;
            }
            if name == "test" || name == "check" {
                has_test = true;
            }
        }
    }
    if !has_build && !has_test {
        return None;
    }
    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::TaskScript,
        build: if has_build {
            Some("just build".into())
        } else {
            None
        },
        test: if has_test {
            Some("just test".into())
        } else {
            None
        },
    })
}

fn infer_contributing_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    // Look for build/test instructions in code blocks within CONTRIBUTING.md
    let mut build: Option<String> = None;
    let mut test: Option<String> = None;
    let mut in_code_block = false;
    for line in file.contents.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with("```") {
            in_code_block = !in_code_block;
            continue;
        }
        if !in_code_block {
            continue;
        }
        let lower = trimmed.to_lowercase();
        if build.is_none()
            && (lower.starts_with("cargo build")
                || lower == "make"
                || lower.starts_with("make build")
                || lower.starts_with("make all")
                || lower.starts_with("npm run build")
                || lower.starts_with("go build")
                || lower.starts_with("just build"))
        {
            build = Some(trimmed.to_string());
        }
        if test.is_none()
            && (lower.starts_with("cargo test")
                || lower.starts_with("make test")
                || lower.starts_with("make check")
                || lower.starts_with("npm test")
                || lower.starts_with("go test")
                || lower.starts_with("just test"))
        {
            test = Some(trimmed.to_string());
        }
    }
    if build.is_none() && test.is_none() {
        return None;
    }
    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::ContribDoc,
        build,
        test,
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
        source_tier: CommandSourceTier::Workflow,
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
    candidates: &[ImportedCommandCandidate],
    field: &'static str,
    select_build: bool,
    notes: &mut Vec<String>,
    evidence_bullets: &mut Vec<String>,
    inferred_fields: &mut Vec<String>,
) -> Option<ImportedCommandSelection> {
    // Resolution goes top-down by tier:
    // Manifest > ContribDoc > TaskScript > Workflow.
    // Within a tier, conflicts are genuine and block the field.
    // If a higher tier resolves, lower tiers are ignored.
    let tiers = [
        CommandSourceTier::Manifest,
        CommandSourceTier::ContribDoc,
        CommandSourceTier::TaskScript,
        CommandSourceTier::Workflow,
    ];

    for tier in &tiers {
        let tier_candidates: Vec<&ImportedCommandCandidate> = candidates
            .iter()
            .filter(|c| c.source_tier == *tier)
            .collect();

        if tier_candidates.is_empty() {
            continue;
        }

        let resolution = resolve_unique_command_candidate(&tier_candidates, select_build);

        match &resolution {
            UniqueCommandResolution::Unique {
                command,
                source_path,
            } => {
                let is_manifest_tier = *tier == CommandSourceTier::Manifest
                    || *tier == CommandSourceTier::ContribDoc
                    || *tier == CommandSourceTier::TaskScript;
                let selection = ImportedCommandSelection {
                    command: command.clone(),
                    source_path: source_path.clone(),
                    provenance: if is_manifest_tier {
                        ImportedCommandProvenance::Imported
                    } else {
                        ImportedCommandProvenance::Inferred
                    },
                };
                if !is_manifest_tier {
                    inferred_fields.push(field.into());
                }
                note_selected_command(field, &selection, notes, evidence_bullets);
                return Some(selection);
            }
            UniqueCommandResolution::Conflict { source_paths } => {
                let kind = if select_build { "build" } else { "test" };
                let note = format!(
                    "Left `{}` unset because {} suggested conflicting {} commands.",
                    field,
                    human_join(source_paths),
                    kind
                );
                notes.push(note.clone());
                evidence_bullets.push(note);
                return None;
            }
            UniqueCommandResolution::None => continue,
        }
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
    candidates: &[&ImportedCommandCandidate],
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

pub(crate) fn try_parse_multiline_html_heading(
    lines: &[&str],
    idx: usize,
) -> Option<(String, usize)> {
    let line = lines.get(idx)?.trim();
    let lower = line.to_ascii_lowercase();
    let tag_level = ["<h1", "<h2", "<h3", "<h4", "<h5", "<h6"]
        .iter()
        .find(|needle| lower.starts_with(**needle))?;
    let close_tag = tag_level.replace('<', "</");
    if line.contains(&close_tag) {
        return None;
    }
    let mut accumulated = String::new();
    let mut scan = idx + 1;
    let mut lines_consumed = 1;
    while scan < lines.len() {
        let next = lines[scan].trim();
        lines_consumed += 1;
        if next.contains(&close_tag) {
            if !accumulated.is_empty() {
                if let Some(normalized) = normalize_readme_text(&accumulated) {
                    if !is_non_project_heading(&normalized) {
                        return Some((normalized, lines_consumed));
                    }
                }
            }
            return None;
        }
        if !next.is_empty() {
            if !accumulated.is_empty() {
                accumulated.push(' ');
            }
            accumulated.push_str(next);
        }
        scan += 1;
    }
    None
}

pub(crate) fn parse_readme_metadata(contents: &str) -> ReadmeMetadata {
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
            if let Some((title, advance)) = try_parse_multiline_html_heading(&lines, idx) {
                metadata.title = Some(title);
                idx += advance;
                continue;
            }
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

pub(crate) fn parse_readme_title_line(line: &str) -> Option<String> {
    if line.starts_with('#') {
        let title = strip_badge_run(line.trim_start_matches('#').trim());
        if is_promo_link_heading(title) {
            return None;
        }
        if let Some(normalized) = normalize_readme_text(title) {
            if !is_non_project_heading(&normalized) {
                return Some(normalized);
            }
        }
        return None;
    }

    parse_html_heading(line).filter(|h| !is_non_project_heading(h))
}

fn is_promo_link_heading(text: &str) -> bool {
    let trimmed = text.trim();
    if !trimmed.starts_with('[') {
        return false;
    }
    if let Some(close_bracket) = trimmed.find("](") {
        let after_link = trimmed[close_bracket + 2..].trim();
        after_link.ends_with(')')
            && after_link
                .rfind(')')
                .is_some_and(|pos| pos == after_link.len() - 1)
    } else {
        false
    }
}

pub(crate) fn is_non_project_heading(heading: &str) -> bool {
    let lowered = heading.to_ascii_lowercase();
    let trimmed = lowered.trim();
    if NON_PROJECT_HEADINGS.contains(&trimmed) {
        return true;
    }
    NON_PROJECT_HEADING_KEYWORDS
        .iter()
        .any(|keyword| trimmed.contains(keyword))
}

const NON_PROJECT_HEADINGS: &[&str] = &[
    "about",
    "acknowledgments",
    "api reference",
    "badges",
    "changelog",
    "commands",
    "code of conduct",
    "communication",
    "concepts",
    "configuration",
    "contributing",
    "credits",
    "documentation",
    "donate",
    "example",
    "examples",
    "faq",
    "features",
    "flags",
    "getting started",
    "installation",
    "installing",
    "introduction",
    "license",
    "links",
    "motivation",
    "overview",
    "quick links",
    "quick start",
    "quickstart",
    "readme",
    "resources",
    "roadmap",
    "security",
    "security and privacy",
    "sponsors",
    "support",
    "table of contents",
    "usage",
];

const NON_PROJECT_HEADING_KEYWORDS: &[&str] = &["sponsors", "sponsor", "backed by", "supported by"];

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
        let joined = parts.join(" ");
        if looks_like_artifact(&joined) {
            return None;
        }
        if joined.len() < 15 || !joined.contains(' ') {
            return None;
        }
        Some((joined, idx))
    }
}

pub(crate) fn normalize_description_line(line: &str) -> Option<String> {
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
        || is_pipe_delimited_nav_line(line)
        || is_nav_link_item(line)
    {
        return None;
    }

    let description = line.trim_start_matches('>').trim();
    normalize_readme_text(description)
        .filter(|value| value.chars().any(|ch| ch.is_alphanumeric()))
        .filter(|value| !looks_like_artifact(value))
        .filter(|value| !is_quoted_tagline(value))
}

fn looks_like_artifact(value: &str) -> bool {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return true;
    }
    if trimmed.starts_with("http://") || trimmed.starts_with("https://") {
        return true;
    }
    if looks_like_html_attribute_spill(trimmed) {
        return true;
    }
    if looks_like_file_path(trimmed) {
        return true;
    }
    if has_unbalanced_brackets(trimmed) {
        return true;
    }
    if is_pipe_delimited_nav_text(trimmed) {
        return true;
    }
    false
}

fn looks_like_html_attribute_spill(value: &str) -> bool {
    let lowered = value.to_ascii_lowercase();
    lowered.contains("src=\"") || lowered.contains("alt=\"") || lowered.contains("href=\"")
}

fn is_pipe_delimited_nav_line(line: &str) -> bool {
    is_pipe_delimited_nav_text(line.trim())
}

fn is_pipe_delimited_nav_text(value: &str) -> bool {
    let pipe_count = value.chars().filter(|ch| *ch == '|').count();
    if pipe_count < 2 {
        return false;
    }
    let segments = value.split('|').collect::<Vec<_>>();
    segments.len() >= 3 && segments.iter().all(|s| s.trim().len() <= 40)
}

fn is_nav_link_item(line: &str) -> bool {
    let trimmed = line.trim();
    if trimmed.starts_with('|') && trimmed.contains('|') {
        return true;
    }
    if trimmed.contains('|') && trimmed.ends_with('|') {
        return true;
    }
    let normalized = normalize_readme_text(trimmed);
    normalized
        .as_ref()
        .is_some_and(|text| text.ends_with('|') || text.trim().ends_with('|'))
}

fn looks_like_file_path(value: &str) -> bool {
    let has_extension = value.rsplit_once('.').is_some_and(|(_, ext)| {
        ext.len() <= 10
            && ext
                .chars()
                .all(|ch| ch.is_ascii_alphanumeric() || ch == '-')
    });
    if !has_extension {
        return false;
    }
    let sep_count = value.chars().filter(|ch| *ch == '/').count();
    sep_count >= 1
}

fn has_unbalanced_brackets(value: &str) -> bool {
    let mut depth_paren = 0i32;
    let mut depth_bracket = 0i32;
    for ch in value.chars() {
        match ch {
            '(' => depth_paren += 1,
            ')' => depth_paren -= 1,
            '[' => depth_bracket += 1,
            ']' => depth_bracket -= 1,
            _ => {}
        }
    }
    depth_paren != 0 || depth_bracket != 0
}

// ---------------------------------------------------------------------------
// Universal post-extraction cleaners
// ---------------------------------------------------------------------------
// These operate on the *result* of README/GitHub parsing and apply
// language-agnostic quality rules that work for any repo at scale.

/// Strip emoji prefix, parenthetical aliases, and trailing punctuation from
/// an extracted project name. Returns `None` when the cleaned result is
/// clearly not a project name (generic phrase, too short, etc.).
fn clean_project_name(raw: &str, _repo_dir_fallback: &str) -> Option<String> {
    let trimmed = raw.trim();

    // Strip leading emoji / non-ASCII symbols.
    let name = trim_leading_emoji(trimmed);

    // Strip parenthetical alias: "ripgrep (rg)" → "ripgrep"
    let name = strip_parenthetical_suffix(&name);

    // Strip trailing colon or dash patterns: "npm - a JavaScript package manager"
    let name = strip_name_trailer(&name);

    let cleaned = name.trim().to_string();
    if cleaned.is_empty() {
        return None;
    }

    // Reject generic phrases that somehow passed the heading skip-list.
    if is_generic_phrase(&cleaned) {
        return None;
    }

    Some(cleaned)
}

fn trim_leading_emoji(s: &str) -> String {
    s.chars()
        .skip_while(|ch| !ch.is_ascii_alphabetic() && !ch.is_ascii_digit())
        .collect()
}

fn strip_parenthetical_suffix(name: &str) -> String {
    if let Some(open) = name.rfind(" (") {
        if name.ends_with(')') {
            return name[..open].to_string();
        }
    }
    name.to_string()
}

/// Strip " - description" or ": description" trailers that leak into names
/// when README titles use the pattern "Name — A description of the project".
fn strip_name_trailer(name: &str) -> String {
    if let Some(idx) = name.find(" - ") {
        let candidate = name[..idx].trim();
        if candidate.len() >= 2 {
            return candidate.to_string();
        }
    }
    if let Some(idx) = name.find(" — ") {
        let candidate = name[..idx].trim();
        if candidate.len() >= 2 {
            return candidate.to_string();
        }
    }
    if let Some(idx) = name.find(": ") {
        let candidate = name[..idx].trim();
        if candidate.len() >= 2 && candidate.chars().next().is_some_and(|c| c.is_uppercase()) {
            return candidate.to_string();
        }
    }
    name.to_string()
}

/// Reject names that are clearly not project identifiers.
fn is_generic_phrase(name: &str) -> bool {
    let lowered = name.to_ascii_lowercase();
    let trimmed = lowered.trim();

    // Exact-match against known generic names that slip through heading checks.
    GENERIC_NAME_REJECTS.contains(&trimmed)
}

const GENERIC_NAME_REJECTS: &[&str] = &[
    "a project",
    "the project",
    "this project",
    "project",
    "a tool",
    "a library",
    "a framework",
    "welcome",
    "overview",
    "introduction",
];

/// Clean a description extracted from a README: fix backtick artifacts,
/// truncate at the first sentence boundary, and reject fragments.
pub(crate) fn clean_project_description(raw: &str) -> Option<String> {
    let trimmed = raw.trim();

    // Strip orphaned backtick artifacts: "gh` is..." → "gh is..."
    let cleaned = strip_orphan_backticks(trimmed);

    // Truncate at first sentence boundary.
    let cleaned = truncate_at_first_sentence(&cleaned);

    let cleaned = cleaned.trim().to_string();

    // Reject fragments: starts with lowercase (likely mid-sentence).
    if cleaned
        .chars()
        .next()
        .is_some_and(|ch| ch.is_ascii_lowercase())
    {
        return None;
    }

    // Reject very short results or language names.
    if cleaned.len() < 20 || !cleaned.contains(' ') {
        return None;
    }

    // Reject meta-descriptions about the repo itself.
    if is_meta_description(&cleaned) {
        return None;
    }

    // Reject quoted taglines: "Any color you like."
    if is_quoted_tagline(&cleaned) {
        return None;
    }

    Some(cleaned)
}

/// Replace backtick-space patterns like "gh` is" with "gh is".
fn strip_orphan_backticks(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let chars: Vec<char> = s.chars().collect();
    let mut i = 0;
    while i < chars.len() {
        if chars[i] == '`' {
            let next_is_continuation = chars
                .get(i + 1)
                .is_some_and(|ch| *ch == ' ' || ch.is_ascii_lowercase());
            let prev_is_alphanum = i > 0 && chars[i - 1].is_ascii_alphanumeric();
            if prev_is_alphanum && next_is_continuation {
                i += 1;
                continue;
            }
        }
        out.push(chars[i]);
        i += 1;
    }
    out
}

/// Truncate text at the first sentence boundary (period + space).
/// Keeps the first sentence only, which is the core description.
fn truncate_at_first_sentence(s: &str) -> String {
    // Look for ". " (period followed by space) — standard sentence boundary.
    if let Some(idx) = s.find(". ") {
        let first = &s[..idx + 1];
        if first.len() >= 20 {
            return first.to_string();
        }
    }
    // Also truncate at ".\n" boundary.
    if let Some(idx) = s.find(".\n") {
        let first = &s[..idx + 1];
        if first.len() >= 20 {
            return first.to_string();
        }
    }
    s.to_string()
}

/// Detect descriptions that are about the repository rather than the project.
fn is_meta_description(s: &str) -> bool {
    let lowered = s.to_ascii_lowercase();
    lowered.starts_with("this repository is")
        || lowered.starts_with("this repo is")
        || lowered.starts_with("this is the")
        || lowered.starts_with("this is a repo")
}

fn is_quoted_tagline(s: &str) -> bool {
    let trimmed = s.trim();
    let openers = ['"', '\u{201c}', '\u{201e}'];
    let closers = ['"', '\u{201d}', '\u{201e}'];
    if trimmed.len() > 2
        && openers.iter().any(|&q| trimmed.starts_with(q))
        && closers.iter().any(|&q| trimmed.ends_with(q))
    {
        let inner = &trimmed[trimmed.chars().next().unwrap().len_utf8()
            ..trimmed.len() - trimmed.chars().last().unwrap().len_utf8()];
        return !inner.contains(". ");
    }
    false
}

/// Validate that a URL is structurally sound for use in the index.
/// Rejects localhost, anchor-only, and bare domains without scheme.
pub(crate) fn is_quality_url(url: &str) -> bool {
    let trimmed = url.trim();

    // Reject empty.
    if trimmed.is_empty() {
        return false;
    }

    // Reject anchor-only: "#documentation", "#getting-started"
    if trimmed.starts_with('#') {
        return false;
    }

    // Reject localhost / private IPs.
    if trimmed.starts_with("http://127.0")
        || trimmed.starts_with("http://localhost")
        || trimmed.starts_with("https://localhost")
        || trimmed.starts_with("http://0.0.0")
        || trimmed.starts_with("http://[::1]")
    {
        return false;
    }

    // Require http:// or https:// scheme for absolute URLs.
    // Allow relative paths like "docs/" but reject bare domains like "docs.rs/clap".
    if !trimmed.starts_with("http://")
        && !trimmed.starts_with("https://")
        && !trimmed.starts_with('/')
        && !trimmed.starts_with("./")
        && !trimmed.contains(char::is_whitespace)
    {
        // If it looks like a domain (contains dots and slashes but no scheme), reject.
        if trimmed.contains('.') && trimmed.contains('/') && !trimmed.starts_with('#') {
            return false;
        }
        // If it looks like a bare domain without any path, reject.
        if trimmed.contains('.') && !trimmed.contains('/') {
            return false;
        }
    }

    true
}

pub(crate) fn is_actionable_security_url(url: &str) -> bool {
    let trimmed = url.trim();

    // GitHub's built-in vulnerability disclosure form per repo.
    if trimmed.contains("/security/advisories/new") {
        return true;
    }

    // Microsoft Security Response Center report form.
    if trimmed.contains("msrc.microsoft.com/create-report") {
        return true;
    }

    // Vendor security pages with clear first-party reporting instructions.
    if trimmed.contains("djangoproject.com/security") {
        return true;
    }

    false
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

pub(crate) fn parse_readme_docs_signal(line: &str) -> ReadmeDocsMetadata {
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

pub(crate) fn extract_markdown_links(line: &str) -> Vec<(String, String)> {
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

pub(crate) fn parse_codeowners_metadata(contents: &str) -> CodeownersMetadata {
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

pub(crate) fn parse_security_contact(contents: &str) -> Option<String> {
    find_mailto_or_email(contents).or_else(|| find_first_url(contents))
}

pub(crate) fn parse_security_import_metadata(contents: &str) -> SecurityImportMetadata {
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

pub(crate) fn parse_contributing_security(contents: &str) -> Option<String> {
    // Extract the security reporting section from CONTRIBUTING.md.
    // Only look under headings that mention "security", "vulnerability",
    // or "responsible disclosure".
    let mut in_security_section = false;
    let mut section_depth = 0;
    let mut security_text = String::new();

    for line in contents.lines() {
        let trimmed = line.trim();
        let heading_depth = trimmed.chars().take_while(|c| *c == '#').count();
        let is_heading = heading_depth > 0 && trimmed.starts_with('#');

        if is_heading {
            let heading_text = trimmed.trim_start_matches('#').trim().to_lowercase();

            if in_security_section {
                // Same or higher-level heading ends the security section
                if heading_depth <= section_depth {
                    in_security_section = false;
                }
            }

            if !in_security_section
                && (heading_text.contains("security")
                    || heading_text.contains("vulnerability")
                    || heading_text.contains("responsible disclosure"))
            {
                in_security_section = true;
                section_depth = heading_depth;
                continue;
            }
        }

        if in_security_section {
            security_text.push_str(line);
            security_text.push('\n');
        }
    }

    if security_text.trim().is_empty() {
        return None;
    }

    parse_security_contact(&security_text)
}

pub(crate) fn parse_issue_template_security(contents: &str) -> Option<String> {
    // Look for security reporting links or emails in issue templates.
    // YAML front matter or plain markdown.
    parse_security_contact(contents)
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

    // Fall back to the first URL that looks semantically related to security reporting.
    // This catches cases where the URL contains "security" in its path but the surrounding
    // text triggers a negative score (e.g., "policy" in the line penalizes the URL).
    let rewritten = rewrite_markdown_links(contents);

    for destination in security_link_destinations(contents) {
        if let Some(url) = extract_url_candidate(&destination) {
            if looks_like_security_url(&url) {
                return Some(url);
            }
        }
    }

    for token in rewritten.split_whitespace() {
        if let Some(url) = extract_url_candidate(token) {
            if looks_like_security_url(&url) {
                return Some(url);
            }
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

fn looks_like_security_url(url: &str) -> bool {
    let lowered = url.to_ascii_lowercase();

    // Reject known non-security URL patterns.
    let non_security_path_keywords = [
        "blog", "docs/", "tutorial", "guide/", "wiki/", "example", "demo",
    ];
    for keyword in &non_security_path_keywords {
        if lowered.contains(keyword) {
            return false;
        }
    }

    // Accept URLs that contain security-related keywords in their path.
    let security_path_keywords = [
        "security",
        "vulnerability",
        "disclosure",
        "advisories",
        "report",
        "contact",
        "issue",
    ];
    for keyword in &security_path_keywords {
        if lowered.contains(keyword) {
            return true;
        }
    }

    false
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
            '<' | '>'
                | '('
                | ')'
                | '['
                | ']'
                | '{'
                | '}'
                | ','
                | ';'
                | ':'
                | '.'
                | '"'
                | '\''
                | '`'
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
