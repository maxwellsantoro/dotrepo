use anyhow::{anyhow, bail, Context, Result};
use clap::{Args, Parser, Subcommand};
use dotrepo_core::{load_manifest_from_root, load_synthesis_from_root};
use dotrepo_crawler::{
    apply_crawl_writeback, crawl_repository, load_crawler_state, refresh_candidates_from_state,
    schedule_refresh, seed_repositories, write_crawler_state, CrawlDiagnostic,
    CrawlRepositoryRequest, CrawlStateRecord, CrawlerStateSnapshot, DiscoveredRepository,
    RefreshCandidate, RefreshReason, RepositoryRef, ScheduleRefreshReport, ScheduleRefreshRequest,
    SeedRepositoriesReport, SeedRepositoriesRequest, StarBand, MAX_SEED_LIMIT,
};
use dotrepo_schema::{Manifest, RecordStatus};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, HashSet};
use std::path::{Path, PathBuf};

#[derive(Parser)]
#[command(name = "dotrepo-crawler")]
#[command(about = "Discovery, factual crawl planning, and batch seed writeback for dotrepo.")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Discover GitHub repositories by star band for factual crawl candidates.
    Discover(DiscoverArgs),
    /// Crawl one repository into a factual overlay plan, optionally writing it to the index.
    Crawl(CrawlArgs),
    /// Discover and seed a batch of factual overlay entries into an index root.
    Seed(SeedArgs),
    /// Schedule refresh work from discovery output and persisted crawler state.
    Schedule(ScheduleArgs),
    /// Fetch current GitHub heads for tracked repositories and emit a refresh plan.
    RefreshPlan(RefreshPlanArgs),
}

#[derive(Args, Debug, Clone)]
struct DiscoverArgs {
    /// Repository host. Only github.com is supported today.
    #[arg(long, default_value = "github.com")]
    host: String,
    /// Maximum number of repositories to return.
    #[arg(long, default_value_t = 20)]
    limit: usize,
    /// Star-band filter such as 1000..10000 or 10000+.
    #[arg(long = "star-band", value_parser = parse_star_band)]
    star_bands: Vec<StarBand>,
    /// Include archived repositories in discovery results.
    #[arg(long)]
    include_archived: bool,
    /// Include forks in discovery results.
    #[arg(long)]
    include_forks: bool,
    /// Emit JSON instead of human-readable output.
    #[arg(long)]
    json: bool,
}

#[derive(Args, Debug, Clone)]
struct CrawlArgs {
    /// Index root that will receive record.toml and evidence.md when --write is set.
    #[arg(long, default_value = "index")]
    index_root: PathBuf,
    /// Repository host. Only github.com is supported today.
    #[arg(long, default_value = "github.com")]
    host: String,
    /// Repository owner.
    #[arg(long)]
    owner: String,
    /// Repository name.
    #[arg(long)]
    repo: String,
    /// Optional fixed RFC 3339 generated_at timestamp for deterministic output.
    #[arg(long)]
    generated_at: Option<String>,
    /// Optional explicit source URL override.
    #[arg(long)]
    source_url: Option<String>,
    /// Write the planned overlay into the index root and update crawler state.
    #[arg(long)]
    write: bool,
    /// Optional crawler state path override.
    #[arg(long)]
    state_path: Option<PathBuf>,
    /// Emit JSON instead of human-readable output.
    #[arg(long)]
    json: bool,
}

#[derive(Args, Debug, Clone)]
struct SeedArgs {
    /// Index root that will receive seeded overlay entries.
    #[arg(long, default_value = "index")]
    index_root: PathBuf,
    /// Repository host. Only github.com is supported today.
    #[arg(long, default_value = "github.com")]
    host: String,
    /// Maximum number of repositories to crawl.
    ///
    /// Defaults to 10 for discovery-based seeding and to the full target-list length when
    /// --targets-file is used.
    #[arg(long)]
    limit: Option<usize>,
    /// Star-band filter such as 1000..10000 or 10000+.
    #[arg(long = "star-band", value_parser = parse_star_band)]
    star_bands: Vec<StarBand>,
    /// Optional newline-delimited repository target list. Supports owner/repo or host/owner/repo.
    #[arg(long)]
    targets_file: Option<PathBuf>,
    /// Include archived repositories in discovery results.
    #[arg(long)]
    include_archived: bool,
    /// Include forks in discovery results.
    #[arg(long)]
    include_forks: bool,
    /// Plan the batch without writing files or crawler state.
    #[arg(long)]
    dry_run: bool,
    /// Optional markdown path for a reviewer-oriented triage report.
    #[arg(long)]
    review_report_md: Option<PathBuf>,
    /// Optional fixed RFC 3339 generated_at timestamp for deterministic output.
    #[arg(long)]
    generated_at: Option<String>,
    /// Optional crawler state path override.
    #[arg(long)]
    state_path: Option<PathBuf>,
    /// Emit JSON instead of human-readable output.
    #[arg(long)]
    json: bool,
}

#[derive(Args, Debug, Clone)]
struct ScheduleArgs {
    /// Path to a JSON file produced by `dotrepo-crawler discover --json`.
    #[arg(long)]
    discovery_json: PathBuf,
    /// Path to the crawler state TOML file.
    #[arg(long)]
    state_path: PathBuf,
    /// Maximum number of refreshes to schedule.
    #[arg(long, default_value_t = 20)]
    limit: usize,
    /// Optional fixed RFC 3339 timestamp for deterministic scheduling output.
    #[arg(long)]
    now: Option<String>,
    /// Whether scheduled entries should request synthesis on top of factual refresh.
    #[arg(long)]
    synthesize: bool,
    /// Optional synthesis model marker used when scheduling synthesized refreshes.
    #[arg(long)]
    synthesis_model: Option<String>,
    /// Emit JSON instead of human-readable output.
    #[arg(long)]
    json: bool,
}

