//! Ecosystem-specific build/test command *extraction*: locating candidate
//! commands from language/build-tool manifests (Cargo.toml, package.json,
//! pyproject.toml, go.mod, Maven/Gradle, Composer, .csproj, Mix, Rebar,
//! CMakePresets.json, Makefiles/justfiles/Rakefiles, CONTRIBUTING.md, and
//! GitHub Actions workflow files). Ranking/safety policy for the resulting
//! candidates lives in `policy`.
use super::super::types::{CommandSourceTier, ImportedCommandCandidate, ImportedFile};
use super::policy::{
    detect_node_package_runner, is_placeholder_package_json_test_script, pick_node_script_command,
};
use crate::util::contains_unsafe_shell_like_value;

pub(crate) fn infer_cargo_manifest_commands(
    file: &ImportedFile,
) -> Option<ImportedCommandCandidate> {
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
        source_tier: CommandSourceTier::EcosystemDefault,
        build: Some(build.into()),
        test: Some(test.into()),
    })
}

pub(crate) fn infer_package_json_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
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
        source_tier: CommandSourceTier::EcosystemDefault,
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

pub(crate) fn infer_setup_py_test_command(contents: &str) -> Option<String> {
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

pub(crate) fn infer_setup_py_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let test = infer_setup_py_test_command(&file.contents)?;
    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::EcosystemDefault,
        build: None,
        test: Some(test),
    })
}

/// Classic `tox.ini` is the strongest honest signal for multi-env Python tests.
pub(crate) fn infer_tox_ini_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let mut has_tox = false;
    let mut has_testenv = false;
    for line in file.contents.lines() {
        let trimmed = line.trim();
        if !trimmed.starts_with('[') || !trimmed.ends_with(']') {
            continue;
        }
        let section = trimmed[1..trimmed.len() - 1]
            .split(':')
            .next()
            .unwrap_or("")
            .trim()
            .to_ascii_lowercase();
        has_tox |= section == "tox";
        has_testenv |= section == "testenv" || section.starts_with("testenv");
    }
    if !has_tox && !has_testenv {
        return None;
    }
    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::Manifest,
        build: None,
        test: Some("tox".into()),
    })
}

pub(crate) fn infer_setup_cfg_test_command(contents: &str) -> Option<String> {
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

pub(crate) fn infer_setup_cfg_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let test = infer_setup_cfg_test_command(&file.contents)?;
    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::EcosystemDefault,
        build: None,
        test: Some(test),
    })
}

pub(crate) fn infer_go_module_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
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
        source_tier: CommandSourceTier::EcosystemDefault,
        build: Some("go build ./...".into()),
        test: Some("go test ./...".into()),
    })
}

pub(crate) fn infer_maven_commands(
    file: &ImportedFile,
    has_wrapper: bool,
) -> Option<ImportedCommandCandidate> {
    let document = roxmltree::Document::parse(&file.contents).ok()?;
    if document.root_element().tag_name().name() != "project" {
        return None;
    }

    // Prefer the executable Maven wrapper when present in real repositories
    // (common for reproducible builds). The inference here is based on the
    // pom alone; workflow inference will surface the actual CI command used.
    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::EcosystemDefault,
        build: Some(
            if has_wrapper {
                "./mvnw package"
            } else {
                "mvn package"
            }
            .into(),
        ),
        test: Some(
            if has_wrapper {
                "./mvnw test"
            } else {
                "mvn test"
            }
            .into(),
        ),
    })
}

pub(crate) fn infer_gradle_commands(
    file: &ImportedFile,
    has_wrapper: bool,
) -> Option<ImportedCommandCandidate> {
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
        source_tier: CommandSourceTier::EcosystemDefault,
        build: Some(
            if has_wrapper {
                "./gradlew build"
            } else {
                "gradle build"
            }
            .into(),
        ),
        test: Some(
            if has_wrapper {
                "./gradlew test"
            } else {
                "gradle test"
            }
            .into(),
        ),
    })
}

pub(crate) fn infer_composer_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
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

