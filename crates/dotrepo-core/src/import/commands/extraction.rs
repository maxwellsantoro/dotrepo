//! Ecosystem-specific build/test command *extraction*: locating candidate
//! commands from language/build-tool manifests (Cargo.toml, package.json,
//! pyproject.toml, go.mod, Maven/Gradle, Composer, .csproj, Mix, Rebar,
//! CMakePresets.json, Makefiles/justfiles/Rakefiles, CONTRIBUTING.md, and
//! GitHub Actions workflow files). Ranking/safety policy for the resulting
//! candidates lives in `policy`.
use super::super::types::{CommandSourceTier, ImportedCommandCandidate, ImportedFile};
use super::policy::{
    detect_node_package_runner, is_nonexecuting_test_command,
    is_placeholder_package_json_test_script, is_setup_only_command, pick_node_script_command,
};

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

    let build =
        pick_node_script_command(scripts, &["build", "compile", "dist", "bundle"], |name| {
            runner.script_command(name)
        });
    // A monorepo may only declare test-all. Never turn that into an absent
    // root test script or a package-local example from its contribution guide.
    let tests = scripts
        .iter()
        .filter(|(_, value)| {
            value
                .as_str()
                .is_some_and(|v| !is_placeholder_package_json_test_script(v))
        })
        .map(|(k, v)| (k.clone(), v.clone()))
        .collect();
    let test = pick_node_script_command(&tests, &["test", "test-all"], |name| {
        runner.script_command(name)
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
    // Preserve the entrypoint: prerequisites, variables, shell settings and
    // directory changes belong to Make, even for a one-line recipe.
    let pick = |names: &[&str]| {
        names.iter().find_map(|name| {
            targets
                .iter()
                .find(|target| target.eq_ignore_ascii_case(name))
                .map(|target| format!("make {target}"))
        })
    };
    let build = pick(&["build", "all", "compile", "dist", "package"]);
    let test = pick(&["unit-test", "test-unit", "test", "check", "verify", "spec"]);
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
    let pick = |names: &[&str]| {
        names.iter().find_map(|name| {
            recipes
                .iter()
                .find(|recipe| recipe.eq_ignore_ascii_case(name))
                .map(|recipe| format!("just {recipe}"))
        })
    };
    let build = pick(&["build", "all"]);
    let test = pick(&["unit-test", "test-unit", "test", "check"]);
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

/// Static literal declarations only. Never evaluate upstream Make expressions.
fn parse_makefile_targets(contents: &str) -> Vec<String> {
    let mut targets = Vec::new();
    let mut define_depth = 0usize;
    let mut conditional_depth = 0usize;
    let mut continued = false;
    for line in contents.lines() {
        let trimmed = line.split('#').next().unwrap_or("").trim();
        let was_continued = continued;
        continued = trimmed.ends_with('\\');
        if line.starts_with('\t') || trimmed.is_empty() {
            continue;
        }
        let directive = trimmed.split_whitespace().next().unwrap_or("");
        if matches!(
            directive,
            "define" | "override" | "export" | "private" | "unexport"
        ) && trimmed.split_whitespace().any(|token| token == "define")
        {
            define_depth += 1;
            continue;
        }
        if directive == "endef" {
            define_depth = define_depth.saturating_sub(1);
            continue;
        }
        if define_depth > 0 {
            continue;
        }
        if matches!(directive, "ifdef" | "ifndef" | "ifeq" | "ifneq") {
            conditional_depth += 1;
            continue;
        }
        if directive == "endif" {
            conditional_depth = conditional_depth.saturating_sub(1);
            continue;
        }
        if conditional_depth > 0 || was_continued {
            continue;
        }
        // A top-level diagnostic or changed recipe syntax prevents us from
        // establishing any usable default with this conservative parser.
        if trimmed.starts_with("$(error")
            || trimmed.starts_with("${error")
            || trimmed.starts_with(".RECIPEPREFIX")
        {
            return Vec::new();
        }
        if continued || line.starts_with(char::is_whitespace) {
            continue;
        }
        let Some((lhs, rhs)) = trimmed.split_once(':') else {
            continue;
        };
        if rhs.starts_with(['=', ':']) || rhs.contains(':') || rhs.contains('=') {
            continue;
        }
        let names = lhs.split_whitespace().collect::<Vec<_>>();
        if names.is_empty() || !names.iter().all(|name| literal_task_name(name)) {
            continue;
        }
        targets.extend(names.into_iter().map(str::to_string));
    }
    targets
}

fn literal_task_name(name: &str) -> bool {
    name.chars()
        .next()
        .is_some_and(|ch| ch.is_ascii_alphabetic() || ch == '_')
        && name
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '_' | '-'))
}

