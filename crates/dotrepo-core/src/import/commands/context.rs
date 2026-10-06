//! Conservative extraction of explicitly scoped, complete documentation blocks.
//! Unsupported prose or shell state stays unassessed, rather than implying cwd
//! or an empty prerequisite list from a recognizable command token.
use std::path::Path;

use dotrepo_schema::{BuildTestCandidate, ExecutionContext, ExecutionScope};

use super::super::read::check_input_path;
use super::super::types::{ImportSources, ImportedFile};
use super::extraction::{documented_build_command, documented_test_command};
use super::policy::{is_setup_only_command, sanitize_import_command};

pub(crate) fn infer_documented_context_candidates(
    root: &Path,
    sources: &ImportSources<'_>,
) -> (Vec<BuildTestCandidate>, Vec<BuildTestCandidate>) {
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
    (build, test)
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
            current.heading = trimmed.trim_start_matches('#').trim().to_string();
            if parse_heading(&current.heading).is_none() && mentions_setup(&current.heading) {
                outside_setup = true;
            }
        } else if !trimmed.is_empty() {
            if parse_heading(&current.heading).is_none() && mentions_setup(trimmed) {
                outside_setup = true;
            }
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

fn parse_section(
    root: &Path,
    file: &ImportedFile,
    section: Section,
) -> Option<(bool, BuildTestCandidate)> {
    let (is_build, scope, component) = parse_heading(&section.heading)?;
    if section.invalid || section.blocks.len() != 1 {
        return None;
    }
    // Explicit none is the sole supported prose contract. Unknown preceding
    // setup prose, omitted versions, and descriptive lists remain unassessed.
    let explicit_none = section.prose.as_slice() == ["Prerequisites: none."];
    if !section.prose.is_empty() && !explicit_none {
        return None;
    }
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
    let mut prerequisites = Vec::new();
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
