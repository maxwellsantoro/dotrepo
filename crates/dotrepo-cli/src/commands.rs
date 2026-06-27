use anyhow::{bail, Context, Result};
use dotrepo_core::{
    adopt_managed_surface, adopt_overlay_record, adoption_status_repository,
    analyze_index_promotion, append_claim_event, build_public_freshness_with_digest,
    current_public_freshness, current_timestamp_rfc3339, export_public_index_static_with_base,
    generate_check_repository, import_repository_with_options, index_snapshot_digest,
    inspect_claim_directory, inspect_surface_states, load_manifest_document,
    load_manifest_from_root, managed_outputs, preview_surfaces, public_profile_compare_with_base,
    public_profile_search_with_base, public_repository_batch_profiles_with_base,
    public_repository_batch_query_with_base, public_repository_profile_or_error_with_base,
    public_repository_query_or_error_with_base, public_repository_relations_with_base,
    public_repository_summary_or_error_with_base, public_repository_trust_or_error_with_base,
    query_repository, render_dotrepo_ci_workflow, resolve_claim_directory,
    scaffold_claim_directory, trust_repository, validate_index_root, validate_manifest,
    validate_repository, write_import_outputs, ClaimEventAppendInput, ClaimScaffoldInput,
    DoctorReport, DoctorSurface, ImportOptions, IndexFindingSeverity, PublicErrorResponse,
    PublicProfileSearchOptions, PublicRepositoryIdentity,
};
use dotrepo_schema::scaffold_manifest as render_scaffold_manifest;
use dotrepo_schema::RecordMode;
use serde::Serialize;
use std::fs;
use std::path::PathBuf;

use crate::cli::{
    CiCommand, ClaimEventKindArg, CorrectedClaimStateArg, ImportModeArg, PreviewSurfaceArg,
    PublicCommand,
};

use crate::error::CliExit;
use crate::format::{
    format_claim_report, format_doctor_surface, format_managed_file_state, format_query_value,
    format_trust_report, print_surface_preview_report,
};

pub fn cmd_validate(root: PathBuf) -> Result<()> {
    let report = validate_repository(&root);
    if !report.valid {
        return Err(CliExit {
            code: 1,
            message: format!(
                "manifest invalid:\n{}",
                report
                    .diagnostics
                    .into_iter()
                    .map(|diagnostic| format!("- [{}] {}", diagnostic.source, diagnostic.message))
                    .collect::<Vec<_>>()
                    .join("\n")
            ),
        }
        .into());
    }
    println!("manifest valid");
    Ok(())
}

pub fn cmd_init(root: PathBuf, force: bool) -> Result<()> {
    let manifest_path = root.join(".repo");
    if manifest_path.exists() && !force {
        bail!(
            "{} already exists; rerun with --force to overwrite it",
            manifest_path.display()
        );
    }

    let repo_name = root
        .file_name()
        .and_then(|name| name.to_str())
        .filter(|name| !name.is_empty())
        .unwrap_or("repository")
        .to_string();
    // When falling back to directory name or the generic default "repository",
    // the generated .repo will contain a placeholder. Users should edit repo.name
    // (or pass a more specific root). We deliberately do not fail init for usability.
    let manifest = render_scaffold_manifest(&repo_name)?;
    fs::write(&manifest_path, manifest)?;
    println!("initialized {}", manifest_path.display());
    Ok(())
}

pub fn cmd_import(
    root: PathBuf,
    mode: ImportModeArg,
    source: Option<String>,
    force: bool,
) -> Result<()> {
    let plan = import_repository_with_options(
        &root,
        mode.into(),
        source.as_deref(),
        &ImportOptions {
            generated_at: Some(current_timestamp()?),
        },
    )?;

    let mut outputs = vec![(plan.manifest_path.clone(), plan.manifest_text.clone())];
    if let (Some(path), Some(contents)) = (&plan.evidence_path, &plan.evidence_text) {
        outputs.push((path.clone(), contents.clone()));
    }

    let written_paths = outputs
        .iter()
        .map(|(path, _)| path.clone())
        .collect::<Vec<_>>();
    write_import_outputs(outputs, force, "--force")?;
    for path in written_paths {
        println!("imported {}", path.display());
    }

    if !plan.imported_sources.is_empty() {
        println!("- imported from: {}", plan.imported_sources.join(", "));
    }
    if !plan.inferred_fields.is_empty() {
        println!("- inferred defaults: {}", plan.inferred_fields.join(", "));
    }
    println!("- mode: {:?}", plan.manifest.record.mode);
    println!("- status: {:?}", plan.manifest.record.status);

    Ok(())
}

