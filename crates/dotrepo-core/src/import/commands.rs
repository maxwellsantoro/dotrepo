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

pub(super) fn load_first_root_file_with_extension(
    root: &Path,
    extension: &str,
) -> Result<Option<ImportedFile>> {
    let mut matches = fs::read_dir(root)
        .map_err(|err| anyhow!("failed to read {}: {}", root.display(), err))?
        .filter_map(|entry| entry.ok())
        .filter_map(|entry| {
            let path = entry.path();
            let file_name = path.file_name()?.to_str()?.to_string();
            let matches_extension = path
                .extension()
                .and_then(|value| value.to_str())
                .is_some_and(|value| value.eq_ignore_ascii_case(extension));
            (path.is_file() && matches_extension).then_some((file_name, path))
        })
        .collect::<Vec<_>>();
    matches.sort_by(|left, right| left.0.cmp(&right.0));

    let Some((file_name, path)) = matches.into_iter().next() else {
        return Ok(None);
    };
    let contents = fs::read_to_string(&path)
        .map_err(|err| anyhow!("failed to read {}: {}", path.display(), err))?;
    Ok(Some(ImportedFile {
        path: file_name,
        contents,
    }))
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
    if let Some(candidate) = sources.setup_py.and_then(infer_setup_py_commands) {
        candidates.push(candidate);
    }
    if let Some(candidate) = sources.setup_cfg.and_then(infer_setup_cfg_commands) {
        candidates.push(candidate);
    }
    if let Some(candidate) = sources.go_mod.and_then(infer_go_module_commands) {
        candidates.push(candidate);
    }
    if let Some(candidate) = sources.pom_xml.and_then(infer_maven_commands) {
        candidates.push(candidate);
    }
    if let Some(candidate) = sources.build_gradle.and_then(infer_gradle_commands) {
        candidates.push(candidate);
    }
    if let Some(candidate) = sources.composer_json.and_then(infer_composer_commands) {
        candidates.push(candidate);
    }
    if let Some(candidate) = sources.csproj.and_then(infer_dotnet_commands) {
        candidates.push(candidate);
    }
    if let Some(candidate) = sources.mix_exs.and_then(infer_mix_commands) {
        candidates.push(candidate);
    }
    if let Some(candidate) = sources.rebar_config.and_then(infer_rebar_commands) {
        candidates.push(candidate);
    }
    if let Some(candidate) = sources
        .cmake_presets_json
        .and_then(infer_cmake_workflow_commands)
    {
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
    if let Some(candidate) = sources.rakefile.and_then(infer_rakefile_commands) {
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

    let build = pick_node_script_command(scripts, &["build", "compile", "dist", "bundle"], || {
        runner.build_command()
    });
    let test =
        pick_node_script_command(scripts, &["test"], || runner.test_command()).filter(|_| {
            scripts
                .get("test")
                .and_then(serde_json::Value::as_str)
                .is_none_or(|v| !is_placeholder_package_json_test_script(v))
        });

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

fn infer_setup_py_test_command(contents: &str) -> Option<String> {
    let lower = contents.to_ascii_lowercase();
    // Conservative: only claim test when the runner is identifiable.
    // Avoid claiming build from setup.py (often just package metadata).
    if lower.contains("pytest") {
        return Some("python -m pytest".into());
    }
    if lower.contains("unittest") || lower.contains("test_suite") {
        return Some("python -m unittest discover".into());
    }
    None
}

fn infer_setup_py_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let test = infer_setup_py_test_command(&file.contents)?;
    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::Manifest,
        build: None,
        test: Some(test),
    })
}

