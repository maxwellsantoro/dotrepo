//! Diagnostics generation for open manifest documents.
//!
//! Builds `textDocument/publishDiagnostics` payloads by combining parse
//! errors, `dotrepo_core` manifest/repository validation, and adoption
//! status hints, mapped onto source ranges via `DocumentIndex`.

use crate::protocol::LspDiagnostic;
use crate::state::{byte_span_to_range, validation_root_for_manifest, DocumentIndex};
use dotrepo_core::{
    adoption_status_repository, display_path, native_repository_identity,
    validate_manifest_diagnostics, validate_repository, RepositoryDiagnostic, ValidationDiagnostic,
    ValidationDiagnosticSeverity,
};
use dotrepo_schema::{parse_manifest, Manifest, ParseError, RecordMode};
use std::path::{Path, PathBuf};

pub(crate) fn diagnostics_for_document(
    path: &Path,
    text: &str,
    workspace_roots: &[PathBuf],
) -> Vec<LspDiagnostic> {
    let index = DocumentIndex::from_text(text);
    let root = validation_root_for_manifest(path, workspace_roots);
    let current_manifest_path = display_path(&root, path).ok();

    let mut diagnostics = match parse_manifest(text) {
        Ok(manifest) => validate_manifest_diagnostics(&root, &manifest)
            .into_iter()
            .map(|diagnostic| map_validation_diagnostic(&index, &root, &diagnostic))
            .chain(adoption_diagnostics_for_manifest(&index, &root, &manifest))
            .collect(),
        Err(ParseError::Toml(err)) => vec![LspDiagnostic {
            range: err
                .span()
                .map(|span| byte_span_to_range(text, span.start, span.end))
                .unwrap_or_else(|| index.default_range()),
            severity: 1,
            source: "parse_manifest".into(),
            message: ParseError::Toml(err).to_string(),
        }],
        Err(ParseError::ConflictingTrustPlacement) => vec![LspDiagnostic {
            range: index
                .section_range("trust")
                .or_else(|| index.section_range("record.trust"))
                .or_else(|| index.section_range("record"))
                .unwrap_or_else(|| index.default_range()),
            severity: 1,
            source: "parse_manifest".into(),
            message: ParseError::ConflictingTrustPlacement.to_string(),
        }],
    };

    if path.exists() || has_other_root_manifests(&root, path) {
        diagnostics.extend(repository_level_diagnostics(
            &index,
            &root,
            current_manifest_path.as_deref(),
        ));
    }

    diagnostics
}

pub(crate) fn has_other_root_manifests(root: &Path, current: &Path) -> bool {
    for name in [".repo", "record.toml"] {
        let candidate = root.join(name);
        if candidate != current && candidate.exists() {
            return true;
        }
    }
    false
}

fn repository_level_diagnostics(
    index: &DocumentIndex,
    root: &Path,
    current_manifest_path: Option<&str>,
) -> Vec<LspDiagnostic> {
    validate_repository(root)
        .diagnostics
        .into_iter()
        .filter(|diagnostic| {
            diagnostic.manifest_path.as_deref() != current_manifest_path
                || current_manifest_path.is_none()
        })
        .map(|diagnostic| map_repository_diagnostic(index, &diagnostic))
        .collect()
}

fn map_repository_diagnostic(
    index: &DocumentIndex,
    diagnostic: &RepositoryDiagnostic,
) -> LspDiagnostic {
    let message = match diagnostic.manifest_path.as_deref() {
        Some(manifest_path) => format!("{manifest_path}: {}", diagnostic.message),
        None => diagnostic.message.clone(),
    };
    LspDiagnostic {
        range: index.default_range(),
        severity: 1,
        source: diagnostic.source.clone(),
        message,
    }
}

