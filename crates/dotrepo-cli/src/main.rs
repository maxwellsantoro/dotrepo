use anyhow::{bail, Result};
use clap::{Parser, Subcommand, ValueEnum};
use dotrepo_core::{
    append_claim_event, export_public_index_static_with_base, generate_check_repository,
    import_repository, index_snapshot_digest, inspect_claim_directory, inspect_surface_states,
    load_manifest_document, load_manifest_from_root, managed_outputs,
    public_repository_query_or_error_with_base, public_repository_summary_or_error_with_base,
    public_repository_trust_or_error_with_base, query_repository, scaffold_claim_directory,
    trust_repository, validate_index_root, validate_manifest, validate_repository,
    ClaimEventAppendInput, ClaimEventKind, ClaimHandoffOutcome, ClaimInspectionReport,
    ClaimScaffoldInput, ConflictRelationship, ImportMode, IndexFindingSeverity, ManagedFileState,
    PublicErrorResponse, PublicFreshness, SelectionReason, TrustReport,
};
use dotrepo_schema::scaffold_manifest as render_scaffold_manifest;
use dotrepo_schema::{RecordMode, Trust};
use serde::Serialize;
use serde_json::Value;
use std::fs;
use std::path::PathBuf;
use std::process;
use thiserror::Error;
use time::format_description::well_known::Rfc3339;
use time::{Duration, OffsetDateTime};

#[derive(Parser)]
#[command(name = "dotrepo")]
#[command(about = "reference cli for the dotrepo protocol")]
struct Cli {
    /// Repository root containing `.repo` or overlay records.
    #[arg(long, default_value = ".")]
    root: PathBuf,
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Initialize a canonical root `.repo` scaffold.
    Init {
        /// Overwrite an existing root `.repo`.
        #[arg(long)]
        force: bool,
    },
    /// Import conventional repository surfaces into a dotrepo record.
    Import {
        /// Record mode for the imported manifest.
        #[arg(long, value_enum, default_value_t = ImportModeArg::Native)]
        mode: ImportModeArg,
        /// Explicit repository source URL for overlays.
        #[arg(long)]
        source: Option<String>,
        /// Overwrite previously imported artifacts.
        #[arg(long)]
        force: bool,
    },
    /// Validate the manifest at the selected repository root.
    Validate,
    /// Validate a public index tree rooted at `index/`.
    ValidateIndex {
        /// Index root to validate.
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
    },
    /// Query one field from the selected record, preserving trust-aware selection in `--json`.
    Query {
        /// Dot-path such as `repo.name` or `record.trust.provenance`.
        path: String,
        /// Emit the full conflict-aware query report as JSON.
        #[arg(long, conflicts_with = "raw")]
        json: bool,
        /// Emit only the selected scalar value. Refuses when competing records exist.
        #[arg(long, conflicts_with = "json")]
        raw: bool,
    },
    /// Render generated compatibility surfaces or fail when they drift.
    Generate {
        /// Check generated surfaces for drift without writing files.
        #[arg(long)]
        check: bool,
    },
    /// Inspect unmanaged conventional files at the repository root.
    Doctor,
    /// Inspect trust, authority handoff, and competing records for one repository identity.
    Trust {
        /// Emit the full conflict-aware trust report as JSON.
        #[arg(long)]
        json: bool,
    },
    /// Inspect one maintainer-claim directory from the index.
    Claim {
        /// Claim directory relative to --root or an absolute path.
        path: PathBuf,
        /// Emit the full claim inspection report as JSON.
        #[arg(long)]
        json: bool,
    },
    /// Scaffold a draft maintainer-claim directory for one index repository.
    ClaimInit {
        /// Repository host under index_root/repos/<host>/<owner>/<repo>/.
        #[arg(long)]
        host: String,
        /// Repository owner under index_root/repos/<host>/<owner>/<repo>/.
        #[arg(long)]
        owner: String,
        /// Repository name under index_root/repos/<host>/<owner>/<repo>/.
        #[arg(long)]
        repo: String,
        /// Claim directory name under claims/<claim-id>/.
        #[arg(long)]
        claim_id: String,
        /// Claimant display name recorded in claim.toml.
        #[arg(long)]
        claimant_name: String,
        /// Claimed repository role, such as `maintainer`.
        #[arg(long)]
        asserted_role: String,
        /// Optional claimant contact detail.
        #[arg(long)]
        contact: Option<String>,
        /// Additional record source URLs tied to this claim.
        #[arg(long = "record-source")]
        record_sources: Vec<String>,
        /// Optional canonical repository URL for the claim target.
        #[arg(long)]
        canonical_repo_url: Option<String>,
        /// Create a placeholder review.md next to claim.toml.
        #[arg(long)]
        review_md: bool,
        /// Replace an existing empty scaffold, but never overwrite event history.
        #[arg(long)]
        force: bool,
    },
    /// Append a new claim event and update the current claim state.
    ClaimEvent {
        /// Claim directory relative to --root or an absolute path.
        path: PathBuf,
        /// Event kind to append.
        #[arg(long, value_enum)]
        kind: ClaimEventKindArg,
        /// Actor label recorded in the event.
        #[arg(long)]
        actor: String,
        /// Short event summary recorded in the audit trail.
        #[arg(long)]
        summary: String,
        /// Optional corrected current state when kind=corrected.
        #[arg(long, value_enum)]
        corrected_state: Option<CorrectedClaimStateArg>,
        /// Optional canonical `.repo` path recorded for accepted handoff.
        #[arg(long)]
        canonical_record_path: Option<String>,
        /// Optional canonical mirror record path recorded for accepted handoff.
        #[arg(long)]
        canonical_mirror_path: Option<String>,
    },
    /// Inspect or export public read-only index responses.
    Public {
        #[command(subcommand)]
        command: PublicCommand,
    },
}