pub fn cmd_adopt_overlay(root: PathBuf, overlay_record: PathBuf, force: bool) -> Result<()> {
    let plan = adopt_overlay_record(&root, &overlay_record)?;
    let manifest_path = plan.manifest_path.clone();
    write_import_outputs(
        vec![(plan.manifest_path, plan.manifest_text)],
        force,
        "--force",
    )?;
    println!("adopted overlay into {}", manifest_path.display());
    println!("- imported from: {}", overlay_record.display());
    println!("- mode: {:?}", plan.manifest.record.mode);
    println!("- status: {:?}", plan.manifest.record.status);
    Ok(())
}

pub fn cmd_query(root: PathBuf, path: &str, json: bool, raw: bool) -> Result<()> {
    let report = query_repository(&root, path)?;
    if json {
        println!("{}", serde_json::to_string_pretty(&report)?);
    } else {
        if raw && !report.conflicts.is_empty() {
            bail!("--raw is only supported when query selection has no competing records");
        }
        println!("{}", format_query_value(&report.value, raw)?);
    }
    Ok(())
}

pub fn cmd_validate_index(index_root: PathBuf) -> Result<()> {
    let findings = validate_index_root(&index_root)?;
    if findings.is_empty() {
        println!("index valid");
        return Ok(());
    }

    let mut warnings = Vec::new();
    let mut errors = Vec::new();
    for finding in findings {
        match finding.severity {
            IndexFindingSeverity::Warning => warnings.push(finding),
            IndexFindingSeverity::Error => errors.push(finding),
        }
    }

    if errors.is_empty() {
        println!("index valid with warnings");
        for finding in warnings {
            println!("warning: {}: {}", finding.path.display(), finding.message);
        }
        return Ok(());
    }

    let mut sections = vec![format!(
        "index validation failed:\n{}",
        errors
            .into_iter()
            .map(|finding| format!("- {}: {}", finding.path.display(), finding.message))
            .collect::<Vec<_>>()
            .join("\n")
    )];

    if !warnings.is_empty() {
        sections.push(format!(
            "warnings:\n{}",
            warnings
                .into_iter()
                .map(|finding| format!("- {}: {}", finding.path.display(), finding.message))
                .collect::<Vec<_>>()
                .join("\n")
        ));
    }

    Err(CliExit {
        code: 1,
        message: sections.join("\n"),
    }
    .into())
}

