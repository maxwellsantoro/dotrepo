//! CLI command execution bodies.
//!
//! Each `cmd_*` function implements one subcommand's orchestration: calling
//! into the domain modules (`pipeline`, `discover`, `writeback`, `schedule`,
//! `state`, ...), then handing the result to `report.rs` for shaping and
//! printing. `main.rs` only does argument parsing and dispatch to these
//! functions.

use crate::report::{
    build_seed_review_assessment, build_seed_review_report, print_json,
    refresh_plan_state_source_label, refresh_reason_label, CrawlCommandReport,
    RefreshPlanCommandReport, RefreshPlanStateSource, SeedCommandReport, SeedCommandResult,
    SeedResultStatus, SeedReviewAssessmentInput,
};
use crate::{CrawlArgs, DiscoverArgs, RefreshPlanArgs, ScheduleArgs, SeedArgs};
use anyhow::{anyhow, bail, Context, Result};
use dotrepo_core::{
    autonomous_writeback_eligible, load_manifest_from_root, load_synthesis_from_root,
};
use dotrepo_crawler::{
    apply_crawl_writeback, crawl_repository, discovery_report_from_targets, load_crawler_state,
    load_repository_targets, refresh_candidates_from_state, schedule_refresh, seed_repositories,
    write_crawler_state, CrawlRepositoryRequest, CrawlStateRecord, CrawlerStateSnapshot,
    RefreshCandidate, RepositoryRef, ScheduleRefreshRequest, SeedRepositoriesReport,
    SeedRepositoriesRequest, StarBand, MAX_SEED_LIMIT,
};
use dotrepo_schema::Manifest;
use serde::Deserialize;
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