fn infer_setup_cfg_test_command(contents: &str) -> Option<String> {
    let mut current_section: Option<String> = None;
    let mut has_pytest_section = false;
    let mut has_test_extras_pytest = false;
    let mut has_test_suite = false;

    for line in contents.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with('[') && trimmed.ends_with(']') {
            let section = trimmed[1..trimmed.len() - 1].trim().to_ascii_lowercase();
            has_pytest_section |= section == "tool:pytest" || section == "pytest";
            current_section = Some(section);
            continue;
        }
        if trimmed.is_empty() || trimmed.starts_with('#') || trimmed.starts_with(';') {
            continue;
        }
        let Some(section) = current_section.as_ref() else {
            continue;
        };
        let Some((key, value)) = trimmed.split_once('=') else {
            continue;
        };
        let key = key.trim().to_ascii_lowercase();
        let value = value.trim().to_ascii_lowercase();
        match section.as_str() {
            "options" | "metadata" if key == "test_suite" => has_test_suite = true,
            "options.extras_require"
                if (key == "test" || key == "testing") && value.contains("pytest") =>
            {
                has_test_extras_pytest = true;
            }
            _ => {}
        }
    }

    if has_pytest_section || has_test_extras_pytest {
        Some("python -m pytest".into())
    } else if has_test_suite {
        Some("python -m unittest discover".into())
    } else {
        None
    }
}

fn infer_setup_cfg_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let test = infer_setup_cfg_test_command(&file.contents)?;
    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::Manifest,
        build: None,
        test: Some(test),
    })
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

fn infer_maven_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let document = roxmltree::Document::parse(&file.contents).ok()?;
    if document.root_element().tag_name().name() != "project" {
        return None;
    }

    // Prefer the executable Maven wrapper when present in real repositories
    // (common for reproducible builds). The inference here is based on the
    // pom alone; workflow inference will surface the actual CI command used.
    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::Manifest,
        build: Some("./mvnw package".into()),
        test: Some("./mvnw test".into()),
    })
}

pub(crate) fn infer_gradle_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    // Simple presence check for Gradle build files (Groovy or Kotlin DSL).
    // We prefer the Gradle wrapper for the same reproducibility reasons as Maven.
    // A more sophisticated parser could look inside for tasks, but presence + standard
    // wrapper commands is sufficient for the majority of projects.
    let name = file.path.to_ascii_lowercase();
    if !name.ends_with("build.gradle") && !name.ends_with("build.gradle.kts") {
        return None;
    }

    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::Manifest,
        build: Some("./gradlew build".into()),
        test: Some("./gradlew test".into()),
    })
}

fn infer_composer_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let parsed: serde_json::Value = serde_json::from_str(&file.contents).ok()?;
    let scripts = parsed
        .get("scripts")
        .and_then(serde_json::Value::as_object)?;
    let build = scripts
        .get("build")
        .filter(|value| has_nonempty_composer_script(value))
        .map(|_| "composer run-script build".to_string());
    let test = scripts
        .get("test")
        .filter(|value| has_nonempty_composer_script(value))
        .map(|_| "composer run-script test".to_string());

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

fn has_nonempty_composer_script(value: &serde_json::Value) -> bool {
    match value {
        serde_json::Value::String(script) => !script.trim().is_empty(),
        serde_json::Value::Array(scripts) => scripts.iter().any(|script| {
            script
                .as_str()
                .is_some_and(|script| !script.trim().is_empty())
        }),
        _ => false,
    }
}

fn infer_dotnet_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let document = roxmltree::Document::parse(&file.contents).ok()?;
    if document.root_element().tag_name().name() != "Project" {
        return None;
    }

    let is_test_project = document.descendants().any(|node| {
        node.is_element()
            && node.tag_name().name() == "IsTestProject"
            && node
                .text()
                .is_some_and(|value| value.trim().eq_ignore_ascii_case("true"))
    });
    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::Manifest,
        build: Some("dotnet build".into()),
        test: is_test_project.then(|| "dotnet test".into()),
    })
}

