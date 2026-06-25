use anyhow::{anyhow, Result};
use std::fs;
use std::path::Path;

use super::{
    human_join, push_unique, CommandSourceTier, ImportSources, ImportedCommandCandidate,
    ImportedCommandMetadata, ImportedCommandProvenance, ImportedCommandSelection, ImportedFile,
};
use crate::util::contains_unsafe_shell_like_value;

pub(super) fn load_first_existing_file(
    root: &Path,
    candidates: &[&'static str],
) -> Result<Option<ImportedFile>> {
    for candidate in candidates {
        let path = root.join(candidate);
        if path.exists() {
            let contents = fs::read_to_string(&path)
                .map_err(|err| anyhow!("failed to read {}: {}", path.display(), err))?;
            return Ok(Some(ImportedFile {
                path: candidate.to_string(),
                contents,
            }));
        }
    }

    Ok(None)
}

pub(super) fn load_workflow_import_files(root: &Path) -> Result<Vec<ImportedFile>> {
    let workflows_root = root.join(".github").join("workflows");
    if !workflows_root.is_dir() {
        return Ok(Vec::new());
    }

    let mut files = fs::read_dir(&workflows_root)
        .map_err(|err| anyhow!("failed to read {}: {}", workflows_root.display(), err))?
        .filter_map(|entry| entry.ok())
        .filter_map(|entry| {
            let path = entry.path();
            let file_name = path.file_name()?.to_str()?;
            let lower = file_name.to_ascii_lowercase();
            if !path.is_file() || !(lower.ends_with(".yml") || lower.ends_with(".yaml")) {
                return None;
            }
            Some((file_name.to_string(), path))
        })
        .collect::<Vec<_>>();
    files.sort_by(|left, right| left.0.cmp(&right.0));

    let mut imported = Vec::new();
    for (file_name, path) in files {
        let contents = fs::read_to_string(&path)
            .map_err(|err| anyhow!("failed to read {}: {}", path.display(), err))?;
        imported.push(ImportedFile {
            path: format!(".github/workflows/{}", file_name),
            contents,
        });
    }

    Ok(imported)
}

pub(crate) fn infer_imported_commands(sources: &ImportSources) -> ImportedCommandMetadata {
    let mut candidates = Vec::new();
    // Manifest tier
    if let Some(candidate) = sources.cargo_toml.and_then(infer_cargo_manifest_commands) {
        candidates.push(candidate);
    }
    if let Some(candidate) = sources.package_json.and_then(infer_package_json_commands) {
        candidates.push(candidate);
    }
    if let Some(candidate) = sources.pyproject_toml.and_then(infer_pyproject_commands) {
        candidates.push(candidate);
    }
    if let Some(candidate) = sources.go_mod.and_then(infer_go_module_commands) {
        candidates.push(candidate);
    }
    // ContribDoc tier
    if let Some(candidate) = sources.contributing.and_then(infer_contributing_commands) {
        candidates.push(candidate);
    }
    // TaskScript tier
    if let Some(candidate) = sources.makefile.and_then(infer_makefile_commands) {
        candidates.push(candidate);
    }
    if let Some(candidate) = sources.justfile.and_then(infer_justfile_commands) {
        candidates.push(candidate);
    }
    // Workflow tier
    candidates.extend(
        sources
            .workflow_files
            .iter()
            .filter_map(infer_workflow_commands),
    );

    let mut metadata = ImportedCommandMetadata::default();
    metadata.build = resolve_command_field(
        &candidates,
        "repo.build",
        true,
        &mut metadata.notes,
        &mut metadata.evidence_bullets,
        &mut metadata.inferred_fields,
    );
    metadata.test = resolve_command_field(
        &candidates,
        "repo.test",
        false,
        &mut metadata.notes,
        &mut metadata.evidence_bullets,
        &mut metadata.inferred_fields,
    );
    metadata.candidates = candidates;
    metadata
}

fn infer_cargo_manifest_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let parsed: toml::Value = toml::from_str(&file.contents).ok()?;
    let has_workspace = parsed
        .get("workspace")
        .and_then(toml::Value::as_table)
        .is_some();
    let has_package = parsed
        .get("package")
        .and_then(toml::Value::as_table)
        .is_some();
    if !has_workspace && !has_package {
        return None;
    }

    let (build, test) = if has_workspace {
        ("cargo build --workspace", "cargo test --workspace")
    } else {
        ("cargo build", "cargo test")
    };

    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::Manifest,
        build: Some(build.into()),
        test: Some(test.into()),
    })
}

