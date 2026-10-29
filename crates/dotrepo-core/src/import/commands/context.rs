//! Conservative extraction of explicitly scoped, complete documentation blocks.
//! Unsupported prose or shell state stays unassessed, rather than implying cwd
//! or an empty prerequisite list from a recognizable command token.
use std::path::Path;

use dotrepo_schema::{BuildTestCandidate, ExecutionContext, ExecutionScope};

use super::super::read::check_input_path;
use super::super::types::{ImportSources, ImportedFile};
use super::extraction::{documented_build_command, documented_test_command};
use super::policy::{is_setup_only_command, sanitize_import_command};

mod python_recipe;
#[cfg(test)]
mod tests;

pub(crate) fn infer_documented_context_candidates(
    root: &Path,
    sources: &ImportSources<'_>,
) -> (
    Vec<BuildTestCandidate>,
    Vec<BuildTestCandidate>,
    Vec<(String, toml::Value)>,
) {
    let mut build = Vec::new();
    let mut test = Vec::new();
    for file in [sources.contributing, sources.readme].into_iter().flatten() {
        for (is_build, candidate) in extract_contexts(root, file) {
            let target = if is_build { &mut build } else { &mut test };
            if !target.contains(&candidate) {
                target.push(candidate);
            }
        }
    }
    let mut evidence = Vec::new();
    if let Some((candidate, assessment)) = python_recipe::infer(root, sources) {
        if !test.contains(&candidate) {
            evidence.push((format!("repo.test_candidates.{}", test.len()), assessment));
            test.push(candidate);
        }
    }
    (build, test, evidence)
}

#[derive(Default)]
struct Section {
    heading: String,
    prose: Vec<String>,
    blocks: Vec<Vec<String>>,
    invalid: bool,
}

fn extract_contexts(root: &Path, file: &ImportedFile) -> Vec<(bool, BuildTestCandidate)> {
    let mut sections = Vec::new();
    let mut current = Section::default();
    let mut fence: Option<&str> = None;
    let mut outside_setup = false;
    let mut ancestors: Vec<(usize, String)> = Vec::new();
    for line in file.contents.lines() {
        let trimmed = line.trim();
        if let Some(delimiter) = fence {
            if trimmed == delimiter {
                fence = None;
            } else {
                if parse_heading(&current.heading).is_none()
                    && (is_setup_only_command(trimmed) || mentions_setup(trimmed))
                {
                    outside_setup = true;
                }
                current.blocks.last_mut().unwrap().push(trimmed.to_string());
            }
            continue;
        }
        if trimmed.starts_with("```") || trimmed.starts_with("~~~") {
            let delimiter = &trimmed[..3];
            let language = &trimmed[3..];
            current.invalid |= !matches!(language, "sh" | "bash" | "shell" | "");
            current.blocks.push(Vec::new());
            fence = Some(if delimiter == "```" { "```" } else { "~~~" });
        } else if trimmed.starts_with('#') {
            sections.push(std::mem::take(&mut current));
            let depth = trimmed.chars().take_while(|ch| *ch == '#').count();
            while ancestors.last().is_some_and(|(level, _)| *level >= depth) {
                ancestors.pop();
            }
            current.heading = trimmed.trim_start_matches('#').trim().to_string();
            if parse_heading(&current.heading).is_some() {
                current.invalid |= unsupported_scope_ancestor(&ancestors);
            }
            if parse_heading(&current.heading).is_none() && mentions_setup(&current.heading) {
                outside_setup = true;
            }
            ancestors.push((depth, current.heading.clone()));
        } else if !trimmed.is_empty() {
            if parse_heading(&current.heading).is_none() && mentions_setup(trimmed) {
                outside_setup = true;
            }
            // Indented list entries may be continuations or nested conditions.
            // Do not flatten those into an unconditional prerequisite list.
            current.invalid |=
                parse_heading(&current.heading).is_some() && line.starts_with(char::is_whitespace);
            current.prose.push(trimmed.to_string());
        }
    }
    current.invalid |= fence.is_some();
    sections.push(current);
    if outside_setup {
        // A setup contract outside this supported block cannot be safely
        // associated or ignored. Do not pretend that local [] means none.
        return Vec::new();
    }
    sections
        .into_iter()
        .filter_map(|section| parse_section(root, file, section))
        .collect()
}

fn unsupported_scope_ancestor(ancestors: &[(usize, String)]) -> bool {
    ancestors.iter().any(|(depth, heading)| {
        // A nested section may carry scope or conditions that this small
        // extractor cannot establish. Permit only an unqualified document
        // title; do not flatten other ancestor headings away.
        *depth != 1
            || heading
                .to_ascii_lowercase()
                .split(|ch: char| !ch.is_ascii_alphanumeric())
                .any(|word| {
                    matches!(
                        word,
                        "windows"
                            | "linux"
                            | "macos"
                            | "osx"
                            | "unix"
                            | "freebsd"
                            | "android"
                            | "ios"
                            | "docker"
                            | "container"
                            | "wasm"
                            | "cross"
                            | "only"
                            | "if"
                            | "when"
                            | "conditional"
                            | "example"
                            | "benchmark"
                            | "component"
                    )
                })
    })
}

fn mentions_setup(text: &str) -> bool {
    text.to_ascii_lowercase()
        .split(|ch: char| !ch.is_ascii_alphanumeric())
        .any(|word| {
            matches!(
                word,
                "prerequisites"
                    | "prerequisite"
                    | "install"
                    | "setup"
                    | "requires"
                    | "require"
                    | "required"
                    | "requirement"
                    | "requirements"
                    | "activate"
                    | "export"
                    | "configure"
                    | "dependencies"
                    | "toolchain"
                    | "venv"
            )
        })
}

