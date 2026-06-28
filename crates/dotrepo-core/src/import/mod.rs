use anyhow::{anyhow, Result};
use dotrepo_schema::{
    parse_manifest, render_manifest, Compat, CompatMode, Docs, GitHubCompat, Manifest, Owners,
    Readme, Record, RecordMode, RecordStatus, Relations, Repo, Trust,
};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};

use crate::render::{
    render_contributing_body, render_pull_request_template_body, render_security_body,
};
use crate::surfaces::is_banner_line;
use crate::util::{display_path, display_root, normalize_rfc3339};
use crate::validate_manifest;
use crate::{record_summary, RecordSummary};

mod adjudication;
mod commands;
mod escalation;
mod parsing;

pub use adjudication::{
    AdjudicationProvider, AdjudicationProviderResponse, AdjudicationTier, AdjudicationTierProvider,
    ImportEscalationOptions, NoopAdjudicationProvider, StubAdjudicationProvider,
    TieredAdjudicationProviders,
};
pub use escalation::{
    adjudicate_requests_deterministic, apply_adjudication_to_import_plan,
    autonomous_writeback_eligible, run_import_escalation, ImportEscalationReport,
};

use commands::{
    load_first_existing_file, load_first_root_file_with_extension, load_workflow_import_files,
    sanitize_import_command,
};

#[allow(unused_imports)]
pub(crate) use commands::{infer_imported_commands, infer_pyproject_commands};

#[allow(unused_imports)]
pub(crate) use parsing::{
    clean_project_description, extract_markdown_links, is_actionable_security_url,
    is_non_project_heading, is_quality_url, normalize_description_line, parse_codeowners_metadata,
    parse_contributing_security, parse_issue_template_security, parse_readme_docs_signal,
    parse_readme_metadata, parse_readme_security, parse_readme_title_line, parse_security_contact,
    parse_security_import_metadata, try_parse_multiline_html_heading,
};

use parsing::clean_project_name;

