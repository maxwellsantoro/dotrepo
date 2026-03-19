use crate::github::{GitHubClient, HttpGitHubClient};
use crate::materialize::{
    materialize_repository, MaterializeRepositoryInput, MaterializedRepository,
};
use crate::synth::synthesize_repository_impl;
use crate::{
    CrawlDiagnostic, CrawlRepositoryReport, CrawlRepositoryRequest, CrawlStateRecord,
    CrawlWritebackPlan, FactualWritebackPlan, GitHubRepositorySnapshot, RepositoryRef,
    SynthesisFailureClass, SynthesisFailureMetadata, SynthesizeRepositoryRequest,
};
use anyhow::{anyhow, bail, Result};
use dotrepo_core::{
    current_timestamp_rfc3339, import_repository_with_options, validate_manifest, ImportMode,
    ImportOptions,
};
use dotrepo_schema::{render_manifest, Manifest};
use std::fs;
use std::path::Path;
use toml::Value;

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
    let files = client.fetch_repository_files(&request.repository, &snapshot.default_branch)?;
    let materialized = materialize_repository(&MaterializeRepositoryInput {
        repository: request.repository.clone(),
        files,
    })?;

    let report = crawl_repository_from_snapshot(request, &snapshot, &materialized);
    let cleanup_error = fs::remove_dir_all(&materialized.temp_root).err();

    match (report, cleanup_error) {
        (Ok(mut report), None) => {
            report.diagnostics.push(CrawlDiagnostic::info(
                "pipeline.temp_cleanup",
                "removed temporary materialized repository root after crawl planning",
            ));
            Ok(report)
        }
        (Ok(mut report), Some(err)) => {
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
        },
    )?;
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

    validate_manifest(&record_root, &import_plan.manifest)?;
    import_plan.manifest_text = render_manifest(&import_plan.manifest)?;
    import_plan.evidence_text =
        append_github_evidence(import_plan.evidence_text, &import_plan.manifest, snapshot);

    let (synthesis, synthesis_failure, synthesis_diagnostics) =
        maybe_attempt_synthesis(request, &record_root, &generated_at);
    diagnostics.extend(synthesis_diagnostics);

    let state_record = CrawlStateRecord {
        repository: request.repository.clone(),
        default_branch: Some(snapshot.default_branch.clone()),
        head_sha: snapshot.head_sha.clone(),
        last_factual_crawl_at: Some(generated_at.clone()),
        last_synthesis_success_at: synthesis.as_ref().map(|_| generated_at.clone()),
        last_synthesis_failure: synthesis_failure.clone(),
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
        diagnostics,
    })
}

