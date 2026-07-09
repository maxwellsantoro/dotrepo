//! Optional bounded synthesis after factual crawl planning.

use crate::synth::synthesize_repository_impl;
use crate::{
    CrawlDiagnostic, CrawlRepositoryRequest, SynthesisFailureClass, SynthesisFailureMetadata,
    SynthesizeRepositoryRequest,
};
use std::path::Path;

use super::merge::trimmed_non_empty;

pub(crate) fn maybe_attempt_synthesis(
    request: &CrawlRepositoryRequest,
    record_root: &Path,
    manifest: &dotrepo_schema::Manifest,
    sources: Vec<crate::SynthesisSourceDocument>,
    source_commit: Option<&str>,
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
        manifest: manifest.clone(),
        sources,
        generated_at: Some(occurred_at.into()),
        source_commit: source_commit.map(str::to_string),
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

pub(crate) fn synthesis_sources_from_materialized(
    materialized: &crate::materialize::MaterializedRepository,
) -> Vec<crate::SynthesisSourceDocument> {
    materialized
        .written_files
        .iter()
        .take(12)
        .filter_map(|file| {
            let path = materialized.repository_root.join(&file.relative_path);
            let contents = std::fs::read_to_string(path).ok()?;
            let contents = contents.chars().take(32_000).collect::<String>();
            Some(crate::SynthesisSourceDocument {
                path: file.relative_path.to_string_lossy().replace('\\', "/"),
                contents,
            })
        })
        .scan(0usize, |total, source| {
            let remaining = 128_000usize.saturating_sub(*total);
            if remaining == 0 {
                return None;
            }
            let contents = source.contents.chars().take(remaining).collect::<String>();
            *total += contents.chars().count();
            Some(crate::SynthesisSourceDocument { contents, ..source })
        })
        .collect()
}

pub(crate) fn classify_synthesis_failure(
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
    } else if message.contains("schema")
        || message.contains("invalid JSON")
        || message.contains("unknown field")
    {
        SynthesisFailureClass::InvalidSchemaOutput
    } else if message.contains("not grounded") || message.contains("safe relative path") {
        SynthesisFailureClass::GroundingViolation
    } else if message.contains("bound")
        || message.contains("too long")
        || message.contains("must not exceed")
        || message.contains("more than")
    {
        SynthesisFailureClass::FieldBoundsViolation
    } else if message.contains("rate limit") || message.contains("HTTP 429") {
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