pub(crate) fn infer_dotnet_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let lower = file.path.to_ascii_lowercase();
    if lower.ends_with(".sln") {
        // Solution files are the primary entrypoint for many .NET monorepos.
        return Some(ImportedCommandCandidate {
            source_path: file.path.clone(),
            source_tier: CommandSourceTier::EcosystemDefault,
            build: Some("dotnet build".into()),
            test: Some("dotnet test".into()),
        });
    }

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
    }) || lower.contains(".tests.")
        || lower.ends_with("tests.csproj")
        || lower.ends_with("test.csproj");
    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::EcosystemDefault,
        build: Some("dotnet build".into()),
        // Non-test projects still use `dotnet test` at solution/repo scope in
        // common workflows; keep test only when the project itself is a test
        // assembly so we do not invent coverage for pure libraries.
        test: is_test_project.then(|| "dotnet test".into()),
    })
}

pub(crate) fn infer_mix_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
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
        source_tier: CommandSourceTier::EcosystemDefault,
        build: Some("mix compile".into()),
        test: Some("mix test".into()),
    })
}

pub(crate) fn infer_rebar_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let has_config_term = file.contents.lines().any(|line| {
        let line = line.split('%').next().unwrap_or("").trim();
        line.starts_with('{') && line.ends_with("}.")
    });
    if !has_config_term {
        return None;
    }

    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::EcosystemDefault,
        build: Some("rebar3 compile".into()),
        test: Some("rebar3 eunit".into()),
    })
}

pub(crate) fn infer_cmake_workflow_commands(
    file: &ImportedFile,
) -> Option<ImportedCommandCandidate> {
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

pub(crate) fn infer_makefile_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let targets = parse_makefile_targets(&file.contents);
    // The published command must name a target the Makefile actually
    // declares. A `ci:` pipeline target or a prefixed variant like
    // `test-readme:` is not a canonical build/test entrypoint and must not
    // be rewritten to a `build`/`test` target that does not exist. If the
    // target is a single safe canonical command wearing a Make wrapper, publish
    // the underlying command; otherwise keep the wrapper as the audited
    // entrypoint.
    let pick = |names: &[&str], select_build: bool| {
        names.iter().find_map(|name| {
            let target = targets.iter().find(|target| target.name == *name)?;
            simple_task_script_command(&target.commands, select_build)
                .or_else(|| Some(format!("make {}", target.name)))
        })
    };
    let build = pick(&["build", "all", "compile", "dist", "package"], true);
    let test = pick(&["test", "check", "verify", "spec"], false);
    if build.is_none() && test.is_none() {
        return None;
    }
    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::TaskScript,
        build,
        test,
    })
}

pub(crate) fn infer_justfile_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    let recipes = parse_justfile_recipes(&file.contents);
    // Publish the recipe name that actually exists rather than assuming a
    // `build`/`test` recipe. As with Makefiles, unwrap only one-line recipes
    // that are themselves safe canonical developer commands.
    let pick = |names: &[&str], select_build: bool| {
        names.iter().find_map(|name| {
            let recipe = recipes.iter().find(|recipe| recipe.name == *name)?;
            simple_task_script_command(&recipe.commands, select_build)
                .or_else(|| Some(format!("just {}", recipe.name)))
        })
    };
    let build = pick(&["build", "all"], true);
    let test = pick(&["test", "check"], false);
    if build.is_none() && test.is_none() {
        return None;
    }
    Some(ImportedCommandCandidate {
        source_path: file.path.clone(),
        source_tier: CommandSourceTier::TaskScript,
        build,
        test,
    })
}

#[derive(Debug, Clone)]
struct TaskScriptTarget {
    name: String,
    commands: Vec<String>,
}