fn infer_package_json_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let parsed: serde_json::Value = serde_json::from_str(&file.contents).ok()?;
    let scripts = parsed
        .get("scripts")
        .and_then(serde_json::Value::as_object)?;
    let runner = detect_node_package_runner(
        parsed
            .get("packageManager")
            .and_then(serde_json::Value::as_str),
    );

    let build = scripts
        .get("build")
        .and_then(serde_json::Value::as_str)
        .filter(|value| !value.trim().is_empty())
        .map(|_| runner.build_command());
    let test = scripts
        .get("test")
        .and_then(serde_json::Value::as_str)
        .filter(|value| !value.trim().is_empty())
        .filter(|value| !is_placeholder_package_json_test_script(value))
        .map(|_| runner.test_command());

    if build.is_none() && test.is_none() {
        return None;
    }

    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::Manifest,
        build,
        test,
    })
}

pub(crate) fn infer_pyproject_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let parsed: toml::Value = toml::from_str(&file.contents).ok()?;
    let has_build_system = parsed
        .get("build-system")
        .and_then(toml::Value::as_table)
        .is_some();
    let build = has_build_system.then(|| "python -m build".to_string());

    let test = infer_pyproject_test_command(&parsed);

    if build.is_none() && test.is_none() {
        return None;
    }

    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::Manifest,
        build,
        test,
    })
}

fn infer_pyproject_test_command(parsed: &toml::Value) -> Option<String> {
    let tool = parsed.get("tool").and_then(toml::Value::as_table);
    if let Some(tool_table) = tool {
        if tool_table.contains_key("pytest") {
            return Some("python -m pytest".to_string());
        }
        if tool_table.contains_key("tox") || tool_table.contains_key("tox-gh-actions") {
            return Some("tox".to_string());
        }
        if tool_table.contains_key("nox") {
            return Some("nox".to_string());
        }
    }

    let project = parsed.get("project").and_then(toml::Value::as_table);
    if let Some(project_table) = project {
        if let Some(scripts) = project_table.get("scripts").and_then(toml::Value::as_table) {
            if scripts.contains_key("test") {
                return Some("python -m pytest".to_string());
            }
        }
        if let Some(optional_deps) = project_table
            .get("optional-dependencies")
            .and_then(toml::Value::as_table)
        {
            if optional_deps.contains_key("test") || optional_deps.contains_key("testing") {
                return Some("python -m pytest".to_string());
            }
        }
    }

    if parsed
        .get("build-system")
        .and_then(toml::Value::as_table)
        .is_some()
    {
        return Some("python -m pytest".to_string());
    }

    None
}

fn infer_go_module_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let has_module = file
        .contents
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .any(|line| line.starts_with("module "));
    if !has_module {
        return None;
    }

    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::Manifest,
        build: Some("go build ./...".into()),
        test: Some("go test ./...".into()),
    })
}

fn infer_makefile_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let mut has_build = false;
    let mut has_test = false;
    for line in file.contents.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with("build:") || trimmed.starts_with("all:") {
            has_build = true;
        }
        if trimmed.starts_with("test:") || trimmed.starts_with("check:") {
            has_test = true;
        }
    }
    if !has_build && !has_test {
        return None;
    }
    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::TaskScript,
        build: if has_build {
            Some("make build".into())
        } else {
            None
        },
        test: if has_test {
            Some("make test".into())
        } else {
            None
        },
    })
}

fn infer_justfile_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let mut has_build = false;
    let mut has_test = false;
    for line in file.contents.lines() {
        let trimmed = line.trim();
        // Skip ':=' assignments (variables) and '[' (settings/aliases)
        if trimmed.contains(":=") || trimmed.starts_with('[') {
            continue;
        }
        // Recipes: "name:" or "name arg:" — split on first ':' and check the lhs
        if let Some(colon_pos) = trimmed.find(':') {
            let lhs = trimmed[..colon_pos].trim();
            // lhs must be a valid recipe identifier (no spaces, no '=')
            if lhs.contains(' ') || lhs.contains('=') || lhs.is_empty() {
                continue;
            }
            // The first word of lhs is the recipe name (may have args after it)
            let name = lhs.split_whitespace().next().unwrap_or(lhs);
            if name == "build" || name == "all" {
                has_build = true;
            }
            if name == "test" || name == "check" {
                has_test = true;
            }
        }
    }
    if !has_build && !has_test {
        return None;
    }
    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::TaskScript,
        build: if has_build {
            Some("just build".into())
        } else {
            None
        },
        test: if has_test {
            Some("just test".into())
        } else {
            None
        },
    })
}