fn infer_mix_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let lines = file
        .contents
        .lines()
        .map(|line| line.split('#').next().unwrap_or("").trim())
        .filter(|line| !line.is_empty())
        .collect::<Vec<_>>();
    let has_module = lines.iter().any(|line| line.starts_with("defmodule "));
    let uses_mix_project = lines
        .iter()
        .any(|line| *line == "use Mix.Project" || line.starts_with("use Mix.Project,"));
    let has_project_function = lines
        .iter()
        .any(|line| line.starts_with("def project do") || line.starts_with("def project,"));
    if !(has_module && uses_mix_project && has_project_function) {
        return None;
    }

    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::Manifest,
        build: Some("mix compile".into()),
        test: Some("mix test".into()),
    })
}

fn infer_rebar_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let has_config_term = file.contents.lines().any(|line| {
        let line = line.split('%').next().unwrap_or("").trim();
        line.starts_with('{') && line.ends_with("}.")
    });
    if !has_config_term {
        return None;
    }

    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::Manifest,
        build: Some("rebar3 compile".into()),
        test: Some("rebar3 eunit".into()),
    })
}

fn infer_cmake_workflow_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let parsed: serde_json::Value = serde_json::from_str(&file.contents).ok()?;
    if parsed
        .get("version")
        .and_then(serde_json::Value::as_u64)
        .is_none_or(|version| version < 6)
    {
        return None;
    }
    let workflows = parsed
        .get("workflowPresets")
        .and_then(serde_json::Value::as_array)?;

    let build_name = workflows
        .iter()
        .find(|workflow| {
            cmake_workflow_has_steps(workflow, &["configure", "build"])
                && !cmake_workflow_has_step(workflow, "test")
        })
        .or_else(|| {
            workflows
                .iter()
                .find(|workflow| cmake_workflow_has_steps(workflow, &["configure", "build"]))
        })
        .and_then(cmake_workflow_name);
    let test_name = workflows
        .iter()
        .find(|workflow| cmake_workflow_has_steps(workflow, &["configure", "build", "test"]))
        .and_then(cmake_workflow_name);

    if build_name.is_none() && test_name.is_none() {
        return None;
    }
    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::Manifest,
        build: build_name.map(|name| format!("cmake --workflow --preset {name}")),
        test: test_name.map(|name| format!("cmake --workflow --preset {name}")),
    })
}

fn cmake_workflow_name(workflow: &serde_json::Value) -> Option<&str> {
    workflow
        .get("name")
        .and_then(serde_json::Value::as_str)
        .filter(|name| {
            !name.is_empty()
                && name
                    .chars()
                    .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '-' | '_' | '.' | '+'))
        })
}

fn cmake_workflow_has_steps(workflow: &serde_json::Value, required: &[&str]) -> bool {
    required
        .iter()
        .all(|required| cmake_workflow_has_step(workflow, required))
}

fn cmake_workflow_has_step(workflow: &serde_json::Value, required: &str) -> bool {
    workflow
        .get("steps")
        .and_then(serde_json::Value::as_array)
        .is_some_and(|steps| {
            steps.iter().any(|step| {
                step.get("type").and_then(serde_json::Value::as_str) == Some(required)
                    && step
                        .get("name")
                        .and_then(serde_json::Value::as_str)
                        .is_some_and(|name| !name.trim().is_empty())
            })
        })
}

fn infer_makefile_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let mut has_build = false;
    let mut has_test = false;
    for line in file.contents.lines() {
        // Makefile targets are defined at the start of a line (column 0).
        // Recipe bodies are indented (tab or spaces) and may contain ":" in
        // shell expansions like ":-" or "$(var:pat=rep)".
        if line.starts_with(|c: char| c.is_whitespace()) {
            continue;
        }
        let trimmed = line.trim();
        // Common explicit targets (allow "target:" or "target :" forms)
        let target_name = trimmed
            .split_once(':')
            .map(|(lhs, _)| lhs.trim().to_ascii_lowercase());
        if let Some(name) = target_name {
            if ["build", "all", "compile", "dist", "package", "ci"]
                .iter()
                .any(|t| name == *t || name.starts_with(&format!("{}-", t)))
            {
                has_build = true;
            }
            if ["test", "check", "verify", "spec"]
                .iter()
                .any(|t| name == *t || name.starts_with(&format!("{}-", t)))
            {
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

fn infer_rakefile_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let has_build = file
        .contents
        .lines()
        .any(|line| declares_rake_task(line, "build"));
    let has_test = file
        .contents
        .lines()
        .any(|line| declares_rake_task(line, "test"));
    if !has_build && !has_test {
        return None;
    }

    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::TaskScript,
        build: has_build.then(|| "rake build".into()),
        test: has_test.then(|| "rake test".into()),
    })
}