#[derive(Args, Debug, Clone)]
struct RefreshPlanArgs {
    /// Path to the crawler state TOML file.
    #[arg(long, default_value = "index/.crawler-state.toml")]
    state_path: PathBuf,
    /// Maximum number of refreshes to schedule. Defaults to the tracked repo count.
    #[arg(long)]
    limit: Option<usize>,
    /// Optional fixed RFC 3339 timestamp for deterministic scheduling output.
    #[arg(long)]
    now: Option<String>,
    /// Whether scheduled entries should request synthesis on top of factual refresh.
    #[arg(long)]
    synthesize: bool,
    /// Optional synthesis model marker used when scheduling synthesized refreshes.
    #[arg(long)]
    synthesis_model: Option<String>,
    /// Emit JSON instead of human-readable output.
    #[arg(long)]
    json: bool,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct CrawlCommandReport {
    repository: RepositoryRef,
    wrote: bool,
    manifest_path: PathBuf,
    evidence_path: Option<PathBuf>,
    state_path: Option<PathBuf>,
    diagnostics: Vec<CrawlDiagnostic>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
enum SeedResultStatus {
    Applied,
    Planned,
    SkippedExisting,
    Failed,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct SeedCommandResult {
    repository: RepositoryRef,
    status: SeedResultStatus,
    manifest_path: Option<PathBuf>,
    evidence_path: Option<PathBuf>,
    message: Option<String>,
    diagnostics: Vec<CrawlDiagnostic>,
    #[serde(skip_serializing_if = "Option::is_none")]
    review: Option<SeedReviewAssessment>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct SeedCommandReport {
    discovery: SeedRepositoriesReport,
    dry_run: bool,
    state_path: Option<PathBuf>,
    results: Vec<SeedCommandResult>,
    review: SeedReviewReport,
    #[serde(skip_serializing_if = "Option::is_none")]
    review_report_path: Option<PathBuf>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
enum SeedReviewPriority {
    High,
    Medium,
    Low,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct SeedReviewAssessment {
    repository: RepositoryRef,
    status: SeedResultStatus,
    priority: SeedReviewPriority,
    reasons: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    manifest_path: Option<PathBuf>,
    #[serde(skip_serializing_if = "Option::is_none")]
    evidence_path: Option<PathBuf>,
    #[serde(skip_serializing_if = "Option::is_none")]
    record_status: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    build: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    test: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    security_contact: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    inferred_fields: Vec<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    warning_codes: Vec<String>,
}

#[derive(Debug, Clone, Default, Serialize)]
#[serde(rename_all = "camelCase")]
struct SeedReviewSummary {
    actionable: usize,
    high: usize,
    medium: usize,
    low: usize,
    failed: usize,
    missing_security_contact: usize,
    inferred_execution_fields: usize,
    missing_execution_fields: usize,
    missing_owner_signal: usize,
    warnings: usize,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct SeedReviewReport {
    summary: SeedReviewSummary,
    items: Vec<SeedReviewAssessment>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct RefreshPlanCommandReport {
    state_path: PathBuf,
    state_source: RefreshPlanStateSource,
    tracked_repositories: usize,
    candidate_count: usize,
    candidates: Vec<RefreshCandidate>,
    schedule: ScheduleRefreshReport,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
enum RefreshPlanStateSource {
    CrawlerState,
    IndexRecords,
}

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(rename_all = "snake_case")]
struct GitHubRecordExtension {
    default_branch: Option<String>,
    head_sha: Option<String>,
}

fn main() {
    if let Err(err) = run() {
        eprintln!("{err}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::Discover(args) => cmd_discover(args),
        Command::Crawl(args) => cmd_crawl(args),
        Command::Seed(args) => cmd_seed(args),
        Command::Schedule(args) => cmd_schedule(args),
        Command::RefreshPlan(args) => cmd_refresh_plan(args),
    }
}

fn cmd_discover(args: DiscoverArgs) -> Result<()> {
    let report = seed_repositories(&seed_request_from_args(
        &args.host,
        args.limit,
        args.star_bands,
        args.include_archived,
        args.include_forks,
    ))?;

    if args.json {
        print_json(&report)?;
        return Ok(());
    }

    println!(
        "discovered {} repositories{}",
        report.discovered.len(),
        if report.exhausted_bands {
            " after exhausting configured star bands"
        } else {
            ""
        }
    );
    for entry in &report.discovered {
        let branch = entry
            .default_branch
            .as_deref()
            .map(|value| format!("default branch {}", value))
            .unwrap_or_else(|| "default branch unknown".into());
        println!(
            "- {}/{}/{} ({} stars, {})",
            entry.repository.host,
            entry.repository.owner,
            entry.repository.repo,
            entry.stars,
            branch
        );
    }

    Ok(())
}

fn cmd_crawl(args: CrawlArgs) -> Result<()> {
    let repository = RepositoryRef {
        host: args.host,
        owner: args.owner,
        repo: args.repo,
    };
    let report = crawl_repository(&CrawlRepositoryRequest {
        index_root: args.index_root.clone(),
        repository: repository.clone(),
        generated_at: args.generated_at,
        source_url: args.source_url,
        synthesize: false,
        synthesis_model: None,
        synthesis_provider: None,
        prior_synthesis_failure: None,
    })?;

    let mut state_path = None;
    if args.write {
        apply_crawl_writeback(&report.writeback_plan)?;
        let resolved_state_path = resolve_state_path(&args.index_root, args.state_path.as_deref());
        let mut state = load_crawler_state(&resolved_state_path)?;
        upsert_state_record(&mut state, report.state_record.clone());
        write_crawler_state(&resolved_state_path, &state)?;
        state_path = Some(resolved_state_path);
    }

    let command_report = CrawlCommandReport {
        repository,
        wrote: args.write,
        manifest_path: report.writeback_plan.factual.manifest_path.clone(),
        evidence_path: report.writeback_plan.factual.evidence_path.clone(),
        state_path,
        diagnostics: report.diagnostics,
    };

    if args.json {
        print_json(&command_report)?;
        return Ok(());
    }

    println!(
        "{} overlay for {}/{}/{}",
        if command_report.wrote {
            "wrote"
        } else {
            "planned"
        },
        command_report.repository.host,
        command_report.repository.owner,
        command_report.repository.repo
    );
    println!("manifest: {}", command_report.manifest_path.display());
    if let Some(path) = &command_report.evidence_path {
        println!("evidence: {}", path.display());
    }
    if let Some(path) = &command_report.state_path {
        println!("state: {}", path.display());
    }
    for diagnostic in &command_report.diagnostics {
        println!(
            "- {:?} {}: {}",
            diagnostic.severity, diagnostic.code, diagnostic.message
        );
    }

    Ok(())
}

fn cmd_seed(args: SeedArgs) -> Result<()> {
    let explicit_targets = args
        .targets_file
        .as_deref()
        .map(|path| load_repository_targets(path, &args.host))
        .transpose()?;
    if explicit_targets.is_some()
        && (!args.star_bands.is_empty() || args.include_archived || args.include_forks)
    {
        bail!(
            "--targets-file cannot be combined with --star-band, --include-archived, or --include-forks"
        );
    }

    let effective_limit = args.limit.unwrap_or_else(|| {
        explicit_targets
            .as_ref()
            .map(|targets| targets.len())
            .unwrap_or(10)
    });
    if effective_limit > MAX_SEED_LIMIT {
        bail!(
            "seed limit {} exceeds max {}",
            effective_limit,
            MAX_SEED_LIMIT
        );
    }
    let discovery = if let Some(targets) = explicit_targets {
        discovery_report_from_targets(&args.host, targets, effective_limit)
    } else {
        seed_repositories(&seed_request_from_args(
            &args.host,
            effective_limit,
            args.star_bands.clone(),
            args.include_archived,
            args.include_forks,
        ))?
    };

    let mut state = if args.dry_run {
        CrawlerStateSnapshot::default()
    } else {
        load_crawler_state(&resolve_state_path(
            &args.index_root,
            args.state_path.as_deref(),
        ))?
    };
    let mut results = Vec::new();

    for entry in &discovery.discovered {
        let manifest_path = entry
            .repository
            .record_root(&args.index_root)
            .join("record.toml");
        if manifest_path.exists() {
            results.push(SeedCommandResult {
                repository: entry.repository.clone(),
                status: SeedResultStatus::SkippedExisting,
                manifest_path: Some(manifest_path),
                evidence_path: None,
                message: Some("record.toml already exists under the index root".into()),
                diagnostics: Vec::new(),
                review: None,
            });
            continue;
        }

        match crawl_repository(&CrawlRepositoryRequest {
            index_root: args.index_root.clone(),
            repository: entry.repository.clone(),
            generated_at: args.generated_at.clone(),
            source_url: None,
            synthesize: false,
            synthesis_model: None,
            synthesis_provider: None,
            prior_synthesis_failure: None,
        }) {
            Ok(report) => {
                if args.dry_run {
                    results.push(SeedCommandResult {
                        repository: entry.repository.clone(),
                        status: SeedResultStatus::Planned,
                        manifest_path: Some(report.writeback_plan.factual.manifest_path.clone()),
                        evidence_path: report.writeback_plan.factual.evidence_path.clone(),
                        message: None,
                        review: Some(build_seed_review_assessment(SeedReviewAssessmentInput {
                            repository: entry.repository.clone(),
                            status: SeedResultStatus::Planned,
                            manifest: Some(&report.writeback_plan.factual.import_plan.manifest),
                            inferred_fields: &report
                                .writeback_plan
                                .factual
                                .import_plan
                                .inferred_fields,
                            diagnostics: &report.diagnostics,
                            manifest_path: report.writeback_plan.factual.manifest_path.clone(),
                            evidence_path: report.writeback_plan.factual.evidence_path.clone(),
                            failure_message: None,
                        })),
                        diagnostics: report.diagnostics,
                    });
                } else {
                    apply_crawl_writeback(&report.writeback_plan)?;
                    upsert_state_record(&mut state, report.state_record);
                    results.push(SeedCommandResult {
                        repository: entry.repository.clone(),
                        status: SeedResultStatus::Applied,
                        manifest_path: Some(report.writeback_plan.factual.manifest_path.clone()),
                        evidence_path: report.writeback_plan.factual.evidence_path.clone(),
                        message: None,
                        review: Some(build_seed_review_assessment(SeedReviewAssessmentInput {
                            repository: entry.repository.clone(),
                            status: SeedResultStatus::Applied,
                            manifest: Some(&report.writeback_plan.factual.import_plan.manifest),
                            inferred_fields: &report
                                .writeback_plan
                                .factual
                                .import_plan
                                .inferred_fields,
                            diagnostics: &report.diagnostics,
                            manifest_path: report.writeback_plan.factual.manifest_path.clone(),
                            evidence_path: report.writeback_plan.factual.evidence_path.clone(),
                            failure_message: None,
                        })),
                        diagnostics: report.diagnostics,
                    });
                }
            }
            Err(err) => results.push(SeedCommandResult {
                repository: entry.repository.clone(),
                status: SeedResultStatus::Failed,
                manifest_path: Some(manifest_path.clone()),
                evidence_path: Some(
                    entry
                        .repository
                        .record_root(&args.index_root)
                        .join("evidence.md"),
                ),
                message: Some(err.to_string()),
                diagnostics: Vec::new(),
                review: Some(build_seed_review_assessment(SeedReviewAssessmentInput {
                    repository: entry.repository.clone(),
                    status: SeedResultStatus::Failed,
                    manifest: None,
                    inferred_fields: &[],
                    diagnostics: &[],
                    manifest_path,
                    evidence_path: Some(
                        entry
                            .repository
                            .record_root(&args.index_root)
                            .join("evidence.md"),
                    ),
                    failure_message: Some(err.to_string()),
                })),
            }),
        }
    }

    let state_path = if args.dry_run {
        None
    } else {
        let path = resolve_state_path(&args.index_root, args.state_path.as_deref());
        write_crawler_state(&path, &state)?;
        Some(path)
    };
    let review = build_seed_review_report(&results);
    let review_report_path = args.review_report_md.clone();
    if let Some(path) = review_report_path.as_deref() {
        let markdown = render_seed_review_report_markdown(&review, args.dry_run);
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(path, markdown)?;
    }
    let command_report = SeedCommandReport {
        discovery,
        dry_run: args.dry_run,
        state_path,
        results,
        review,
        review_report_path,
    };

    if args.json {
        print_json(&command_report)?;
    } else {
        println!(
            "{} {} repositories from {} discovered candidates",
            if args.dry_run { "planned" } else { "processed" },
            command_report.results.len(),
            command_report.discovery.discovered.len()
        );
        for result in &command_report.results {
            let identity = format!(
                "{}/{}/{}",
                result.repository.host, result.repository.owner, result.repository.repo
            );
            match result.status {
                SeedResultStatus::Applied => {
                    let path = result
                        .manifest_path
                        .as_ref()
                        .map(|value| value.display().to_string())
                        .unwrap_or_else(|| "<unknown>".into());
                    println!("- applied {} -> {}", identity, path);
                }
                SeedResultStatus::Planned => {
                    let path = result
                        .manifest_path
                        .as_ref()
                        .map(|value| value.display().to_string())
                        .unwrap_or_else(|| "<unknown>".into());
                    println!("- planned {} -> {}", identity, path);
                }
                SeedResultStatus::SkippedExisting => {
                    println!("- skipped existing {}", identity);
                }
                SeedResultStatus::Failed => {
                    println!(
                        "- failed {}: {}",
                        identity,
                        result.message.as_deref().unwrap_or("unknown error")
                    );
                }
            }
        }
        println!(
            "review triage: {} high, {} medium, {} low",
            command_report.review.summary.high,
            command_report.review.summary.medium,
            command_report.review.summary.low
        );
        println!(
            "review signals: {} missing security, {} inferred build/test, {} missing build/test, {} missing maintainer/team, {} warning-bearing repos",
            command_report.review.summary.missing_security_contact,
            command_report.review.summary.inferred_execution_fields,
            command_report.review.summary.missing_execution_fields,
            command_report.review.summary.missing_owner_signal,
            command_report.review.summary.warnings
        );
        if let Some(path) = &command_report.state_path {
            println!("state: {}", path.display());
        }
        if let Some(path) = &command_report.review_report_path {
            println!("review report: {}", path.display());
        }
    }

    let failure_count = command_report
        .results
        .iter()
        .filter(|result| matches!(result.status, SeedResultStatus::Failed))
        .count();
    if failure_count > 0 {
        bail!("seed completed with {} crawl failures", failure_count);
    }

    Ok(())
}

fn cmd_schedule(args: ScheduleArgs) -> Result<()> {
    let discovery: SeedRepositoriesReport =
        serde_json::from_str(&std::fs::read_to_string(&args.discovery_json)?)?;
    let state = load_crawler_state(&args.state_path)?;
    let report = schedule_refresh(&ScheduleRefreshRequest {
        now: args.now,
        limit: args.limit,
        synthesize: args.synthesize,
        synthesis_model: args.synthesis_model,
        state,
        candidates: discovery
            .discovered
            .into_iter()
            .map(|entry| RefreshCandidate {
                repository: entry.repository,
                default_branch: entry.default_branch,
                head_sha: None,
            })
            .collect(),
    })?;

    if args.json {
        print_json(&report)?;
        return Ok(());
    }

    println!("scheduled {} refreshes", report.scheduled.len());
    for entry in &report.scheduled {
        println!(
            "- {}/{}/{} ({:?})",
            entry.repository.host, entry.repository.owner, entry.repository.repo, entry.reason
        );
    }
    if !report.skipped.is_empty() {
        println!("skipped {} repositories", report.skipped.len());
        for entry in &report.skipped {
            println!(
                "- {}/{}/{} ({})",
                entry.repository.host, entry.repository.owner, entry.repository.repo, entry.reason
            );
        }
    }

    Ok(())
}

fn cmd_refresh_plan(args: RefreshPlanArgs) -> Result<()> {
    let (state, state_source) = load_refresh_state_for_plan(&args.state_path)?;
    let tracked_repositories = state.repositories.len();
    let candidates = refresh_candidates_from_state(&state)?;
    let effective_limit = args.limit.unwrap_or(candidates.len());
    let schedule = schedule_refresh(&ScheduleRefreshRequest {
        now: args.now,
        limit: effective_limit,
        synthesize: args.synthesize,
        synthesis_model: args.synthesis_model,
        state,
        candidates: candidates.clone(),
    })?;
    let report = RefreshPlanCommandReport {
        state_path: args.state_path,
        state_source,
        tracked_repositories,
        candidate_count: candidates.len(),
        candidates,
        schedule,
    };

    if args.json {
        print_json(&report)?;
        return Ok(());
    }

    println!(
        "planned {} refreshes from {} tracked repositories",
        report.schedule.scheduled.len(),
        report.tracked_repositories
    );
    println!(
        "state source: {}",
        refresh_plan_state_source_label(report.state_source)
    );
    let mut reasons = BTreeMap::new();
    for entry in &report.schedule.scheduled {
        *reasons
            .entry(refresh_reason_label(entry.reason).to_string())
            .or_insert(0_usize) += 1;
    }
    if !reasons.is_empty() {
        println!("scheduled reasons:");
        for (reason, count) in reasons {
            println!("- {}: {}", reason, count);
        }
    }
    for entry in &report.schedule.scheduled {
        println!(
            "- {}/{}/{} ({})",
            entry.repository.host,
            entry.repository.owner,
            entry.repository.repo,
            refresh_reason_label(entry.reason)
        );
    }
    if !report.schedule.skipped.is_empty() {
        println!("skipped {} repositories", report.schedule.skipped.len());
        for entry in &report.schedule.skipped {
            println!(
                "- {}/{}/{} ({})",
                entry.repository.host, entry.repository.owner, entry.repository.repo, entry.reason
            );
        }
    }

    Ok(())
}

fn seed_request_from_args(
    host: &str,
    limit: usize,
    star_bands: Vec<StarBand>,
    include_archived: bool,
    include_forks: bool,
) -> SeedRepositoriesRequest {
    SeedRepositoriesRequest {
        host: host.into(),
        limit,
        star_bands,
        include_archived,
        include_forks,
    }
}

fn refresh_reason_label(reason: RefreshReason) -> &'static str {
    match reason {
        RefreshReason::MissingFactualCrawl => "missing factual crawl",
        RefreshReason::HeadChanged => "head changed",
        RefreshReason::MissingSynthesis => "missing synthesis",
        RefreshReason::PreviousSynthesisFailed => "previous synthesis failed",
        RefreshReason::SynthesisModelChanged => "synthesis model changed",
    }
}

fn load_repository_targets(path: &Path, default_host: &str) -> Result<Vec<RepositoryRef>> {
    let contents = std::fs::read_to_string(path)?;
    parse_repository_targets(&contents, default_host)
}

fn parse_repository_targets(contents: &str, default_host: &str) -> Result<Vec<RepositoryRef>> {
    let mut targets = Vec::new();
    let mut seen = HashSet::new();

    for (line_number, raw_line) in contents.lines().enumerate() {
        let line = raw_line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }

        let repository = parse_repository_target(line, default_host).map_err(|err| {
            anyhow!(
                "invalid repository target on line {}: {} ({})",
                line_number + 1,
                line,
                err
            )
        })?;
        let key = format!(
            "{}/{}/{}",
            repository.host, repository.owner, repository.repo
        );
        if seen.insert(key) {
            targets.push(repository);
        }
    }

    if targets.is_empty() {
        bail!("repository target list did not contain any repositories");
    }

    Ok(targets)
}

fn parse_repository_target(value: &str, default_host: &str) -> Result<RepositoryRef> {
    let trimmed = value
        .trim()
        .trim_start_matches("https://")
        .trim_start_matches("http://")
        .trim_matches('/');
    let segments = trimmed.split('/').collect::<Vec<_>>();
    let repository = match segments.as_slice() {
        [owner, repo] => RepositoryRef {
            host: default_host.into(),
            owner: owner.to_string(),
            repo: repo.to_string(),
        },
        [host, owner, repo] => RepositoryRef {
            host: host.to_string(),
            owner: owner.to_string(),
            repo: repo.to_string(),
        },
        _ => bail!("expected owner/repo or host/owner/repo"),
    };
    repository.validate_identity()?;
    Ok(repository)
}

fn discovery_report_from_targets(
    host: &str,
    repositories: Vec<RepositoryRef>,
    limit: usize,
) -> SeedRepositoriesReport {
    let total_targets = repositories.len();
    let discovered = repositories
        .into_iter()
        .take(limit)
        .map(|repository| DiscoveredRepository {
            repository,
            stars: 0,
            default_branch: None,
            archived: false,
            fork: false,
        })
        .collect::<Vec<_>>();

    SeedRepositoriesReport {
        host: host.into(),
        requested_limit: limit,
        exhausted_bands: total_targets <= limit,
        discovered,
    }
}

fn resolve_state_path(index_root: &Path, state_path: Option<&Path>) -> PathBuf {
    state_path
        .map(Path::to_path_buf)
        .unwrap_or_else(|| index_root.join(".crawler-state.toml"))
}

fn load_refresh_state_for_plan(
    state_path: &Path,
) -> Result<(CrawlerStateSnapshot, RefreshPlanStateSource)> {
    let state = load_crawler_state(state_path)?;
    if !state.repositories.is_empty() {
        return Ok((state, RefreshPlanStateSource::CrawlerState));
    }

    let index_root = state_path.parent().unwrap_or_else(|| Path::new("."));
    let derived = derive_refresh_state_from_index(index_root)?;
    if !derived.repositories.is_empty() {
        return Ok((derived, RefreshPlanStateSource::IndexRecords));
    }

    Ok((state, RefreshPlanStateSource::CrawlerState))
}

fn derive_refresh_state_from_index(index_root: &Path) -> Result<CrawlerStateSnapshot> {
    let repos_root = index_root.join("repos");
    if !repos_root.is_dir() {
        return Ok(CrawlerStateSnapshot::default());
    }

    let mut repositories = Vec::new();
    for host_entry in std::fs::read_dir(&repos_root)
        .with_context(|| format!("failed to read index repositories {}", repos_root.display()))?
    {
        let host_entry = host_entry?;
        if !host_entry.file_type()?.is_dir() {
            continue;
        }
        let host = host_entry.file_name().to_string_lossy().to_string();
        if host != "github.com" {
            continue;
        }

        for owner_entry in std::fs::read_dir(host_entry.path()).with_context(|| {
            format!(
                "failed to read repository owner directory {}",
                host_entry.path().display()
            )
        })? {
            let owner_entry = owner_entry?;
            if !owner_entry.file_type()?.is_dir() {
                continue;
            }
            let owner = owner_entry.file_name().to_string_lossy().to_string();

            for repo_entry in std::fs::read_dir(owner_entry.path()).with_context(|| {
                format!(
                    "failed to read repository directory {}",
                    owner_entry.path().display()
                )
            })? {
                let repo_entry = repo_entry?;
                if !repo_entry.file_type()?.is_dir() {
                    continue;
                }
                let repo = repo_entry.file_name().to_string_lossy().to_string();
                let repo_root = repo_entry.path();
                if !repo_root.join("record.toml").is_file() {
                    continue;
                }

                let manifest = load_manifest_from_root(&repo_root).with_context(|| {
                    format!(
                        "failed to load repository manifest for refresh planning {}",
                        repo_root.display()
                    )
                })?;
                let github = github_record_extension(&manifest).with_context(|| {
                    format!(
                        "failed to parse GitHub metadata for refresh planning {}",
                        repo_root.display()
                    )
                })?;
                let synthesis = if repo_root.join("synthesis.toml").is_file() {
                    Some(load_synthesis_from_root(&repo_root).with_context(|| {
                        format!(
                            "failed to load synthesis document for refresh planning {}",
                            repo_root.display()
                        )
                    })?)
                } else {
                    None
                };

                repositories.push(CrawlStateRecord {
                    repository: RepositoryRef {
                        host: host.clone(),
                        owner: owner.clone(),
                        repo,
                    },
                    default_branch: github.default_branch,
                    head_sha: github.head_sha,
                    last_factual_crawl_at: manifest.record.generated_at.clone(),
                    last_synthesis_success_at: synthesis
                        .as_ref()
                        .map(|document| document.synthesis.generated_at.clone()),
                    last_synthesis_failure: None,
                    synthesis_model: synthesis
                        .as_ref()
                        .map(|document| document.synthesis.model.clone()),
                });
            }
        }
    }

    repositories.sort_by(|left, right| {
        (
            left.repository.host.as_str(),
            left.repository.owner.as_str(),
            left.repository.repo.as_str(),
        )
            .cmp(&(
                right.repository.host.as_str(),
                right.repository.owner.as_str(),
                right.repository.repo.as_str(),
            ))
    });

    Ok(CrawlerStateSnapshot { repositories })
}

fn github_record_extension(manifest: &Manifest) -> Result<GitHubRecordExtension> {
    let Some(value) = manifest.x.get("github") else {
        return Ok(GitHubRecordExtension::default());
    };

    value
        .clone()
        .try_into()
        .map_err(|err| anyhow!("invalid [x.github] extension: {err}"))
}

fn refresh_plan_state_source_label(source: RefreshPlanStateSource) -> &'static str {
    match source {
        RefreshPlanStateSource::CrawlerState => "crawler state",
        RefreshPlanStateSource::IndexRecords => "committed index records",
    }
}

fn upsert_state_record(state: &mut CrawlerStateSnapshot, record: CrawlStateRecord) {
    if let Some(existing) = state
        .repositories
        .iter_mut()
        .find(|existing| existing.repository == record.repository)
    {
        *existing = record;
    } else {
        state.repositories.push(record);
    }

    state.repositories.sort_by(|left, right| {
        (
            left.repository.host.as_str(),
            left.repository.owner.as_str(),
            left.repository.repo.as_str(),
        )
            .cmp(&(
                right.repository.host.as_str(),
                right.repository.owner.as_str(),
                right.repository.repo.as_str(),
            ))
    });
}

fn parse_star_band(value: &str) -> Result<StarBand, String> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return Err("star band must not be empty".into());
    }

    if let Some((min, max)) = trimmed.split_once("..") {
        let min_stars = min
            .trim()
            .parse::<u64>()
            .map_err(|_| format!("invalid star-band lower bound `{}`", min.trim()))?;
        let max_stars = max
            .trim()
            .parse::<u64>()
            .map_err(|_| format!("invalid star-band upper bound `{}`", max.trim()))?;
        if max_stars < min_stars {
            return Err(format!(
                "star-band upper bound {} must be >= lower bound {}",
                max_stars, min_stars
            ));
        }
        return Ok(StarBand {
            min_stars,
            max_stars: Some(max_stars),
        });
    }

    if let Some(min) = trimmed.strip_suffix('+') {
        let min_stars = min
            .trim()
            .parse::<u64>()
            .map_err(|_| format!("invalid star-band lower bound `{}`", min.trim()))?;
        return Ok(StarBand {
            min_stars,
            max_stars: None,
        });
    }

    let min_stars = trimmed
        .parse::<u64>()
        .map_err(|_| format!("invalid star-band `{}`", trimmed))?;
    Ok(StarBand {
        min_stars,
        max_stars: None,
    })
}

fn print_json<T: Serialize>(value: &T) -> Result<()> {
    println!("{}", serde_json::to_string_pretty(value)?);
    Ok(())
}

fn build_seed_review_report(results: &[SeedCommandResult]) -> SeedReviewReport {
    let items = results
        .iter()
        .filter_map(|result| result.review.clone())
        .collect::<Vec<_>>();
    let mut summary = SeedReviewSummary {
        actionable: items.len(),
        ..SeedReviewSummary::default()
    };

    for item in &items {
        match item.priority {
            SeedReviewPriority::High => summary.high += 1,
            SeedReviewPriority::Medium => summary.medium += 1,
            SeedReviewPriority::Low => summary.low += 1,
        }
        let failed = matches!(item.status, SeedResultStatus::Failed);
        if failed {
            summary.failed += 1;
        }
        if !failed
            && (item.security_contact.is_none()
                || item
                    .security_contact
                    .as_deref()
                    .is_some_and(|value| value == "unknown"))
        {
            summary.missing_security_contact += 1;
        }
        if item
            .inferred_fields
            .iter()
            .any(|field| field == "repo.build" || field == "repo.test")
        {
            summary.inferred_execution_fields += 1;
        }
        if !failed && (item.build.is_none() || item.test.is_none()) {
            summary.missing_execution_fields += 1;
        }
        if item
            .reasons
            .iter()
            .any(|reason| reason.contains("maintainer or team"))
        {
            summary.missing_owner_signal += 1;
        }
        if !item.warning_codes.is_empty() {
            summary.warnings += 1;
        }
    }

    SeedReviewReport { summary, items }
}

struct SeedReviewAssessmentInput<'a> {
    repository: RepositoryRef,
    status: SeedResultStatus,
    manifest: Option<&'a Manifest>,
    inferred_fields: &'a [String],
    diagnostics: &'a [CrawlDiagnostic],
    manifest_path: PathBuf,
    evidence_path: Option<PathBuf>,
    failure_message: Option<String>,
}

fn build_seed_review_assessment(input: SeedReviewAssessmentInput<'_>) -> SeedReviewAssessment {
    let SeedReviewAssessmentInput {
        repository,
        status,
        manifest,
        inferred_fields,
        diagnostics,
        manifest_path,
        evidence_path,
        failure_message,
    } = input;

    let mut priority = SeedReviewPriority::Low;
    let mut reasons = Vec::new();
    let warning_codes = diagnostics
        .iter()
        .filter(|diagnostic| {
            matches!(
                diagnostic.severity,
                dotrepo_crawler::CrawlDiagnosticSeverity::Warning
            )
        })
        .map(|diagnostic| diagnostic.code.clone())
        .collect::<Vec<_>>();

    if let Some(message) = failure_message {
        priority = SeedReviewPriority::High;
        reasons.push(format!("crawl failed before writeback: {}", message));
        return SeedReviewAssessment {
            repository,
            status,
            priority,
            reasons,
            manifest_path: Some(manifest_path),
            evidence_path,
            record_status: None,
            build: None,
            test: None,
            security_contact: None,
            inferred_fields: Vec::new(),
            warning_codes,
        };
    }

    let Some(manifest) = manifest else {
        raise_seed_review_priority(&mut priority, SeedReviewPriority::High);
        reasons.push("seed review missing manifest for successful crawl result".into());
        return SeedReviewAssessment {
            repository,
            status,
            priority,
            reasons,
            manifest_path: Some(manifest_path),
            evidence_path,
            record_status: None,
            build: None,
            test: None,
            security_contact: None,
            inferred_fields: inferred_fields.to_vec(),
            warning_codes,
        };
    };

    if !warning_codes.is_empty() {
        raise_seed_review_priority(&mut priority, SeedReviewPriority::Medium);
        reasons.push(format!(
            "crawler emitted warning diagnostics: {}",
            warning_codes.join(", ")
        ));
    }

    let security_contact = manifest
        .owners
        .as_ref()
        .and_then(|owners| owners.security_contact.clone());

    let inferred_execution = inferred_fields
        .iter()
        .filter(|field| field.as_str() == "repo.build" || field.as_str() == "repo.test")
        .cloned()
        .collect::<Vec<_>>();
    if !inferred_execution.is_empty() {
        raise_seed_review_priority(&mut priority, SeedReviewPriority::High);
        reasons.push(format!(
            "execution fields are inferred: {}",
            inferred_execution.join(", ")
        ));
    } else if !inferred_fields.is_empty() {
        raise_seed_review_priority(&mut priority, SeedReviewPriority::Medium);
        reasons.push(format!(
            "non-execution fields are inferred: {}",
            inferred_fields.join(", ")
        ));
    }

    let has_owner_signal = manifest
        .owners
        .as_ref()
        .is_some_and(|owners| !owners.maintainers.is_empty() || owners.team.is_some());
    if !has_owner_signal {
        raise_seed_review_priority(&mut priority, SeedReviewPriority::Medium);
        reasons.push("no maintainer or team ownership signal is present yet".into());
    }

    if matches!(manifest.record.status, RecordStatus::Inferred) {
        raise_seed_review_priority(&mut priority, SeedReviewPriority::High);
        reasons.push("record.status is inferred, so the whole overlay needs closer review".into());
    }

    if reasons.is_empty() {
        reasons.push(
            "ready for light review: execution, security, and ownership signals are present".into(),
        );
    }

    SeedReviewAssessment {
        repository,
        status,
        priority,
        reasons,
        manifest_path: Some(manifest_path),
        evidence_path,
        record_status: Some(record_status_label(&manifest.record.status).into()),
        build: manifest.repo.build.clone(),
        test: manifest.repo.test.clone(),
        security_contact,
        inferred_fields: inferred_fields.to_vec(),
        warning_codes,
    }
}

fn raise_seed_review_priority(current: &mut SeedReviewPriority, candidate: SeedReviewPriority) {
    let current_rank = seed_review_priority_rank(*current);
    let candidate_rank = seed_review_priority_rank(candidate);
    if candidate_rank > current_rank {
        *current = candidate;
    }
}

fn seed_review_priority_rank(priority: SeedReviewPriority) -> u8 {
    match priority {
        SeedReviewPriority::Low => 0,
        SeedReviewPriority::Medium => 1,
        SeedReviewPriority::High => 2,
    }
}

fn record_status_label(status: &RecordStatus) -> &'static str {
    match status {
        RecordStatus::Draft => "draft",
        RecordStatus::Imported => "imported",
        RecordStatus::Inferred => "inferred",
        RecordStatus::Reviewed => "reviewed",
        RecordStatus::Verified => "verified",
        RecordStatus::Canonical => "canonical",
    }
}

fn seed_result_status_label(status: SeedResultStatus) -> &'static str {
    match status {
        SeedResultStatus::Applied => "applied",
        SeedResultStatus::Planned => "planned",
        SeedResultStatus::SkippedExisting => "skipped_existing",
        SeedResultStatus::Failed => "failed",
    }
}

fn seed_review_priority_label(priority: SeedReviewPriority) -> &'static str {
    match priority {
        SeedReviewPriority::High => "high",
        SeedReviewPriority::Medium => "medium",
        SeedReviewPriority::Low => "low",
    }
}

