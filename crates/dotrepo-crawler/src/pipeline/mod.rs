//! Factual crawl planning: materialize → import → escalate → promote → optional synthesis.
//!
//! Split for maintainability:
//! - [`merge`] — GitHub snapshot field merge and homepage identity guards
//! - [`writeback_gate`] — verified auto-promotion and downgrade preservation
//! - [`synthesis`] — optional bounded synthesis after factual planning

mod merge;
mod synthesis;
mod writeback_gate;

use crate::adjudication::{
    import_escalation_options_from_env, resolve_adjudication_providers_from_env,
};
use crate::github::{GitHubClient, HttpGitHubClient};
use crate::materialize::{
    materialize_repository, MaterializeRepositoryInput, MaterializedRepository,
};
use crate::{
    CrawlDiagnostic, CrawlRepositoryReport, CrawlRepositoryRequest, CrawlStateRecord,
    CrawlWritebackPlan, FactualWritebackPlan, GitHubRepositorySnapshot, RepositoryRef,
};
use anyhow::{anyhow, bail, Result};
use dotrepo_core::{
    current_timestamp_rfc3339, import_repository_with_options, run_import_escalation,
    score_import_fields, validate_manifest, verify_import_plan, AdjudicationProvider,
    GitHubSnapshotFacts, ImportMode, ImportOptions, TieredAdjudicationProviders,
};
use dotrepo_schema::{render_manifest, Manifest};
use std::fs;
use std::path::Path;

use merge::{
    append_github_evidence, manifest_is_missing_description, merge_snapshot_fields,
    trimmed_non_empty,
};
use synthesis::{maybe_attempt_synthesis, synthesis_sources_from_materialized};
use writeback_gate::apply_promotion_and_downgrade_guard;

pub(crate) fn crawl_repository_impl(
    request: &CrawlRepositoryRequest,
) -> Result<CrawlRepositoryReport> {
    let client = HttpGitHubClient::new()?;
    crawl_repository_with_client(request, &client)
}

pub(crate) fn crawl_repository_with_client<C: GitHubClient>(
    request: &CrawlRepositoryRequest,
    client: &C,
) -> Result<CrawlRepositoryReport> {
    validate_repository_identity(&request.repository)?;

    let snapshot = client.fetch_repository_snapshot(&request.repository)?;
    let files = client.fetch_repository_files(
        &request.repository,
        &snapshot.default_branch,
        &snapshot.languages,
    )?;
    let materialized = materialize_repository(&MaterializeRepositoryInput {
        repository: request.repository.clone(),
        files,
    })?;

    let report = crawl_repository_from_snapshot(request, &snapshot, &materialized);
    let cleanup_error = fs::remove_dir_all(&materialized.temp_root).err();

    match (report, cleanup_error) {
        (Ok(mut report), None) => {
            report.network = client.network_usage();
            report.diagnostics.push(CrawlDiagnostic::info(
                "pipeline.temp_cleanup",
                "removed temporary materialized repository root after crawl planning",
            ));
            Ok(report)
        }
        (Ok(mut report), Some(err)) => {
            report.network = client.network_usage();
            report.diagnostics.push(CrawlDiagnostic::warning(
                "pipeline.temp_cleanup_failed",
                format!(
                    "failed to remove temporary materialized repository root {}: {}",
                    materialized.temp_root.display(),
                    err
                ),
            ));
            Ok(report)
        }
        (Err(err), None) => Err(err),
        (Err(err), Some(_)) => Err(err),
    }
}