pub fn cmd_promotion_report(index_root: PathBuf, json: bool, verbose: bool) -> Result<()> {
    let report = analyze_index_promotion(&index_root)?;

    if json {
        #[derive(Serialize)]
        #[serde(rename_all = "camelCase")]
        struct JsonReport {
            total_records: usize,
            eligible_count: usize,
            field_blocker_counts: std::collections::HashMap<String, usize>,
            records: Vec<JsonRecord>,
        }
        #[derive(Serialize)]
        #[serde(rename_all = "camelCase")]
        struct JsonRecord {
            path: String,
            source_url: Option<String>,
            status: Option<String>,
            eligible: bool,
            blockers: Vec<String>,
        }
        let json_report = JsonReport {
            total_records: report.summary.total_records,
            eligible_count: report.summary.eligible_count,
            field_blocker_counts: report.summary.field_blocker_counts,
            records: report
                .records
                .into_iter()
                .map(|r| {
                    let blockers: Vec<String> = r
                        .scores
                        .iter()
                        .filter(|s| {
                            !matches!(
                                s.confidence,
                                dotrepo_core::FieldConfidence::HighConfidencePresent
                                    | dotrepo_core::FieldConfidence::HighConfidenceAbsent
                            )
                        })
                        .map(|s| {
                            format!(
                                "{}: {:?} — {}",
                                s.field,
                                match s.confidence {
                                    dotrepo_core::FieldConfidence::MediumConfidencePresent =>
                                        "medium-present",
                                    dotrepo_core::FieldConfidence::Unresolved => "unresolved",
                                    _ => "other",
                                },
                                s.reason
                            )
                        })
                        .collect();
                    JsonRecord {
                        path: r.path,
                        source_url: r.source_url,
                        status: r.status,
                        eligible: r.eligible,
                        blockers,
                    }
                })
                .collect(),
        };
        println!("{}", serde_json::to_string_pretty(&json_report)?);
        return Ok(());
    }

    let s = &report.summary;
    println!(
        "promotion analysis: {}/{} records eligible for verified auto-publish",
        s.eligible_count, s.total_records
    );
    println!();

    if !s.field_blocker_counts.is_empty() {
        let mut blockers: Vec<_> = s.field_blocker_counts.iter().collect();
        blockers.sort_by(|a, b| b.1.cmp(a.1));
        println!("field blockers (blocking auto-publish):");
        for (field, count) in &blockers {
            println!("  {} × {}", count, field);
        }
        println!();
    }

    if verbose {
        for record in &report.records {
            let tag = if record.eligible {
                "ELIGIBLE"
            } else {
                "BLOCKED"
            };
            println!(
                "[{}] {} ({})",
                tag,
                record.path,
                record.source_url.as_deref().unwrap_or("?")
            );
            for score in &record.scores {
                let marker = match score.confidence {
                    dotrepo_core::FieldConfidence::HighConfidencePresent => "H+",
                    dotrepo_core::FieldConfidence::MediumConfidencePresent => "M+",
                    dotrepo_core::FieldConfidence::HighConfidenceAbsent => "H-",
                    dotrepo_core::FieldConfidence::Unresolved => "??",
                };
                println!("  {} {}: {}", marker, score.field, score.reason);
            }
            println!();
        }
    }

    Ok(())
}

pub fn cmd_generate(root: PathBuf, check: bool) -> Result<()> {
    if check {
        let manifest = load_manifest_from_root(&root)?;
        validate_manifest(&root, &manifest)?;
        ensure_native_record_command(&manifest.record.mode, "generate-check")?;
        let report = generate_check_repository(&root)?;
        if !report.stale.is_empty() {
            return Err(CliExit {
                code: 2,
                message: format!(
                    "generated files are out of date:\n{}",
                    report
                        .outputs
                        .into_iter()
                        .filter(|output| output.stale)
                        .map(|output| {
                            let mut line = format!(
                                "- {} [{}]",
                                output.path,
                                format_managed_file_state(output.state)
                            );
                            if let Some(message) = output.message {
                                line.push_str(&format!(": {}", message));
                            }
                            line
                        })
                        .collect::<Vec<_>>()
                        .join("\n")
                ),
            }
            .into());
        }
        return Ok(());
    }

    let document = load_manifest_document(&root)?;
    validate_manifest(&root, &document.manifest)?;
    ensure_native_record_command(&document.manifest.record.mode, "generate")?;
    let outputs = managed_outputs(&root, &document.manifest, &document.raw)?;

    for (path, contents) in outputs {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::write(&path, contents)?;
        println!("generated {}", path.display());
    }

    Ok(())
}

pub fn cmd_doctor(root: PathBuf, json: bool) -> Result<()> {
    let manifest = load_manifest_from_root(&root)?;
    validate_manifest(&root, &manifest)?;
    ensure_native_record_command(&manifest.record.mode, "doctor")?;
    let findings = inspect_surface_states(&root)?;
    if json {
        let report = DoctorReport {
            mode: manifest.record.mode.clone(),
            status: manifest.record.status.clone(),
            findings,
        };
        println!("{}", serde_json::to_string_pretty(&report)?);
        return Ok(());
    }

    println!("dotrepo doctor");
    println!("- mode: {:?}", manifest.record.mode);
    println!("- status: {:?}", manifest.record.status);
    if findings.is_empty() {
        println!("- no managed-surface findings detected");
    } else {
        println!("- conventional surface states:");
        for finding in findings {
            println!(
                "  - {} [{}]: {}",
                finding.path.display(),
                format_managed_file_state(finding.state),
                finding.message
            );
        }
    }
    Ok(())
}