fn render_seed_review_report_markdown(report: &SeedReviewReport, dry_run: bool) -> String {
    let mut output = String::new();
    output.push_str("# Seed Review Report\n\n");
    output.push_str(&format!(
        "- mode: {}\n- actionable repositories: {}\n- high priority: {}\n- medium priority: {}\n- low priority: {}\n- failed crawls: {}\n- missing security contact: {}\n- inferred build/test: {}\n- missing build/test: {}\n- missing maintainer/team signal: {}\n- repos with crawler warnings: {}\n\n",
        if dry_run { "dry-run" } else { "writeback" },
        report.summary.actionable,
        report.summary.high,
        report.summary.medium,
        report.summary.low,
        report.summary.failed,
        report.summary.missing_security_contact,
        report.summary.inferred_execution_fields,
        report.summary.missing_execution_fields,
        report.summary.missing_owner_signal,
        report.summary.warnings,
    ));

    for priority in [
        SeedReviewPriority::High,
        SeedReviewPriority::Medium,
        SeedReviewPriority::Low,
    ] {
        let items = report
            .items
            .iter()
            .filter(|item| item.priority == priority)
            .collect::<Vec<_>>();
        if items.is_empty() {
            continue;
        }
        output.push_str(&format!(
            "## {} priority\n\n",
            seed_review_priority_label(priority).to_ascii_uppercase()
        ));
        for item in items {
            let identity = format!(
                "{}/{}/{}",
                item.repository.host, item.repository.owner, item.repository.repo
            );
            let mut detail_parts = Vec::new();
            if let Some(status) = item.record_status.as_deref() {
                detail_parts.push(format!("record {}", status));
            }
            detail_parts.push(seed_result_status_label(item.status).into());
            if let Some(build) = item.build.as_deref() {
                detail_parts.push(format!("build `{}`", build));
            }
            if let Some(test) = item.test.as_deref() {
                detail_parts.push(format!("test `{}`", test));
            }
            if let Some(contact) = item.security_contact.as_deref() {
                detail_parts.push(format!("security `{}`", contact));
            }
            if !item.warning_codes.is_empty() {
                detail_parts.push(format!("warnings {}", item.warning_codes.join(", ")));
            }
            if let Some(path) = item.manifest_path.as_ref() {
                detail_parts.push(format!("manifest `{}`", path.display()));
            }
            output.push_str(&format!(
                "- `{}`: {}. {}\n",
                identity,
                item.reasons.join("; "),
                detail_parts.join("; ")
            ));
        }
        output.push('\n');
    }

    output
}

