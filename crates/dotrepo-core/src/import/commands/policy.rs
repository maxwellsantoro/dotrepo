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
    // Declared manifest scripts > contribution docs > task scripts > observed
    // workflows > ecosystem defaults. A build-tool file proves the ecosystem,
    // but it does not prove that its conventional command works in this repo.
    // Within a tier, conflicts are genuine and block the field.
    // If a higher tier resolves, lower tiers are ignored.
    if !select_build {
        if let Some(source_paths) = conflicting_cross_ecosystem_test_sources(candidates) {
            let note = format!(
                "Left `{}` unset because {} suggested conflicting test commands.",
                field,
                human_join(&source_paths)
            );
            notes.push(note.clone());
            evidence_bullets.push(note);
            return None;
        }
    }

    let tiers = [
        CommandSourceTier::GitHubApi,
        CommandSourceTier::Manifest,
        CommandSourceTier::ContribDoc,
        CommandSourceTier::TaskScript,
        CommandSourceTier::Workflow,
        CommandSourceTier::EcosystemDefault,
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
                let (command, source_path, tier) = if *tier == CommandSourceTier::Workflow {
                    preferred_ecosystem_default_for_workflow_command(
                        candidates,
                        command,
                        select_build,
                    )
                    .unwrap_or_else(|| (command.clone(), source_path.clone(), *tier))
                } else {
                    (command.clone(), source_path.clone(), *tier)
                };
                let Some(command) = sanitize_import_command(&command) else {
                    let note = format!(
                        "Left `{}` unset because `{}` suggested an unsafe shell-like command.",
                        field, source_path
                    );
                    notes.push(note.clone());
                    evidence_bullets.push(note);
                    return None;
                };
                let is_declared_tier = tier == CommandSourceTier::Manifest
                    || tier == CommandSourceTier::ContribDoc
                    || tier == CommandSourceTier::TaskScript;
                let selection = ImportedCommandSelection {
                    command,
                    source_path,
                    source_tier: tier,
                    provenance: if is_declared_tier {
                        ImportedCommandProvenance::Imported
                    } else {
                        ImportedCommandProvenance::Inferred
                    },
                };
                if !is_declared_tier {
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

fn preferred_ecosystem_default_for_workflow_command(
    candidates: &[ImportedCommandCandidate],
    workflow_command: &str,
    select_build: bool,
) -> Option<(String, String, CommandSourceTier)> {
    preferred_cargo_workspace_default_for_workflow_command(
        candidates,
        workflow_command,
        select_build,
    )
    .or_else(|| {
        preferred_go_module_default_for_workflow_command(candidates, workflow_command, select_build)
    })
    .or_else(|| {
        preferred_wrapper_default_for_workflow_command(candidates, workflow_command, select_build)
    })
}

/// Gradle and Maven CI workflows almost always run pipeline-flavored tasks
/// (`systemTest`, `clean publish`, profile-specific goals, `$VAR` POM paths).
/// When the manifest tier already supplies the conventional wrapper-aware
/// default, that default is the canonical developer command.
fn preferred_wrapper_default_for_workflow_command(
    candidates: &[ImportedCommandCandidate],
    workflow_command: &str,
    select_build: bool,
) -> Option<(String, String, CommandSourceTier)> {
    let normalized = workflow_command.trim().trim_matches('\'').trim_matches('"');
    let manifest_paths: &[&str] = if normalized.starts_with("./gradlew")
        || normalized.starts_with("gradlew")
        || normalized.starts_with("gradle ")
    {
        &["build.gradle", "build.gradle.kts"]
    } else if normalized.starts_with("./mvnw") || normalized.starts_with("mvn ") {
        &["pom.xml"]
    } else {
        return None;
    };
    let (mut replacement, source_path, tier) = candidates.iter().find_map(|candidate| {
        (candidate.source_tier == CommandSourceTier::EcosystemDefault
            && manifest_paths.contains(&candidate.source_path.as_str()))
        .then(|| {
            if select_build {
                candidate.build.clone()
            } else {
                candidate.test.clone()
            }
            .map(|value| (value, candidate.source_path.clone(), candidate.source_tier))
        })
        .flatten()
    })?;
    // A workflow command that invokes the wrapper is itself proof the wrapper
    // exists, even when it was not materialized for the manifest default.
    if normalized.starts_with("./gradlew") {
        if let Some(rest) = replacement.strip_prefix("gradle ") {
            replacement = format!("./gradlew {rest}");
        }
    } else if normalized.starts_with("./mvnw") {
        if let Some(rest) = replacement.strip_prefix("mvn ") {
            replacement = format!("./mvnw {rest}");
        }
    }
    if normalized == replacement {
        return None;
    }
    Some((replacement, source_path, tier))
}

fn preferred_cargo_workspace_default_for_workflow_command(
    candidates: &[ImportedCommandCandidate],
    workflow_command: &str,
    select_build: bool,
) -> Option<(String, String, CommandSourceTier)> {
    if !is_less_canonical_cargo_workflow_command(workflow_command, select_build) {
        return None;
    }
    let expected = if select_build {
        "cargo build --workspace"
    } else {
        "cargo test --workspace"
    };
    ecosystem_default_candidate(candidates, "Cargo.toml", expected, select_build)
}

fn preferred_go_module_default_for_workflow_command(
    candidates: &[ImportedCommandCandidate],
    workflow_command: &str,
    select_build: bool,
) -> Option<(String, String, CommandSourceTier)> {
    if !is_less_canonical_go_workflow_command(workflow_command, select_build) {
        return None;
    }
    let expected = if select_build {
        "go build ./..."
    } else {
        "go test ./..."
    };
    ecosystem_default_candidate(candidates, "go.mod", expected, select_build)
}

fn ecosystem_default_candidate(
    candidates: &[ImportedCommandCandidate],
    manifest_path: &str,
    expected: &str,
    select_build: bool,
) -> Option<(String, String, CommandSourceTier)> {
    candidates.iter().find_map(|candidate| {
        (candidate.source_tier == CommandSourceTier::EcosystemDefault
            && candidate.source_path == manifest_path
            && if select_build {
                candidate.build.as_deref() == Some(expected)
            } else {
                candidate.test.as_deref() == Some(expected)
            })
        .then(|| {
            (
                expected.to_string(),
                candidate.source_path.clone(),
                candidate.source_tier,
            )
        })
    })
}

fn is_less_canonical_go_workflow_command(command: &str, select_build: bool) -> bool {
    let normalized = command.trim().trim_matches('\'').trim_matches('"');
    let (runner, canonical) = if select_build {
        ("go build", "go build ./...")
    } else {
        ("go test", "go test ./...")
    };
    if normalized == canonical || normalized == runner {
        return false;
    }
    // Any flagged invocation (-race, -coverprofile, -tags, ...) is a
    // CI-specialized variant of the module default, not the canonical
    // developer command.
    normalized.strip_prefix(runner).is_some_and(|rest| {
        rest.starts_with(char::is_whitespace)
            && rest.split_whitespace().any(|token| token.starts_with('-'))
    })
}

fn is_less_canonical_cargo_workflow_command(command: &str, select_build: bool) -> bool {
    let normalized = command.trim().trim_matches('\'').trim_matches('"');
    if select_build {
        return normalized == "cargo build";
    }
    if normalized == "cargo test" {
        return false;
    }
    normalized.starts_with("cargo test")
        && (contains_specializing_command_token(normalized) || normalized.contains("::"))
}

fn contains_specializing_command_token(command: &str) -> bool {
    command.split_whitespace().any(|token| {
        matches!(
            token,
            "--all-features"
                | "--bench"
                | "--benches"
                | "--bin"
                | "--bins"
                | "--doc"
                | "--example"
                | "--examples"
                | "--features"
                | "--no-default-features"
                | "--package"
                | "--target"
                | "--test"
                | "--tests"
                | "-f"
                | "-p"
        ) || token.starts_with("--features=")
            || token.starts_with("--package=")
            || token.starts_with("--target=")
            || token.starts_with("--test=")
    })
}

fn conflicting_cross_ecosystem_test_sources(
    candidates: &[ImportedCommandCandidate],
) -> Option<Vec<String>> {
    let node = candidates.iter().find(|candidate| {
        candidate.source_tier == CommandSourceTier::Manifest
            && candidate.source_path == "package.json"
            && candidate
                .test
                .as_deref()
                .is_some_and(is_node_package_test_command)
    })?;
    let python = candidates.iter().find(|candidate| {
        candidate.source_tier == CommandSourceTier::EcosystemDefault
            && matches!(
                candidate.source_path.as_str(),
                "pyproject.toml" | "setup.py" | "setup.cfg"
            )
            && candidate
                .test
                .as_deref()
                .is_some_and(is_python_test_command)
            && candidate.test != node.test
    })?;

    let mut source_paths = Vec::new();
    push_unique(&mut source_paths, node.source_path.clone());
    push_unique(&mut source_paths, python.source_path.clone());
    Some(source_paths)
}

fn is_node_package_test_command(command: &str) -> bool {
    matches!(
        command.trim(),
        "npm test" | "pnpm test" | "yarn test" | "bun test"
    )
}

fn is_python_test_command(command: &str) -> bool {
    matches!(
        command.trim(),
        "python -m pytest" | "python -m unittest discover" | "tox" | "nox"
    )
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

    if let Some((command, path)) = resolve_preferred_command_candidate(&present, select_build) {
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

fn resolve_preferred_command_candidate(
    present: &[(String, String)],
    select_build: bool,
) -> Option<(String, String)> {
    if present
        .iter()
        .all(|(_, path)| path.starts_with(".github/workflows/"))
    {
        return resolve_preferred_workflow_command_candidate(present);
    }

    if select_build {
        return resolve_preferred_ecosystem_default_build_candidate(present);
    }

    None
}

fn resolve_preferred_workflow_command_candidate(
    present: &[(String, String)],
) -> Option<(String, String)> {
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

fn resolve_preferred_ecosystem_default_build_candidate(
    present: &[(String, String)],
) -> Option<(String, String)> {
    let cargo = present
        .iter()
        .find(|(command, path)| path == "Cargo.toml" && command.starts_with("cargo build"))?;
    let only_cargo_and_generic_python_build = present.iter().all(|(command, path)| {
        (path == "Cargo.toml" && command.starts_with("cargo build"))
            || (path == "pyproject.toml" && command == "python -m build")
    });
    only_cargo_and_generic_python_build.then(|| (cargo.0.clone(), cargo.1.clone()))
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

    // Platform, packaging, and monorepo-slice workflows lose to generic CI when
    // two workflow-tier commands would otherwise conflict (e.g. units_test_cli
    // vs units_test_desktop, or ci-framework vs ci-binary-installer).
    const DEPRIORITIZED: &[&str] = &[
        "android",
        "ios",
        "windows",
        "macos",
        "freebsd",
        "desktop",
        "electron",
        "binary",
        "installer",
        "gcc",
        "clang",
        "cross",
        "release",
        "bindings",
        "packages",
        "preview",
        "apk",
        "docker",
        "helm",
        "npm",
        "nuget",
        "pypi",
        "crates",
        "openapi",
        "ui",
        "wasm",
        "nightly",
        "canary",
    ];
    let lower = file.to_ascii_lowercase();
    for (index, keyword) in DEPRIORITIZED.iter().enumerate() {
        if lower.contains(keyword) {
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
