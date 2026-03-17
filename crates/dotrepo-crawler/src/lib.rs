use anyhow::Result;
use dotrepo_core::{ImportPlan, SynthesisWritePlan};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

mod discover;
mod github;
mod materialize;
mod pipeline;
mod schedule;
mod state;
mod synth;
mod writeback;

pub fn seed_repositories(request: &SeedRepositoriesRequest) -> Result<SeedRepositoriesReport> {
    discover::seed_repositories_impl(request)
}

pub fn crawl_repository(request: &CrawlRepositoryRequest) -> Result<CrawlRepositoryReport> {
    pipeline::crawl_repository_impl(request)
}

pub fn synthesize_repository(
    request: &SynthesizeRepositoryRequest,
) -> Result<SynthesizeRepositoryReport> {
    synth::synthesize_repository_impl(request)
}

pub fn schedule_refresh(request: &ScheduleRefreshRequest) -> Result<ScheduleRefreshReport> {
    schedule::schedule_refresh_impl(request)
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RepositoryRef {
    pub host: String,
    pub owner: String,
    pub repo: String,
}

impl RepositoryRef {
    pub fn record_relative_dir(&self) -> PathBuf {
        PathBuf::from("repos")
            .join(&self.host)
            .join(&self.owner)
            .join(&self.repo)
    }

    pub fn record_root(&self, index_root: &Path) -> PathBuf {
        index_root.join(self.record_relative_dir())
    }

    pub fn source_url(&self) -> String {
        format!("https://{}/{}/{}", self.host, self.owner, self.repo)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StarBand {
    pub min_stars: u64,
    pub max_stars: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SeedRepositoriesRequest {
    pub host: String,
    pub limit: usize,
    #[serde(default)]
    pub star_bands: Vec<StarBand>,
    #[serde(default)]
    pub include_archived: bool,
    #[serde(default)]
    pub include_forks: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DiscoveredRepository {
    pub repository: RepositoryRef,
    pub stars: u64,
    pub default_branch: Option<String>,
    pub archived: bool,
    pub fork: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SeedRepositoriesReport {
    pub host: String,
    pub requested_limit: usize,
    pub exhausted_bands: bool,
    #[serde(default)]
    pub discovered: Vec<DiscoveredRepository>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GitHubRepositorySnapshot {
    pub html_url: String,
    pub clone_url: String,
    pub default_branch: String,
    pub head_sha: Option<String>,
    pub description: Option<String>,
    pub homepage: Option<String>,
    pub license: Option<String>,
    #[serde(default)]
    pub languages: Vec<String>,
    #[serde(default)]
    pub topics: Vec<String>,
    pub visibility: Option<String>,
    pub stars: Option<u64>,
    pub archived: bool,
    pub fork: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CrawlDiagnosticSeverity {
    Info,
    Warning,
    Error,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CrawlDiagnostic {
    pub severity: CrawlDiagnosticSeverity,
    pub code: String,
    pub message: String,
}

impl CrawlDiagnostic {
    pub(crate) fn info(code: &str, message: impl Into<String>) -> Self {
        Self {
            severity: CrawlDiagnosticSeverity::Info,
            code: code.into(),
            message: message.into(),
        }
    }

    pub(crate) fn warning(code: &str, message: impl Into<String>) -> Self {
        Self {
            severity: CrawlDiagnosticSeverity::Warning,
            code: code.into(),
            message: message.into(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SynthesisFailureClass {
    TransportError,
    RateLimited,
    InvalidSchemaOutput,
    FieldBoundsViolation,
    FactualConflict,
    UnsafeShellLikeValue,
    EmptyRequiredField,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SynthesisFailureMetadata {
    pub class: SynthesisFailureClass,
    pub message: String,
    pub occurred_at: Option<String>,
    pub model: Option<String>,
    pub provider: Option<String>,
}

#[derive(Debug, Clone)]
pub struct FactualWritebackPlan {
    pub import_plan: ImportPlan,
    pub manifest_path: PathBuf,
    pub evidence_path: Option<PathBuf>,
}

#[derive(Debug, Clone)]
pub struct SynthesisPlan {
    pub write_plan: SynthesisWritePlan,
    pub synthesis_path: PathBuf,
}

#[derive(Debug, Clone)]
pub struct CrawlWritebackPlan {
    pub repository: RepositoryRef,
    pub record_root: PathBuf,
    pub github: GitHubRepositorySnapshot,
    pub factual: FactualWritebackPlan,
    pub synthesis: Option<SynthesisPlan>,
    pub synthesis_failure: Option<SynthesisFailureMetadata>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CrawlStateRecord {
    pub repository: RepositoryRef,
    pub default_branch: Option<String>,
    pub head_sha: Option<String>,
    pub last_factual_crawl_at: Option<String>,
    pub last_synthesis_success_at: Option<String>,
    pub last_synthesis_failure: Option<SynthesisFailureMetadata>,
    pub synthesis_model: Option<String>,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CrawlerStateSnapshot {
    #[serde(default)]
    pub repositories: Vec<CrawlStateRecord>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CrawlRepositoryRequest {
    pub index_root: PathBuf,
    pub repository: RepositoryRef,
    pub generated_at: Option<String>,
    pub source_url: Option<String>,
    pub synthesize: bool,
    pub synthesis_model: Option<String>,
    pub synthesis_provider: Option<String>,
}

#[derive(Debug, Clone)]
pub struct CrawlRepositoryReport {
    pub repository: RepositoryRef,
    pub writeback_plan: CrawlWritebackPlan,
    pub state_record: CrawlStateRecord,
    pub diagnostics: Vec<CrawlDiagnostic>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SynthesizeRepositoryRequest {
    pub record_root: PathBuf,
    pub repository: RepositoryRef,
    pub generated_at: Option<String>,
    pub source_commit: Option<String>,
    pub model: String,
    pub provider: String,
}

#[derive(Debug, Clone)]
pub struct SynthesizeRepositoryReport {
    pub repository: RepositoryRef,
    pub record_root: PathBuf,
    pub synthesis: Option<SynthesisPlan>,
    pub failure: Option<SynthesisFailureMetadata>,
    pub diagnostics: Vec<CrawlDiagnostic>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RefreshCandidate {
    pub repository: RepositoryRef,
    pub default_branch: Option<String>,
    pub head_sha: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RefreshReason {
    MissingFactualCrawl,
    HeadChanged,
    MissingSynthesis,
    PreviousSynthesisFailed,
    SynthesisModelChanged,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ScheduleRefreshRequest {
    pub now: Option<String>,
    pub limit: usize,
    pub synthesize: bool,
    pub synthesis_model: Option<String>,
    pub state: CrawlerStateSnapshot,
    #[serde(default)]
    pub candidates: Vec<RefreshCandidate>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ScheduledRefresh {
    pub repository: RepositoryRef,
    pub default_branch: Option<String>,
    pub head_sha: Option<String>,
    pub reason: RefreshReason,
    pub scheduled_at: Option<String>,
    pub synthesize: bool,
    pub synthesis_model: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SkippedRefresh {
    pub repository: RepositoryRef,
    pub reason: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ScheduleRefreshReport {
    #[serde(default)]
    pub scheduled: Vec<ScheduledRefresh>,
    #[serde(default)]
    pub skipped: Vec<SkippedRefresh>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn repository_ref_builds_record_paths() {
        let repository = RepositoryRef {
            host: "github.com".into(),
            owner: "example".into(),
            repo: "orbit".into(),
        };

        assert_eq!(
            repository.record_relative_dir(),
            PathBuf::from("repos/github.com/example/orbit")
        );
        assert_eq!(
            repository.record_root(Path::new("/tmp/index")),
            PathBuf::from("/tmp/index/repos/github.com/example/orbit")
        );
        assert_eq!(repository.source_url(), "https://github.com/example/orbit");
    }
}