fn declares_rake_task(line: &str, name: &str) -> bool {
    let line = line.split('#').next().unwrap_or("").trim();
    let Some(rest) = line.strip_prefix("task ").map(str::trim_start) else {
        return false;
    };
    let prefixes = [
        format!(":{name}"),
        format!("\"{name}\""),
        format!("'{name}'"),
        format!("{name}:"),
    ];
    prefixes.iter().any(|prefix| {
        rest.strip_prefix(prefix).is_some_and(|suffix| {
            suffix.is_empty()
                || suffix
                    .chars()
                    .next()
                    .is_some_and(|ch| ch.is_whitespace() || matches!(ch, ',' | '=' | '{'))
        })
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

fn looks_like_shell_assignment(command: &str) -> bool {
    let trimmed = command.trim();
    if trimmed.is_empty() {
        return false;
    }
    let without_export = trimmed.strip_prefix("export ").unwrap_or(trimmed).trim();
    without_export.contains('=') && !without_export.contains(' ')
}

fn first_matching_workflow_command(commands: &[String], select_build: bool) -> Option<String> {
    commands.iter().find_map(|command| {
        let trimmed = command.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') || looks_like_shell_assignment(trimmed) {
            return None;
        }

        // Direct clean prefixes (preserve previous behavior for simple cases)
        if select_build {
            for prefix in [
                "bazel build",
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
                "bazel test",
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

        // Flexible capture for real CI usage: compound commands, wrappers, flags.
        // Return the full line when it contains a recognizable build/test invocation.
        let lower = trimmed.to_ascii_lowercase();
        if select_build {
            if lower.contains(" mvnw")
                || lower.contains("./mvnw")
                || (lower.contains("mvn ") && lower.contains("package")
                    || lower.contains("compile"))
            {
                return Some(trimmed.to_string());
            }
            if lower.contains("gradlew")
                || lower.contains("gradle ")
                    && (lower.contains("build") || lower.contains("assemble"))
            {
                return Some(trimmed.to_string());
            }
            if lower.contains("npm ") && lower.contains("build") {
                return Some(trimmed.to_string());
            }
            if lower.contains("pnpm ") && lower.contains("build") {
                return Some(trimmed.to_string());
            }
            if lower.contains("yarn ") && lower.contains("build") {
                return Some(trimmed.to_string());
            }
            if lower.contains("bazel ") && lower.contains("build") {
                return Some(trimmed.to_string());
            }
            if lower.contains("make ")
                && (lower.contains(" build")
                    || lower.trim_start().starts_with("make build")
                    || lower.contains(" all"))
            {
                return Some(trimmed.to_string());
            }
            if lower.starts_with("make ") && lower.contains("build") {
                return Some(trimmed.to_string());
            }
        } else {
            if lower.contains("bazel ") && lower.contains("test") {
                return Some(trimmed.to_string());
            }
            if lower.contains(" mvnw")
                || lower.contains("./mvnw")
                || (lower.contains("mvn ") && lower.contains("test"))
            {
                return Some(trimmed.to_string());
            }
            if lower.contains("gradlew") || (lower.contains("gradle ") && lower.contains("test")) {
                return Some(trimmed.to_string());
            }
            if (lower.contains("npm ")
                || lower.contains("pnpm ")
                || lower.contains("yarn ")
                || lower.contains("bun "))
                && (lower.contains(" test") || lower.contains("test "))
            {
                return Some(trimmed.to_string());
            }
            if lower.contains("make ") && (lower.contains(" test") || lower.contains("check")) {
                return Some(trimmed.to_string());
            }
            if lower.starts_with("make ") && (lower.contains("test") || lower.contains("check")) {
                return Some(trimmed.to_string());
            }
            if lower.contains("cargo test")
                || lower.contains("go test")
                || lower.contains("pytest")
                || lower.trim() == "pytest"
            {
                return Some(trimmed.to_string());
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

/// Return a runner-wrapped command if any of the candidate script names exists and is non-empty.
fn pick_node_script_command(
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
        assert!(sanitize_import_command("cargo test; curl attacker").is_none());
        assert!(sanitize_import_command("cargo test && rm -rf /").is_none());
        assert!(sanitize_import_command("cargo test | sh").is_none());
        assert!(sanitize_import_command("cargo test > /tmp/out").is_none());
    }

    #[test]
    fn workflow_inference_skips_shell_assignments_and_prefers_bazel_build() {
        use super::{
            extract_workflow_run_commands, first_matching_workflow_command,
            infer_workflow_commands, ImportedFile,
        };

        let workflow = ImportedFile {
            path: ".github/workflows/bazel.yml".into(),
            contents: r#"
jobs:
  build:
    steps:
      - run: bazel_wrapper_args+=(--windows-cross-compile)
      - run: bazel build //...
"#
            .into(),
        };

        let commands = extract_workflow_run_commands(&workflow.contents);
        assert_eq!(commands.len(), 2);
        assert!(first_matching_workflow_command(&["# setup only".to_string()], true).is_none());
        assert_eq!(
            first_matching_workflow_command(&commands, true).as_deref(),
            Some("bazel build //...")
        );

        let candidate = infer_workflow_commands(&workflow).expect("workflow");
        assert_eq!(candidate.build.as_deref(), Some("bazel build //..."));
    }

    #[test]
    fn workflow_and_makefile_inference_improvements_do_not_regress_safety() {
        // The improvements to workflow matching and makefile target detection
        // must continue to respect sanitize_import_command. Compound shell is
        // rejected (defense in depth); clean tool invocations are kept.
        assert!(sanitize_import_command("./mvnw -B package").is_some());
        assert!(sanitize_import_command("make test").is_some());
        assert!(sanitize_import_command("pnpm test").is_some());
        assert!(sanitize_import_command("npm ci && npm run build").is_none());
    }

    #[test]
    fn infer_gradle_commands_detects_presence_and_prefers_wrapper() {
        use super::{infer_gradle_commands, ImportedFile};
        let groovy = ImportedFile {
            path: "build.gradle".into(),
            contents: "plugins { id 'java' }".into(),
        };
        let kts = ImportedFile {
            path: "build.gradle.kts".into(),
            contents: "plugins { java }".into(),
        };
        let g1 = infer_gradle_commands(&groovy).expect("groovy");
        let g2 = infer_gradle_commands(&kts).expect("kts");
        assert_eq!(g1.build.as_deref(), Some("./gradlew build"));
        assert_eq!(g2.test.as_deref(), Some("./gradlew test"));
    }

    #[test]
    fn infer_setup_commands_provide_pytest_for_classic_python() {
        use super::{infer_setup_cfg_commands, infer_setup_py_commands, ImportedFile};
        let setup_py = ImportedFile {
            path: "setup.py".into(),
            contents: "from setuptools import setup\nsetup(tests_require=['pytest'])".into(),
        };
        let setup_cfg = ImportedFile {
            path: "setup.cfg".into(),
            contents: "[tool:pytest]\naddopts = -q".into(),
        };
        let p = infer_setup_py_commands(&setup_py).expect("setup.py");
        let c = infer_setup_cfg_commands(&setup_cfg).expect("setup.cfg");
        assert_eq!(p.test.as_deref(), Some("python -m pytest"));
        assert_eq!(c.test.as_deref(), Some("python -m pytest"));
    }

    #[test]
    fn infer_setup_py_abstains_without_test_signals() {
        use super::{infer_setup_py_commands, infer_setup_py_test_command, ImportedFile};
        let minimal = ImportedFile {
            path: "setup.py".into(),
            contents: "from setuptools import setup\nsetup(name='demo')".into(),
        };
        let contest = ImportedFile {
            path: "setup.py".into(),
            contents: "from setuptools import setup\nsetup(name='contest-kit')".into(),
        };
        assert!(infer_setup_py_test_command(&minimal.contents).is_none());
        assert!(infer_setup_py_test_command(&contest.contents).is_none());
        assert!(infer_setup_py_commands(&minimal).is_none());
        assert!(infer_setup_py_commands(&contest).is_none());
    }

    #[test]
    fn infer_setup_py_prefers_unittest_when_pytest_is_absent() {
        use super::{infer_setup_py_commands, ImportedFile};
        let setup_py = ImportedFile {
            path: "setup.py".into(),
            contents: "from setuptools import setup\nsetup(test_suite='tests')".into(),
        };
        let candidate = infer_setup_py_commands(&setup_py).expect("setup.py");
        assert_eq!(
            candidate.test.as_deref(),
            Some("python -m unittest discover")
        );
    }

    #[test]
    fn infer_setup_cfg_abstains_on_unrelated_test_substrings() {
        use super::{infer_setup_cfg_commands, infer_setup_cfg_test_command, ImportedFile};
        let metadata_only = ImportedFile {
            path: "setup.cfg".into(),
            contents: "[metadata]\nname = latest-contest-kit\n".into(),
        };
        assert!(infer_setup_cfg_test_command(&metadata_only.contents).is_none());
        assert!(infer_setup_cfg_commands(&metadata_only).is_none());
    }

    #[test]
    fn infer_setup_cfg_detects_extras_require_test_pytest() {
        use super::{infer_setup_cfg_commands, ImportedFile};
        let setup_cfg = ImportedFile {
            path: "setup.cfg".into(),
            contents: "[options.extras_require]\ntest = pytest>=7\n".into(),
        };
        let candidate = infer_setup_cfg_commands(&setup_cfg).expect("setup.cfg");
        assert_eq!(candidate.test.as_deref(), Some("python -m pytest"));
    }

    #[test]
    fn pyproject_tox_conflicts_with_setup_py_pytest_instead_of_losing() {
        use super::{infer_imported_commands, ImportedFile};
        use crate::import::ImportSources;

        let pyproject = ImportedFile {
            path: "pyproject.toml".into(),
            contents: "[build-system]\nrequires = [\"setuptools\"]\n[tool.tox]\n".into(),
        };
        let setup_py = ImportedFile {
            path: "setup.py".into(),
            contents: "from setuptools import setup\nsetup(tests_require=['pytest'])".into(),
        };

        let result = infer_imported_commands(&ImportSources {
            cargo_toml: None,
            package_json: None,
            pyproject_toml: Some(&pyproject),
            setup_py: Some(&setup_py),
            setup_cfg: None,
            go_mod: None,
            pom_xml: None,
            build_gradle: None,
            composer_json: None,
            csproj: None,
            mix_exs: None,
            rebar_config: None,
            cmake_presets_json: None,
            makefile: None,
            justfile: None,
            rakefile: None,
            contributing: None,
            workflow_files: &[],
        });

        assert!(
            result.test.is_none(),
            "pyproject tox and setup.py pytest should conflict: {:?}",
            result.test
        );
        assert!(
            result.notes.iter().any(|note| note.contains("conflicting")),
            "expected conflict note, got: {:?}",
            result.notes
        );
    }
}