pub(crate) fn crawl_repository_from_snapshot(
    request: &CrawlRepositoryRequest,
    snapshot: &GitHubRepositorySnapshot,
    materialized: &MaterializedRepository,
) -> Result<CrawlRepositoryReport> {
    validate_repository_identity(&request.repository)?;

    let generated_at = request
        .generated_at
        .clone()
        .map(Ok)
        .unwrap_or_else(current_timestamp_rfc3339)?;
    let source_url = resolve_source_url(request, snapshot);
    let record_root = request.repository.record_root(&request.index_root);
    let previous_manifest = read_previous_manifest(&record_root);
    let mut diagnostics = materialized.diagnostics.clone();
    if !materialized.written_files.is_empty() {
        diagnostics.push(CrawlDiagnostic::info(
            "pipeline.materialized_sources",
            format!(
                "materialized {} repository files into a temporary repository root",
                materialized.written_files.len()
            ),
        ));
    }

    let mut import_plan = import_repository_with_options(
        &materialized.repository_root,
        ImportMode::Overlay,
        Some(&source_url),
        &ImportOptions {
            generated_at: Some(generated_at.clone()),
            github: Some(GitHubSnapshotFacts {
                fork: snapshot.fork,
                parent: snapshot.parent.clone(),
                repo_name: Some(request.repository.repo.clone()),
                description: snapshot.description.clone(),
                topics: snapshot.topics.clone(),
            }),
        },
    )?;

    let verification = verify_import_plan(&materialized.repository_root, &import_plan, &source_url);
    import_plan.manifest_path = record_root.join("record.toml");
    import_plan.evidence_path = Some(record_root.join("evidence.md"));

    diagnostics.extend(merge_snapshot_fields(
        &request.repository,
        &source_url,
        &mut import_plan.manifest,
        snapshot,
    ));

    if manifest_is_missing_description(&import_plan.manifest) {
        return Err(anyhow!(
            "repo.description is required for crawler overlays; the README surface and GitHub metadata both left it empty"
        ));
    }

    let mut field_scores = score_import_fields(&import_plan, &verification);
    let escalation_options = import_escalation_options_from_env();
    let resolved_providers = resolve_adjudication_providers_from_env()?;
    let local_primary = resolved_providers
        .local_primary
        .as_ref()
        .map(|provider| provider as &dyn AdjudicationProvider);
    let local_second_opinion = resolved_providers
        .local_second_opinion
        .as_ref()
        .map(|provider| provider as &dyn AdjudicationProvider);
    let api_escalation = resolved_providers
        .api_escalation
        .as_ref()
        .map(|provider| provider as &dyn AdjudicationProvider);
    let escalation = run_import_escalation(
        &materialized.repository_root,
        &mut import_plan,
        &verification,
        &mut field_scores,
        &escalation_options,
        TieredAdjudicationProviders {
            local_primary,
            local_second_opinion,
            api_escalation,
        },
    );
    if escalation.deterministic_requests > 0
        || escalation.security_owners_deepened > 0
        || escalation.model_calls > 0
    {
        diagnostics.push(CrawlDiagnostic::info(
            "pipeline.escalation",
            format!(
                "escalation deepened {} owner/security fields, resolved {}/{} deterministic requests, made {} model calls using {} tokens; {} unresolved fields remain",
                escalation.security_owners_deepened,
                escalation.deterministic_resolved,
                escalation.deterministic_requests,
                escalation.model_calls,
                escalation.tokens_used,
                escalation.remaining_unresolved
            ),
        ));
    }

    let verification = verify_import_plan(&materialized.repository_root, &import_plan, &source_url);
    field_scores = score_import_fields(&import_plan, &verification);

    validate_manifest(&record_root, &import_plan.manifest)?;
    import_plan.manifest_text = render_manifest(&import_plan.manifest)?;
    import_plan.evidence_text =
        append_github_evidence(import_plan.evidence_text, &import_plan.manifest, snapshot);

    apply_promotion_and_downgrade_guard(
        &mut import_plan,
        &field_scores,
        previous_manifest.as_ref(),
        &mut diagnostics,
    )?;

    let synthesis_sources = synthesis_sources_from_materialized(materialized);
    let (synthesis, synthesis_failure, synthesis_diagnostics) = maybe_attempt_synthesis(
        request,
        &record_root,
        &import_plan.manifest,
        synthesis_sources,
        snapshot.head_sha.as_deref(),
        &generated_at,
    );
    diagnostics.extend(synthesis_diagnostics);

    let preserved_synthesis_failure = if request.synthesize {
        synthesis_failure.clone()
    } else {
        request.prior_synthesis_failure.clone()
    };

    let state_record = CrawlStateRecord {
        repository: request.repository.clone(),
        default_branch: Some(snapshot.default_branch.clone()),
        head_sha: snapshot.head_sha.clone(),
        last_factual_crawl_at: Some(generated_at.clone()),
        last_synthesis_success_at: synthesis.as_ref().map(|_| generated_at.clone()),
        last_synthesis_failure: preserved_synthesis_failure,
        synthesis_model: request.synthesis_model.clone(),
    };

    Ok(CrawlRepositoryReport {
        repository: request.repository.clone(),
        writeback_plan: CrawlWritebackPlan {
            repository: request.repository.clone(),
            record_root,
            github: snapshot.clone(),
            factual: FactualWritebackPlan {
                manifest_path: import_plan.manifest_path.clone(),
                evidence_path: import_plan.evidence_path.clone(),
                import_plan,
            },
            synthesis,
            synthesis_failure,
        },
        state_record,
        verification,
        field_scores,
        escalation,
        diagnostics,
        // Filled in by the caller (`crawl_repository_impl`/
        // `crawl_repository_with_client`) once the client has finished
        // making requests; this snapshot function only builds the plan.
        network: crate::NetworkUsage::default(),
    })
}
fn validate_repository_identity(repository: &RepositoryRef) -> Result<()> {
    dotrepo_core::validate_repository_identity_segments(
        &repository.host,
        &repository.owner,
        &repository.repo,
    )?;
    if repository.host.trim() != "github.com" {
        bail!("crawl_repository currently supports github.com identities only");
    }
    Ok(())
}