fn parse_justfile_recipes(contents: &str) -> Vec<String> {
    let mut recipes = Vec::new();
    let mut attributed = false;
    for line in contents.lines() {
        if line.starts_with(char::is_whitespace) {
            continue;
        }
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }
        if trimmed.starts_with('[') {
            attributed = true;
            continue;
        }
        let skip = std::mem::take(&mut attributed);
        let Some((lhs, rhs)) = trimmed.split_once(':') else {
            continue;
        };
        let name = lhs.trim();
        // Parameters (including defaults and variadics) require a richer
        // invocation contract. Withhold them rather than guessing arguments.
        if skip || rhs.starts_with('=') || name.starts_with('_') || !literal_task_name(name) {
            continue;
        }
        recipes.push(name.to_string());
    }
    recipes
}

pub(crate) fn infer_rakefile_commands(file: &ImportedFile) -> Option<ImportedCommandCandidate> {
    // Ruby namespaces and dynamic evaluation can change task identity. Until
    // those constructs have a static parser, withhold the entire Rake source.
    if file.contents.contains("namespace")
        || ["module ", "class ", "instance_eval", "class_eval", "eval("]
            .iter()
            .any(|marker| file.contents.contains(marker))
        || file.contents.lines().any(|line| {
            // A # inside a Ruby string is not a comment delimiter. Scan the
            // complete line conservatively so it cannot hide a later modifier.
            let line = line.trim();
            // This deliberately withholds keywords even in strings/symbols.
            // Static recognition supports unconditional literal declarations;
            // statement modifiers and control-flow bodies need Ruby semantics.
            line.split(|ch: char| !ch.is_ascii_alphanumeric() && ch != '_')
                .any(|word| {
                    matches!(
                        word,
                        "if" | "unless"
                            | "case"
                            | "while"
                            | "until"
                            | "for"
                            | "loop"
                            | "begin"
                            | "rescue"
                            | "def"
                    )
                })
                || (line.contains(" do") && !line.starts_with("task "))
        })
    {
        return None;
    }
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
    if line.starts_with(char::is_whitespace) {
        return false;
    }
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
    // A fence is one instruction sequence. Inspect it before selecting a line:
    // setup and directory state must not disappear when publishing a scalar.
    let mut build: Option<String> = None;
    let mut test: Option<String> = None;
    let mut in_code_block = false;
    let mut current_heading = String::new();
    let mut headings: Vec<(usize, String)> = Vec::new();
    let mut block_lines = Vec::new();
    for line in file.contents.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with("```") || trimmed.starts_with("~~~") {
            if in_code_block {
                let has_context = block_lines.iter().any(|line: &String| {
                    let unprompted = line.trim_start_matches(['$', '>', '%', '❯']).trim();
                    unprompted == "cd"
                        || unprompted.starts_with("cd ")
                        || is_setup_only_command(unprompted)
                });
                if !has_context {
                    for line in &block_lines {
                        let Some(command) = normalize_documented_command_line(line) else {
                            continue;
                        };
                        if build.is_none() && doc_heading_allows_command(&current_heading, true) {
                            build = documented_build_command(&command);
                        }
                        if test.is_none() && doc_heading_allows_command(&current_heading, false) {
                            test = documented_test_command(&command);
                        }
                    }
                }
                block_lines.clear();
            }
            in_code_block = !in_code_block;
            continue;
        }
        if !in_code_block {
            if let Some(heading) = markdown_heading_text(trimmed) {
                let level = trimmed.chars().take_while(|ch| *ch == '#').count();
                headings.retain(|(ancestor_level, _)| *ancestor_level < level);
                headings.push((level, heading));
                current_heading = headings
                    .iter()
                    .map(|(_, heading)| heading.as_str())
                    .collect::<Vec<_>>()
                    .join(" ");
            }
            continue;
        }
        block_lines.push(trimmed.to_string());
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
    if [
        "playground",
        "extension",
        "example",
        "benchmark",
        "single test",
        "specific test",
        "component",
        // Explicit context sections must pass the complete tuple extractor;
        // incomplete declarations cannot fall back to root scalar guesses.
        "repository tests",
        "repository build",
    ]
    .iter()
    .any(|component| heading.contains(component))
    {
        return false;
    }
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

    let parts = trimmed.split_whitespace().collect::<Vec<_>>();
    // Environment setup is a prerequisite, not disposable decoration.
    if parts
        .first()
        .is_some_and(|part| *part == "env" || is_env_assignment_token(part))
    {
        return None;
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

pub(super) fn documented_build_command(command: &str) -> Option<String> {
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

pub(super) fn documented_test_command(command: &str) -> Option<String> {
    if is_nonexecuting_test_command(command) {
        return None;
    }
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
    // Until working directory and prerequisites have an explicit contract,
    // component CI steps cannot be promoted to repository defaults.
    if file.contents.lines().any(|line| {
        let line = line.trim().strip_prefix("- ").unwrap_or(line.trim());
        line.strip_prefix("working-directory:")
            .is_some_and(|value| !matches!(strip_matching_yaml_quotes(value.trim()), "." | "./"))
            || line.starts_with("cd ")
    }) {
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
        if trimmed.is_empty()
            || trimmed.starts_with('#')
            || looks_like_shell_assignment(trimmed)
            || (!select_build && is_nonexecuting_test_command(trimmed))
        {
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
        // Host package installs often list `make` / `build-essential` as packages
        // (pyenv CI). Those are not repository build commands.
        if is_host_package_install_command(trimmed) || is_setup_only_command(trimmed) {
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
                if starts_with_command_prefix(trimmed, prefix) {
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
                if starts_with_command_prefix(trimmed, prefix) {
                    if prefix == "cargo test"
                        && is_specialized_cargo_workflow_command(trimmed, "test")
                    {
                        return None;
                    }
                    if prefix == "go test" && is_specialized_go_workflow_test_command(trimmed) {
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
            // Token-aware: do not treat Debian package `build-essential` as `make build`.
            if make_invocation_has_task(&lower, &["build", "all"]) {
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
            if make_invocation_has_task(&lower, &["test", "check"]) {
                return Some(trimmed.to_string());
            }
            if lower.contains("cargo test")
                && !is_specialized_cargo_workflow_command(trimmed, "test")
                || (lower.contains("go test") && !is_specialized_go_workflow_test_command(trimmed))
                || python_test_invocation(trimmed)
            {
                return Some(trimmed.to_string());
            }
        }

        None
    })
}

/// Recognize an invoked runner, not its name in another command's arguments.
fn python_test_invocation(command: &str) -> bool {
    let tokens = command.split_whitespace().collect::<Vec<_>>();
    let tokens = match tokens.as_slice() {
        ["uv", "run", rest @ ..] => {
            let offset = rest
                .iter()
                .take_while(|token| matches!(**token, "--locked" | "--offline" | "--no-sync"))
                .count();
            &rest[offset..]
        }
        ["poetry" | "pdm", "run", rest @ ..] => rest,
        _ => tokens.as_slice(),
    };
    matches!(
        tokens,
        ["pytest", ..] | ["python" | "python3", "-m", "pytest", ..]
    )
}

/// CI-only go test lines (coverage dirs, -args passthrough, etc.) are not
/// developer-facing repo.test values.
fn is_specialized_go_workflow_test_command(command: &str) -> bool {
    let lower = command.to_ascii_lowercase();
    if !lower.contains("go test") {
        return false;
    }
    lower.split_whitespace().any(|token| {
        matches!(
            token,
            "-args"
                | "-coverprofile"
                | "-covermode"
                | "-bench"
                | "-benchmem"
                | "-fuzz"
                | "-fuzztime"
        ) || token.starts_with("-coverprofile=")
            || token.starts_with("-covermode=")
            || token.contains("gocoverdir")
            || token.starts_with("-test.gocoverdir")
    })
}

/// `apt-get install … make build-essential` is a host dependency install, not
/// a repository build. Also covers `sudo apt …` and sibling package managers.
fn is_host_package_install_command(command: &str) -> bool {
    let mut tokens = command.split_whitespace();
    let mut first = tokens.next().unwrap_or("");
    if first == "sudo" {
        first = tokens.next().unwrap_or("");
    }
    matches!(
        first,
        "apt" | "apt-get" | "yum" | "dnf" | "pacman" | "apk" | "brew" | "choco" | "zypper" | "pkg"
    )
}

/// True when a `make` invocation includes one of `tasks` as a whole make target
/// token (not a package name like `build-essential` or a substring of another
/// word).
fn make_invocation_has_task(lower_command: &str, tasks: &[&str]) -> bool {
    let mut rest = lower_command;
    while let Some(idx) = rest.find("make") {
        let after_make = &rest[idx + 4..];
        // Require a token boundary after `make` (`make build`, not `makefile`).
        let after_make = match after_make.chars().next() {
            None => return false,
            Some(ch) if ch.is_whitespace() => after_make.trim_start(),
            _ => {
                rest = after_make;
                continue;
            }
        };
        for token in after_make.split_whitespace() {
            // Stop at shell operators if present on the same logical line.
            if token.starts_with('#') {
                break;
            }
            let task = token.trim_matches(|c| matches!(c, ';' | '&' | '|' | '`' | '\'' | '"'));
            if tasks.contains(&task) {
                return true;
            }
        }
        rest = after_make;
    }
    false
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