#[cfg(test)]
mod tests {
    use super::*;
    use clap::Parser;
    use dotrepo_schema::{Owners, Record, RecordMode, Repo};
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn parse_star_band_supports_range_and_open_ended_forms() {
        assert_eq!(
            parse_star_band("1000..5000").expect("range parses"),
            StarBand {
                min_stars: 1000,
                max_stars: Some(5000)
            }
        );
        assert_eq!(
            parse_star_band("10000+").expect("open-ended parses"),
            StarBand {
                min_stars: 10000,
                max_stars: None
            }
        );
        assert_eq!(
            parse_star_band("250").expect("single number parses"),
            StarBand {
                min_stars: 250,
                max_stars: None
            }
        );
    }

    #[test]
    fn upsert_state_record_replaces_existing_repository() {
        let repository = RepositoryRef {
            host: "github.com".into(),
            owner: "example".into(),
            repo: "orbit".into(),
        };
        let mut state = CrawlerStateSnapshot {
            repositories: vec![CrawlStateRecord {
                repository: repository.clone(),
                default_branch: Some("main".into()),
                head_sha: Some("old".into()),
                last_factual_crawl_at: Some("2026-03-18T00:00:00Z".into()),
                last_synthesis_success_at: None,
                last_synthesis_failure: None,
                synthesis_model: None,
            }],
        };

        upsert_state_record(
            &mut state,
            CrawlStateRecord {
                repository,
                default_branch: Some("main".into()),
                head_sha: Some("new".into()),
                last_factual_crawl_at: Some("2026-03-19T00:00:00Z".into()),
                last_synthesis_success_at: None,
                last_synthesis_failure: None,
                synthesis_model: None,
            },
        );

        assert_eq!(state.repositories.len(), 1);
        assert_eq!(state.repositories[0].head_sha.as_deref(), Some("new"));
    }

