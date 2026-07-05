//! CLI-facing report/output types and rendering.
//!
//! This module holds the serializable report shapes returned by each
//! subcommand along with the logic that renders them (JSON serialization
//! glue, human-readable labels, and the seed review markdown report). It is
//! intentionally free of business-logic orchestration: `commands.rs` builds
//! these reports and calls into this module purely to shape output.

use dotrepo_core::ImportEscalationReport;
use dotrepo_crawler::{
    CrawlDiagnostic, NetworkUsage, RefreshCandidate, RefreshReason, RepositoryRef,
    ScheduleRefreshReport,
};
use dotrepo_schema::{Manifest, RecordStatus};
use serde::Serialize;
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct CrawlCommandReport {
    pub(crate) repository: RepositoryRef,
    pub(crate) wrote: bool,
    pub(crate) manifest_path: PathBuf,
    pub(crate) evidence_path: Option<PathBuf>,
    pub(crate) synthesis_path: Option<PathBuf>,
    pub(crate) synthesis_failure: Option<dotrepo_crawler::SynthesisFailureMetadata>,
    pub(crate) record_status: RecordStatus,
    pub(crate) state_path: Option<PathBuf>,
    pub(crate) escalation: ImportEscalationReport,
    pub(crate) diagnostics: Vec<CrawlDiagnostic>,
    /// Wall-clock duration of the `crawl_repository` step alone (fetch,
    /// import, verify, escalate, synthesize) in milliseconds. Excludes
    /// writeback/state I/O; see `total_wall_time_ms` for that.
    pub(crate) wall_time_ms: u64,
    /// Wall-clock duration of the entire `crawl` command invocation,
    /// including writeback and crawler-state read/write, in milliseconds.
    pub(crate) total_wall_time_ms: u64,
    /// GitHub HTTP request/byte usage for this crawl.
    pub(crate) network: NetworkUsage,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub(crate) enum SeedResultStatus {
    Applied,
    Planned,
    SkippedExisting,
    Failed,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct SeedCommandResult {
    pub(crate) repository: RepositoryRef,
    pub(crate) status: SeedResultStatus,
    pub(crate) manifest_path: Option<PathBuf>,
    pub(crate) evidence_path: Option<PathBuf>,
    pub(crate) message: Option<String>,
    pub(crate) diagnostics: Vec<CrawlDiagnostic>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) review: Option<SeedReviewAssessment>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct SeedCommandReport {
    pub(crate) discovery: dotrepo_crawler::SeedRepositoriesReport,
    pub(crate) dry_run: bool,
    pub(crate) state_path: Option<PathBuf>,
    pub(crate) results: Vec<SeedCommandResult>,
    pub(crate) review: SeedReviewReport,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) review_report_path: Option<PathBuf>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub(crate) enum SeedReviewPriority {
    High,
    Medium,
    Low,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct SeedReviewAssessment {
    pub(crate) repository: RepositoryRef,
    pub(crate) status: SeedResultStatus,
    pub(crate) priority: SeedReviewPriority,
    pub(crate) reasons: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) manifest_path: Option<PathBuf>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) evidence_path: Option<PathBuf>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) record_status: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) build: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) test: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) security_contact: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub(crate) inferred_fields: Vec<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub(crate) warning_codes: Vec<String>,
}

#[derive(Debug, Clone, Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct SeedReviewSummary {
    pub(crate) actionable: usize,
    pub(crate) high: usize,
    pub(crate) medium: usize,
    pub(crate) low: usize,
    pub(crate) failed: usize,
    pub(crate) missing_security_contact: usize,
    pub(crate) inferred_execution_fields: usize,
    pub(crate) missing_execution_fields: usize,
    pub(crate) missing_owner_signal: usize,
    pub(crate) warnings: usize,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct SeedReviewReport {
    pub(crate) summary: SeedReviewSummary,
    pub(crate) items: Vec<SeedReviewAssessment>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct RefreshPlanCommandReport {
    pub(crate) state_path: PathBuf,
    pub(crate) state_source: RefreshPlanStateSource,
    pub(crate) tracked_repositories: usize,
    pub(crate) candidate_count: usize,
    pub(crate) candidates: Vec<RefreshCandidate>,
    pub(crate) schedule: ScheduleRefreshReport,
    /// Wall-clock duration of the whole `refresh-plan` command invocation
    /// (state load, per-candidate head fetches, and scheduling) in
    /// milliseconds.
    pub(crate) total_wall_time_ms: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub(crate) enum RefreshPlanStateSource {
    CrawlerState,
    IndexRecords,
}

pub(crate) fn refresh_reason_label(reason: RefreshReason) -> &'static str {
    match reason {
        RefreshReason::MissingFactualCrawl => "missing factual crawl",
        RefreshReason::HeadChanged => "head changed",
        RefreshReason::MissingSynthesis => "missing synthesis",
        RefreshReason::PreviousSynthesisFailed => "previous synthesis failed",
        RefreshReason::SynthesisModelChanged => "synthesis model changed",
    }
}

pub(crate) fn refresh_plan_state_source_label(source: RefreshPlanStateSource) -> &'static str {
    match source {
        RefreshPlanStateSource::CrawlerState => "crawler state",
        RefreshPlanStateSource::IndexRecords => "committed index records",
    }
}

pub(crate) fn print_json<T: Serialize>(value: &T) -> anyhow::Result<()> {
    println!("{}", serde_json::to_string_pretty(value)?);
    Ok(())
}

pub(crate) fn build_seed_review_report(results: &[SeedCommandResult]) -> SeedReviewReport {
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

pub(crate) struct SeedReviewAssessmentInput<'a> {
    pub(crate) repository: RepositoryRef,
    pub(crate) status: SeedResultStatus,
    pub(crate) manifest: Option<&'a Manifest>,
    pub(crate) inferred_fields: &'a [String],
    pub(crate) diagnostics: &'a [CrawlDiagnostic],
    pub(crate) manifest_path: PathBuf,
    pub(crate) evidence_path: Option<PathBuf>,
    pub(crate) failure_message: Option<String>,
}

pub(crate) fn build_seed_review_assessment(
    input: SeedReviewAssessmentInput<'_>,
) -> SeedReviewAssessment {
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

pub(crate) fn render_seed_review_report_markdown(
    report: &SeedReviewReport,
    dry_run: bool,
) -> String {
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
    use dotrepo_schema::{Owners, Record, RecordMode, Repo};
    use std::path::PathBuf;

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
                build_candidates: Vec::new(),
                test_candidates: Vec::new(),
                toolchain: None,
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
                build_candidates: Vec::new(),
                test_candidates: Vec::new(),
                toolchain: None,
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
}