#[derive(Subcommand)]
enum PublicCommand {
    /// Render one public repository summary response as JSON.
    Summary {
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
        host: String,
        owner: String,
        repo: String,
        /// URL base path prefix for hosted public links, such as `/dotrepo`.
        #[arg(long, default_value = "/")]
        base_path: String,
        /// Advisory staleness window in hours for the rendered response.
        #[arg(long)]
        stale_after_hours: Option<i64>,
    },
    /// Render one public trust response as JSON.
    Trust {
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
        host: String,
        owner: String,
        repo: String,
        /// URL base path prefix for hosted public links, such as `/dotrepo`.
        #[arg(long, default_value = "/")]
        base_path: String,
        /// Advisory staleness window in hours for the rendered response.
        #[arg(long)]
        stale_after_hours: Option<i64>,
    },
    /// Render one public query response as JSON.
    Query {
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
        host: String,
        owner: String,
        repo: String,
        path: String,
        /// URL base path prefix for hosted public links, such as `/dotrepo`.
        #[arg(long, default_value = "/")]
        base_path: String,
        /// Advisory staleness window in hours for the rendered response.
        #[arg(long)]
        stale_after_hours: Option<i64>,
    },
    /// Export the static-first public JSON tree for repository summary and trust.
    Export {
        #[arg(long, default_value = "index")]
        index_root: PathBuf,
        #[arg(long, default_value = "public")]
        out_dir: PathBuf,
        /// URL base path prefix for hosted public links, such as `/dotrepo`.
        #[arg(long, default_value = "/")]
        base_path: String,
        /// Advisory staleness window in hours for exported responses.
        #[arg(long)]
        stale_after_hours: Option<i64>,
        /// Fixed RFC 3339 generation timestamp for deterministic export review.
        #[arg(long)]
        generated_at: Option<String>,
        /// Fixed RFC 3339 staleness timestamp for deterministic export review.
        #[arg(long)]
        stale_after: Option<String>,
    },
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, ValueEnum)]
enum ImportModeArg {
    Native,
    Overlay,
}

#[derive(Clone, Debug, Eq, PartialEq, ValueEnum)]
enum ClaimEventKindArg {
    Submitted,
    ReviewStarted,
    Accepted,
    Rejected,
    Withdrawn,
    Disputed,
    Corrected,
}

#[derive(Clone, Debug, Eq, PartialEq, ValueEnum)]
enum CorrectedClaimStateArg {
    Submitted,
    InReview,
    Accepted,
    Rejected,
    Withdrawn,
    Disputed,
}

impl From<ImportModeArg> for ImportMode {
    fn from(value: ImportModeArg) -> Self {
        match value {
            ImportModeArg::Native => ImportMode::Native,
            ImportModeArg::Overlay => ImportMode::Overlay,
        }
    }
}

impl From<ClaimEventKindArg> for ClaimEventKind {
    fn from(value: ClaimEventKindArg) -> Self {
        match value {
            ClaimEventKindArg::Submitted => ClaimEventKind::Submitted,
            ClaimEventKindArg::ReviewStarted => ClaimEventKind::ReviewStarted,
            ClaimEventKindArg::Accepted => ClaimEventKind::Accepted,
            ClaimEventKindArg::Rejected => ClaimEventKind::Rejected,
            ClaimEventKindArg::Withdrawn => ClaimEventKind::Withdrawn,
            ClaimEventKindArg::Disputed => ClaimEventKind::Disputed,
            ClaimEventKindArg::Corrected => ClaimEventKind::Corrected,
        }
    }
}

impl From<CorrectedClaimStateArg> for dotrepo_core::ClaimState {
    fn from(value: CorrectedClaimStateArg) -> Self {
        match value {
            CorrectedClaimStateArg::Submitted => dotrepo_core::ClaimState::Submitted,
            CorrectedClaimStateArg::InReview => dotrepo_core::ClaimState::InReview,
            CorrectedClaimStateArg::Accepted => dotrepo_core::ClaimState::Accepted,
            CorrectedClaimStateArg::Rejected => dotrepo_core::ClaimState::Rejected,
            CorrectedClaimStateArg::Withdrawn => dotrepo_core::ClaimState::Withdrawn,
            CorrectedClaimStateArg::Disputed => dotrepo_core::ClaimState::Disputed,
        }
    }
}

#[derive(Debug, Error)]
#[error("{message}")]
struct CliExit {
    code: i32,
    message: String,
}

fn main() {
    if let Err(err) = run() {
        if let Some(err) = err.downcast_ref::<CliExit>() {
            if !err.message.is_empty() {
                eprintln!("{}", err.message);
            }
            process::exit(err.code);
        }

        eprintln!("{err}");
        process::exit(1);
    }
}

fn run() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::Init { force } => cmd_init(cli.root, force),
        Command::Import {
            mode,
            source,
            force,
        } => cmd_import(cli.root, mode, source, force),
        Command::Validate => cmd_validate(cli.root),
        Command::ValidateIndex { index_root } => cmd_validate_index(index_root),
        Command::Query { path, json, raw } => cmd_query(cli.root, &path, json, raw),
        Command::Generate { check } => cmd_generate(cli.root, check),
        Command::Doctor => cmd_doctor(cli.root),
        Command::Trust { json } => cmd_trust(cli.root, json),
        Command::Claim { path, json } => cmd_claim(cli.root, path, json),
        Command::ClaimInit {
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
        } => cmd_claim_init(
            cli.root,
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
        ),
        Command::ClaimEvent {
            path,
            kind,
            actor,
            summary,
            corrected_state,
            canonical_record_path,
            canonical_mirror_path,
        } => cmd_claim_event(
            cli.root,
            path,
            kind,
            actor,
            summary,
            corrected_state,
            canonical_record_path,
            canonical_mirror_path,
        ),
        Command::Public { command } => cmd_public(command),
    }
}

