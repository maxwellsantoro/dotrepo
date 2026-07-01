use anyhow::{anyhow, Result};
use dotrepo_schema::{
    parse_manifest, render_manifest, Compat, Manifest, Readme, Record, RecordMode, RecordStatus,
    Relations, Repo, Trust,
};
use std::fs;
use std::path::{Path, PathBuf};

use crate::record_summary;
use crate::util::{display_path, display_root, normalize_rfc3339};
use crate::validate_manifest;

mod adjudication;
mod commands;
mod escalation;
mod evidence;
mod fields;
mod parsing;
mod types;

pub use adjudication::{
    AdjudicationProvider, AdjudicationProviderResponse, AdjudicationTier, AdjudicationTierProvider,
    ImportEscalationOptions, NoopAdjudicationProvider, StubAdjudicationProvider,
    TieredAdjudicationProviders,
};
pub use escalation::{
    adjudicate_requests_deterministic, apply_adjudication_to_import_plan,
    autonomous_writeback_eligible, run_import_escalation, ImportEscalationReport,
};
pub use evidence::infer_docs_root_from_external_homepage;
pub use fields::{
    apply_adjudication_response, apply_adjudication_results, build_adjudication_requests,
    score_import_fields,
};
pub use types::{
    AdjudicationCandidate, AdjudicationModelConfidence, AdjudicationModelResponse,
    AdjudicationOutcome, AdjudicationRequest, AdjudicationResult, CandidateProvenance,
    CommandCandidateSelection, CommandCandidateSummary, CommandSourceTier, FieldConfidence,
    FieldScore, FieldScoreReport, FieldScoreSummary, GitHubSnapshotFacts, ImportCommandCandidates,
    ImportMode, ImportOptions, ImportPlan, ImportPreviewReport, ImportedCommandProvenance,
    VerificationCheck, VerificationReport, VerificationSeverity,
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

use evidence::{
    build_imported_docs, build_imported_owners, discover_relations_from_github_facts,
    discover_relations_from_manifest_files, native_import_github_compat, render_import_evidence,
    ImportEvidenceNotes,
};
use parsing::clean_project_name;
pub(crate) use types::{ImportSources, ImportedFile, SecurityImportMetadata};

pub(crate) const IMPORT_README_CANDIDATES: &[&str] = &[
    "README.md",
    "README.MD",
    "readme.md",
    "README.mdx",
    "README.markdown",
    "README",
];

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
        root: display_root(root)?,
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
            // Populated later by escalation (see
            // apply_adjudication_to_import_plan's Absent branch) if a
            // genuine multi-ecosystem tie is found for build or test.
            build_candidates: Vec::new(),
            test_candidates: Vec::new(),
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

    // Deterministic, conservative relation discovery for autonomous overlay records.
    // Only populates high-certainty links (e.g. GitHub fork parent) grounded in provided facts.
    // Never fabricates; native records and cases without evidence remain unaffected.
    let (mut discovered_links, mut relation_evidence_notes) =
        discover_relations_from_github_facts(options.github.as_ref());
    // Additional conservative discovery from package manifests (Cargo.toml / package.json
    // "repository" fields containing github urls). High-certainty only; used for overlay
    // autonomous path to satisfy declared-references requirement.
    if matches!(mode, ImportMode::Overlay) {
        if let Some((extra, enotes)) = discover_relations_from_manifest_files(root) {
            for l in extra {
                if !discovered_links.iter().any(|x| x.target == l.target) {
                    discovered_links.push(l);
                }
            }
            relation_evidence_notes.extend(enotes);
        }
    }
    manifest.relations = match mode {
        ImportMode::Native => None,
        ImportMode::Overlay if discovered_links.is_empty() => None,
        ImportMode::Overlay => Some(Relations {
            references: Vec::new(),
            links: discovered_links,
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
                ImportEvidenceNotes {
                    security_contact: security_contact.as_deref(),
                    codeowners_note: codeowners_metadata.note.as_deref(),
                    security_note: security_note.as_deref(),
                    imported_docs: imported_docs.is_some(),
                },
                &imported_commands.evidence_bullets,
                &relation_evidence_notes,
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