pub fn cmd_manage(root: PathBuf, surface: PreviewSurfaceArg, adopt: bool) -> Result<()> {
    let manifest = load_manifest_from_root(&root)?;
    validate_manifest(&root, &manifest)?;
    ensure_native_record_command(&manifest.record.mode, "manage")?;

    if !adopt {
        return Err(CliExit {
            code: 2,
            message: "manage currently requires --adopt".into(),
        }
        .into());
    }

    let plan = adopt_managed_surface(&root, surface.into())?;
    if let Some(parent) = plan.path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(&plan.path, plan.contents)?;
    println!(
        "adopted {} as a partially managed {} surface",
        plan.path.display(),
        format_doctor_surface(plan.surface)
    );
    Ok(())
}

pub fn cmd_preview(
    root: PathBuf,
    surface: Option<PreviewSurfaceArg>,
    all: bool,
    json: bool,
) -> Result<()> {
    let manifest = load_manifest_from_root(&root)?;
    validate_manifest(&root, &manifest)?;
    ensure_native_record_command(&manifest.record.mode, "preview")?;

    let selected_surfaces = if all {
        vec![
            DoctorSurface::Readme,
            DoctorSurface::Security,
            DoctorSurface::Contributing,
            DoctorSurface::Codeowners,
            DoctorSurface::PullRequestTemplate,
        ]
    } else if let Some(surface) = surface {
        vec![surface.into()]
    } else {
        return Err(CliExit {
            code: 2,
            message: "preview requires either --surface <name> or --all".into(),
        }
        .into());
    };

    let report = preview_surfaces(&root, &selected_surfaces)?;
    if json {
        println!("{}", serde_json::to_string_pretty(&report)?);
        return Ok(());
    }

    print_surface_preview_report(&report);
    Ok(())
}

pub fn cmd_ci(root: PathBuf, command: CiCommand) -> Result<()> {
    match command {
        CiCommand::Init { force, version } => cmd_ci_init(root, force, version),
    }
}

fn ensure_native_record_command(mode: &RecordMode, command: &str) -> Result<()> {
    if *mode == RecordMode::Overlay {
        return Err(CliExit {
            code: 2,
            message: format!(
                "{} is only supported for native records; found record.mode = \"overlay\"",
                command
            ),
        }
        .into());
    }

    Ok(())
}

pub fn cmd_ci_init(root: PathBuf, force: bool, version: Option<String>) -> Result<()> {
    let manifest = load_manifest_from_root(&root)?;
    validate_manifest(&root, &manifest)?;
    ensure_native_record_command(&manifest.record.mode, "ci init")?;

    let workflow_path = root.join(".github/workflows/dotrepo-check.yml");
    if workflow_path.exists() && !force {
        bail!(
            "{} already exists; rerun with --force to overwrite it",
            workflow_path.display()
        );
    }

    let version = version.unwrap_or_else(|| env!("CARGO_PKG_VERSION").to_string());
    let workflow = render_dotrepo_ci_workflow(&version);
    if let Some(parent) = workflow_path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(&workflow_path, workflow)?;
    println!(
        "initialized {} with dotrepo {}",
        workflow_path.display(),
        version
    );
    Ok(())
}

pub fn cmd_trust(root: PathBuf, json: bool) -> Result<()> {
    let report = trust_repository(&root)?;
    if json {
        println!("{}", serde_json::to_string_pretty(&report)?);
        return Ok(());
    }

    println!("{}", format_trust_report(&report));
    Ok(())
}