fn parse_heading(heading: &str) -> Option<(bool, ExecutionScope, Option<String>)> {
    let lower = heading.to_ascii_lowercase();
    for (title, is_build) in [("repository build", true), ("repository tests", false)] {
        if lower == title {
            return Some((is_build, ExecutionScope::Repository, None));
        }
    }
    for (title, is_build) in [("component build: ", true), ("component tests: ", false)] {
        if lower.starts_with(title) {
            let component = &heading[title.len()..];
            if literal_directory(component) && component != "." {
                return Some((
                    is_build,
                    ExecutionScope::Component,
                    Some(component.to_string()),
                ));
            }
        }
    }
    None
}

fn literal_directory(path: &str) -> bool {
    path == "."
        || (!path.is_empty()
            && path
                .chars()
                .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '/' | '_' | '-' | '.'))
            && path
                .split('/')
                .all(|part| !part.is_empty() && !matches!(part, "." | "..")))
}

/// Accept only an explicit, local list of runtime requirements. This grammar
/// preserves the source assertion; it neither resolves versions nor infers
/// missing setup. Arbitrary prose may hide conditions or external instructions.
fn declared_prerequisites(prose: &[String]) -> Option<(Vec<String>, bool)> {
    if prose.is_empty() {
        return Some((Vec::new(), false));
    }
    if prose == ["Prerequisites: none."] {
        return Some((Vec::new(), true));
    }
    let (heading, requirements) = prose.split_first()?;
    if heading != "Prerequisites:" || requirements.is_empty() {
        return None;
    }
    let mut prerequisites = Vec::new();
    let mut tools = Vec::new();
    for line in requirements {
        let requirement = line
            .strip_prefix("- ")
            .or_else(|| line.strip_prefix("* "))?;
        let tool = literal_runtime_requirement(requirement)?;
        // Conflicting declarations must not be silently reconciled, including
        // alternate version constraints for the same runtime.
        if tools.contains(&tool) {
            return None;
        }
        tools.push(tool);
        prerequisites.push(requirement.to_string());
    }
    Some((prerequisites, false))
}

fn literal_runtime_requirement(requirement: &str) -> Option<&str> {
    let (tool, version) = requirement.split_once(' ')?;
    if !matches!(
        tool,
        "Rust" | "Python" | "Go" | "Node.js" | "npm" | "pnpm" | "Yarn" | "Bun" | "uv"
    ) {
        return None;
    }
    if tool == "Rust" && matches!(version, "stable" | "nightly") {
        return Some(tool);
    }
    let bound = version
        .strip_suffix(" or higher")
        .or_else(|| version.strip_suffix(" or newer"))
        .or_else(|| version.strip_suffix('+'));
    let compared = [">=", "<=", "==", ">", "<", "="]
        .into_iter()
        .find_map(|operator| version.strip_prefix(operator));
    // Two forms of bounds in one declaration can contradict one another.
    if bound.is_some() && compared.is_some() {
        return None;
    }
    let version = bound.or(compared).unwrap_or(version);
    let components = version.split('.').collect::<Vec<_>>();
    (components.len() <= 3
        && components.iter().all(|component| {
            !component.is_empty() && component.bytes().all(|byte| byte.is_ascii_digit())
        }))
    .then_some(tool)
}

fn parse_section(
    root: &Path,
    file: &ImportedFile,
    section: Section,
) -> Option<(bool, BuildTestCandidate)> {
    let (is_build, scope, component) = parse_heading(&section.heading)?;
    if section.invalid || section.blocks.len() != 1 {
        return None;
    }
    let (mut prerequisites, explicit_none) = declared_prerequisites(&section.prose)?;
    let lines = section.blocks[0]
        .iter()
        .filter(|line| !line.is_empty())
        .collect::<Vec<_>>();
    let directory = lines.first()?.strip_prefix("cd ")?;
    if !literal_directory(directory) {
        return None;
    }
    match (&scope, component.as_deref()) {
        (ExecutionScope::Repository, None) if directory == "." => {}
        (ExecutionScope::Component, Some(path)) if directory == path => {}
        _ => return None,
    }
    if directory != "." && check_input_path(root, Path::new(directory)).is_err() {
        return None;
    }
    if !root.join(directory).is_dir() {
        return None;
    }
    let command = lines.last()?.as_str();
    if lines.len() < 2 || sanitize_import_command(command).as_deref() != Some(command) {
        return None;
    }
    let recognized = if is_build {
        documented_build_command(command)
    } else {
        documented_test_command(command)
    }?;
    // Do not broaden nextest selectors or rewrite an instruction to fit.
    if recognized != command {
        return None;
    }
    for setup in &lines[1..lines.len() - 1] {
        if !is_setup_only_command(setup)
            || setup.contains(['&', ';', '|', '$', '`', '<', '>', '{', '}', '\\'])
            || setup.chars().any(char::is_control)
        {
            return None;
        }
        prerequisites.push(format!(
            "Run `{setup}` in `{directory}` before this command."
        ));
    }
    if prerequisites.is_empty() != explicit_none {
        return None;
    }
    let command = command.to_string();
    Some((
        is_build,
        BuildTestCandidate {
            command: command.clone(),
            ecosystem: None,
            source: file.path.clone(),
            context: Some(ExecutionContext {
                command,
                working_directory: directory.to_string(),
                scope,
                component,
                prerequisites,
                source: file.path.clone(),
            }),
        },
    ))
}
