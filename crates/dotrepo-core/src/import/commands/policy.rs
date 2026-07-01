//! Command safety checking and ranking policy: sanitizing shell-unsafe
//! values, resolving a single build/test command from multiple candidate
//! tiers, and Node.js package-runner detection used by extraction.
use super::super::types::{
    CommandSourceTier, ImportedCommandCandidate, ImportedCommandProvenance,
    ImportedCommandSelection,
};
use super::super::{human_join, push_unique};
use crate::util::contains_unsafe_shell_like_value;

#[derive(Debug)]
pub(crate) enum UniqueCommandResolution {
    None,
    Unique {
        command: String,
        source_path: String,
    },
    Conflict {
        source_paths: Vec<String>,
    },
}

pub(crate) fn sanitize_import_command(command: &str) -> Option<String> {
    if contains_unsafe_shell_like_value(command) {
        None
    } else {
        Some(command.to_string())
    }
}

pub(crate) fn resolve_command_field(
    candidates: &[ImportedCommandCandidate],
    field: &'static str,
    select_build: bool,
    notes: &mut Vec<String>,
    evidence_bullets: &mut Vec<String>,
    inferred_fields: &mut Vec<String>,
) -> Option<ImportedCommandSelection> {
    // Resolution goes top-down by tier:
    // Manifest > ContribDoc > TaskScript > Workflow.
    // Within a tier, conflicts are genuine and block the field.
    // If a higher tier resolves, lower tiers are ignored.
    let tiers = [
        CommandSourceTier::Manifest,
        CommandSourceTier::ContribDoc,
        CommandSourceTier::TaskScript,
        CommandSourceTier::Workflow,
    ];

    for tier in &tiers {
        let tier_candidates: Vec<&ImportedCommandCandidate> = candidates
            .iter()
            .filter(|c| c.source_tier == *tier)
            .collect();

        if tier_candidates.is_empty() {
            continue;
        }

        let resolution = resolve_unique_command_candidate(&tier_candidates, select_build);

        match &resolution {
            UniqueCommandResolution::Unique {
                command,
                source_path,
            } => {
                let Some(command) = sanitize_import_command(command) else {
                    let note = format!(
                        "Left `{}` unset because `{}` suggested an unsafe shell-like command.",
                        field, source_path
                    );
                    notes.push(note.clone());
                    evidence_bullets.push(note);
                    return None;
                };
                let is_manifest_tier = *tier == CommandSourceTier::Manifest
                    || *tier == CommandSourceTier::ContribDoc
                    || *tier == CommandSourceTier::TaskScript;
                let selection = ImportedCommandSelection {
                    command,
                    source_path: source_path.clone(),
                    provenance: if is_manifest_tier {
                        ImportedCommandProvenance::Imported
                    } else {
                        ImportedCommandProvenance::Inferred
                    },
                };
                if !is_manifest_tier {
                    inferred_fields.push(field.into());
                }
                note_selected_command(field, &selection, notes, evidence_bullets);
                return Some(selection);
            }
            UniqueCommandResolution::Conflict { source_paths } => {
                let kind = if select_build { "build" } else { "test" };
                let note = format!(
                    "Left `{}` unset because {} suggested conflicting {} commands.",
                    field,
                    human_join(source_paths),
                    kind
                );
                notes.push(note.clone());
                evidence_bullets.push(note);
                return None;
            }
            UniqueCommandResolution::None => continue,
        }
    }

    None
}

fn note_selected_command(
    field: &'static str,
    selection: &ImportedCommandSelection,
    notes: &mut Vec<String>,
    evidence_bullets: &mut Vec<String>,
) {
    match selection.provenance {
        ImportedCommandProvenance::Imported => {
            notes.push(format!(
                "Imported `{}` from `{}`.",
                field, selection.source_path
            ));
            evidence_bullets.push(format!(
                "Imported {} from {} as `{}`.",
                field, selection.source_path, selection.command
            ));
        }
        ImportedCommandProvenance::Inferred => {
            notes.push(format!(
                "Inferred `{}` from `{}`.",
                field, selection.source_path
            ));
            evidence_bullets.push(format!(
                "Inferred {} from {} as `{}`.",
                field, selection.source_path, selection.command
            ));
        }
    }
}