    #[test]
    fn cli_parses_seed_command() {
        let cli = Cli::try_parse_from([
            "dotrepo-crawler",
            "seed",
            "--index-root",
            "index",
            "--limit",
            "25",
            "--star-band",
            "1000..10000",
            "--star-band",
            "10000+",
            "--dry-run",
            "--review-report-md",
            "tmp/review.md",
        ])
        .expect("cli parses");

        match cli.command {
            Command::Seed(seed) => {
                assert_eq!(seed.limit, Some(25));
                assert!(seed.dry_run);
                assert_eq!(seed.star_bands.len(), 2);
                assert_eq!(
                    seed.review_report_md.as_deref(),
                    Some(Path::new("tmp/review.md"))
                );
            }
            _ => panic!("expected seed command"),
        }
    }

    #[test]
    fn parse_repository_targets_supports_comments_and_dedupes() {
        let parsed = parse_repository_targets(
            r#"
# Rust
tokio-rs/tokio
github.com/fastapi/fastapi
https://github.com/tokio-rs/tokio
"#,
            "github.com",
        )
        .expect("targets parse");

        assert_eq!(
            parsed,
            vec![
                RepositoryRef {
                    host: "github.com".into(),
                    owner: "tokio-rs".into(),
                    repo: "tokio".into(),
                },
                RepositoryRef {
                    host: "github.com".into(),
                    owner: "fastapi".into(),
                    repo: "fastapi".into(),
                },
            ]
        );
    }