fn parse_makefile_targets(contents: &str) -> Vec<TaskScriptTarget> {
    let mut targets: Vec<TaskScriptTarget> = Vec::new();
    let mut active_target_indices: Vec<usize> = Vec::new();

    for line in contents.lines() {
        // Makefile targets are defined at the start of a line (column 0).
        // Recipe bodies are indented (tab or spaces) and may contain ":" in
        // shell expansions like ":-" or "$(var:pat=rep)".
        if line.starts_with(|c: char| c.is_whitespace()) {
            if active_target_indices.is_empty() {
                continue;
            }
            if let Some(command) = normalize_task_script_recipe_line(line) {
                for index in &active_target_indices {
                    targets[*index].commands.push(command.clone());
                }
            }
            continue;
        }

        active_target_indices.clear();
        let Some((lhs, rhs)) = line.trim().split_once(':') else {
            continue;
        };
        // Variable assignments and special directives are not executable
        // targets, even if they contain a colon.
        if lhs.contains('=') || lhs.trim_start().starts_with('.') {
            continue;
        }

        for name in lhs.split_whitespace() {
            let normalized = name.to_ascii_lowercase();
            let index = targets.len();
            targets.push(TaskScriptTarget {
                name: normalized,
                commands: Vec::new(),
            });
            active_target_indices.push(index);
        }

        if let Some((_, inline_command)) = rhs.split_once(';') {
            if let Some(command) = normalize_task_script_recipe_line(inline_command) {
                for index in &active_target_indices {
                    targets[*index].commands.push(command.clone());
                }
            }
        }
    }

    targets
}

fn parse_justfile_recipes(contents: &str) -> Vec<TaskScriptTarget> {
    let mut recipes: Vec<TaskScriptTarget> = Vec::new();
    let mut active_recipe: Option<usize> = None;

    for line in contents.lines() {
        if line.starts_with(|c: char| c.is_whitespace()) {
            let Some(index) = active_recipe else {
                continue;
            };
            if let Some(command) = normalize_task_script_recipe_line(line) {
                recipes[index].commands.push(command);
            }
            continue;
        }

        active_recipe = None;
        let trimmed = line.trim();
        // Skip ':=' assignments, aliases/settings/attributes, comments, and
        // private helper recipes. Private helpers can still be called through a
        // public wrapper, but they should not define top-level build/test facts.
        if trimmed.is_empty()
            || trimmed.starts_with('#')
            || trimmed.contains(":=")
            || trimmed.starts_with('[')
            || trimmed.starts_with("alias ")
            || trimmed.starts_with('_')
        {
            continue;
        }
        let Some(colon_pos) = trimmed.find(':') else {
            continue;
        };
        let lhs = trimmed[..colon_pos].trim();
        if lhs.contains('=') || lhs.is_empty() {
            continue;
        }
        // Recipes may include parameters: "name arg:". The first token is the
        // command users type.
        let Some(name) = lhs.split_whitespace().next() else {
            continue;
        };
        let normalized = name.to_ascii_lowercase();
        let index = recipes.len();
        recipes.push(TaskScriptTarget {
            name: normalized,
            commands: Vec::new(),
        });
        active_recipe = Some(index);
    }

    recipes
}

fn normalize_task_script_recipe_line(line: &str) -> Option<String> {
    let mut trimmed = line.trim();
    while let Some(rest) = trimmed.strip_prefix(['@', '-', '+']) {
        trimmed = rest.trim_start();
    }
    normalize_documented_command_line(trimmed)
}

fn simple_task_script_command(commands: &[String], select_build: bool) -> Option<String> {
    let [command] = commands else {
        return None;
    };
    if contains_unsafe_shell_like_value(command) {
        return None;
    }
    if select_build {
        documented_build_command(command)
    } else {
        documented_test_command(command)
    }
}

pub(crate) fn infer_rakefile_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
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

pub(crate) fn infer_contributing_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    infer_markdown_doc_commands(file)
}

pub(crate) fn infer_readme_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    infer_markdown_doc_commands(file)
}