fn adoption_diagnostics_for_manifest(
    index: &DocumentIndex,
    root: &Path,
    manifest: &Manifest,
) -> Vec<LspDiagnostic> {
    if manifest.record.mode == RecordMode::Overlay {
        return Vec::new();
    }

    let report = adoption_status_repository(root);
    let mut diagnostics = Vec::new();
    let homepage_range = index
        .section_range("repo")
        .or_else(|| index.field_range("repo.homepage"))
        .unwrap_or_else(|| index.default_range());

    if native_repository_identity(manifest).is_err() {
        let homepage_present = manifest
            .repo
            .homepage
            .as_deref()
            .map(str::trim)
            .is_some_and(|value| !value.is_empty());
        let message = if homepage_present {
            "repo.homepage must resolve to a host/owner/repo URL for claim-from-native".to_string()
        } else {
            "set repo.homepage to enable claim-from-native and derived claim handoff commands"
                .to_string()
        };
        diagnostics.push(LspDiagnostic {
            range: homepage_range,
            severity: 4,
            source: "adoption_status".into(),
            message,
        });
    }

    if !report.ci_workflow_present {
        let ci_check = report
            .checks
            .iter()
            .find(|check| check.name == "ci workflow");
        diagnostics.push(LspDiagnostic {
            range: index
                .section_range("record")
                .unwrap_or_else(|| index.default_range()),
            severity: 4,
            source: "adoption_status".into(),
            message: ci_check
                .map(|check| check.detail.clone())
                .unwrap_or_else(|| {
                    "run dotrepo ci init to add the native-repo adoption check workflow".into()
                }),
        });
    }

    diagnostics
}

fn map_validation_diagnostic(
    index: &DocumentIndex,
    root: &Path,
    diagnostic: &ValidationDiagnostic,
) -> LspDiagnostic {
    let range =
        range_for_diagnostic_code(index, root, diagnostic).unwrap_or_else(|| index.default_range());

    LspDiagnostic {
        range,
        severity: severity_code(diagnostic.severity),
        source: diagnostic.source.into(),
        message: diagnostic.message.clone(),
    }
}

fn range_for_diagnostic_code(
    index: &DocumentIndex,
    root: &Path,
    diagnostic: &ValidationDiagnostic,
) -> Option<crate::protocol::LspRange> {
    match diagnostic.code {
        "unsupported_schema" => index.field_range("schema"),
        "invalid_generated_at" => index.field_range("record.generated_at"),
        "repo_name_empty" => index.field_range("repo.name"),
        "unsafe_shell_command" => {
            if diagnostic.message.contains("repo.build") {
                index.field_range("repo.build")
            } else if diagnostic.message.contains("repo.test") {
                index.field_range("repo.test")
            } else {
                None
            }
        }
        "overlay_source_required" => index
            .field_range("record.source")
            .or_else(|| index.section_range("record")),
        "overlay_trust_provenance_required" => index
            .field_range("record.trust.provenance")
            .or_else(|| index.section_range("record.trust")),
        "overlay_trust_required" => index
            .section_range("record.trust")
            .or_else(|| index.section_range("trust"))
            .or_else(|| index.section_range("record")),
        "readme_section_content_or_path_required" | "readme_section_content_and_path_conflict" => {
            missing_custom_section_name(&diagnostic.message).and_then(|section_name| {
                index
                    .section_range(&format!("readme.custom_sections.{section_name}"))
                    .or_else(|| index.field_range("readme.custom_sections.path"))
            })
        }
        "missing_referenced_path" | "invalid_referenced_path" => {
            missing_path_target(&diagnostic.message)
                .and_then(|target| range_for_missing_path(index, root, &target))
        }
        "readme_section_missing_path" | "readme_section_invalid_path" => {
            missing_custom_section_name(&diagnostic.message).and_then(|section_name| {
                index.section_range(&format!("readme.custom_sections.{section_name}"))
            })
        }
        _ => None,
    }
}

fn severity_code(severity: ValidationDiagnosticSeverity) -> u8 {
    match severity {
        ValidationDiagnosticSeverity::Error => 1,
    }
}

fn missing_custom_section_name(message: &str) -> Option<String> {
    let prefix = "custom README section `";
    let remainder = message.strip_prefix(prefix)?;
    let end = remainder.find('`')?;
    Some(remainder[..end].to_string())
}

fn missing_path_target(message: &str) -> Option<PathBuf> {
    let path = message.split(": ").last()?;
    Some(PathBuf::from(path))
}

fn range_for_missing_path(
    index: &DocumentIndex,
    root: &Path,
    target: &Path,
) -> Option<crate::protocol::LspRange> {
    let relative = target.strip_prefix(root).ok();
    let mut candidates = Vec::new();
    if let Some(relative) = relative {
        let rel = relative.display().to_string();
        if !rel.is_empty() {
            candidates.push(rel.clone());
            if !rel.starts_with("./") {
                candidates.push(format!("./{rel}"));
            }
        }
    }
    candidates.push(target.display().to_string());

    index.find_line_containing_any(&candidates)
}