    #[test]
    fn parse_repository_targets_rejects_path_traversal() {
        let err = parse_repository_targets("example/..", "github.com")
            .expect_err("dot-dot should be rejected");
        assert!(
            err.to_string().contains("must not be empty"),
            "expected segment validation error, got: {}",
            err
        );

        let err = parse_repository_targets("example/repo\\name", "github.com")
            .expect_err("backslash should be rejected");
        assert!(
            err.to_string().contains("path separators"),
            "expected path separator error, got: {}",
            err
        );

        // Multi-segment traversal that parses as 3 segments: host / owner / ".."
        let err = parse_repository_targets("github.com/example/..", "github.com")
            .expect_err("dot-dot in repo should be rejected");
        assert!(err.to_string().contains("must not be empty"));
    }

    #[test]
    fn cli_parses_seed_command_with_targets_file() {
        let cli = Cli::try_parse_from([
            "dotrepo-crawler",
            "seed",
            "--targets-file",
            "index/tranche-one-targets.txt",
            "--dry-run",
        ])
        .expect("cli parses");

        match cli.command {
            Command::Seed(seed) => {
                assert_eq!(
                    seed.targets_file.as_deref(),
                    Some(Path::new("index/tranche-one-targets.txt"))
                );
                assert_eq!(seed.limit, None);
                assert!(seed.dry_run);
            }
            _ => panic!("expected seed command"),
        }
    }