pub fn cmd_adoption_status(root: PathBuf, json: bool) -> Result<()> {
    let report = adoption_status_repository(&root);
    if json {
        println!("{}", serde_json::to_string_pretty(&report)?);
        return Ok(());
    }

    println!("adoption status for {}", report.root);
    if let Some(status) = &report.record_status {
        println!("- record status: {status}");
    }
    if let Some(identity) = &report.repository_identity {
        println!(
            "- repository identity: {}/{}/{} ({})",
            identity.host, identity.owner, identity.repo, identity.url
        );
    }
    for check in &report.checks {
        let marker = if check.ready { "ok" } else { "needs attention" };
        println!("- {}: {} - {}", check.name, marker, check.detail);
    }
    println!("next steps:");
    for step in &report.next_steps {
        println!("- {step}");
    }
    Ok(())
}

pub fn cmd_claim(root: PathBuf, path: PathBuf, json: bool) -> Result<()> {
    let claim_dir = resolve_claim_directory(
        &root,
        path.to_str().context("claim path must be valid UTF-8")?,
    )?;
    let report = inspect_claim_directory(&root, &claim_dir)?;
    if json {
        println!("{}", serde_json::to_string_pretty(&report)?);
        return Ok(());
    }

    println!("{}", format_claim_report(&report));
    Ok(())
}

pub struct ClaimInitArgs {
    pub host: String,
    pub owner: String,
    pub repo: String,
    pub claim_id: String,
    pub claimant_name: String,
    pub asserted_role: String,
    pub contact: Option<String>,
    pub record_sources: Vec<String>,
    pub canonical_repo_url: Option<String>,
    pub review_md: bool,
    pub force: bool,
}

pub struct ClaimFromNativeArgs {
    pub index_root: PathBuf,
    pub claim_id: String,
    pub claimant_name: String,
    pub asserted_role: String,
    pub contact: Option<String>,
    pub review_md: bool,
    pub force: bool,
}

struct NativeRepositoryIdentity {
    host: String,
    owner: String,
    repo: String,
    url: String,
}

fn repository_identity_from_url(url: &str) -> Option<(String, String, String)> {
    let (_scheme, rest) = url.split_once("://")?;
    let without_query = rest
        .split(['?', '#'])
        .next()
        .unwrap_or(rest)
        .trim_end_matches('/');
    let mut parts = without_query.split('/').filter(|part| !part.is_empty());
    let host = parts.next()?.to_string();
    let owner = parts.next()?.to_string();
    let repo = parts.next()?.trim_end_matches(".git").to_string();
    if parts.next().is_some() || host.is_empty() || owner.is_empty() || repo.is_empty() {
        return None;
    }
    Some((host, owner, repo))
}

pub fn cmd_claim_init(root: PathBuf, args: ClaimInitArgs) -> Result<()> {
    let ClaimInitArgs {
        host,
        owner,
        repo,
        claim_id,
        claimant_name,
        asserted_role,
        contact,
        record_sources,
        canonical_repo_url,
        review_md,
        force,
    } = args;

    let plan = scaffold_claim_directory(
        &root,
        &ClaimScaffoldInput {
            host,
            owner,
            repo,
            claim_id,
            claimant_display_name: claimant_name,
            asserted_role,
            contact,
            record_sources,
            canonical_repo_url,
            create_review_md: review_md,
            timestamp: current_timestamp()?,
        },
    )?;

    if plan.claim_dir.exists() {
        if !force {
            bail!(
                "{} already exists; rerun with --force to replace an empty scaffold",
                plan.claim_dir.display()
            );
        }
        ensure_replaceable_claim_scaffold(&plan.claim_dir)?;
        fs::remove_dir_all(&plan.claim_dir)?;
    }

    fs::create_dir_all(plan.claim_dir.join("events"))?;
    fs::write(&plan.claim_path, &plan.claim_text)?;
    println!("initialized {}", plan.claim_path.display());
    if let (Some(review_path), Some(review_text)) = (&plan.review_path, &plan.review_text) {
        fs::write(review_path, review_text)?;
        println!("initialized {}", review_path.display());
    }
    Ok(())
}

pub fn cmd_claim_from_native(root: PathBuf, args: ClaimFromNativeArgs) -> Result<()> {
    let ClaimFromNativeArgs {
        index_root,
        claim_id,
        claimant_name,
        asserted_role,
        contact,
        review_md,
        force,
    } = args;
    let manifest = load_manifest_from_root(&root)?;
    let identity = native_repository_identity(&manifest, "claim-from-native")?;

    cmd_claim_init(
        index_root,
        ClaimInitArgs {
            host: identity.host,
            owner: identity.owner,
            repo: identity.repo,
            claim_id,
            claimant_name,
            asserted_role,
            contact,
            record_sources: vec![identity.url.clone()],
            canonical_repo_url: Some(identity.url),
            review_md,
            force,
        },
    )
}