fn infer_markdown_doc_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    // Look for build/test instructions in fenced code blocks. This intentionally
    // avoids prose-only guesses and user-facing examples that are not standard
    // development commands.
    let mut build: Option<String> = None;
    let mut test: Option<String> = None;
    let mut in_code_block = false;
    let mut current_heading = String::new();
    for line in file.contents.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with("```") || trimmed.starts_with("~~~") {
            in_code_block = !in_code_block;
            continue;
        }
        if !in_code_block {
            if let Some(heading) = markdown_heading_text(trimmed) {
                current_heading = heading;
            }
            continue;
        }
        let Some(command) = normalize_documented_command_line(trimmed) else {
            continue;
        };
        if build.is_none() && doc_heading_allows_command(&current_heading, true) {
            build = documented_build_command(&command);
        }
        if test.is_none() && doc_heading_allows_command(&current_heading, false) {
            test = documented_test_command(&command);
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

fn markdown_heading_text(line: &str) -> Option<String> {
    let heading = line.strip_prefix('#')?.trim_start_matches('#').trim();
    (!heading.is_empty()).then(|| heading.to_ascii_lowercase())
}

fn doc_heading_allows_command(heading: &str, select_build: bool) -> bool {
    let development = heading.contains("develop") || heading.contains("contribut");
    if select_build {
        development || heading.contains("build") || heading.contains("compile")
    } else {
        development
            || heading.contains("test")
            || heading.contains("check")
            || heading.contains("validation")
    }
}

fn normalize_documented_command_line(line: &str) -> Option<String> {
    let mut trimmed = line.trim();
    if trimmed.is_empty() || trimmed.starts_with('#') {
        return None;
    }
    for prompt in ["$", ">", "%", "❯"] {
        if let Some(rest) = trimmed.strip_prefix(prompt) {
            trimmed = rest.trim_start();
            break;
        }
    }
    if trimmed.starts_with("cd ") || trimmed == "cd" {
        return None;
    }

    let mut parts = trimmed.split_whitespace().collect::<Vec<_>>();
    if parts.first().is_some_and(|part| *part == "env") {
        parts.remove(0);
    }
    while parts
        .first()
        .is_some_and(|part| is_env_assignment_token(part))
    {
        parts.remove(0);
    }
    if parts.is_empty() {
        return None;
    }
    let command = parts.join(" ");
    Some(strip_trailing_shell_comment(&command).to_string())
}

fn strip_trailing_shell_comment(command: &str) -> &str {
    command
        .split_once(" #")
        .map(|(before, _)| before.trim_end())
        .unwrap_or(command)
}

fn is_env_assignment_token(token: &str) -> bool {
    let Some((name, value)) = token.split_once('=') else {
        return false;
    };
    !name.is_empty()
        && !value.is_empty()
        && name
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || ch == '_')
        && name
            .chars()
            .next()
            .is_some_and(|ch| ch.is_ascii_alphabetic() || ch == '_')
}

fn is_package_narrowed_go_test_example(command: &str) -> bool {
    let Some(rest) = command.strip_prefix("go test") else {
        return false;
    };
    if !rest.is_empty() && !rest.starts_with(char::is_whitespace) {
        return false;
    }
    rest.split_whitespace()
        .any(|token| (token.starts_with("./") || token.starts_with("../")) && token != "./...")
}

/// Documented cargo commands may pin a toolchain (`cargo +nightly test ...`).
/// Prefix matching must see the plain subcommand; the published command keeps
/// the maintainer's exact toolchain override.
fn without_cargo_toolchain_override(command: &str) -> Option<String> {
    let rest = command.strip_prefix("cargo +")?;
    let tail = rest.split_once(char::is_whitespace)?.1;
    Some(format!("cargo {}", tail.trim_start()))
}

fn documented_build_command(command: &str) -> Option<String> {
    let stripped = without_cargo_toolchain_override(command);
    let matchable = stripped.as_deref().unwrap_or(command);
    for prefix in [
        "bazel build",
        "cargo build",
        "go build",
        "python -m build",
        "npm run build",
        "pnpm build",
        "yarn build",
        "bun run build",
        "make build",
        "make all",
        "just build",
    ] {
        if starts_with_command_prefix(matchable, prefix) {
            return Some(command.to_string());
        }
    }
    (command == "make").then(|| "make".to_string())
}

fn documented_test_command(command: &str) -> Option<String> {
    let stripped = without_cargo_toolchain_override(command);
    let matchable = stripped.as_deref().unwrap_or(command);
    if starts_with_command_prefix(matchable, "cargo nextest run") {
        // Documentation often shows a selector-specific nextest invocation
        // immediately after recommending nextest. Publish the runner command,
        // not the example's one-test selector.
        return Some("cargo nextest run".to_string());
    }
    if is_package_narrowed_go_test_example(matchable) {
        // A documented `go test` narrowed to one package (e.g.
        // `go test ./internal/datanode -cover`) is a walkthrough example,
        // not the repository's test command; let the module default resolve.
        return None;
    }
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
        "make test",
        "make check",
        "just test",
    ] {
        if starts_with_command_prefix(matchable, prefix) {
            return Some(command.to_string());
        }
    }
    None
}

