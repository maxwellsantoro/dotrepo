//! A bounded natural Python local-test recipe join. This recovers an attributed
//! candidate, never a verified instruction. The independent completeness review
//! remains unresolved even when the source chain can be retained.
use std::path::Path;

use dotrepo_schema::{BuildTestCandidate, ExecutionContext, ExecutionScope};
use serde_json::json;
use sha2::{Digest, Sha256};

use super::super::super::read::read_input;
use super::*;

#[cfg(test)]
mod tests;

fn unsupported_condition(text: &str) -> bool {
    text.to_ascii_lowercase()
        .split(|c: char| !c.is_ascii_alphanumeric())
        .any(|word| matches!(word, "if" | "unless" | "except" | "only" | "when"))
}

fn links_are(text: &str, allowed: &[String]) -> bool {
    text.split("](").skip(1).all(|rest| {
        rest.split_once(')')
            .is_some_and(|(target, _)| allowed.iter().any(|url| target == url))
    })
}

fn requirement_words(text: &str) -> bool {
    text.to_ascii_lowercase()
        .split(|c: char| !c.is_ascii_alphanumeric())
        .any(|word| {
            matches!(
                word,
                "requires" | "required" | "prerequisite" | "prerequisites"
            )
        })
}

fn unconsumed_requirement(file: &ImportedFile, covered: &[&Passage<'_>]) -> bool {
    let mut uncovered = Vec::new();
    let explicit = file.contents.lines().enumerate().any(|(index, line)| {
        if covered.iter().any(|part| {
            part.file.path == file.path && (part.start..=part.end).contains(&(index + 1))
        }) {
            uncovered.push("");
            return false;
        }
        uncovered.push(line);
        let lower = line.to_ascii_lowercase();
        let heading = lower.trim_start_matches('#').trim();
        matches!(heading, "requirements" | "prerequisites" | "required setup")
            || requirement_words(line)
    });
    if explicit {
        return true;
    }
    uncovered.join("\n").split("\n\n").any(|paragraph| {
        let paragraph = fold(paragraph);
        // This exact forward reference closes into the selected setup section.
        // Other test-scoped setup prose remains unsupported, not silently lost.
        if paragraph == "To make code changes, you need to fork the repository. You will need to setup a development environment and run the unit tests. This is covered in the section \"Setup environment\"." {
            return false;
        }
        let lower = paragraph.to_ascii_lowercase();
        let words = lower.split(|c: char| !c.is_ascii_alphanumeric()).collect::<Vec<_>>();
        words.iter().any(|word| matches!(*word, "test" | "tests" | "testing"))
            && words.iter().any(|word| {
                matches!(
                    *word,
                    "install" | "installed" | "installing" | "setup" | "dependencies"
                        | "toolchain" | "configure" | "activate" | "export" | "venv"
                )
            })
    })
}

struct Passage<'a> {
    file: &'a ImportedFile,
    start: usize,
    end: usize,
    body: String,
}

fn fold(text: &str) -> String {
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn sha256(bytes: &[u8]) -> String {
    Sha256::digest(bytes)
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

fn passage<'a>(file: &'a ImportedFile, title: &str) -> Option<Passage<'a>> {
    // This intentionally small layout grammar does not interpret HTML comment
    // visibility. A declaration in a comment must never become an instruction.
    if file.contents.contains("<!--") || file.contents.contains("-->") {
        return None;
    }
    let lines = file.contents.lines().collect::<Vec<_>>();
    let mut found = None;
    let mut ancestors: Vec<(usize, String)> = Vec::new();
    let mut fence = false;
    for (index, line) in lines.iter().enumerate() {
        let line = line.trim_end();
        if line.starts_with(char::is_whitespace) {
            continue;
        }
        if line.starts_with("```") || line.starts_with("~~~") {
            fence = !fence;
            continue;
        }
        if fence || !line.starts_with('#') {
            continue;
        }
        let depth = line.chars().take_while(|c| *c == '#').count();
        if depth > 6 || !line[depth..].starts_with(' ') {
            return None;
        }
        let heading = line[depth..].trim();
        if let Some((_, _, level)) = found {
            if depth <= level {
                let (start, _, _) = found.unwrap();
                found = Some((start, index, level));
                break;
            }
        }
        while ancestors.last().is_some_and(|(level, _)| *level >= depth) {
            ancestors.pop();
        }
        if heading == title {
            // Permit ordinary document/installation/test ancestors. Other
            // scopes and conditions must not disappear during section lookup.
            if ancestors.iter().any(|(level, text)| {
                *level != 1
                    && !matches!(
                        text.as_str(),
                        "Run tests"
                            | "Setup environment"
                            | "Local installation"
                            | "Installation"
                            | "Backend Compatibility Table"
                    )
            }) || unsupported_scope_ancestor(
                &ancestors
                    .iter()
                    .filter(|(level, _)| *level == 1)
                    .cloned()
                    .collect::<Vec<_>>(),
            ) {
                return None;
            }
            if found.is_some() {
                return None;
            }
            found = Some((index, lines.len(), depth));
        }
        ancestors.push((depth, heading.to_string()));
    }
    let (start, end, _) = found?;
    // Preserve Markdown's distinction between prose/fences and indented code.
    // The retained recipe uses flush-left declarations; other layouts abstain.
    if lines[start + 1..end]
        .iter()
        .any(|line| !line.trim().is_empty() && line.starts_with(char::is_whitespace))
    {
        return None;
    }
    // A repeated section later in the file must not be resolved by first-match.
    if lines[end..]
        .iter()
        .any(|line| line.trim_start_matches('#').trim() == title && line.starts_with('#'))
    {
        return None;
    }
    Some(Passage {
        file,
        start: start + 1,
        end,
        body: lines[start + 1..end].join("\n"),
    })
}