pub(crate) fn resolve_unique_command_candidate(
    candidates: &[&ImportedCommandCandidate],
    select_build: bool,
) -> UniqueCommandResolution {
    let mut present = Vec::new();
    for candidate in candidates {
        let command = if select_build {
            candidate.build.as_deref()
        } else {
            candidate.test.as_deref()
        };
        if let Some(command) = command.filter(|value| !value.trim().is_empty()) {
            present.push((command.to_string(), candidate.source_path.clone()));
        }
    }

    if present.is_empty() {
        return UniqueCommandResolution::None;
    }

    let mut unique_commands = Vec::new();
    for (command, path) in &present {
        if !unique_commands
            .iter()
            .any(|(existing, _): &(String, String)| existing == command)
        {
            unique_commands.push((command.clone(), path.clone()));
        }
    }

    if unique_commands.len() == 1 {
        let (command, path) = unique_commands.remove(0);
        return UniqueCommandResolution::Unique {
            command,
            source_path: path,
        };
    }

    if let Some((command, path)) = resolve_preferred_command_candidate(&present) {
        return UniqueCommandResolution::Unique {
            command,
            source_path: path,
        };
    }

    let mut source_paths = Vec::new();
    for (_, path) in &present {
        push_unique(&mut source_paths, path.clone());
    }
    UniqueCommandResolution::Conflict { source_paths }
}

fn resolve_preferred_command_candidate(present: &[(String, String)]) -> Option<(String, String)> {
    if !present
        .iter()
        .all(|(_, path)| path.starts_with(".github/workflows/"))
    {
        return None;
    }

    let best_preference = present
        .iter()
        .map(|(_, path)| workflow_source_preference(path.rsplit('/').next().unwrap_or(path)))
        .min()?;

    let preferred: Vec<_> = present
        .iter()
        .filter(|(_, path)| {
            workflow_source_preference(path.rsplit('/').next().unwrap_or(path)) == best_preference
        })
        .collect();

    let mut preferred_unique = Vec::new();
    for (command, path) in preferred {
        if !preferred_unique
            .iter()
            .any(|(existing, _): &(String, String)| existing == command)
        {
            preferred_unique.push((command.clone(), path.clone()));
        }
    }

    if preferred_unique.len() == 1 {
        let (command, path) = preferred_unique.remove(0);
        Some((command, path))
    } else {
        None
    }
}

fn workflow_source_preference(file: &str) -> i32 {
    if matches!(file, "ci.yml" | "ci.yaml") {
        return 0;
    }
    if matches!(file, "main.yml" | "main.yaml") {
        return 1;
    }
    if matches!(file, "test.yml" | "test.yaml") {
        return 2;
    }
    if matches!(file, "build.yml" | "build.yaml") {
        return 3;
    }
    if file.contains("build-and-test") && file.contains("pr") {
        return 4;
    }
    if file.contains("build-and-test") {
        return 5;
    }
    if matches!(file, "pr.yml" | "pr.yaml") {
        return 6;
    }

    const DEPRIORITIZED: &[&str] = &[
        "android", "ios", "windows", "macos", "freebsd", "gcc", "clang", "cross", "release",
        "bindings", "packages", "preview", "apk", "docker", "helm", "npm", "nuget", "pypi",
        "crates", "openapi", "ui",
    ];
    for (index, keyword) in DEPRIORITIZED.iter().enumerate() {
        if file.contains(keyword) {
            return 100 + index as i32;
        }
    }

    50
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum NodePackageRunner {
    Npm,
    Pnpm,
    Yarn,
    Bun,
}

impl NodePackageRunner {
    pub(crate) fn build_command(self) -> String {
        match self {
            Self::Npm => "npm run build".into(),
            Self::Pnpm => "pnpm build".into(),
            Self::Yarn => "yarn build".into(),
            Self::Bun => "bun run build".into(),
        }
    }

    pub(crate) fn test_command(self) -> String {
        match self {
            Self::Npm => "npm test".into(),
            Self::Pnpm => "pnpm test".into(),
            Self::Yarn => "yarn test".into(),
            Self::Bun => "bun run test".into(),
        }
    }
}

pub(crate) fn detect_node_package_runner(package_manager: Option<&str>) -> NodePackageRunner {
    match package_manager
        .filter(|value| !value.trim().is_empty())
        .map(|value| value.to_ascii_lowercase())
    {
        Some(value) if value.starts_with("pnpm@") || value == "pnpm" => NodePackageRunner::Pnpm,
        Some(value) if value.starts_with("yarn@") || value == "yarn" => NodePackageRunner::Yarn,
        Some(value) if value.starts_with("bun@") || value == "bun" => NodePackageRunner::Bun,
        _ => NodePackageRunner::Npm,
    }
}

pub(crate) fn is_placeholder_package_json_test_script(script: &str) -> bool {
    script.to_ascii_lowercase().contains("no test specified")
}

/// Return a runner-wrapped command if any of the candidate script names exists and is non-empty.
pub(crate) fn pick_node_script_command(
    scripts: &serde_json::Map<String, serde_json::Value>,
    names: &[&str],
    make_cmd: impl FnOnce() -> String,
) -> Option<String> {
    for name in names {
        if let Some(v) = scripts.get(*name).and_then(serde_json::Value::as_str) {
            if !v.trim().is_empty() {
                return Some(make_cmd());
            }
        }
    }
    None
}