/// Best-effort read of the on-disk `record.toml` at `record_root`, if any, so
/// a fresh crawl can be checked against it for unjustified downgrades. A
/// missing or unparseable prior record simply means there is nothing to
/// protect; this never fails the crawl.
fn read_previous_manifest(record_root: &Path) -> Option<Manifest> {
    let contents = fs::read_to_string(record_root.join("record.toml")).ok()?;
    dotrepo_schema::parse_manifest(&contents).ok()
}

fn resolve_source_url(
    request: &CrawlRepositoryRequest,
    snapshot: &GitHubRepositorySnapshot,
) -> String {
    trimmed_non_empty(request.source_url.as_deref())
        .or_else(|| trimmed_non_empty(Some(&snapshot.html_url)))
        .map(str::to_string)
        .unwrap_or_else(|| request.repository.source_url())
}

#[cfg(test)]
mod tests {
    use super::merge::homepage_conflicts_with_identity;
    use super::*;
    use crate::materialize::{
        materialize_repository, ConventionalRepositoryFiles, MaterializeRepositoryInput,
        RepositoryTextFile,
    };
    use crate::writeback::apply_writeback_plan;
    use crate::{SynthesisFailureClass, SynthesisFailureMetadata};
    use dotrepo_core::validate_index_root;
    use dotrepo_schema::{parse_manifest, RecordStatus};
    use std::fs;
    use std::path::PathBuf;