pub struct ClaimEventArgs {
    pub path: PathBuf,
    pub kind: ClaimEventKindArg,
    pub actor: String,
    pub summary: String,
    pub corrected_state: Option<CorrectedClaimStateArg>,
    pub canonical_record_path: Option<String>,
    pub canonical_mirror_path: Option<String>,
}

pub struct ClaimSubmitNativeArgs {
    pub index_root: PathBuf,
    pub claim_id: String,
    pub actor: String,
    pub summary: String,
}

pub struct ClaimAcceptNativeArgs {
    pub index_root: PathBuf,
    pub path: Option<PathBuf>,
    pub claim_id: Option<String>,
    pub actor: String,
    pub summary: String,
}

fn native_repository_identity(
    manifest: &dotrepo_schema::Manifest,
    command: &str,
) -> Result<NativeRepositoryIdentity> {
    ensure_native_record_command(&manifest.record.mode, command)?;
    let homepage = manifest
        .repo
        .homepage
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| anyhow::anyhow!("{command} requires repo.homepage"))?;
    repository_identity_from_url(homepage)
        .ok_or_else(|| {
            anyhow::anyhow!("{command} requires repo.homepage to be host/owner/repo URL")
        })
        .map(|(host, owner, repo)| NativeRepositoryIdentity {
            host,
            owner,
            repo,
            url: homepage.to_string(),
        })
}

fn native_claim_path(identity: &NativeRepositoryIdentity, claim_id: &str) -> PathBuf {
    PathBuf::from(format!(
        "repos/{}/{}/{}/claims/{}",
        identity.host, identity.owner, identity.repo, claim_id
    ))
}

pub fn cmd_claim_event(root: PathBuf, args: ClaimEventArgs) -> Result<()> {
    let ClaimEventArgs {
        path,
        kind,
        actor,
        summary,
        corrected_state,
        canonical_record_path,
        canonical_mirror_path,
    } = args;

    let claim_dir = resolve_claim_directory(
        &root,
        path.to_str().context("claim path must be valid UTF-8")?,
    )?;
    let plan = append_claim_event(
        &root,
        &claim_dir,
        &ClaimEventAppendInput {
            kind: kind.into(),
            actor,
            summary,
            timestamp: current_timestamp()?,
            corrected_state: corrected_state.map(Into::into),
            canonical_record_path,
            canonical_mirror_path,
        },
    )?;

    fs::create_dir_all(claim_dir.join("events"))?;
    fs::write(&plan.event_path, &plan.event_text)?;
    fs::write(&plan.claim_path, &plan.claim_text)?;
    println!("updated {}", plan.claim_path.display());
    println!("appended {}", plan.event_path.display());
    Ok(())
}

pub fn cmd_claim_submit_native(root: PathBuf, args: ClaimSubmitNativeArgs) -> Result<()> {
    let ClaimSubmitNativeArgs {
        index_root,
        claim_id,
        actor,
        summary,
    } = args;
    let manifest = load_manifest_from_root(&root)?;
    let identity = native_repository_identity(&manifest, "claim-submit-native")?;
    cmd_claim_event(
        index_root,
        ClaimEventArgs {
            path: native_claim_path(&identity, &claim_id),
            kind: ClaimEventKindArg::Submitted,
            actor,
            summary,
            corrected_state: None,
            canonical_record_path: None,
            canonical_mirror_path: None,
        },
    )
}