pub(crate) fn cmd_discover(args: DiscoverArgs) -> Result<()> {
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

pub(crate) fn cmd_crawl(args: CrawlArgs) -> Result<()> {
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
        synthesize: args.synthesize,
        synthesis_model: args.synthesis_model,
        synthesis_provider: args.synthesis_provider,
        prior_synthesis_failure: None,
    })?;

    let mut state_path = None;
    let mut wrote = false;
    if args.write {
        if autonomous_writeback_eligible(&report.verification) {
            apply_crawl_writeback(&report.writeback_plan)?;
            let resolved_state_path =
                resolve_state_path(&args.index_root, args.state_path.as_deref());
            let mut state = load_crawler_state(&resolved_state_path)?;
            upsert_state_record(&mut state, report.state_record.clone());
            write_crawler_state(&resolved_state_path, &state)?;
            state_path = Some(resolved_state_path);
            wrote = true;
        } else {
            bail!(
                "autonomous writeback gate failed for {}/{}/{}; verification did not pass",
                repository.host,
                repository.owner,
                repository.repo
            );
        }
    }

    let command_report = CrawlCommandReport {
        repository,
        wrote,
        manifest_path: report.writeback_plan.factual.manifest_path.clone(),
        evidence_path: report.writeback_plan.factual.evidence_path.clone(),
        synthesis_path: report
            .writeback_plan
            .synthesis
            .as_ref()
            .map(|plan| plan.synthesis_path.clone()),
        synthesis_failure: report.writeback_plan.synthesis_failure.clone(),
        record_status: report
            .writeback_plan
            .factual
            .import_plan
            .manifest
            .record
            .status,
        state_path,
        escalation: report.escalation,
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

pub(crate) fn cmd_seed(args: SeedArgs) -> Result<()> {
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
                } else if autonomous_writeback_eligible(&report.verification) {
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
                } else {
                    let message = format!(
                        "autonomous writeback gate failed for {}/{}/{}",
                        entry.repository.host, entry.repository.owner, entry.repository.repo
                    );
                    results.push(SeedCommandResult {
                        repository: entry.repository.clone(),
                        status: SeedResultStatus::Failed,
                        manifest_path: Some(report.writeback_plan.factual.manifest_path.clone()),
                        evidence_path: report.writeback_plan.factual.evidence_path.clone(),
                        message: Some(message.clone()),
                        review: Some(build_seed_review_assessment(SeedReviewAssessmentInput {
                            repository: entry.repository.clone(),
                            status: SeedResultStatus::Failed,
                            manifest: Some(&report.writeback_plan.factual.import_plan.manifest),
                            inferred_fields: &report
                                .writeback_plan
                                .factual
                                .import_plan
                                .inferred_fields,
                            diagnostics: &report.diagnostics,
                            manifest_path: report.writeback_plan.factual.manifest_path.clone(),
                            evidence_path: report.writeback_plan.factual.evidence_path.clone(),
                            failure_message: Some(message),
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
        let markdown = crate::report::render_seed_review_report_markdown(&review, args.dry_run);
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

pub(crate) fn cmd_schedule(args: ScheduleArgs) -> Result<()> {
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

pub(crate) fn cmd_refresh_plan(args: RefreshPlanArgs) -> Result<()> {
    let (state, state_source) = load_refresh_state_for_plan(&args.state_path)?;
    let tracked_repositories = state.repositories.len();
    let effective_limit = args.limit.unwrap_or(tracked_repositories);
    let inspection_state = refresh_inspection_state(&state, effective_limit);
    let candidates = refresh_candidates_from_state(&inspection_state)?;
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

fn refresh_inspection_state(state: &CrawlerStateSnapshot, limit: usize) -> CrawlerStateSnapshot {
    let mut repositories = state.repositories.clone();
    repositories.sort_by(|left, right| {
        (
            left.last_factual_crawl_at.as_deref().unwrap_or(""),
            left.repository.host.as_str(),
            left.repository.owner.as_str(),
            left.repository.repo.as_str(),
        )
            .cmp(&(
                right.last_factual_crawl_at.as_deref().unwrap_or(""),
                right.repository.host.as_str(),
                right.repository.owner.as_str(),
                right.repository.repo.as_str(),
            ))
    });
    repositories.truncate(limit);
    CrawlerStateSnapshot { repositories }
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

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(rename_all = "snake_case")]
struct GitHubRecordExtension {
    default_branch: Option<String>,
    head_sha: Option<String>,
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

#[cfg(test)]
mod tests {
    use super::*;
    use dotrepo_crawler::MAX_SEED_LIMIT;
    use std::time::{SystemTime, UNIX_EPOCH};

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
    fn refresh_inspection_limit_rotates_oldest_factual_crawls_first() {
        let record = |repo: &str, last_factual_crawl_at: Option<&str>| CrawlStateRecord {
            repository: RepositoryRef {
                host: "github.com".into(),
                owner: "example".into(),
                repo: repo.into(),
            },
            default_branch: Some("main".into()),
            head_sha: Some(format!("{repo}-sha")),
            last_factual_crawl_at: last_factual_crawl_at.map(str::to_string),
            last_synthesis_success_at: None,
            last_synthesis_failure: None,
            synthesis_model: None,
        };
        let state = CrawlerStateSnapshot {
            repositories: vec![
                record("newest", Some("2026-03-20T00:00:00Z")),
                record("missing", None),
                record("oldest", Some("2026-03-01T00:00:00Z")),
                record("middle", Some("2026-03-10T00:00:00Z")),
            ],
        };

        let inspected = refresh_inspection_state(&state, 3);

        assert_eq!(
            inspected
                .repositories
                .iter()
                .map(|record| record.repository.repo.as_str())
                .collect::<Vec<_>>(),
            vec!["missing", "oldest", "middle"]
        );
        assert_eq!(state.repositories[0].repository.repo, "newest");
    }

    #[test]
    fn refresh_inspection_limit_allows_empty_plans() {
        let state = CrawlerStateSnapshot {
            repositories: vec![CrawlStateRecord {
                repository: RepositoryRef {
                    host: "github.com".into(),
                    owner: "example".into(),
                    repo: "orbit".into(),
                },
                default_branch: Some("main".into()),
                head_sha: Some("abc123".into()),
                last_factual_crawl_at: None,
                last_synthesis_success_at: None,
                last_synthesis_failure: None,
                synthesis_model: None,
            }],
        };

        assert!(refresh_inspection_state(&state, 0).repositories.is_empty());
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
