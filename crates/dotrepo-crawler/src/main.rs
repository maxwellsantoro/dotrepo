use anyhow::Result;
use clap::{Args, Parser, Subcommand};
use dotrepo_crawler::StarBand;
use std::path::PathBuf;

mod commands;
mod report;

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
    /// Request optional bounded synthesis after the factual crawl.
    #[arg(long)]
    synthesize: bool,
    /// Model identifier sent to the configured synthesis sidecar.
    #[arg(long, requires = "synthesize")]
    synthesis_model: Option<String>,
    /// Provider identifier sent to the configured synthesis sidecar.
    #[arg(long, requires = "synthesize")]
    synthesis_provider: Option<String>,
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
    /// Maximum tracked repositories to inspect and schedule.
    /// Oldest factual crawls are inspected first. Defaults to the tracked repo count.
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

fn main() {
    if let Err(err) = run() {
        eprintln!("{err}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::Discover(args) => commands::cmd_discover(args),
        Command::Crawl(args) => commands::cmd_crawl(args),
        Command::Seed(args) => commands::cmd_seed(args),
        Command::Schedule(args) => commands::cmd_schedule(args),
        Command::RefreshPlan(args) => commands::cmd_refresh_plan(args),
    }
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

#[cfg(test)]
mod tests {
    use super::*;
    use clap::Parser;
    use dotrepo_crawler::{parse_repository_targets, RepositoryRef};
    use std::path::Path;

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
    fn cli_parses_crawl_with_bounded_synthesis() {
        let cli = Cli::try_parse_from([
            "dotrepo-crawler",
            "crawl",
            "--owner",
            "example",
            "--repo",
            "orbit",
            "--synthesize",
            "--synthesis-model",
            "research-model",
            "--synthesis-provider",
            "local-sidecar",
        ])
        .expect("cli parses");

        match cli.command {
            Command::Crawl(crawl) => {
                assert!(crawl.synthesize);
                assert_eq!(crawl.synthesis_model.as_deref(), Some("research-model"));
                assert_eq!(crawl.synthesis_provider.as_deref(), Some("local-sidecar"));
            }
            _ => panic!("expected crawl command"),
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
}
