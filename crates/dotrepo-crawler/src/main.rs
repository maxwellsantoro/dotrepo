use anyhow::{bail, Result};
use clap::{Args, Parser, Subcommand};
use dotrepo_crawler::{
    apply_crawl_writeback, crawl_repository, load_crawler_state, schedule_refresh,
    seed_repositories, write_crawler_state, CrawlDiagnostic, CrawlRepositoryRequest,
    CrawlStateRecord, CrawlerStateSnapshot, RefreshCandidate, RepositoryRef,
    ScheduleRefreshRequest, SeedRepositoriesReport, SeedRepositoriesRequest, StarBand,
};
use serde::Serialize;
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
    /// Maximum number of discovery candidates to crawl.
    #[arg(long, default_value_t = 10)]
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
    /// Plan the batch without writing files or crawler state.
    #[arg(long)]
    dry_run: bool,
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

#[derive(Debug, Clone, Serialize)]
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
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct SeedCommandReport {
    discovery: SeedRepositoriesReport,
    dry_run: bool,
    state_path: Option<PathBuf>,
    results: Vec<SeedCommandResult>,
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
    let discovery = seed_repositories(&seed_request_from_args(
        &args.host,
        args.limit,
        args.star_bands,
        args.include_archived,
        args.include_forks,
    ))?;

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
        }) {
            Ok(report) => {
                if args.dry_run {
                    results.push(SeedCommandResult {
                        repository: entry.repository.clone(),
                        status: SeedResultStatus::Planned,
                        manifest_path: Some(report.writeback_plan.factual.manifest_path.clone()),
                        evidence_path: report.writeback_plan.factual.evidence_path.clone(),
                        message: None,
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
                        diagnostics: report.diagnostics,
                    });
                }
            }
            Err(err) => results.push(SeedCommandResult {
                repository: entry.repository.clone(),
                status: SeedResultStatus::Failed,
                manifest_path: Some(manifest_path),
                evidence_path: Some(
                    entry
                        .repository
                        .record_root(&args.index_root)
                        .join("evidence.md"),
                ),
                message: Some(err.to_string()),
                diagnostics: Vec::new(),
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
    let command_report = SeedCommandReport {
        discovery,
        dry_run: args.dry_run,
        state_path,
        results,
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
        if let Some(path) = &command_report.state_path {
            println!("state: {}", path.display());
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

fn resolve_state_path(index_root: &Path, state_path: Option<&Path>) -> PathBuf {
    state_path
        .map(Path::to_path_buf)
        .unwrap_or_else(|| index_root.join(".crawler-state.toml"))
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

#[cfg(test)]
mod tests {
    use super::*;
    use clap::Parser;

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
        ])
        .expect("cli parses");

        match cli.command {
            Command::Seed(seed) => {
                assert_eq!(seed.limit, 25);
                assert!(seed.dry_run);
                assert_eq!(seed.star_bands.len(), 2);
            }
            _ => panic!("expected seed command"),
        }
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
}