fn starts_with_command_prefix(command: &str, prefix: &str) -> bool {
    let command = command.trim();
    command == prefix
        || command
            .strip_prefix(prefix)
            .is_some_and(|rest| rest.chars().next().is_some_and(char::is_whitespace))
}

pub(crate) fn infer_workflow_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    if workflow_file_is_specialized_noncanonical(&file.path) {
        return None;
    }
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

fn workflow_file_is_specialized_noncanonical(path: &str) -> bool {
    let file = path.rsplit('/').next().unwrap_or(path).to_ascii_lowercase();
    [
        "bench",
        "benchmark",
        "clippy",
        "doc",
        "docs",
        "format",
        "fmt",
        "fuzz",
        "lint",
        "release",
    ]
    .iter()
    .any(|term| file.contains(term))
}

fn strip_matching_yaml_quotes(value: &str) -> &str {
    let bytes = value.as_bytes();
    if bytes.len() >= 2 {
        let first = bytes[0];
        if (first == b'\'' || first == b'"') && bytes[bytes.len() - 1] == first {
            return &value[1..value.len() - 1];
        }
    }
    value
}

pub(crate) fn extract_workflow_run_commands(contents: &str) -> Vec<String> {
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
                // Inline run values may be YAML-quoted; the quotes are not
                // part of the shell command.
                commands.push(strip_matching_yaml_quotes(rest).to_string());
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

pub(crate) fn first_matching_workflow_command(
    commands: &[String],
    select_build: bool,
) -> Option<String> {
    commands.iter().find_map(|command| {
        let trimmed = command.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') || looks_like_shell_assignment(trimmed) {
            return None;
        }
        // Lines that merely print or prepare files can mention a runner
        // (`echo go test ...`, `chmod +x gradlew`) without executing it.
        let first_token = trimmed.split_whitespace().next().unwrap_or("");
        if matches!(
            first_token,
            "echo" | "printf" | "chmod" | "mkdir" | "touch" | "cat" | "cp" | "mv" | "rm"
        ) {
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
                    if prefix == "cargo build"
                        && is_specialized_cargo_workflow_command(trimmed, "build")
                    {
                        return None;
                    }
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
                    if prefix == "cargo test"
                        && is_specialized_cargo_workflow_command(trimmed, "test")
                    {
                        return None;
                    }
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
                || (lower.contains("mvn ")
                    && (lower.contains("package") || lower.contains("compile")))
            {
                return Some(trimmed.to_string());
            }
            // Both runner spellings require a build-ish task: a bare mention of
            // the wrapper (e.g. `chmod +x gradlew`) is not a build command.
            if (lower.contains("gradlew") || lower.contains("gradle "))
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
            if !lower.contains("skiptests")
                && (((lower.contains(" mvnw") || lower.contains("./mvnw"))
                    && lower.contains("test"))
                    || (lower.contains("mvn ") && lower.contains("test")))
            {
                return Some(trimmed.to_string());
            }
            if !lower.contains("-x test")
                && ((lower.contains("gradlew") && lower.contains("test"))
                    || (lower.contains("gradle ") && lower.contains("test")))
            {
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
                && !is_specialized_cargo_workflow_command(trimmed, "test")
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

fn is_specialized_cargo_workflow_command(command: &str, subcommand: &str) -> bool {
    let mut tokens = command.split_whitespace();
    if tokens.next() != Some("cargo") || tokens.next() != Some(subcommand) {
        return false;
    }
    tokens.any(|token| {
        matches!(
            token,
            "--all-features"
                | "--bench"
                | "--bin"
                | "--doc"
                | "--example"
                | "--features"
                | "--no-default-features"
                | "--package"
                | "--target"
                | "--test"
                | "-F"
                | "-p"
        ) || token.starts_with("--bench=")
            || token.starts_with("--bin=")
            || token.starts_with("--example=")
            || token.starts_with("--features=")
            || token.starts_with("--package=")
            || token.starts_with("--target=")
            || token.starts_with("--test=")
    })
}