fn shell_blocks(text: &str) -> Option<Vec<Vec<String>>> {
    let mut blocks = Vec::new();
    let mut active = false;
    for line in text.lines() {
        let line = line.trim();
        if line.starts_with("```") {
            if active {
                if line != "```" {
                    return None;
                }
            } else {
                if !matches!(line, "```" | "```shell" | "```sh" | "```bash") {
                    return None;
                }
                blocks.push(Vec::new());
            }
            active = !active;
        } else if active && !line.is_empty() {
            blocks.last_mut()?.push(line.to_string());
        } else if line.starts_with("~~~") {
            return None;
        }
    }
    (!active).then_some(blocks)
}

fn source_binding(file: &ImportedFile, start: usize, end: usize) -> serde_json::Value {
    json!({
        "path": file.path,
        "startLine": start,
        "endLine": end,
        "sha256": sha256(file.contents.as_bytes()),
    })
}

fn description(label: &str, source: &Passage<'_>) -> String {
    format!(
        "{label} ({}:{}-{}): {}",
        source.file.path,
        source.start,
        source.end,
        fold(&source.body)
    )
}

fn requirement_closure(root: &Path, path: &str, files: &mut Vec<ImportedFile>) -> Option<()> {
    if files.len() >= 4
        || !literal_directory(path)
        || path == "."
        || files.iter().any(|file| file.path == path)
    {
        return None;
    }
    let contents = read_input(root, Path::new(path)).ok()?;
    if contents.len() > 128 * 1024
        || contents
            .chars()
            .any(|c| c.is_control() && c != '\n' && c != '\r')
    {
        return None;
    }
    let parent = Path::new(path).parent()?;
    let mut includes = Vec::new();
    for line in contents.lines().map(str::trim) {
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some(include) = line.strip_prefix("-r ") {
            if !literal_directory(include) || include == "." {
                return None;
            }
            includes.push(parent.join(include).to_str()?.to_string());
        } else if let Some(index) = line.strip_prefix("--extra-index-url ") {
            if !index.starts_with("https://")
                || index.contains(['@', '?', '#', '$', '`', '\\'])
                || index.chars().any(char::is_whitespace)
            {
                return None;
            }
        } else if line.starts_with(['-', '.', '/'])
            || line.contains(['@', ':', '$', '`', '\\'])
            || !line.chars().all(|c| {
                c.is_ascii_alphanumeric()
                    || matches!(
                        c,
                        '[' | ']'
                            | '-'
                            | '_'
                            | '.'
                            | ','
                            | '<'
                            | '>'
                            | '='
                            | '!'
                            | '~'
                            | ';'
                            | ' '
                            | '\''
                            | '"'
                            | '*'
                    )
            })
        {
            return None;
        }
    }
    files.push(ImportedFile {
        path: path.to_string(),
        contents,
    });
    for include in includes {
        requirement_closure(root, &include, files)?;
    }
    Some(())
}