pub fn cmd_claim_accept_native(root: PathBuf, args: ClaimAcceptNativeArgs) -> Result<()> {
    let ClaimAcceptNativeArgs {
        index_root,
        path,
        claim_id,
        actor,
        summary,
    } = args;
    let manifest = load_manifest_from_root(&root)?;
    let identity = native_repository_identity(&manifest, "claim-accept-native")?;
    let path = match (path, claim_id) {
        (Some(path), None) => path,
        (None, Some(claim_id)) => native_claim_path(&identity, &claim_id),
        (Some(_), Some(_)) => {
            bail!("claim-accept-native accepts either a claim path or --claim-id, not both")
        }
        (None, None) => bail!("claim-accept-native requires a claim path or --claim-id"),
    };
    cmd_claim_event(
        index_root,
        ClaimEventArgs {
            path,
            kind: ClaimEventKindArg::Accepted,
            actor,
            summary,
            corrected_state: None,
            canonical_record_path: Some(".repo".into()),
            canonical_mirror_path: Some(format!(
                "repos/{}/{}/{}/record.toml",
                identity.host, identity.owner, identity.repo
            )),
        },
    )
}

pub fn cmd_public(command: PublicCommand) -> Result<()> {
    match command {
        PublicCommand::Summary {
            index_root,
            host,
            owner,
            repo,
            base_path,
            stale_after_hours,
        } => {
            let freshness = current_public_freshness(&index_root, stale_after_hours)?;
            print_public_response(public_repository_summary_or_error_with_base(
                &index_root,
                &host,
                &owner,
                &repo,
                freshness,
                &base_path,
            ))
        }
        PublicCommand::Profile {
            index_root,
            host,
            owner,
            repo,
            base_path,
            stale_after_hours,
        } => {
            let freshness = current_public_freshness(&index_root, stale_after_hours)?;
            print_public_response(public_repository_profile_or_error_with_base(
                &index_root,
                &host,
                &owner,
                &repo,
                freshness,
                &base_path,
            ))
        }
        PublicCommand::Trust {
            index_root,
            host,
            owner,
            repo,
            base_path,
            stale_after_hours,
        } => {
            let freshness = current_public_freshness(&index_root, stale_after_hours)?;
            print_public_response(public_repository_trust_or_error_with_base(
                &index_root,
                &host,
                &owner,
                &repo,
                freshness,
                &base_path,
            ))
        }
        PublicCommand::BatchProfiles {
            index_root,
            repos,
            base_path,
            stale_after_hours,
        } => {
            let freshness = current_public_freshness(&index_root, stale_after_hours)?;
            let identities = parse_public_repository_args(&repos)?;
            let response = public_repository_batch_profiles_with_base(
                &index_root,
                &identities,
                freshness,
                &base_path,
            )?;
            println!("{}", serde_json::to_string_pretty(&response)?);
            Ok(())
        }
        PublicCommand::BatchQuery {
            index_root,
            repos,
            paths,
            base_path,
            stale_after_hours,
        } => {
            let freshness = current_public_freshness(&index_root, stale_after_hours)?;
            let identities = parse_public_repository_args(&repos)?;
            let response = public_repository_batch_query_with_base(
                &index_root,
                &identities,
                &paths,
                freshness,
                &base_path,
            )?;
            println!("{}", serde_json::to_string_pretty(&response)?);
            Ok(())
        }
        PublicCommand::Compare {
            index_root,
            repos,
            base_path,
            stale_after_hours,
        } => {
            let freshness = current_public_freshness(&index_root, stale_after_hours)?;
            let identities = parse_public_repository_args(&repos)?;
            let response =
                public_profile_compare_with_base(&index_root, &identities, freshness, &base_path)?;
            println!("{}", serde_json::to_string_pretty(&response)?);
            Ok(())
        }
        PublicCommand::Relations {
            index_root,
            host,
            owner,
            repo,
            base_path,
            stale_after_hours,
        } => {
            let freshness = current_public_freshness(&index_root, stale_after_hours)?;
            print_public_response(Ok(public_repository_relations_with_base(
                &index_root,
                &host,
                &owner,
                &repo,
                freshness,
                &base_path,
            )?))
        }
        PublicCommand::Search {
            index_root,
            q,
            languages,
            topics,
            statuses,
            confidences,
            require_build,
            require_test,
            require_docs,
            require_security_contact,
            require_license,
            limit,
            base_path,
            stale_after_hours,
        } => {
            let freshness = current_public_freshness(&index_root, stale_after_hours)?;
            let response = public_profile_search_with_base(
                &index_root,
                PublicProfileSearchOptions {
                    query: q,
                    languages,
                    topics,
                    statuses,
                    confidences,
                    require_build,
                    require_test,
                    require_docs,
                    require_security_contact,
                    require_license,
                    limit,
                },
                freshness,
                &base_path,
            )?;
            println!("{}", serde_json::to_string_pretty(&response)?);
            Ok(())
        }
        PublicCommand::Query {
            index_root,
            host,
            owner,
            repo,
            path,
            base_path,
            stale_after_hours,
        } => {
            let freshness = current_public_freshness(&index_root, stale_after_hours)?;
            print_public_response(public_repository_query_or_error_with_base(
                &index_root,
                &host,
                &owner,
                &repo,
                &path,
                freshness,
                &base_path,
            ))
        }
        PublicCommand::Export {
            index_root,
            out_dir,
            base_path,
            stale_after_hours,
            generated_at,
            stale_after,
        } => {
            let snapshot_digest = index_snapshot_digest(&index_root)?;
            let freshness = build_public_freshness_with_digest(
                &index_root,
                stale_after_hours,
                generated_at.as_deref(),
                stale_after.as_deref(),
                Some(&snapshot_digest),
            )?;
            let outputs =
                export_public_index_static_with_base(&index_root, &out_dir, freshness, &base_path)?;
            for (path, contents) in outputs {
                if let Some(parent) = path.parent() {
                    fs::create_dir_all(parent)?;
                }
                fs::write(&path, contents)?;
                println!("exported {}", path.display());
            }
            Ok(())
        }
    }
}