fn cmd_validate(root: PathBuf) -> Result<()> {
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

fn cmd_init(root: PathBuf, force: bool) -> Result<()> {
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
        .unwrap_or("repository");
    let manifest = render_scaffold_manifest(repo_name)?;
    fs::write(&manifest_path, manifest)?;
    println!("initialized {}", manifest_path.display());
    Ok(())
}

fn cmd_import(
    root: PathBuf,
    mode: ImportModeArg,
    source: Option<String>,
    force: bool,
) -> Result<()> {
    let plan = import_repository(&root, mode.into(), source.as_deref())?;

    let mut outputs = vec![(plan.manifest_path.clone(), plan.manifest_text.clone())];
    if let (Some(path), Some(contents)) = (&plan.evidence_path, &plan.evidence_text) {
        outputs.push((path.clone(), contents.clone()));
    }

    for (path, _) in &outputs {
        if path.exists() && !force {
            bail!(
                "{} already exists; rerun with --force to overwrite imported artifacts",
                path.display()
            );
        }
    }

    for (path, contents) in outputs {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::write(&path, contents)?;
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

fn cmd_query(root: PathBuf, path: &str, json: bool, raw: bool) -> Result<()> {
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

fn cmd_validate_index(index_root: PathBuf) -> Result<()> {
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

fn cmd_generate(root: PathBuf, check: bool) -> Result<()> {
    if check {
        let manifest = load_manifest_from_root(&root)?;
        validate_manifest(&root, &manifest)?;
        ensure_native_managed_surface_command(&manifest.record.mode, "generate-check")?;
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
    ensure_native_managed_surface_command(&document.manifest.record.mode, "generate")?;
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

fn cmd_doctor(root: PathBuf) -> Result<()> {
    let manifest = load_manifest_from_root(&root)?;
    validate_manifest(&root, &manifest)?;
    ensure_native_managed_surface_command(&manifest.record.mode, "doctor")?;
    let findings = inspect_surface_states(&root)?;
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

fn ensure_native_managed_surface_command(mode: &RecordMode, command: &str) -> Result<()> {
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

fn cmd_trust(root: PathBuf, json: bool) -> Result<()> {
    let report = trust_repository(&root)?;
    if json {
        println!("{}", serde_json::to_string_pretty(&report)?);
        return Ok(());
    }

    println!("{}", format_trust_report(&report));
    Ok(())
}

fn cmd_claim(root: PathBuf, path: PathBuf, json: bool) -> Result<()> {
    let claim_dir = if path.is_absolute() {
        path
    } else {
        root.join(path)
    };
    let report = inspect_claim_directory(&root, &claim_dir)?;
    if json {
        println!("{}", serde_json::to_string_pretty(&report)?);
        return Ok(());
    }

    println!("{}", format_claim_report(&report));
    Ok(())
}

fn cmd_claim_init(
    root: PathBuf,
    host: String,
    owner: String,
    repo: String,
    claim_id: String,
    claimant_name: String,
    asserted_role: String,
    contact: Option<String>,
    record_sources: Vec<String>,
    canonical_repo_url: Option<String>,
    review_md: bool,
    force: bool,
) -> Result<()> {
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

fn cmd_claim_event(
    root: PathBuf,
    path: PathBuf,
    kind: ClaimEventKindArg,
    actor: String,
    summary: String,
    corrected_state: Option<CorrectedClaimStateArg>,
    canonical_record_path: Option<String>,
    canonical_mirror_path: Option<String>,
) -> Result<()> {
    let claim_dir = if path.is_absolute() {
        path
    } else {
        root.join(path)
    };
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

fn cmd_public(command: PublicCommand) -> Result<()> {
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
            let freshness = build_public_freshness(
                &index_root,
                stale_after_hours,
                generated_at.as_deref(),
                stale_after.as_deref(),
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
    Ok(OffsetDateTime::now_utc()
        .format(&Rfc3339)
        .map_err(|err| anyhow::anyhow!("failed to render current timestamp: {err}"))?)
}

fn render_rfc3339(label: &str, timestamp: OffsetDateTime) -> Result<String> {
    timestamp
        .format(&Rfc3339)
        .map_err(|err| anyhow::anyhow!("failed to render {label}: {err}"))
}

fn parse_rfc3339(label: &str, value: &str) -> Result<OffsetDateTime> {
    OffsetDateTime::parse(value, &Rfc3339)
        .map_err(|err| anyhow::anyhow!("failed to parse {label} as RFC3339: {err}"))
}

fn build_public_freshness(
    index_root: &std::path::Path,
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

fn current_public_freshness(
    index_root: &std::path::Path,
    stale_after_hours: Option<i64>,
) -> Result<PublicFreshness> {
    build_public_freshness(index_root, stale_after_hours, None, None)
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

fn format_trust_report(report: &TrustReport) -> String {
    let selected = &report.selection.record;
    let mut lines = vec![
        format!(
            "selected: {} ({:?}, {:?})",
            selected.manifest_path, selected.record.mode, selected.record.status
        ),
        format!(
            "selection reason: {}",
            format_selection_reason(report.selection.reason)
        ),
    ];

    append_record_details(
        &mut lines,
        "",
        selected.record.source.as_deref(),
        selected.record.trust.as_ref(),
        selected.claim.as_ref(),
    );

    if !report.conflicts.is_empty() {
        lines.push("conflicts:".into());
        for conflict in &report.conflicts {
            lines.push(format!(
                "- {} ({:?}, {:?})",
                conflict.record.manifest_path,
                conflict.record.record.mode,
                conflict.record.record.status
            ));
            lines.push(format!(
                "  relationship: {}",
                format_conflict_relationship(conflict.relationship)
            ));
            lines.push(format!(
                "  reason: {}",
                format_selection_reason(conflict.reason)
            ));
            append_record_details(
                &mut lines,
                "  ",
                conflict.record.record.source.as_deref(),
                conflict.record.record.trust.as_ref(),
                conflict.record.claim.as_ref(),
            );
        }
    }

    lines.join("\n")
}

fn format_claim_report(report: &ClaimInspectionReport) -> String {
    let mut lines = vec![
        format!("claim: {}", report.claim_path),
        format!("state: {:?}", report.state),
        format!("kind: {:?}", report.kind),
        format!(
            "identity: {}/{}/{}",
            report.identity.host, report.identity.owner, report.identity.repo
        ),
        format!(
            "claimant: {} ({})",
            report.claimant.display_name, report.claimant.asserted_role
        ),
    ];

    if let Some(contact) = &report.claimant.contact {
        lines.push(format!("contact: {}", contact));
    }
    if let Some(review_path) = &report.review_path {
        lines.push(format!("review: {}", review_path));
    }
    if let Some(handoff) = report.target.handoff {
        lines.push(format!("handoff: {}", format_claim_handoff(handoff)));
    }
    if !report.target.index_paths.is_empty() {
        lines.push("target index paths:".into());
        for path in &report.target.index_paths {
            lines.push(format!("- {}", path));
        }
    }
    if !report.target.record_sources.is_empty() {
        lines.push("target record sources:".into());
        for source in &report.target.record_sources {
            lines.push(format!("- {}", source));
        }
    }
    if let Some(url) = &report.target.canonical_repo_url {
        lines.push(format!("canonical repo url: {}", url));
    }
    if let Some(resolution) = &report.resolution {
        if let Some(path) = &resolution.canonical_record_path {
            lines.push(format!("canonical record path: {}", path));
        }
        if let Some(path) = &resolution.canonical_mirror_path {
            lines.push(format!("canonical mirror path: {}", path));
        }
        if let Some(path) = &resolution.result_event {
            lines.push(format!("result event: {}", path));
        }
    }
    if !report.events.is_empty() {
        lines.push("events:".into());
        for event in &report.events {
            let mut line = format!(
                "- [{}] {:?} at {} by {}",
                event.sequence, event.kind, event.timestamp, event.actor
            );
            if let (Some(from), Some(to)) = (&event.from, &event.to) {
                line.push_str(&format!(" ({from:?} -> {to:?})"));
            }
            lines.push(line);
            lines.push(format!("  {}", event.summary));
        }
    }

    lines.join("\n")
}

fn format_query_value(value: &Value, raw: bool) -> Result<String> {
    match value {
        Value::String(text) => Ok(text.clone()),
        Value::Null => {
            if raw {
                Ok(String::new())
            } else {
                Ok("null".into())
            }
        }
        Value::Bool(flag) => Ok(flag.to_string()),
        Value::Number(number) => Ok(number.to_string()),
        Value::Array(_) | Value::Object(_) => {
            if raw {
                bail!("--raw is only supported for scalar query results");
            }
            Ok(serde_json::to_string_pretty(value)?)
        }
    }
}

fn append_record_details(
    lines: &mut Vec<String>,
    indent: &str,
    source: Option<&str>,
    trust: Option<&Trust>,
    claim: Option<&dotrepo_core::RecordClaimContext>,
) {
    lines.push(format!("{}source: {}", indent, source.unwrap_or("none")));
    if let Some(trust) = trust {
        lines.push(format!(
            "{}confidence: {}",
            indent,
            trust.confidence.as_deref().unwrap_or("none")
        ));
        lines.push(format!(
            "{}provenance: {}",
            indent,
            format_provenance(&trust.provenance)
        ));
        lines.push(format!(
            "{}notes: {}",
            indent,
            trust.notes.as_deref().unwrap_or("none")
        ));
    } else {
        lines.push(format!("{}confidence: none", indent));
        lines.push(format!("{}provenance: none", indent));
        lines.push(format!("{}notes: none", indent));
    }
    if let Some(claim) = claim {
        lines.push(format!(
            "{}claim: {:?} ({})",
            indent,
            claim.state,
            format_claim_handoff(claim.handoff)
        ));
        lines.push(format!("{}claim path: {}", indent, claim.claim_path));
    }
}

fn format_selection_reason(reason: SelectionReason) -> &'static str {
    match reason {
        SelectionReason::OnlyMatchingRecord => "only matching record",
        SelectionReason::CanonicalPreferred => {
            "canonical record preferred over lower-authority competing records"
        }
        SelectionReason::HigherStatusOverlay => {
            "higher-status overlay preferred over lower-status competing overlays"
        }
        SelectionReason::EqualAuthorityConflict => {
            "equal-authority conflict; selected by stable path ordering while preserving competing records"
        }
    }
}

fn format_conflict_relationship(relationship: ConflictRelationship) -> &'static str {
    match relationship {
        ConflictRelationship::Superseded => "superseded",
        ConflictRelationship::Parallel => "parallel",
    }
}

fn format_claim_handoff(handoff: ClaimHandoffOutcome) -> &'static str {
    match handoff {
        ClaimHandoffOutcome::PendingCanonical => "pending_canonical",
        ClaimHandoffOutcome::Superseded => "superseded",
        ClaimHandoffOutcome::Parallel => "parallel",
        ClaimHandoffOutcome::Rejected => "rejected",
        ClaimHandoffOutcome::Withdrawn => "withdrawn",
        ClaimHandoffOutcome::Disputed => "disputed",
    }
}

fn format_provenance(provenance: &[String]) -> String {
    if provenance.is_empty() {
        "none".into()
    } else {
        provenance.join(", ")
    }
}

fn format_managed_file_state(state: ManagedFileState) -> &'static str {
    match state {
        ManagedFileState::Missing => "missing",
        ManagedFileState::FullyGenerated => "fully_generated",
        ManagedFileState::PartiallyManaged => "partially_managed",
        ManagedFileState::Unmanaged => "unmanaged",
        ManagedFileState::MalformedManaged => "malformed_managed",
        ManagedFileState::Unsupported => "unsupported",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn format_query_value_defaults_to_human_readable_strings() {
        let rendered = format_query_value(&Value::String("orbit".into()), false).expect("formats");
        assert_eq!(rendered, "orbit");
    }

    #[test]
    fn format_query_value_rejects_raw_composite_values() {
        let err = format_query_value(&Value::Array(vec![Value::String("orbit".into())]), true)
            .expect_err("raw composite values should fail");
        assert!(err.to_string().contains("--raw"));
    }

    #[test]
    fn format_claim_report_surfaces_handoff_and_events() {
        let report = ClaimInspectionReport {
            claim_path: "repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01/claim.toml".into(),
            state: dotrepo_core::ClaimState::Accepted,
            kind: dotrepo_core::ClaimKind::MaintainerAuthority,
            identity: dotrepo_core::ClaimIdentity {
                host: "github.com".into(),
                owner: "acme".into(),
                repo: "widget".into(),
            },
            claimant: dotrepo_core::Claimant {
                display_name: "Acme maintainers".into(),
                asserted_role: "maintainer".into(),
                contact: Some("maintainers@acme.dev".into()),
            },
            target: dotrepo_core::ClaimTargetInspection {
                index_paths: vec!["repos/github.com/acme/widget/record.toml".into()],
                record_sources: vec!["https://github.com/acme/widget".into()],
                canonical_repo_url: Some("https://github.com/acme/widget".into()),
                handoff: Some(ClaimHandoffOutcome::Superseded),
            },
            resolution: Some(dotrepo_core::ClaimResolution {
                canonical_record_path: Some(".repo".into()),
                canonical_mirror_path: Some("repos/github.com/acme/widget/record.toml".into()),
                result_event: Some("events/0002-accepted.toml".into()),
            }),
            review_path: Some(
                "repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01/review.md"
                    .into(),
            ),
            events: vec![dotrepo_core::ClaimEventInspection {
                path: "repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01/events/0002-accepted.toml".into(),
                sequence: 2,
                kind: dotrepo_core::ClaimEventKind::Accepted,
                timestamp: "2026-03-12T09:15:00Z".into(),
                actor: "index-reviewer".into(),
                summary: "Accepted claim.".into(),
                from: Some(dotrepo_core::ClaimState::Submitted),
                to: Some(dotrepo_core::ClaimState::Accepted),
            }],
        };

        let rendered = format_claim_report(&report);
        assert!(rendered.contains("handoff: superseded"));
        assert!(rendered.contains("target index paths:"));
        assert!(rendered.contains("events:"));
        assert!(rendered.contains("Accepted"));
    }

    #[test]
    fn claim_init_scaffolds_valid_claim_directory() {
        let root = temp_dir("claim-init");
        let repo_dir = root.join("repos/github.com/acme/widget");
        fs::create_dir_all(&repo_dir).expect("repo dir created");
        fs::write(repo_dir.join("record.toml"), "schema = \"dotrepo/v0.1\"\n")
            .expect("record written");

        cmd_claim_init(
            root.clone(),
            "github.com".into(),
            "acme".into(),
            "widget".into(),
            "2026-03-10-maintainer-claim-03".into(),
            "Acme maintainers".into(),
            "maintainer".into(),
            Some("maintainers@acme.dev".into()),
            vec!["https://github.com/acme/widget".into()],
            Some("https://github.com/acme/widget".into()),
            true,
            false,
        )
        .expect("claim scaffold succeeds");

        let claim_dir =
            root.join("repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-03");
        assert!(claim_dir.join("claim.toml").exists());
        assert!(claim_dir.join("review.md").exists());
        assert!(claim_dir.join("events").is_dir());

        let report = inspect_claim_directory(&root, &claim_dir).expect("claim inspection works");
        assert_eq!(report.state, dotrepo_core::ClaimState::Draft);
        assert_eq!(report.events.len(), 0);

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn claim_init_refuses_existing_claim_dir_without_force() {
        let root = temp_dir("claim-init-no-force");
        let claim_dir =
            root.join("repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-03");
        fs::create_dir_all(claim_dir.join("events")).expect("claim dir created");
        fs::create_dir_all(root.join("repos/github.com/acme/widget")).expect("repo dir created");
        fs::write(
            root.join("repos/github.com/acme/widget/record.toml"),
            "schema = \"dotrepo/v0.1\"\n",
        )
        .expect("record written");
        fs::write(
            claim_dir.join("claim.toml"),
            "schema = \"dotrepo-claim/v0\"\n",
        )
        .expect("claim scaffold written");

        let err = cmd_claim_init(
            root.clone(),
            "github.com".into(),
            "acme".into(),
            "widget".into(),
            "2026-03-10-maintainer-claim-03".into(),
            "Acme maintainers".into(),
            "maintainer".into(),
            None,
            Vec::new(),
            None,
            false,
            false,
        )
        .expect_err("existing claim dir should fail");
        assert!(err.to_string().contains("already exists"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn claim_init_force_refuses_existing_event_history() {
        let root = temp_dir("claim-init-history");
        let claim_dir =
            root.join("repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-03");
        fs::create_dir_all(claim_dir.join("events")).expect("claim dir created");
        fs::create_dir_all(root.join("repos/github.com/acme/widget")).expect("repo dir created");
        fs::write(
            root.join("repos/github.com/acme/widget/record.toml"),
            "schema = \"dotrepo/v0.1\"\n",
        )
        .expect("record written");
        fs::write(
            claim_dir.join("events/0001-submitted.toml"),
            "schema = \"dotrepo-claim-event/v0\"\n",
        )
        .expect("event written");

        let err = cmd_claim_init(
            root.clone(),
            "github.com".into(),
            "acme".into(),
            "widget".into(),
            "2026-03-10-maintainer-claim-03".into(),
            "Acme maintainers".into(),
            "maintainer".into(),
            None,
            Vec::new(),
            None,
            false,
            true,
        )
        .expect_err("existing event history should fail");
        assert!(err
            .to_string()
            .contains("refusing to overwrite existing claim history"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn claim_event_appends_submitted_history_and_updates_claim_state() {
        let root = temp_dir("claim-event");
        let repo_dir = root.join("repos/github.com/acme/widget");
        fs::create_dir_all(&repo_dir).expect("repo dir created");
        fs::write(repo_dir.join("record.toml"), "schema = \"dotrepo/v0.1\"\n")
            .expect("record written");
        cmd_claim_init(
            root.clone(),
            "github.com".into(),
            "acme".into(),
            "widget".into(),
            "2026-03-10-maintainer-claim-03".into(),
            "Acme maintainers".into(),
            "maintainer".into(),
            None,
            vec!["https://github.com/acme/widget".into()],
            None,
            true,
            false,
        )
        .expect("claim scaffold succeeds");

        let claim_dir =
            root.join("repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-03");
        cmd_claim_event(
            root.clone(),
            claim_dir.clone(),
            ClaimEventKindArg::Submitted,
            "claimant".into(),
            "Submitted maintainer claim.".into(),
            None,
            None,
            None,
        )
        .expect("claim event succeeds");

        let report = inspect_claim_directory(&root, &claim_dir).expect("claim inspection works");
        assert_eq!(report.state, dotrepo_core::ClaimState::Submitted);
        assert_eq!(report.events.len(), 1);
        assert_eq!(
            report.events[0].kind,
            dotrepo_core::ClaimEventKind::Submitted
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn claim_event_refuses_invalid_transition() {
        let root = temp_dir("claim-event-invalid");
        let repo_dir = root.join("repos/github.com/acme/widget");
        fs::create_dir_all(&repo_dir).expect("repo dir created");
        fs::write(repo_dir.join("record.toml"), "schema = \"dotrepo/v0.1\"\n")
            .expect("record written");
        cmd_claim_init(
            root.clone(),
            "github.com".into(),
            "acme".into(),
            "widget".into(),
            "2026-03-10-maintainer-claim-03".into(),
            "Acme maintainers".into(),
            "maintainer".into(),
            None,
            vec!["https://github.com/acme/widget".into()],
            None,
            false,
            false,
        )
        .expect("claim scaffold succeeds");

        let claim_dir =
            root.join("repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-03");
        let err = cmd_claim_event(
            root.clone(),
            claim_dir,
            ClaimEventKindArg::Accepted,
            "index-reviewer".into(),
            "Accepted maintainer claim.".into(),
            None,
            None,
            None,
        )
        .expect_err("draft claim should not accept directly");
        assert!(err
            .to_string()
            .contains("accepted events are only valid for submitted or in_review claims"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn claim_event_records_canonical_handoff_links() {
        let root = temp_dir("claim-event-handoff");
        let repo_dir = root.join("repos/github.com/acme/widget");
        fs::create_dir_all(&repo_dir).expect("repo dir created");
        fs::write(repo_dir.join("record.toml"), "schema = \"dotrepo/v0.1\"\n")
            .expect("record written");
        cmd_claim_init(
            root.clone(),
            "github.com".into(),
            "acme".into(),
            "widget".into(),
            "2026-03-10-maintainer-claim-03".into(),
            "Acme maintainers".into(),
            "maintainer".into(),
            None,
            vec!["https://github.com/acme/widget".into()],
            Some("https://github.com/acme/widget".into()),
            false,
            false,
        )
        .expect("claim scaffold succeeds");

        let claim_dir =
            root.join("repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-03");
        cmd_claim_event(
            root.clone(),
            claim_dir.clone(),
            ClaimEventKindArg::Submitted,
            "claimant".into(),
            "Submitted maintainer claim.".into(),
            None,
            None,
            None,
        )
        .expect("submitted event succeeds");
        cmd_claim_event(
            root.clone(),
            claim_dir.clone(),
            ClaimEventKindArg::Accepted,
            "index-reviewer".into(),
            "Accepted maintainer claim after review.".into(),
            None,
            Some(".repo".into()),
            Some("repos/github.com/acme/widget/record.toml".into()),
        )
        .expect("accepted handoff succeeds");

        let report = inspect_claim_directory(&root, &claim_dir).expect("claim inspection works");
        assert_eq!(report.target.handoff, Some(ClaimHandoffOutcome::Superseded));
        let resolution = report.resolution.expect("resolution recorded");
        assert_eq!(resolution.canonical_record_path.as_deref(), Some(".repo"));
        assert_eq!(
            resolution.canonical_mirror_path.as_deref(),
            Some("repos/github.com/acme/widget/record.toml")
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn query_raw_should_refuse_competing_records() {
        let root = temp_dir("query-raw-conflict");
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
description = "selected"
"#,
        )
        .expect("root overlay written");
        let alt = root.join("alt");
        fs::create_dir_all(&alt).expect("alt dir created");
        fs::write(
            alt.join("record.toml"),
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
description = "competing"
"#,
        )
        .expect("competing overlay written");

        let err = cmd_query(root.clone(), "repo.description", false, true)
            .expect_err("raw conflict should fail");
        assert!(err.to_string().contains("competing records"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn format_trust_report_explains_canonical_handoff_plainly() {
        let root = temp_dir("trust-conflict-report");
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
notes = "Maintainer-authored root record."

[repo]
name = "orbit"
description = "Canonical project record"
homepage = "https://github.com/example/orbit"
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
notes = "Reviewed overlay retained for audit history."

[repo]
name = "orbit"
description = "Reviewed overlay"
"#,
        )
        .expect("overlay manifest written");

        let report = trust_repository(&root).expect("trust report");
        let rendered = format_trust_report(&report);
        assert!(rendered.contains("selected: .repo (Native, Canonical)"));
        assert!(rendered.contains(
            "selection reason: canonical record preferred over lower-authority competing records"
        ));
        assert!(rendered.contains("conflicts:"));
        assert!(
            rendered.contains("- repos/github.com/example/orbit/record.toml (Overlay, Reviewed)")
        );
        assert!(rendered.contains("relationship: superseded"));
        assert!(rendered
            .contains("reason: canonical record preferred over lower-authority competing records"));
        assert!(rendered.contains("provenance: imported, verified"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn format_trust_report_explains_equal_authority_conflicts() {
        let root = temp_dir("trust-equal-authority-report");
        let first = root.join("a");
        let second = root.join("b");
        fs::create_dir_all(&first).expect("first dir created");
        fs::create_dir_all(&second).expect("second dir created");
        fs::write(
            first.join("record.toml"),
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
description = "First reviewed overlay"
"#,
        )
        .expect("first manifest written");
        fs::write(
            second.join("record.toml"),
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
description = "Second reviewed overlay"
"#,
        )
        .expect("second manifest written");

        let report = trust_repository(&root).expect("trust report");
        let rendered = format_trust_report(&report);
        assert!(rendered.contains(
            "selection reason: equal-authority conflict; selected by stable path ordering while preserving competing records"
        ));
        assert!(rendered.contains("relationship: parallel"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn validate_index_allows_warning_only_runs() {
        let root = temp_dir("index-warning");
        let record_dir = root.join("repos/github.com/example/project");
        fs::create_dir_all(&record_dir).expect("record dir created");
        fs::write(
            record_dir.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://github.com/example/project"

[record.trust]
confidence = "medium"
provenance = ["imported"]

[repo]
name = "project"
description = "Example project"
homepage = "https://github.com/example/project"

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

        cmd_validate_index(root.clone()).expect("warning-only index should pass");

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn validate_index_fails_on_structural_errors() {
        let root = temp_dir("index-error");
        let record_dir = root.join("repos/github.com/example/project");
        fs::create_dir_all(&record_dir).expect("record dir created");
        fs::write(
            record_dir.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "project"
description = "Example project"
homepage = "https://github.com/example/project"
"#,
        )
        .expect("record written");

        let err = cmd_validate_index(root.clone()).expect_err("invalid index should fail");
        let exit = err.downcast_ref::<CliExit>().expect("returns a CliExit");
        assert_eq!(exit.code, 1);
        assert!(exit.message.contains("record.mode = \"overlay\""));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn import_writes_overlay_manifest_and_evidence() {
        let root = temp_dir("import-overlay");
        fs::write(
            root.join("README.md"),
            "# Example Project\n\nProject summary from the README.\n",
        )
        .expect("README written");
        fs::create_dir_all(root.join(".github")).expect(".github created");
        fs::write(root.join(".github/CODEOWNERS"), "* @example\n").expect("CODEOWNERS written");
        fs::write(
            root.join(".github/SECURITY.md"),
            "Report vulnerabilities to security@example.com.\n",
        )
        .expect("SECURITY written");

        cmd_import(
            root.clone(),
            ImportModeArg::Overlay,
            Some("https://github.com/example/project".into()),
            false,
        )
        .expect("overlay import succeeds");

        let manifest = load_manifest_from_root(&root).expect("manifest loads");
        assert_eq!(manifest.record.mode, dotrepo_schema::RecordMode::Overlay);
        assert_eq!(
            manifest.record.status,
            dotrepo_schema::RecordStatus::Imported
        );
        assert_eq!(manifest.repo.name, "Example Project");
        assert!(root.join("evidence.md").exists());

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn generate_refuses_overlay_records() {
        let root = temp_dir("generate-overlay");
        fs::write(
            root.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://github.com/example/project"

[record.trust]
confidence = "medium"
provenance = ["imported"]

[repo]
name = "project"
description = "Example project"
"#,
        )
        .expect("record written");

        let err = cmd_generate(root.clone(), false).expect_err("overlay generate should fail");
        let exit = err.downcast_ref::<CliExit>().expect("returns a CliExit");
        assert_eq!(exit.code, 2);
        assert!(exit
            .message
            .contains("generate is only supported for native records"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn generate_check_refuses_overlay_records() {
        let root = temp_dir("generate-check-overlay");
        fs::write(
            root.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://github.com/example/project"

[record.trust]
confidence = "medium"
provenance = ["imported"]

[repo]
name = "project"
description = "Example project"
"#,
        )
        .expect("record written");

        let err = cmd_generate(root.clone(), true).expect_err("overlay generate-check should fail");
        let exit = err.downcast_ref::<CliExit>().expect("returns a CliExit");
        assert_eq!(exit.code, 2);
        assert!(exit
            .message
            .contains("generate-check is only supported for native records"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn doctor_refuses_overlay_records() {
        let root = temp_dir("doctor-overlay");
        fs::write(
            root.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "reviewed"
source = "https://github.com/example/project"

[record.trust]
confidence = "medium"
provenance = ["verified"]

[repo]
name = "project"
description = "Example project"
"#,
        )
        .expect("record written");

        let err = cmd_doctor(root.clone()).expect_err("overlay doctor should fail");
        let exit = err.downcast_ref::<CliExit>().expect("returns a CliExit");
        assert_eq!(exit.code, 2);
        assert!(exit
            .message
            .contains("doctor is only supported for native records"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn validate_reports_multiple_diagnostics() {
        let root = temp_dir("validate-many");
        fs::write(
            root.join("record.toml"),
            r#"
schema = "dotrepo/v9.9"

[record]
mode = "overlay"
status = "imported"

[repo]
name = " "
description = "Broken overlay"
"#,
        )
        .expect("record written");

        let err = cmd_validate(root.clone()).expect_err("invalid manifest should fail");
        let exit = err.downcast_ref::<CliExit>().expect("returns a CliExit");
        assert!(exit.message.contains("unsupported schema"));
        assert!(exit.message.contains("repo.name must not be empty"));
        assert!(exit.message.contains("record.source must be set"));
        assert!(exit.message.contains("record.trust must be set"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn public_export_writes_static_repository_and_trust_json() {
        let root = temp_dir("public-export");
        let index_root = root.join("index");
        let record_dir = index_root.join("repos/github.com/example/orbit");
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

        let out_dir = root.join("public");
        cmd_public(PublicCommand::Export {
            index_root: index_root.clone(),
            out_dir: out_dir.clone(),
            base_path: "/".into(),
            stale_after_hours: Some(24),
            generated_at: None,
            stale_after: None,
        })
        .expect("public export succeeds");

        assert!(out_dir.join("v0/meta.json").exists());
        assert!(out_dir
            .join("v0/repos/github.com/example/orbit/index.json")
            .exists());
        assert!(out_dir
            .join("v0/repos/github.com/example/orbit/trust.json")
            .exists());

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn public_export_honors_base_path_in_inventory_links() {
        let root = temp_dir("public-export-base-path");
        let index_root = root.join("index");
        let record_dir = index_root.join("repos/github.com/example/orbit");
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

        let out_dir = root.join("public");
        cmd_public(PublicCommand::Export {
            index_root: index_root.clone(),
            out_dir: out_dir.clone(),
            base_path: "/dotrepo".into(),
            stale_after_hours: Some(24),
            generated_at: None,
            stale_after: None,
        })
        .expect("public export succeeds");

        let inventory = fs::read_to_string(out_dir.join("v0/repos/index.json")).expect("inventory");
        assert!(inventory.contains("\"self\": \"/dotrepo/v0/repos/github.com/example/orbit\""));
        assert!(
            inventory.contains("\"trust\": \"/dotrepo/v0/repos/github.com/example/orbit/trust\"")
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn public_freshness_reuses_snapshot_digest() {
        let root = temp_dir("public-freshness");
        let index_root = root.join("index");
        let record_dir = index_root.join("repos/github.com/example/orbit");
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

        let digest = index_snapshot_digest(&index_root).expect("snapshot digest");
        let freshness =
            current_public_freshness(&index_root, Some(24)).expect("public freshness builds");
        assert_eq!(freshness.snapshot_digest, digest);
        assert!(freshness.stale_after.is_some());

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn deterministic_public_export_repeats_byte_for_byte() {
        let root = temp_dir("public-export-deterministic");
        let index_root = root.join("index");
        let record_dir = index_root.join("repos/github.com/example/orbit");
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

        let out_a = root.join("public-a");
        let out_b = root.join("public-b");
        let generated_at = "2026-03-10T18:30:00Z".to_string();
        let stale_after = "2026-03-11T18:30:00Z".to_string();

        cmd_public(PublicCommand::Export {
            index_root: index_root.clone(),
            out_dir: out_a.clone(),
            base_path: "/".into(),
            stale_after_hours: None,
            generated_at: Some(generated_at.clone()),
            stale_after: Some(stale_after.clone()),
        })
        .expect("first deterministic export succeeds");
        cmd_public(PublicCommand::Export {
            index_root: index_root.clone(),
            out_dir: out_b.clone(),
            base_path: "/".into(),
            stale_after_hours: None,
            generated_at: Some(generated_at),
            stale_after: Some(stale_after),
        })
        .expect("second deterministic export succeeds");

        assert_eq!(read_tree(&out_a), read_tree(&out_b));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn deterministic_public_export_requires_generated_at_for_fixed_stale_after() {
        let root = temp_dir("public-export-invalid");
        let index_root = root.join("index");
        let record_dir = index_root.join("repos/github.com/example/orbit");
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

        let err = cmd_public(PublicCommand::Export {
            index_root: index_root.clone(),
            out_dir: root.join("public"),
            base_path: "/".into(),
            stale_after_hours: None,
            generated_at: None,
            stale_after: Some("2026-03-11T18:30:00Z".into()),
        })
        .expect_err("fixed stale-after without generated-at should fail");
        assert!(
            err.to_string()
                .contains("--stale-after requires --generated-at"),
            "unexpected error: {err}"
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    fn read_tree(root: &PathBuf) -> Vec<(String, String)> {
        let mut paths = Vec::new();
        collect_files(root, &mut paths);
        paths
            .into_iter()
            .map(|path| {
                (
                    path.strip_prefix(root)
                        .expect("relative path")
                        .display()
                        .to_string(),
                    fs::read_to_string(&path).expect("file is readable"),
                )
            })
            .collect()
    }

    fn collect_files(root: &PathBuf, out: &mut Vec<PathBuf>) {
        let mut entries = fs::read_dir(root)
            .expect("directory exists")
            .filter_map(|entry| entry.ok())
            .map(|entry| entry.path())
            .collect::<Vec<_>>();
        entries.sort();

        for path in entries {
            if path.is_dir() {
                collect_files(&path, out);
            } else {
                out.push(path);
            }
        }
    }

    fn temp_dir(label: &str) -> PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock works")
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "dotrepo-cli-{}-{}-{}",
            label,
            std::process::id(),
            unique
        ));
        fs::create_dir_all(&path).expect("temp dir created");
        path
    }
}