    #[test]
    fn cmd_seed_rejects_targets_file_limits_above_maximum() {
        let root = temp_dir("seed-limit");
        let targets = root.join("targets.txt");
        std::fs::write(&targets, "github.com/example/a\n").expect("targets written");

        let err = cmd_seed(SeedArgs {
            index_root: root.join("index"),
            host: "github.com".into(),
            limit: Some(MAX_SEED_LIMIT + 1),
            star_bands: Vec::new(),
            targets_file: Some(targets),
            include_archived: false,
            include_forks: false,
            dry_run: true,
            review_report_md: None,
            generated_at: None,
            state_path: None,
            json: true,
        })
        .expect_err("oversized limit rejected");

        assert!(err.to_string().contains("exceeds max"));
        std::fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn cli_parses_schedule_command() {
        let cli = Cli::try_parse_from([
            "dotrepo-crawler",
            "schedule",
            "--discovery-json",
            "discovered.json",
            "--state-path",
            "index/.crawler-state.toml",
            "--limit",
            "5",
            "--synthesize",
            "--synthesis-model",
            "gpt-5.4",
        ])
        .expect("cli parses");

        match cli.command {
            Command::Schedule(schedule) => {
                assert_eq!(schedule.limit, 5);
                assert!(schedule.synthesize);
                assert_eq!(schedule.synthesis_model.as_deref(), Some("gpt-5.4"));
            }
            _ => panic!("expected schedule command"),
        }
    }

    #[test]
    fn cli_parses_refresh_plan_command() {
        let cli = Cli::try_parse_from([
            "dotrepo-crawler",
            "refresh-plan",
            "--state-path",
            "index/.crawler-state.toml",
            "--limit",
            "8",
            "--synthesize",
            "--synthesis-model",
            "gpt-5.4",
            "--json",
        ])
        .expect("cli parses");

        match cli.command {
            Command::RefreshPlan(plan) => {
                assert_eq!(plan.state_path, Path::new("index/.crawler-state.toml"));
                assert_eq!(plan.limit, Some(8));
                assert!(plan.synthesize);
                assert_eq!(plan.synthesis_model.as_deref(), Some("gpt-5.4"));
                assert!(plan.json);
            }
            _ => panic!("expected refresh-plan command"),
        }
    }

    #[test]
    fn refresh_plan_falls_back_to_committed_index_records_when_state_is_empty() {
        let root = temp_dir("refresh-plan-fallback");
        let index_root = root.join("index");
        let repo_root = index_root.join("repos/github.com/example/orbit");
        std::fs::create_dir_all(&repo_root).expect("repo root created");
        std::fs::write(
            repo_root.join("record.toml"),
            r#"schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://github.com/example/orbit"
generated_at = "2026-03-20T05:00:23Z"

[repo]
name = "orbit"
description = "Example repository"

[x.github]
default_branch = "main"
head_sha = "abc123"
"#,
        )
        .expect("record written");
        std::fs::write(
            repo_root.join("synthesis.toml"),
            r#"schema = "dotrepo-synthesis/v0"

[synthesis]
generated_at = "2026-03-20T05:10:00Z"
source_commit = "abc123"
model = "gpt-5.4"
provider = "openai"
mode = "generated"

[synthesis.architecture]
summary = "Example architecture"

[synthesis.for_agents]
how_to_build = "cargo build"
how_to_test = "cargo test"
how_to_contribute = "Open a PR"
"#,
        )
        .expect("synthesis written");

        let state_path = index_root.join(".crawler-state.toml");
        let (state, source) = load_refresh_state_for_plan(&state_path).expect("state loads");

        assert_eq!(source, RefreshPlanStateSource::IndexRecords);
        assert_eq!(state.repositories.len(), 1);
        let record = &state.repositories[0];
        assert_eq!(
            record.repository,
            RepositoryRef {
                host: "github.com".into(),
                owner: "example".into(),
                repo: "orbit".into(),
            }
        );
        assert_eq!(record.default_branch.as_deref(), Some("main"));
        assert_eq!(record.head_sha.as_deref(), Some("abc123"));
        assert_eq!(
            record.last_factual_crawl_at.as_deref(),
            Some("2026-03-20T05:00:23Z")
        );
        assert_eq!(
            record.last_synthesis_success_at.as_deref(),
            Some("2026-03-20T05:10:00Z")
        );
        assert_eq!(record.synthesis_model.as_deref(), Some("gpt-5.4"));

        std::fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn build_seed_review_assessment_flags_inferred_execution_and_missing_security() {
        let repository = RepositoryRef {
            host: "github.com".into(),
            owner: "example".into(),
            repo: "orbit".into(),
        };
        let manifest = Manifest::new(
            Record {
                mode: RecordMode::Overlay,
                status: RecordStatus::Imported,
                source: Some("https://github.com/example/orbit".into()),
                generated_at: Some("2026-03-21T00:00:00Z".into()),
                trust: None,
            },
            Repo {
                name: "orbit".into(),
                description: "Example repo".into(),
                homepage: None,
                license: None,
                status: None,
                visibility: Some("public".into()),
                languages: vec!["rust".into()],
                build: Some("cargo build --workspace".into()),
                test: Some("cargo test --workspace".into()),
                topics: Vec::new(),
            },
        );

        let assessment = build_seed_review_assessment(SeedReviewAssessmentInput {
            repository,
            status: SeedResultStatus::Planned,
            manifest: Some(&manifest),
            inferred_fields: &["repo.build".into(), "repo.test".into()],
            diagnostics: &[CrawlDiagnostic {
                severity: dotrepo_crawler::CrawlDiagnosticSeverity::Warning,
                code: "materialize.missing_security".into(),
                message: "SECURITY.md missing".into(),
            }],
            manifest_path: PathBuf::from("index/repos/github.com/example/orbit/record.toml"),
            evidence_path: Some(PathBuf::from(
                "index/repos/github.com/example/orbit/evidence.md",
            )),
            failure_message: None,
        });

        assert_eq!(assessment.priority, SeedReviewPriority::High);
        assert!(assessment
            .reasons
            .iter()
            .any(|reason| reason.contains("execution fields are inferred")));
        assert!(assessment
            .reasons
            .iter()
            .any(|reason| reason.contains("crawler emitted warning diagnostics")));
        assert_eq!(
            assessment.warning_codes,
            vec!["materialize.missing_security".to_string()]
        );
    }

    #[test]
    fn build_seed_review_assessment_allows_honest_absence_without_high_priority() {
        let repository = RepositoryRef {
            host: "github.com".into(),
            owner: "example".into(),
            repo: "orbit".into(),
        };
        let mut manifest = Manifest::new(
            Record {
                mode: RecordMode::Overlay,
                status: RecordStatus::Imported,
                source: Some("https://github.com/example/orbit".into()),
                generated_at: Some("2026-03-21T00:00:00Z".into()),
                trust: None,
            },
            Repo {
                name: "orbit".into(),
                description: "Example repo".into(),
                homepage: None,
                license: None,
                status: None,
                visibility: Some("public".into()),
                languages: vec!["rust".into()],
                build: None,
                test: None,
                topics: Vec::new(),
            },
        );
        manifest.owners = Some(Owners {
            maintainers: vec!["example-maintainer".into()],
            team: None,
            security_contact: Some("unknown".into()),
        });

        let assessment = build_seed_review_assessment(SeedReviewAssessmentInput {
            repository,
            status: SeedResultStatus::Planned,
            manifest: Some(&manifest),
            inferred_fields: &[],
            diagnostics: &[],
            manifest_path: PathBuf::from("index/repos/github.com/example/orbit/record.toml"),
            evidence_path: Some(PathBuf::from(
                "index/repos/github.com/example/orbit/evidence.md",
            )),
            failure_message: None,
        });

        assert_eq!(assessment.priority, SeedReviewPriority::Low);
        assert_eq!(
            assessment.reasons,
            vec!["ready for light review: execution, security, and ownership signals are present"]
        );
        assert_eq!(assessment.security_contact.as_deref(), Some("unknown"));
        assert_eq!(assessment.build, None);
        assert_eq!(assessment.test, None);
    }

    #[test]
    fn build_seed_review_report_summarizes_priority_buckets() {
        let report = build_seed_review_report(&[
            SeedCommandResult {
                repository: RepositoryRef {
                    host: "github.com".into(),
                    owner: "example".into(),
                    repo: "high".into(),
                },
                status: SeedResultStatus::Planned,
                manifest_path: None,
                evidence_path: None,
                message: None,
                diagnostics: Vec::new(),
                review: Some(SeedReviewAssessment {
                    repository: RepositoryRef {
                        host: "github.com".into(),
                        owner: "example".into(),
                        repo: "high".into(),
                    },
                    status: SeedResultStatus::Planned,
                    priority: SeedReviewPriority::High,
                    reasons: vec!["security_contact is missing or still unknown".into()],
                    manifest_path: None,
                    evidence_path: None,
                    record_status: Some("imported".into()),
                    build: Some("cargo build".into()),
                    test: Some("cargo test".into()),
                    security_contact: None,
                    inferred_fields: vec!["repo.build".into()],
                    warning_codes: vec!["materialize.missing_security".into()],
                }),
            },
            SeedCommandResult {
                repository: RepositoryRef {
                    host: "github.com".into(),
                    owner: "example".into(),
                    repo: "low".into(),
                },
                status: SeedResultStatus::Planned,
                manifest_path: None,
                evidence_path: None,
                message: None,
                diagnostics: Vec::new(),
                review: Some(SeedReviewAssessment {
                    repository: RepositoryRef {
                        host: "github.com".into(),
                        owner: "example".into(),
                        repo: "low".into(),
                    },
                    status: SeedResultStatus::Planned,
                    priority: SeedReviewPriority::Low,
                    reasons: vec!["ready for light review".into()],
                    manifest_path: None,
                    evidence_path: None,
                    record_status: Some("imported".into()),
                    build: Some("cargo build".into()),
                    test: Some("cargo test".into()),
                    security_contact: Some("security@example.com".into()),
                    inferred_fields: Vec::new(),
                    warning_codes: Vec::new(),
                }),
            },
        ]);

        assert_eq!(report.summary.actionable, 2);
        assert_eq!(report.summary.high, 1);
        assert_eq!(report.summary.low, 1);
        assert_eq!(report.summary.missing_security_contact, 1);
        assert_eq!(report.summary.inferred_execution_fields, 1);
        assert_eq!(report.summary.warnings, 1);
    }

    #[test]
    fn build_seed_review_report_excludes_failed_crawls_from_missing_metadata_counts() {
        let report = build_seed_review_report(&[SeedCommandResult {
            repository: RepositoryRef {
                host: "github.com".into(),
                owner: "example".into(),
                repo: "failed".into(),
            },
            status: SeedResultStatus::Failed,
            manifest_path: None,
            evidence_path: None,
            message: Some("network timeout".into()),
            diagnostics: Vec::new(),
            review: Some(SeedReviewAssessment {
                repository: RepositoryRef {
                    host: "github.com".into(),
                    owner: "example".into(),
                    repo: "failed".into(),
                },
                status: SeedResultStatus::Failed,
                priority: SeedReviewPriority::High,
                reasons: vec!["crawl failed before writeback: network timeout".into()],
                manifest_path: None,
                evidence_path: None,
                record_status: None,
                build: None,
                test: None,
                security_contact: None,
                inferred_fields: Vec::new(),
                warning_codes: Vec::new(),
            }),
        }]);

        assert_eq!(report.summary.actionable, 1);
        assert_eq!(report.summary.failed, 1);
        assert_eq!(report.summary.high, 1);
        assert_eq!(report.summary.missing_security_contact, 0);
        assert_eq!(report.summary.missing_execution_fields, 0);
    }

    fn temp_dir(label: &str) -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock works")
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "dotrepo-crawler-{}-{}-{}",
            label,
            std::process::id(),
            nanos
        ));
        std::fs::create_dir_all(&path).expect("temp dir created");
        path
    }
}