pub(crate) const IMPORT_README_CANDIDATES: &[&str] = &[
    "README.md",
    "README.MD",
    "readme.md",
    "README.mdx",
    "README.markdown",
    "README",
];
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

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
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
    let source_url = source
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .or(plan.manifest.record.source.as_deref())
        .unwrap_or("");
    let verification = verify_import_plan(root, &plan, source_url);
    let field_scores = score_import_fields(&plan, &verification);
    Ok(ImportPreviewReport {
        root: display_root(root),
        mode: import_mode_name(mode),
        manifest_path: display_path(root, &plan.manifest_path)?,
        manifest: plan.manifest.clone(),
        manifest_text: plan.manifest_text.clone(),
        evidence_path: match plan.evidence_path.as_ref() {
            Some(path) => Some(display_path(root, path)?),
            None => None,
        },
        evidence_text: plan.evidence_text.clone(),
        imported_sources: plan.imported_sources.clone(),
        inferred_fields: plan.inferred_fields.clone(),
        field_scores: field_scores.summary,
        verification_passed: verification.passed,
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

pub fn adopt_overlay_record(root: &Path, overlay_record_path: &Path) -> Result<ImportPlan> {
    let raw = fs::read_to_string(overlay_record_path)
        .map_err(|err| anyhow!("failed to read {}: {}", overlay_record_path.display(), err))?;
    let mut manifest = parse_manifest(&raw)
        .map_err(|err| anyhow!("failed to parse {}: {}", overlay_record_path.display(), err))?;
    if manifest.record.mode != RecordMode::Overlay {
        return Err(anyhow!(
            "adopt-overlay requires record.mode = \"overlay\" in {}",
            overlay_record_path.display()
        ));
    }

    let overlay_source = manifest.record.source.clone();
    let omitted_doc_entries = scrub_overlay_docs_for_native(root, &mut manifest);
    manifest.record.mode = RecordMode::Native;
    manifest.record.status = RecordStatus::Draft;
    manifest.record.source = None;
    manifest.record.generated_at = None;
    manifest.record.trust = Some(Trust {
        confidence: Some("low".into()),
        provenance: vec!["imported".into()],
        notes: Some({
            let mut note = match overlay_source {
                Some(source) => format!(
                "Bootstrapped from overlay record {} for {}; maintainers should review before claiming canonical authority.",
                overlay_record_path.display(),
                source
            ),
                None => format!(
                "Bootstrapped from overlay record {}; maintainers should review before claiming canonical authority.",
                overlay_record_path.display()
            ),
            };
            if omitted_doc_entries > 0 {
                note.push_str(
                    " Overlay documentation URLs were omitted because native docs entries must reference local repository paths.",
                );
            }
            note
        }),
    });
    manifest.readme = None;
    manifest.compat = None;

    validate_manifest(root, &manifest)?;
    let manifest_text = render_manifest(&manifest)?;
    Ok(ImportPlan {
        manifest_path: root.join(".repo"),
        manifest,
        manifest_text,
        evidence_path: None,
        evidence_text: None,
        imported_sources: vec![overlay_record_path.display().to_string()],
        inferred_fields: Vec::new(),
        command_candidates: ImportCommandCandidates::default(),
    })
}

fn scrub_overlay_docs_for_native(root: &Path, manifest: &mut Manifest) -> usize {
    let Some(docs) = manifest.docs.as_mut() else {
        return 0;
    };
    let mut omitted = 0;
    let mut scrub = |value: &mut Option<String>| {
        let Some(current) = value.as_deref() else {
            return;
        };
        let trimmed = current.trim();
        if trimmed.contains("://") || !root.join(trimmed).exists() {
            *value = None;
            omitted += 1;
        }
    };
    scrub(&mut docs.root);
    scrub(&mut docs.getting_started);
    scrub(&mut docs.architecture);
    scrub(&mut docs.api);
    if docs.root.is_none()
        && docs.getting_started.is_none()
        && docs.architecture.is_none()
        && docs.api.is_none()
    {
        manifest.docs = None;
    }
    omitted
}

fn importable_docs_entry(root: &Path, mode: ImportMode, value: Option<&str>) -> Option<String> {
    let value = value?.trim();
    if !is_quality_url(value) {
        return None;
    }
    match mode {
        ImportMode::Overlay => Some(value.to_string()),
        ImportMode::Native => {
            (!value.contains("://") && root.join(value).exists()).then(|| value.to_string())
        }
    }
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
    let setup_py = load_first_existing_file(root, &["setup.py"])?;
    let setup_cfg = load_first_existing_file(root, &["setup.cfg"])?;
    let go_mod = load_first_existing_file(root, &["go.mod"])?;
    let pom_xml = load_first_existing_file(root, &["pom.xml"])?;
    let build_gradle = load_first_existing_file(root, &["build.gradle", "build.gradle.kts"])?;
    let composer_json = load_first_existing_file(root, &["composer.json"])?;
    let csproj = load_first_root_file_with_extension(root, "csproj")?;
    let mix_exs = load_first_existing_file(root, &["mix.exs"])?;
    let rebar_config = load_first_existing_file(root, &["rebar.config"])?;
    let cmake_presets_json = load_first_existing_file(root, &["CMakePresets.json"])?;
    let workflow_files = load_workflow_import_files(root)?;
    let contributing =
        load_first_existing_file(root, &["CONTRIBUTING.md", ".github/CONTRIBUTING.md"])?;
    let makefile = load_first_existing_file(root, &["GNUmakefile", "Makefile", "makefile"])?;
    let justfile = load_first_existing_file(root, &["justfile", "Justfile"])?;
    let rakefile = load_first_existing_file(root, &["Rakefile", "rakefile"])?;
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

    let (security_contact, security_note) = infer_security_contact_and_note(
        security.as_ref(),
        &parsed_security,
        contributing_security,
        template_security,
        has_contributing_security,
        has_template_security,
    );

    /// Centralizes the decision tree for security_contact + accompanying note.
    /// This reduces duplication between the primary import path and any preview/evidence synthesis.
    fn infer_security_contact_and_note(
        security: Option<&ImportedFile>,
        parsed: &SecurityImportMetadata,
        from_contributing: Option<String>,
        from_template: Option<String>,
        has_contrib: bool,
        has_template: bool,
    ) -> (Option<String>, Option<String>) {
        let contact = parsed
            .contact
            .clone()
            .or(from_contributing.clone())
            .or(from_template.clone())
            .or_else(|| {
                if security.is_some() {
                    Some("unknown".into())
                } else {
                    None
                }
            });

        let note = if security.is_some() {
            if parsed.contact.is_some() {
                parsed.note.clone()
            } else if has_contrib {
                Some(
                "SECURITY.md did not expose a direct mailbox or reporting URL. `security_contact` was extracted from CONTRIBUTING.md instead."
                    .to_string(),
            )
            } else if has_template {
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
        } else if has_contrib {
            Some(
                "`security_contact` was extracted from CONTRIBUTING.md (no SECURITY.md found)."
                    .to_string(),
            )
        } else if has_template {
            Some(
                "`security_contact` was extracted from an issue template (no SECURITY.md found)."
                    .to_string(),
            )
        } else {
            None
        };

        (contact, note)
    }
    let imported_commands = infer_imported_commands(&ImportSources {
        cargo_toml: cargo_toml.as_ref(),
        package_json: package_json.as_ref(),
        pyproject_toml: pyproject_toml.as_ref(),
        setup_py: setup_py.as_ref(),
        setup_cfg: setup_cfg.as_ref(),
        go_mod: go_mod.as_ref(),
        pom_xml: pom_xml.as_ref(),
        build_gradle: build_gradle.as_ref(),
        composer_json: composer_json.as_ref(),
        csproj: csproj.as_ref(),
        mix_exs: mix_exs.as_ref(),
        rebar_config: rebar_config.as_ref(),
        cmake_presets_json: cmake_presets_json.as_ref(),
        makefile: makefile.as_ref(),
        justfile: justfile.as_ref(),
        rakefile: rakefile.as_ref(),
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
    // dir_name fallback is used only when README signals are weak or absent.
    // import_quality_gate and expectations track when "repo.name" is inferred.
    // Root at filesystem root or odd paths will produce the generic default.

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
        importable_docs_entry(root, mode, readme_metadata.docs_root.as_deref()),
        importable_docs_entry(root, mode, readme_metadata.docs_getting_started.as_deref()),
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
                .and_then(|command| sanitize_import_command(&command.command)),
            test: imported_commands
                .test
                .as_ref()
                .and_then(|command| sanitize_import_command(&command.command)),
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

    // Final defense-in-depth sanitization of build/test before validation/render.
    // Unsafe values are rejected even if an earlier path missed the filter.
    if let Some(cmd) = manifest.repo.build.take() {
        if sanitize_import_command(&cmd).is_some() {
            manifest.repo.build = Some(cmd);
        }
    }
    if let Some(cmd) = manifest.repo.test.take() {
        if sanitize_import_command(&cmd).is_some() {
            manifest.repo.test = Some(cmd);
        }
    }

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

fn command_field_has_safe_candidates(
    candidates: &[CommandCandidateSummary],
    select_build: bool,
) -> bool {
    candidates.iter().any(|candidate| {
        let value = if select_build {
            candidate.build.as_ref()
        } else {
            candidate.test.as_ref()
        };
        value
            .and_then(|command| sanitize_import_command(command))
            .is_some()
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

    // Field completeness: check build/test resolution. Unsafe shell-like candidates
    // are ignored for unresolved scoring so escalation cannot re-apply them.
    if plan.manifest.repo.build.is_none() {
        if command_field_has_safe_candidates(&plan.command_candidates.candidates, true) {
            unresolved_fields.push("repo.build".into());
        } else {
            absent_fields.push("repo.build".into());
        }
    }
    if plan.manifest.repo.test.is_none() {
        if command_field_has_safe_candidates(&plan.command_candidates.candidates, false) {
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

    for output in &mut reserved {
        if let Err(err) = output
            .file
            .write_all(output.contents.as_bytes())
            .and_then(|_| output.file.flush())
        {
            for item in &reserved {
                let _ = fs::remove_file(&item.path);
            }
            return Err(err.into());
        }
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
            if let Some(value) = value.filter(|command| sanitize_import_command(command).is_some())
            {
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
    pub(crate) setup_py: Option<&'a ImportedFile>,
    pub(crate) setup_cfg: Option<&'a ImportedFile>,
    pub(crate) go_mod: Option<&'a ImportedFile>,
    pub(crate) pom_xml: Option<&'a ImportedFile>,
    pub(crate) build_gradle: Option<&'a ImportedFile>,
    pub(crate) composer_json: Option<&'a ImportedFile>,
    pub(crate) csproj: Option<&'a ImportedFile>,
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
pub(super) fn push_unique(values: &mut Vec<String>, value: String) {
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

pub(super) fn human_join(values: &[String]) -> String {
    match values {
        [] => String::new(),
        [only] => format!("`{}`", only),
        [first, second] => format!("`{}` and `{}`", first, second),
        _ => {
            let (leading, [last]) = values.split_at(values.len() - 1) else {
                return String::new();
            };
            let leading = leading
                .iter()
                .map(|value| format!("`{}`", value))
                .collect::<Vec<_>>()
                .join(", ");
            format!("{}, and `{}`", leading, last)
        }
    }
}

#[cfg(test)]
mod write_import_output_tests {
    use super::write_import_outputs;
    use std::fs;
    use std::path::PathBuf;

    fn temp_dir(label: &str) -> PathBuf {
        let unique = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        let path = std::env::temp_dir().join(format!("dotrepo-import-write-{label}-{unique}"));
        fs::create_dir_all(&path).expect("temp dir created");
        path
    }

    #[test]
    fn write_import_outputs_rolls_back_when_second_write_fails() {
        use std::os::unix::fs::PermissionsExt;

        let root = temp_dir("rollback");
        let first = root.join("record.toml");
        let readonly_dir = root.join("readonly_dir");
        fs::create_dir(&readonly_dir).expect("readonly dir created");
        let mut permissions = fs::metadata(&readonly_dir)
            .expect("readonly dir metadata")
            .permissions();
        permissions.set_mode(0o555);
        fs::set_permissions(&readonly_dir, permissions).expect("readonly dir permissions set");

        let err = write_import_outputs(
            vec![
                (first.clone(), "manifest\n".into()),
                (readonly_dir.join("evidence.md"), "evidence\n".into()),
            ],
            false,
            "--force",
        )
        .expect_err("second write should fail");

        assert!(
            !first.exists(),
            "partial manifest should be rolled back: {err}"
        );

        let mut permissions = fs::metadata(&readonly_dir)
            .expect("readonly dir metadata")
            .permissions();
        permissions.set_mode(0o755);
        fs::set_permissions(&readonly_dir, permissions).expect("readonly dir permissions reset");
        fs::remove_dir_all(root).expect("temp dir removed");
    }
}