fn parse_public_repository_args(values: &[String]) -> Result<Vec<PublicRepositoryIdentity>> {
    values
        .iter()
        .map(|value| parse_public_repository_arg(value))
        .collect()
}

fn parse_public_repository_arg(value: &str) -> Result<PublicRepositoryIdentity> {
    let trimmed = value.trim();
    let without_scheme = trimmed
        .strip_prefix("https://")
        .or_else(|| trimmed.strip_prefix("http://"))
        .unwrap_or(trimmed);
    let without_git = without_scheme.trim_end_matches(".git");
    let parts = without_git
        .split('/')
        .filter(|part| !part.is_empty())
        .collect::<Vec<_>>();
    if parts.len() != 3 {
        bail!("repository must be host/owner/repo or https://host/owner/repo: {value}");
    }
    Ok(PublicRepositoryIdentity {
        host: parts[0].to_string(),
        owner: parts[1].to_string(),
        repo: parts[2].to_string(),
        source: None,
    })
}

fn print_public_response<T: Serialize>(
    response: std::result::Result<T, PublicErrorResponse>,
) -> Result<()> {
    match response {
        Ok(response) => {
            println!("{}", serde_json::to_string_pretty(&response)?);
            Ok(())
        }
        Err(response) => {
            println!("{}", serde_json::to_string_pretty(&response)?);
            Err(CliExit {
                code: 1,
                message: String::new(),
            }
            .into())
        }
    }
}

fn current_timestamp() -> Result<String> {
    current_timestamp_rfc3339()
}

fn ensure_replaceable_claim_scaffold(claim_dir: &std::path::Path) -> Result<()> {
    if !claim_dir.is_dir() {
        bail!(
            "{} exists but is not a claim directory",
            claim_dir.display()
        );
    }

    for entry in fs::read_dir(claim_dir)? {
        let entry = entry?;
        let path = entry.path();
        let name = entry.file_name();
        let name = name.to_string_lossy();
        match name.as_ref() {
            "claim.toml" | "review.md" => {}
            "events" => {
                if !path.is_dir() {
                    bail!(
                        "{} must be a directory before it can be replaced",
                        path.display()
                    );
                }
                if fs::read_dir(&path)?.next().is_some() {
                    bail!(
                        "refusing to overwrite existing claim history in {}",
                        path.display()
                    );
                }
            }
            _ => {
                bail!(
                    "refusing to overwrite unexpected claim scaffold contents in {}",
                    path.display()
                );
            }
        }
    }

    Ok(())
}
