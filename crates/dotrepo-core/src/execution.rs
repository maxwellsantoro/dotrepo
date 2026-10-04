//! Value binding and path contracts for explicit execution metadata.

use std::path::Path;

use dotrepo_schema::{ExecutionContext, ExecutionScope, Manifest, RecordMode};

use crate::claims::resolve_repository_local_path_for_read;
use crate::validation::{ValidationDiagnostic, ValidationDiagnosticSeverity};

pub(crate) fn validate_execution_contexts(
    root: &Path,
    manifest: &Manifest,
) -> Vec<ValidationDiagnostic> {
    let mut diagnostics = Vec::new();
    for (field, command, context) in [
        (
            "repo.build_context",
            manifest.repo.build.as_deref(),
            manifest.repo.build_context.as_ref(),
        ),
        (
            "repo.test_context",
            manifest.repo.test.as_deref(),
            manifest.repo.test_context.as_ref(),
        ),
    ] {
        if let Some(context) = context {
            validate_context(
                root,
                manifest,
                field,
                command,
                context,
                true,
                &mut diagnostics,
            );
        }
    }
    for (field, candidates) in [
        ("repo.build_candidates", &manifest.repo.build_candidates),
        ("repo.test_candidates", &manifest.repo.test_candidates),
    ] {
        for (index, candidate) in candidates.iter().enumerate() {
            if let Some(context) = &candidate.context {
                validate_context(
                    root,
                    manifest,
                    &format!("{field}[{index}].context"),
                    Some(&candidate.command),
                    context,
                    false,
                    &mut diagnostics,
                );
            }
        }
    }
    diagnostics
}

fn validate_context(
    root: &Path,
    manifest: &Manifest,
    field: &str,
    command: Option<&str>,
    context: &ExecutionContext,
    scalar: bool,
    diagnostics: &mut Vec<ValidationDiagnostic>,
) {
    let mut error = |message: String| {
        diagnostics.push(ValidationDiagnostic {
            severity: ValidationDiagnosticSeverity::Error,
            code: "invalid_execution_context",
            source: "validate_manifest",
            message: format!("{field}: {message}"),
        });
    };
    if command != Some(context.command.as_str()) || context.command.trim().is_empty() {
        error("command must exactly match its associated command value".into());
    }
    if context.command.trim() != context.command {
        error(
            "command must omit surrounding whitespace to preserve its public value binding".into(),
        );
    }
    if scalar && (context.scope != ExecutionScope::Repository || context.working_directory != ".") {
        error("scalar commands must have repository scope and working_directory = '.'; use candidates for scoped commands".into());
    }
    match (&context.scope, &context.component) {
        (ExecutionScope::Repository, Some(_)) => {
            error("repository scope must omit component".into())
        }
        (ExecutionScope::Component, None) => error("component scope requires component".into()),
        _ => {}
    }
    for (name, path, directory, allow_root) in [
        (
            "working_directory",
            Some(context.working_directory.as_str()),
            true,
            true,
        ),
        ("component", context.component.as_deref(), true, false),
        ("source", Some(context.source.as_str()), false, false),
    ] {
        let Some(path) = path else { continue };
        if !portable_repository_path(path, allow_root) {
            error(format!(
                "{name} must be a normalized repository-relative path"
            ));
            continue;
        }
        // Overlay paths refer to upstream, never the index checkout. Native
        // paths can additionally be checked against the actual repository.
        if manifest.record.mode == RecordMode::Native {
            match resolve_repository_local_path_for_read(root, path) {
                Ok(resolved)
                    if if directory {
                        resolved.is_dir()
                    } else {
                        resolved.is_file()
                    } => {}
                _ => error(format!(
                    "{name} must resolve to a contained {}",
                    if directory { "directory" } else { "file" }
                )),
            }
        }
    }
    if context
        .prerequisites
        .iter()
        .any(|value| value.trim().is_empty() || value.chars().any(char::is_control))
    {
        error("prerequisites must contain nonempty descriptions without control characters".into());
    }
}

fn portable_repository_path(value: &str, allow_root: bool) -> bool {
    if value == "." {
        return allow_root;
    }
    !value.is_empty()
        && value.trim() == value
        && !value.contains(['\\', ':'])
        && !value.chars().any(char::is_control)
        && value
            .split('/')
            .all(|part| !part.is_empty() && part != "." && part != "..")
}