    fn temp_dir(label: &str) -> PathBuf {
        let unique = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("clock works")
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "dotrepo-crawler-pipeline-{}-{}-{}",
            label,
            std::process::id(),
            unique
        ));
        fs::create_dir_all(&path).expect("temp dir created");
        path
    }

    fn repository() -> RepositoryRef {
        RepositoryRef {
            host: "github.com".into(),
            owner: "example".into(),
            repo: "orbit".into(),
        }
    }

    fn snapshot(description: Option<&str>) -> GitHubRepositorySnapshot {
        GitHubRepositorySnapshot {
            html_url: "https://github.com/example/orbit".into(),
            clone_url: "https://github.com/example/orbit.git".into(),
            default_branch: "main".into(),
            head_sha: Some("57c190d5".into()),
            description: description.map(|value| value.into()),
            homepage: Some("https://orbit.example.dev".into()),
            license: Some("MIT".into()),
            languages: vec!["Rust".into(), "Shell".into()],
            topics: vec!["cli".into(), "index".into()],
            visibility: Some("public".into()),
            stars: Some(42),
            archived: false,
            fork: false,
            parent: None,
        }
    }

    struct FakeGitHubClient {
        snapshot: GitHubRepositorySnapshot,
        files: ConventionalRepositoryFiles,
    }

    impl GitHubClient for FakeGitHubClient {
        fn fetch_repository_head(
            &self,
            _repository: &RepositoryRef,
            _default_branch: Option<&str>,
        ) -> Result<crate::github::RepositoryHeadSnapshot> {
            Ok(crate::github::RepositoryHeadSnapshot {
                default_branch: self.snapshot.default_branch.clone(),
                head_sha: self.snapshot.head_sha.clone(),
            })
        }

        fn fetch_repository_snapshot(
            &self,
            _repository: &RepositoryRef,
        ) -> Result<GitHubRepositorySnapshot> {
            Ok(self.snapshot.clone())
        }

        fn fetch_repository_files(
            &self,
            _repository: &RepositoryRef,
            _default_branch: &str,
            _languages: &[String],
        ) -> Result<ConventionalRepositoryFiles> {
            Ok(self.files.clone())
        }
    }

    #[test]
    fn crawl_repository_from_snapshot_builds_factual_writeback_plan() {
        let index_root = temp_dir("factual-index");
        let materialized = materialize_repository(&MaterializeRepositoryInput {
            repository: repository(),
            files: ConventionalRepositoryFiles {
                readme: Some(RepositoryTextFile {
                    relative_path: PathBuf::from("README.md"),
                    contents:
                        "# Orbit\n\nREADME description is longer than the repository summary.\n"
                            .into(),
                }),
                ..Default::default()
            },
        })
        .expect("materialization succeeds");
        let request = CrawlRepositoryRequest {
            index_root: index_root.clone(),
            repository: repository(),
            generated_at: Some("2026-03-17T12:00:00Z".into()),
            source_url: None,
            synthesize: false,
            synthesis_model: None,
            synthesis_provider: None,
            prior_synthesis_failure: None,
        };

        let report = crawl_repository_from_snapshot(
            &request,
            &snapshot(Some("GitHub description wins for crawler overlays.")),
            &materialized,
        )
        .expect("crawl succeeds");

        assert_eq!(
            report
                .writeback_plan
                .factual
                .import_plan
                .manifest
                .repo
                .description,
            "GitHub description wins for crawler overlays."
        );
        assert_eq!(
            report
                .writeback_plan
                .factual
                .import_plan
                .manifest
                .repo
                .homepage
                .as_deref(),
            Some("https://orbit.example.dev")
        );
        assert_eq!(
            report
                .writeback_plan
                .factual
                .import_plan
                .manifest
                .repo
                .license
                .as_deref(),
            Some("MIT")
        );
        assert_eq!(
            report
                .writeback_plan
                .factual
                .import_plan
                .manifest
                .record
                .generated_at
                .as_deref(),
            Some("2026-03-17T12:00:00Z")
        );
        assert!(report
            .writeback_plan
            .factual
            .import_plan
            .evidence_text
            .as_deref()
            .is_some_and(|text| text.contains("GitHub repository metadata")));
        assert!(report
            .writeback_plan
            .factual
            .import_plan
            .manifest
            .x
            .contains_key("github"));

        let written = apply_writeback_plan(&report.writeback_plan).expect("writeback succeeds");
        let record_text = fs::read_to_string(&written.manifest_path).expect("record read");
        let manifest = parse_manifest(&record_text).expect("record parses");
        assert_eq!(manifest.repo.languages, vec!["Rust", "Shell"]);
        assert_eq!(manifest.repo.topics, vec!["cli", "index"]);
        assert!(validate_index_root(&index_root)
            .expect("index validates")
            .iter()
            .all(|finding| !finding.path.ends_with("record.toml")));

        fs::remove_dir_all(materialized.temp_root).expect("materialized temp removed");
        fs::remove_dir_all(index_root).expect("index temp removed");
    }

    #[test]
    fn crawl_prefers_github_description_over_suspect_readme_description() {
        let index_root = temp_dir("github-description-constraint");
        let materialized = materialize_repository(&MaterializeRepositoryInput {
            repository: repository(),
            files: ConventionalRepositoryFiles {
                readme: Some(RepositoryTextFile {
                    relative_path: PathBuf::from("README.md"),
                    contents: "# fd\n\n[中文] [한국어]\n\nA better description appears later.\n"
                        .into(),
                }),
                ..Default::default()
            },
        })
        .expect("materialization succeeds");
        let request = CrawlRepositoryRequest {
            index_root: index_root.clone(),
            repository: repository(),
            generated_at: Some("2026-03-17T12:00:00Z".into()),
            source_url: None,
            synthesize: false,
            synthesis_model: None,
            synthesis_provider: None,
            prior_synthesis_failure: None,
        };
        let github = snapshot(Some(
            "A simple, fast and user-friendly alternative to find.",
        ));

        let report = crawl_repository_from_snapshot(&request, &github, &materialized)
            .expect("crawl succeeds");
        let import_plan = &report.writeback_plan.factual.import_plan;
        assert_eq!(
            import_plan.manifest.repo.description,
            "A simple, fast and user-friendly alternative to find."
        );
        assert!(import_plan
            .evidence_text
            .as_deref()
            .is_some_and(|text| text
                .contains("Constrained repo.description with GitHub repository metadata.")));
        let trust_notes = import_plan
            .manifest
            .record
            .trust
            .as_ref()
            .and_then(|trust| trust.notes.as_deref())
            .unwrap_or("");
        assert!(trust_notes.contains("Bootstrapped from `README.md`"));

        fs::remove_dir_all(materialized.temp_root).expect("materialized temp removed");
        fs::remove_dir_all(index_root).expect("index temp removed");
    }

    #[test]
    fn crawl_prefers_github_description_over_overlapping_readme_description() {
        let index_root = temp_dir("github-description-overlap");
        let materialized = materialize_repository(&MaterializeRepositoryInput {
            repository: repository(),
            files: ConventionalRepositoryFiles {
                readme: Some(RepositoryTextFile {
                    relative_path: PathBuf::from("README.md"),
                    contents:
                        "# bat\n\nA cat(1) clone with syntax highlighting and Git integration.\n"
                            .into(),
                }),
                ..Default::default()
            },
        })
        .expect("materialization succeeds");
        let request = CrawlRepositoryRequest {
            index_root: index_root.clone(),
            repository: repository(),
            generated_at: Some("2026-03-17T12:00:00Z".into()),
            source_url: None,
            synthesize: false,
            synthesis_model: None,
            synthesis_provider: None,
            prior_synthesis_failure: None,
        };
        let github = snapshot(Some("A cat(1) clone with wings."));

        let report = crawl_repository_from_snapshot(&request, &github, &materialized)
            .expect("crawl succeeds");
        let import_plan = &report.writeback_plan.factual.import_plan;
        assert_eq!(
            import_plan.manifest.repo.description,
            "A cat(1) clone with wings."
        );
        assert!(report.field_scores.scores.iter().any(|score| {
            score.field == "repo.description"
                && score.source.as_deref() == Some("GitHub API")
                && score.reason == "constrained by GitHub repository metadata"
        }));
        assert!(import_plan
            .evidence_text
            .as_deref()
            .is_some_and(|text| text
                .contains("Constrained repo.description with GitHub repository metadata.")));

        fs::remove_dir_all(materialized.temp_root).expect("materialized temp removed");
        fs::remove_dir_all(index_root).expect("index temp removed");
    }

    #[test]
    fn crawl_replaces_suspect_readme_identity_with_github_facts() {
        let index_root = temp_dir("suspect-readme-identity");
        let materialized = materialize_repository(&MaterializeRepositoryInput {
            repository: repository(),
            files: ConventionalRepositoryFiles {
                readme: Some(RepositoryTextFile {
                    relative_path: PathBuf::from("README.md"),
                    contents: "# discussions\n\nDownload the latest release here.\n".into(),
                }),
                ..Default::default()
            },
        })
        .expect("materialization succeeds");
        let request = CrawlRepositoryRequest {
            index_root: index_root.clone(),
            repository: repository(),
            generated_at: Some("2026-03-17T12:00:00Z".into()),
            source_url: None,
            synthesize: false,
            synthesis_model: None,
            synthesis_provider: None,
            prior_synthesis_failure: None,
        };
        let github = snapshot(Some(
            "Automation platform for coordinated multi-service deploys.",
        ));

        let report = crawl_repository_from_snapshot(&request, &github, &materialized)
            .expect("crawl succeeds");
        let manifest = &report.writeback_plan.factual.import_plan.manifest;
        assert_eq!(manifest.repo.name, "orbit");
        assert_eq!(
            manifest.repo.description,
            "Automation platform for coordinated multi-service deploys."
        );
        assert!(report
            .writeback_plan
            .factual
            .import_plan
            .evidence_text
            .as_deref()
            .is_some_and(|text| {
                text.contains("Constrained repo.description with GitHub repository metadata.")
            }));

        fs::remove_dir_all(materialized.temp_root).expect("materialized temp removed");
        fs::remove_dir_all(index_root).expect("index temp removed");
    }

    #[test]
    fn crawl_repository_from_snapshot_preserves_prior_verified_status_without_regression() {
        let index_root = temp_dir("downgrade-guard-preserve");
        let record_root = repository().record_root(&index_root);
        fs::create_dir_all(&record_root).expect("record root created");
        fs::write(
            record_root.join("record.toml"),
            r#"schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "verified"
source = "https://github.com/example/orbit"
generated_at = "2026-01-01T00:00:00Z"

[record.trust]
confidence = "high"
provenance = ["imported", "verified"]
notes = "Auto-promoted to verified: all fields are honestly resolved."

[repo]
name = "orbit"
description = "Prior verified description."
"#,
        )
        .expect("prior record written");

        let materialized = materialize_repository(&MaterializeRepositoryInput {
            repository: repository(),
            files: ConventionalRepositoryFiles {
                readme: Some(RepositoryTextFile {
                    relative_path: PathBuf::from("README.md"),
                    contents: "# Orbit\n\nFresh README description.\n".into(),
                }),
                extra_files: vec![
                    RepositoryTextFile {
                        relative_path: PathBuf::from(".github/workflows/check.yml"),
                        contents: "name: Check\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build --workspace\n".into(),
                    },
                    RepositoryTextFile {
                        relative_path: PathBuf::from(".github/workflows/verify.yml"),
                        contents: "name: Verify\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo build\n".into(),
                    },
                ],
                ..Default::default()
            },
        })
        .expect("materialization succeeds");
        let request = CrawlRepositoryRequest {
            index_root: index_root.clone(),
            repository: repository(),
            generated_at: Some("2026-03-17T12:00:00Z".into()),
            source_url: None,
            synthesize: false,
            synthesis_model: None,
            synthesis_provider: None,
            prior_synthesis_failure: None,
        };

        let report = crawl_repository_from_snapshot(
            &request,
            &snapshot(Some("GitHub description should not overwrite README.")),
            &materialized,
        )
        .expect("crawl succeeds");

        // Two conflicting build-command workflows make repo.build Unresolved
        // in the fresh import, which alone would leave the record below
        // verified. The previous record never had repo.build present either
        // (it was absent), so this is not a genuine regression -- the guard
        // must restore verified/high rather than let this routine refresh
        // silently downgrade the record over an unrelated ambiguity.
        let manifest = &report.writeback_plan.factual.import_plan.manifest;
        assert_eq!(manifest.record.status, RecordStatus::Verified);
        assert_eq!(
            manifest
                .record
                .trust
                .as_ref()
                .and_then(|trust| trust.confidence.as_deref()),
            Some("high")
        );
        assert!(report
            .writeback_plan
            .factual
            .import_plan
            .evidence_text
            .as_deref()
            .is_some_and(|text| text.contains("Downgrade guard")));

        fs::remove_dir_all(materialized.temp_root).expect("materialized temp removed");
        fs::remove_dir_all(index_root).expect("index temp removed");
    }

    #[test]
    fn homepage_conflicts_with_identity_detects_cross_repository_urls() {
        let repo = repository();
        assert!(homepage_conflicts_with_identity(
            &repo,
            "https://github.com/someone-else/other-project"
        ));
        assert!(!homepage_conflicts_with_identity(
            &repo,
            "https://github.com/example/orbit"
        ));
        assert!(!homepage_conflicts_with_identity(
            &repo,
            "https://github.com/example/orbit#readme"
        ));
        // Non-code-host URLs are always fine regardless of content.
        assert!(!homepage_conflicts_with_identity(
            &repo,
            "https://orbit.example.dev"
        ));
    }

    #[test]
    fn crawl_repository_from_snapshot_skips_github_homepage_pointing_at_a_different_repository() {
        // Reproduces a real case found while re-crawling the index:
        // GitHub's repository "Website" field is maintainer-set free text
        // and can point at an unrelated repository (e.g. a renamed or
        // duplicated project left pointing at its original). Blindly
        // merging it in previously produced a repo.homepage that failed
        // validate-index's cross-identity check.
        let index_root = temp_dir("homepage-identity-conflict-index");
        let materialized = materialize_repository(&MaterializeRepositoryInput {
            repository: repository(),
            files: ConventionalRepositoryFiles {
                readme: Some(RepositoryTextFile {
                    relative_path: PathBuf::from("README.md"),
                    contents: "# Orbit\n\nA CLI tool.\n".into(),
                }),
                ..Default::default()
            },
        })
        .expect("materialization succeeds");
        let mut conflicting_snapshot = snapshot(Some("A CLI tool."));
        conflicting_snapshot.homepage =
            Some("https://github.com/someone-else/other-project".into());
        let request = CrawlRepositoryRequest {
            index_root: index_root.clone(),
            repository: repository(),
            generated_at: Some("2026-03-17T12:00:00Z".into()),
            source_url: None,
            synthesize: false,
            synthesis_model: None,
            synthesis_provider: None,
            prior_synthesis_failure: None,
        };

        let report = crawl_repository_from_snapshot(&request, &conflicting_snapshot, &materialized)
            .expect("crawl succeeds");

        let homepage = report
            .writeback_plan
            .factual
            .import_plan
            .manifest
            .repo
            .homepage
            .clone();
        assert_ne!(
            homepage.as_deref(),
            Some("https://github.com/someone-else/other-project"),
            "must not adopt a homepage that resolves to a different repository identity"
        );
        assert!(report
            .diagnostics
            .iter()
            .any(|d| d.code == "pipeline.homepage_identity_conflict"));

        fs::remove_dir_all(materialized.temp_root).expect("materialized temp removed");
        fs::remove_dir_all(index_root).expect("index temp removed");
    }

    #[test]
    fn crawl_repository_from_snapshot_rejects_missing_description() {
        let index_root = temp_dir("missing-description-index");
        let materialized = materialize_repository(&MaterializeRepositoryInput {
            repository: repository(),
            files: ConventionalRepositoryFiles {
                readme: Some(RepositoryTextFile {
                    relative_path: PathBuf::from("README.md"),
                    contents: "# Orbit\n".into(),
                }),
                ..Default::default()
            },
        })
        .expect("materialization succeeds");
        let request = CrawlRepositoryRequest {
            index_root: index_root.clone(),
            repository: repository(),
            generated_at: Some("2026-03-17T12:00:00Z".into()),
            source_url: None,
            synthesize: false,
            synthesis_model: None,
            synthesis_provider: None,
            prior_synthesis_failure: None,
        };

        let err = crawl_repository_from_snapshot(&request, &snapshot(None), &materialized)
            .expect_err("missing description should fail cleanly");
        assert!(err
            .to_string()
            .contains("repo.description is required for crawler overlays"));

        fs::remove_dir_all(materialized.temp_root).expect("materialized temp removed");
        fs::remove_dir_all(index_root).expect("index temp removed");
    }

    #[test]
    fn crawl_repository_from_snapshot_keeps_synthesis_non_blocking() {
        let index_root = temp_dir("synthesis-non-blocking-index");
        let materialized = materialize_repository(&MaterializeRepositoryInput {
            repository: repository(),
            files: ConventionalRepositoryFiles {
                readme: Some(RepositoryTextFile {
                    relative_path: PathBuf::from("README.md"),
                    contents: "# Orbit\n\nRepository description.\n".into(),
                }),
                ..Default::default()
            },
        })
        .expect("materialization succeeds");
        let request = CrawlRepositoryRequest {
            index_root: index_root.clone(),
            repository: repository(),
            generated_at: Some("2026-03-17T12:00:00Z".into()),
            source_url: None,
            synthesize: true,
            synthesis_model: Some("gpt-5.4".into()),
            synthesis_provider: Some("openai".into()),
            prior_synthesis_failure: None,
        };

        let report = crawl_repository_from_snapshot(
            &request,
            &snapshot(Some("GitHub description")),
            &materialized,
        )
        .expect("factual crawl succeeds");

        assert!(report.writeback_plan.synthesis.is_none());
        assert_eq!(
            report
                .writeback_plan
                .synthesis_failure
                .as_ref()
                .map(|failure| &failure.class),
            Some(&SynthesisFailureClass::TransportError)
        );
        assert!(report
            .writeback_plan
            .factual
            .import_plan
            .manifest_text
            .contains("generated_at = \"2026-03-17T12:00:00Z\""));

        fs::remove_dir_all(materialized.temp_root).expect("materialized temp removed");
        fs::remove_dir_all(index_root).expect("index temp removed");
    }

    #[test]
    fn crawl_repository_with_client_materializes_and_plans_factual_writeback() {
        let index_root = temp_dir("with-client-index");
        let request = CrawlRepositoryRequest {
            index_root: index_root.clone(),
            repository: repository(),
            generated_at: Some("2026-03-17T12:00:00Z".into()),
            source_url: None,
            synthesize: false,
            synthesis_model: None,
            synthesis_provider: None,
            prior_synthesis_failure: None,
        };
        let client = FakeGitHubClient {
            snapshot: snapshot(Some("GitHub description fallback")),
            files: ConventionalRepositoryFiles {
                readme: Some(RepositoryTextFile {
                    relative_path: PathBuf::from("README.mdx"),
                    contents: "# Orbit\n\nRepository description.\n".into(),
                }),
                ..Default::default()
            },
        };

        let report = crawl_repository_with_client(&request, &client).expect("crawl succeeds");
        assert_eq!(
            report
                .writeback_plan
                .factual
                .import_plan
                .manifest
                .repo
                .visibility
                .as_deref(),
            Some("public")
        );
        assert!(report
            .diagnostics
            .iter()
            .any(|diagnostic| diagnostic.code == "pipeline.materialized_sources"));

        let written = apply_writeback_plan(&report.writeback_plan).expect("writeback succeeds");
        assert!(written.manifest_path.is_file());
        assert!(written
            .evidence_path
            .as_ref()
            .is_some_and(|path| path.is_file()));

        fs::remove_dir_all(index_root).expect("index temp removed");
    }

    #[test]
    fn crawl_repository_with_client_preserves_readme_variant_in_evidence() {
        let index_root = temp_dir("with-client-readme-variant-index");
        let request = CrawlRepositoryRequest {
            index_root: index_root.clone(),
            repository: repository(),
            generated_at: Some("2026-03-19T12:00:00Z".into()),
            source_url: None,
            synthesize: false,
            synthesis_model: None,
            synthesis_provider: None,
            prior_synthesis_failure: None,
        };
        let client = FakeGitHubClient {
            snapshot: snapshot(Some("GitHub description fallback")),
            files: ConventionalRepositoryFiles {
                readme: Some(RepositoryTextFile {
                    relative_path: PathBuf::from("README.mdx"),
                    contents: "# Orbit\n\nRepository description.\n".into(),
                }),
                ..Default::default()
            },
        };

        let report = crawl_repository_with_client(&request, &client).expect("crawl succeeds");
        let evidence = report
            .writeback_plan
            .factual
            .import_plan
            .evidence_text
            .as_deref()
            .expect("evidence present");
        assert!(report
            .writeback_plan
            .factual
            .import_plan
            .imported_sources
            .iter()
            .any(|path| path == "README.mdx"));
        assert!(evidence.contains("Imported repository name from README.mdx."));
        assert!(evidence.contains("Constrained repo.description with GitHub repository metadata."));

        fs::remove_dir_all(index_root).expect("index temp removed");
    }

    #[test]
    fn crawl_from_snapshot_preserves_prior_synthesis_failure_when_not_synthesizing() {
        let index_root = temp_dir("preserve-synthesis-failure");
        let materialized = materialize_repository(&MaterializeRepositoryInput {
            repository: repository(),
            files: ConventionalRepositoryFiles {
                readme: Some(RepositoryTextFile {
                    relative_path: PathBuf::from("README.md"),
                    contents: "# Orbit\n\nRepository description.\n".into(),
                }),
                ..Default::default()
            },
        })
        .expect("materialization succeeds");
        let prior_failure = SynthesisFailureMetadata {
            class: SynthesisFailureClass::RateLimited,
            message: "secondary rate limit".into(),
            occurred_at: Some("2026-03-16T12:00:00Z".into()),
            model: Some("gpt-5.3".into()),
            provider: Some("openai".into()),
        };
        let request = CrawlRepositoryRequest {
            index_root: index_root.clone(),
            repository: repository(),
            generated_at: Some("2026-03-17T12:00:00Z".into()),
            source_url: None,
            synthesize: false,
            synthesis_model: None,
            synthesis_provider: None,
            prior_synthesis_failure: Some(prior_failure.clone()),
        };

        let report = crawl_repository_from_snapshot(
            &request,
            &snapshot(Some("GitHub description")),
            &materialized,
        )
        .expect("crawl succeeds");

        assert_eq!(
            report.state_record.last_synthesis_failure,
            Some(prior_failure),
            "synthesis failure should be preserved when synthesis is not requested"
        );

        fs::remove_dir_all(materialized.temp_root).expect("materialized temp removed");
        fs::remove_dir_all(index_root).expect("index temp removed");
    }
}