fn infer_contributing_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    // Look for build/test instructions in code blocks within CONTRIBUTING.md
    let mut build: Option<String> = None;
    let mut test: Option<String> = None;
    let mut in_code_block = false;
    for line in file.contents.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with("```") {
            in_code_block = !in_code_block;
            continue;
        }
        if !in_code_block {
            continue;
        }
        let lower = trimmed.to_lowercase();
        if build.is_none()
            && (lower.starts_with("cargo build")
                || lower == "make"
                || lower.starts_with("make build")
                || lower.starts_with("make all")
                || lower.starts_with("npm run build")
                || lower.starts_with("go build")
                || lower.starts_with("just build"))
        {
            build = Some(trimmed.to_string());
        }
        if test.is_none()
            && (lower.starts_with("cargo test")
                || lower.starts_with("make test")
                || lower.starts_with("make check")
                || lower.starts_with("npm test")
                || lower.starts_with("go test")
                || lower.starts_with("just test"))
        {
            test = Some(trimmed.to_string());
        }
    }
    if build.is_none() && test.is_none() {
        return None;
    }
    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::ContribDoc,
        build,
        test,
    })
}

fn infer_workflow_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let run_commands = extract_workflow_run_commands(&file.contents);
    let build = first_matching_workflow_command(&run_commands, true);
    let test = first_matching_workflow_command(&run_commands, false);
    if build.is_none() && test.is_none() {
        return None;
    }

    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::Workflow,
        build,
        test,
    })
}

fn extract_workflow_run_commands(contents: &str) -> Vec<String> {
    let mut commands = Vec::new();
    let mut run_block_indent = None;

    for line in contents.lines() {
        let indent = line.chars().take_while(|ch| ch.is_whitespace()).count();
        let trimmed = line.trim();

        if let Some(block_indent) = run_block_indent {
            if !trimmed.is_empty() && indent > block_indent {
                commands.push(trimmed.to_string());
                continue;
            }
            run_block_indent = None;
        }

        let run_line = trimmed
            .strip_prefix("- run:")
            .or_else(|| trimmed.strip_prefix("run:"));
        if let Some(rest) = run_line {
            let rest = rest.trim();
            if matches!(rest, "|" | "|-" | ">" | ">-") {
                run_block_indent = Some(indent);
            } else if !rest.is_empty() {
                commands.push(rest.to_string());
            }
        }
    }

    commands
}

fn first_matching_workflow_command(commands: &[String], select_build: bool) -> Option<String> {
    commands.iter().find_map(|command| {
        let trimmed = command.trim();
        if trimmed.is_empty() {
            return None;
        }

        if select_build {
            for prefix in [
                "cargo build",
                "go build",
                "python -m build",
                "npm run build",
                "pnpm build",
                "yarn build",
                "bun run build",
            ] {
                if trimmed.starts_with(prefix) {
                    return Some(trimmed.to_string());
                }
            }
        } else {
            for prefix in [
                "cargo test",
                "go test",
                "python -m pytest",
                "pytest",
                "npm test",
                "npm run test",
                "pnpm test",
                "yarn test",
                "bun run test",
            ] {
                if trimmed.starts_with(prefix) {
                    return Some(trimmed.to_string());
                }
            }
        }

        None
    })
}

enum UniqueCommandResolution {
    None,
    Unique {
        command: String,
        source_path: String,
    },
    Conflict {
        source_paths: Vec<String>,
    },
}

pub(super) fn sanitize_import_command(command: &str) -> Option<String> {
    if contains_unsafe_shell_like_value(command) {
        None
    } else {
        Some(command.to_string())
    }
}

fn resolve_command_field(
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

fn resolve_unique_command_candidate(
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

    let mut source_paths = Vec::new();
    for (_, path) in &present {
        push_unique(&mut source_paths, path.clone());
    }
    UniqueCommandResolution::Conflict { source_paths }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum NodePackageRunner {
    Npm,
    Pnpm,
    Yarn,
    Bun,
}

impl NodePackageRunner {
    fn build_command(self) -> String {
        match self {
            Self::Npm => "npm run build".into(),
            Self::Pnpm => "pnpm build".into(),
            Self::Yarn => "yarn build".into(),
            Self::Bun => "bun run build".into(),
        }
    }

    fn test_command(self) -> String {
        match self {
            Self::Npm => "npm test".into(),
            Self::Pnpm => "pnpm test".into(),
            Self::Yarn => "yarn test".into(),
            Self::Bun => "bun run test".into(),
        }
    }
}

fn detect_node_package_runner(package_manager: Option<&str>) -> NodePackageRunner {
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

fn is_placeholder_package_json_test_script(script: &str) -> bool {
    script.to_ascii_lowercase().contains("no test specified")
}

#[cfg(test)]
mod tests {
    use super::sanitize_import_command;

    #[test]
    fn sanitize_import_command_rejects_shell_like_values() {
        assert!(sanitize_import_command("cargo test").is_some());
        assert!(sanitize_import_command("npm run build").is_some());
        assert!(sanitize_import_command("echo $(whoami)").is_none());
        assert!(sanitize_import_command("cargo test\nrm -rf /").is_none());
        assert!(sanitize_import_command("echo `id`").is_none());
    }
}