fn validate_repository_identity(repository: &RepositoryRef) -> Result<()> {
    if repository.host.trim().is_empty()
        || repository.owner.trim().is_empty()
        || repository.repo.trim().is_empty()
    {
        bail!("repository identity must include host, owner, and repo");
    }
    if repository.host.trim() != "github.com" {
        bail!("crawl_repository currently supports github.com identities only");
    }
    Ok(())
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

fn merge_snapshot_fields(
    repository: &RepositoryRef,
    source_url: &str,
    manifest: &mut Manifest,
    snapshot: &GitHubRepositorySnapshot,
) -> Vec<CrawlDiagnostic> {
    let mut diagnostics = Vec::new();
    let mut merged_fields = Vec::new();

    if manifest.repo.name.trim().is_empty() {
        manifest.repo.name = repository.repo.clone();
        merged_fields.push("repo.name");
    }

    if manifest_is_missing_description(manifest) {
        if let Some(description) = trimmed_non_empty(snapshot.description.as_deref()) {
            manifest.repo.description = description.to_string();
            merged_fields.push("repo.description");
        }
    }

    let current_homepage = trimmed_non_empty(manifest.repo.homepage.as_deref());
    let should_replace_homepage =
        current_homepage.is_none() || current_homepage == Some(source_url.trim());
    if should_replace_homepage {
        if let Some(homepage) = trimmed_non_empty(snapshot.homepage.as_deref()) {
            manifest.repo.homepage = Some(homepage.to_string());
            merged_fields.push("repo.homepage");
        }
    }

    if let Some(license) = trimmed_non_empty(snapshot.license.as_deref()) {
        manifest.repo.license = Some(license.to_string());
        merged_fields.push("repo.license");
    }

    if let Some(visibility) = trimmed_non_empty(snapshot.visibility.as_deref()) {
        manifest.repo.visibility = Some(visibility.to_string());
        merged_fields.push("repo.visibility");
    }

    let languages = normalized_list(&snapshot.languages);
    if !languages.is_empty() {
        manifest.repo.languages = languages;
        merged_fields.push("repo.languages");
    }

    let topics = normalized_list(&snapshot.topics);
    if !topics.is_empty() {
        manifest.repo.topics = topics;
        merged_fields.push("repo.topics");
    }

    manifest
        .x
        .insert("github".into(), github_extension(snapshot, source_url));
    diagnostics.push(CrawlDiagnostic::info(
        "pipeline.github_extension",
        "recorded GitHub crawler metadata under x.github",
    ));

    if !merged_fields.is_empty() {
        diagnostics.push(CrawlDiagnostic::info(
            "pipeline.github_merge",
            format!(
                "augmented {} from GitHub repository metadata",
                merged_fields.join(", ")
            ),
        ));
    }

    diagnostics
}

fn append_github_evidence(
    evidence_text: Option<String>,
    manifest: &Manifest,
    snapshot: &GitHubRepositorySnapshot,
) -> Option<String> {
    let mut evidence = evidence_text?;
    let mut bullets = Vec::new();

    let homepage = trimmed_non_empty(manifest.repo.homepage.as_deref());
    if homepage.is_some() && homepage == trimmed_non_empty(snapshot.homepage.as_deref()) {
        bullets.push("Augmented repo.homepage from GitHub repository metadata.".to_string());
    }
    if manifest.repo.license.as_deref() == trimmed_non_empty(snapshot.license.as_deref()) {
        bullets.push("Augmented repo.license from GitHub repository metadata.".to_string());
    }
    if manifest.repo.visibility.as_deref() == trimmed_non_empty(snapshot.visibility.as_deref()) {
        bullets.push("Augmented repo.visibility from GitHub repository metadata.".to_string());
    }
    if !manifest.repo.languages.is_empty()
        && manifest.repo.languages == normalized_list(&snapshot.languages)
    {
        bullets.push("Augmented repo.languages from GitHub repository metadata.".to_string());
    }
    if !manifest.repo.topics.is_empty() && manifest.repo.topics == normalized_list(&snapshot.topics)
    {
        bullets.push("Augmented repo.topics from GitHub repository metadata.".to_string());
    }
    if trimmed_non_empty(Some(manifest.repo.description.as_str()))
        == trimmed_non_empty(snapshot.description.as_deref())
    {
        bullets.push(
            "Filled repo.description from GitHub repository metadata when the README surface did not provide one."
                .to_string(),
        );
    }
    bullets.push(
        "Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state)."
            .to_string(),
    );

    if !evidence.ends_with('\n') {
        evidence.push('\n');
    }
    for bullet in bullets {
        evidence.push_str("- ");
        evidence.push_str(&bullet);
        evidence.push('\n');
    }
    Some(evidence)
}

fn maybe_attempt_synthesis(
    request: &CrawlRepositoryRequest,
    record_root: &Path,
    occurred_at: &str,
) -> (
    Option<crate::SynthesisPlan>,
    Option<SynthesisFailureMetadata>,
    Vec<CrawlDiagnostic>,
) {
    if !request.synthesize {
        return (None, None, Vec::new());
    }

    let model = match trimmed_non_empty(request.synthesis_model.as_deref()) {
        Some(value) => value.to_string(),
        None => {
            let failure = SynthesisFailureMetadata {
                class: SynthesisFailureClass::EmptyRequiredField,
                message: "synthesis requested but synthesis_model was empty".into(),
                occurred_at: Some(occurred_at.into()),
                model: None,
                provider: request.synthesis_provider.clone(),
            };
            return (
                None,
                Some(failure),
                vec![CrawlDiagnostic::warning(
                    "pipeline.synthesis_missing_model",
                    "synthesis requested without a model; factual writeback continues",
                )],
            );
        }
    };
    let provider = match trimmed_non_empty(request.synthesis_provider.as_deref()) {
        Some(value) => value.to_string(),
        None => {
            let failure = SynthesisFailureMetadata {
                class: SynthesisFailureClass::EmptyRequiredField,
                message: "synthesis requested but synthesis_provider was empty".into(),
                occurred_at: Some(occurred_at.into()),
                model: Some(model.clone()),
                provider: None,
            };
            return (
                None,
                Some(failure),
                vec![CrawlDiagnostic::warning(
                    "pipeline.synthesis_missing_provider",
                    "synthesis requested without a provider; factual writeback continues",
                )],
            );
        }
    };

    let synth_request = SynthesizeRepositoryRequest {
        record_root: record_root.to_path_buf(),
        repository: request.repository.clone(),
        generated_at: Some(occurred_at.into()),
        source_commit: None,
        model: model.clone(),
        provider: provider.clone(),
    };

    match synthesize_repository_impl(&synth_request) {
        Ok(report) => (report.synthesis, report.failure, report.diagnostics),
        Err(err) => {
            let failure = classify_synthesis_failure(&err, occurred_at, &model, &provider);
            (
                None,
                Some(failure),
                vec![CrawlDiagnostic::warning(
                    "pipeline.synthesis_failed",
                    "synthesis failed; factual writeback continues",
                )],
            )
        }
    }
}

fn classify_synthesis_failure(
    err: &anyhow::Error,
    occurred_at: &str,
    model: &str,
    provider: &str,
) -> SynthesisFailureMetadata {
    let message = err.to_string();
    let class = if message.contains("unsafe shell-like value") {
        SynthesisFailureClass::UnsafeShellLikeValue
    } else if message.contains("conflicts with factual") {
        SynthesisFailureClass::FactualConflict
    } else if message.contains("must not be empty") {
        SynthesisFailureClass::EmptyRequiredField
    } else if message.contains("schema") {
        SynthesisFailureClass::InvalidSchemaOutput
    } else if message.contains("bound") || message.contains("too long") {
        SynthesisFailureClass::FieldBoundsViolation
    } else if message.contains("rate limit") {
        SynthesisFailureClass::RateLimited
    } else {
        SynthesisFailureClass::TransportError
    };

    SynthesisFailureMetadata {
        class,
        message,
        occurred_at: Some(occurred_at.into()),
        model: Some(model.into()),
        provider: Some(provider.into()),
    }
}

fn github_extension(snapshot: &GitHubRepositorySnapshot, source_url: &str) -> Value {
    let mut github = toml::map::Map::new();
    github.insert("html_url".into(), Value::String(source_url.to_string()));
    github.insert(
        "clone_url".into(),
        Value::String(snapshot.clone_url.clone()),
    );
    github.insert(
        "default_branch".into(),
        Value::String(snapshot.default_branch.clone()),
    );
    github.insert("archived".into(), Value::Boolean(snapshot.archived));
    github.insert("fork".into(), Value::Boolean(snapshot.fork));
    if let Some(head_sha) = trimmed_non_empty(snapshot.head_sha.as_deref()) {
        github.insert("head_sha".into(), Value::String(head_sha.to_string()));
    }
    if let Some(stars) = snapshot.stars {
        github.insert("stars".into(), Value::Integer(stars as i64));
    }
    Value::Table(github)
}

fn manifest_is_missing_description(manifest: &Manifest) -> bool {
    let description = manifest.repo.description.trim();
    description.is_empty()
        || description == "Imported repository metadata; review and refine before relying on it."
}

fn normalized_list(values: &[String]) -> Vec<String> {
    let mut normalized = Vec::new();
    for value in values {
        if let Some(value) = trimmed_non_empty(Some(value.as_str())) {
            if !normalized.iter().any(|existing| existing == value) {
                normalized.push(value.to_string());
            }
        }
    }
    normalized
}

fn trimmed_non_empty(value: Option<&str>) -> Option<&str> {
    value.map(str::trim).filter(|value| !value.is_empty())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::materialize::{
        materialize_repository, ConventionalRepositoryFiles, MaterializeRepositoryInput,
        RepositoryTextFile,
    };
    use crate::writeback::apply_writeback_plan;
    use dotrepo_core::validate_index_root;
    use dotrepo_schema::parse_manifest;
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
        }
    }

    struct FakeGitHubClient {
        snapshot: GitHubRepositorySnapshot,
        files: ConventionalRepositoryFiles,
    }

    impl GitHubClient for FakeGitHubClient {
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
                    contents: "# Orbit\n\nREADME description wins over the GitHub fallback.\n"
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
        };

        let report = crawl_repository_from_snapshot(
            &request,
            &snapshot(Some("GitHub description should not overwrite README.")),
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
            "README description wins over the GitHub fallback."
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
        assert!(evidence.contains("Imported repository name and description from README.mdx."));

        fs::remove_dir_all(index_root).expect("index temp removed");
    }
}