pub(super) fn infer(
    root: &Path,
    sources: &ImportSources<'_>,
) -> Option<(BuildTestCandidate, toml::Value)> {
    let contributing = sources.contributing?;
    let readme = sources.readme?;
    let pyproject = sources.pyproject_toml?;
    if pyproject.path != "pyproject.toml" {
        return None;
    }
    let manifest: toml::Value = toml::from_str(&pyproject.contents).ok()?;
    let package = manifest.get("project")?.get("name")?.as_str()?;
    if !literal_directory(package) || package.contains('/') || package == "." {
        return None;
    }
    let python = manifest.get("project")?.get("requires-python")?.as_str()?;
    let minimum = python.strip_prefix(">=")?;
    literal_runtime_requirement(&format!("Python {minimum}"))?;
    let mapping = manifest
        .get("tool")?
        .get("setuptools")?
        .get("package-dir")?
        .get(package)?
        .as_str()?;
    if !mapping.starts_with(&format!("{package}/"))
        || !literal_directory(mapping)
        || check_input_path(root, Path::new(mapping)).is_err()
        || !root.join(mapping).is_dir()
    {
        return None;
    }
    let tests = passage(contributing, "Run all tests")?;
    let before = tests.body.split("```").next()?;
    if fold(before) != "You can run all the tests locally by running the following command in the repo root directory." {
        return None;
    }
    let command = format!("pytest {package}");
    let blocks = shell_blocks(&tests.body)?;
    if blocks.first()?.as_slice() != std::slice::from_ref(&command)
        || blocks.iter().skip(1).any(|block| {
            block.len() != 1
                || !block[0].ends_with(&format!(" {command}"))
                || block[0][..block[0].len() - command.len()]
                    .split_whitespace()
                    .any(|word| {
                        !word.split_once('=').is_some_and(|(key, value)| {
                            !key.is_empty()
                                && key.chars().all(|c| c.is_ascii_uppercase() || c == '_')
                                && !value.is_empty()
                                && value
                                    .chars()
                                    .all(|c| c.is_ascii_alphanumeric() || matches!(c, '_' | '-'))
                        })
                    })
        })
    {
        return None;
    }
    let setup = passage(contributing, "Option 2: Set up a local environment")?;
    if unsupported_condition(&setup.body) {
        return None;
    }
    let setup_blocks = shell_blocks(&setup.body)?;
    if setup_blocks.len() != 2 || setup_blocks[0] != ["git --version", "python --version"] {
        return None;
    }
    let install = &setup_blocks[1];
    if install.len() != 3
        || !install[0].starts_with("git clone https://github.com/YOUR_GITHUB_USERNAME/")
        || !install[0].ends_with(&format!("/{package}.git"))
        || install[1] != format!("cd {package}")
    {
        return None;
    }
    let requirements = install[2].strip_prefix("pip install -r ")?;
    let stated_minimum = setup
        .body
        .split("requires at least Python ")
        .nth(1)?
        .split_whitespace()
        .next()?;
    literal_runtime_requirement(&format!("Python {stated_minimum}"))?;
    let known_runtime = format!("requires at least Python {stated_minimum}");
    if setup.body.matches(&known_runtime).count() != 1
        || requirement_words(&setup.body.replace(&known_runtime, ""))
    {
        return None;
    }
    let version = |value: &str| {
        value
            .split('.')
            .map(str::parse::<u32>)
            .collect::<Result<Vec<_>, _>>()
            .ok()
    };
    // Do not silently reconcile a guide requiring more than the owning package.
    // A weaker guide minimum is retained alongside the controlling manifest.
    if version(stated_minimum)? > version(minimum)? {
        return None;
    }
    let repository = manifest
        .get("project")?
        .get("urls")?
        .get("Repository")?
        .as_str()?;
    if !repository.starts_with("https://github.com/") || repository.split('/').count() != 5 {
        return None;
    }
    for anchor in ["configuring-your-backend", "adding-gpu-support"] {
        if !setup
            .body
            .contains(&format!("{repository}/blob/master/README.md#{anchor}"))
        {
            return None;
        }
    }
    if !links_are(
        &setup.body,
        &[
            "https://github.com/".to_string(),
            "https://www.python.org/".to_string(),
            format!("{repository}/blob/master/README.md#configuring-your-backend"),
            format!("{repository}/blob/master/README.md#adding-gpu-support"),
        ],
    ) {
        return None;
    }
    if setup.body.split_whitespace().any(|word| {
        word.contains(".md")
            && !word.contains("README.md#configuring-your-backend")
            && !word.contains("README.md#adding-gpu-support")
    }) {
        return None;
    }
    let local = passage(readme, "Minimal installation")?;
    let local_blocks = shell_blocks(&local.body)?;
    if local_blocks.len() != 3
        || local_blocks[0] != [install[2].clone()]
        || local_blocks[1] != ["python pip_build.py --install"]
        || local_blocks[2] != ["./shell/api_gen.sh"]
        || !fold(&local.body).contains("Run installation command from the root directory.")
        || !fold(&local.body).contains("is compatible with Linux and macOS systems. For Windows users, we recommend using WSL2")
        || !links_are(&local.body, &[])
        || requirement_words(&local.body)
        || unsupported_condition(&local.body.replace("when creating PRs that update", ""))
    {
        return None;
    }
    let backend = passage(readme, "Configuring your backend")?;
    if !backend.body.contains("KERAS_BACKEND")
        || !fold(&backend.body).contains("backend must be configured before importing")
        || !fold(&backend.body).contains("backend cannot be changed after")
        || !links_are(&backend.body, &[])
        || requirement_words(&backend.body)
        || unsupported_condition(
            &backend
                .body
                .replace("inference-only", "")
                .replace("designed only for", ""),
        )
    {
        return None;
    }
    let gpu = passage(readme, "Adding GPU support")?;
    let cpu = gpu
        .body
        .lines()
        .take_while(|line| !line.is_empty())
        .collect::<Vec<_>>()
        .join(" ");
    // The selected local route is the documented CPU requirements recipe, not
    // an inferred GPU environment or the alternative Codespace setup.
    if !fold(&gpu.body).contains("file will install a CPU-only version") {
        return None;
    }
    let cpu = if cpu.trim().is_empty() {
        fold(&gpu.body).split("For GPU support").next()?.to_string()
    } else {
        cpu
    };
    if !cpu.contains("CPU-only") {
        return None;
    }
    let covered = [&tests, &setup, &local, &backend, &gpu];
    if unconsumed_requirement(contributing, &covered) || unconsumed_requirement(readme, &covered) {
        return None;
    }
    let mut requirements_files = Vec::new();
    requirement_closure(root, requirements, &mut requirements_files)?;
    if !requirements_files
        .iter()
        .any(|file| file.contents.lines().any(|line| line.trim() == "pytest"))
    {
        return None;
    }
    let prerequisites = vec![
        format!("Use Python {python} as declared by pyproject.toml; the local setup guide states the weaker minimum {stated_minimum}. No runtime was inspected."),
        description("Use the documented local setup route", &setup),
        description("Retain the local installation and platform conditions", &local),
        description("Configure a backend before imports and retain backend limitations", &backend),
        format!("Use the documented CPU requirements route; GPU setup is not established by this candidate: {}", fold(&cpu)),
        description("Retain default test coverage and the separately documented optional skip/backend variants", &tests),
        format!("Install the complete retained requirements include chain: {}. Environment markers and index declarations remain source data, not evidence of installed dependencies.", requirements_files.iter().map(|file| file.path.as_str()).collect::<Vec<_>>().join(", ")),
    ];
    let candidate = BuildTestCandidate {
        command: command.clone(),
        ecosystem: Some("Python".to_string()),
        source: contributing.path.clone(),
        context: Some(ExecutionContext {
            command,
            working_directory: ".".to_string(),
            scope: ExecutionScope::Repository,
            component: None,
            prerequisites,
            source: contributing.path.clone(),
        }),
    };
    let mut bindings = [&tests, &setup, &local, &backend, &gpu]
        .into_iter()
        .map(|part| source_binding(part.file, part.start, part.end))
        .collect::<Vec<_>>();
    bindings.push(source_binding(
        pyproject,
        1,
        pyproject.contents.lines().count(),
    ));
    bindings.extend(
        requirements_files
            .iter()
            .map(|file| source_binding(file, 1, file.contents.lines().count())),
    );
    let mut evidence = toml::map::Map::new();
    for (key, value) in [
        ("state", "present".to_string()),
        ("method", "extracted".to_string()),
        ("confidence", "medium".to_string()),
        ("source", contributing.path.clone()),
        ("reason", "Natural local-test recipe joined with owning package, documented setup/platform/backend conditions and retained requirements closure. Independent completeness verification remains unresolved; grammar and source closure do not establish high confidence, environment readiness or execution success.".to_string()),
        ("valueJson", serde_json::to_string(&candidate).ok()?),
        ("sourceBindingsJson", serde_json::to_string(&bindings).ok()?),
    ] {
        evidence.insert(key.to_string(), toml::Value::String(value));
    }
    Some((candidate, toml::Value::Table(evidence)))
}
