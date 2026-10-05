//! Import-time build/test command inference: orchestrates loading
//! candidate files from disk, ecosystem-specific extraction (`extraction`),
//! and safety/ranking policy (`policy`) into a single resolved
//! `ImportedCommandMetadata`.
use anyhow::{anyhow, Result};
use std::fs;
use std::path::{Path, PathBuf};

use super::read::{check_input_path, read_input};
use super::types::{ImportSources, ImportedCommandMetadata, ImportedFile};

mod extraction;
mod policy;

pub(crate) use policy::sanitize_import_command;

#[allow(unused_imports)]
pub(crate) use extraction::infer_pyproject_commands;

use extraction::{
    infer_cargo_manifest_commands,
    infer_cmake_workflow_commands,
    infer_composer_commands,
    infer_contributing_commands,
    infer_dotnet_commands,
    infer_go_module_commands,
    // infer_dotnet_commands also handles .sln
    infer_gradle_commands,
    infer_justfile_commands,
    infer_makefile_commands,
    infer_maven_commands,
    infer_mix_commands,
    infer_package_json_commands,
    infer_rakefile_commands,
    infer_readme_commands,
    infer_rebar_commands,
    infer_setup_cfg_commands,
    infer_setup_py_commands,
    infer_tox_ini_commands,
    infer_workflow_commands,
};
use policy::resolve_command_field;

pub(super) fn load_first_existing_file(
    root: &Path,
    candidates: &[&'static str],
) -> Result<Option<ImportedFile>> {
    for candidate in candidates {
        let path = root.join(candidate);
        if fs::symlink_metadata(&path).is_ok() {
            let contents = read_input(root, Path::new(candidate))?;
            return Ok(Some(ImportedFile {
                path: candidate.to_string(),
                contents,
            }));
        }
    }

    Ok(None)
}

/// Load the best `Cargo.toml` for command inference: root workspace first,
/// else a nested crate/workspace preferred over examples/benches.
pub(super) fn load_best_cargo_toml(root: &Path) -> Result<Option<ImportedFile>> {
    let mut matches = Vec::new();
    collect_files_named(root, root, "Cargo.toml", 3, 1, &mut matches)?;
    matches.sort_by(|left, right| {
        cargo_toml_path_preference(&left.0)
            .cmp(&cargo_toml_path_preference(&right.0))
            .then_with(|| left.0.cmp(&right.0))
    });

    for (relative, path) in matches {
        let contents = read_input(root, path.strip_prefix(root)?)?;
        let file = ImportedFile {
            path: relative,
            contents,
        };
        if extraction::infer_cargo_manifest_commands(&file).is_some() {
            return Ok(Some(file));
        }
    }
    load_first_existing_file(root, &["Cargo.toml"])
}

fn cargo_toml_path_preference(path: &str) -> i32 {
    let lower = path.replace('\\', "/").to_ascii_lowercase();
    if lower == "cargo.toml" {
        return 0;
    }
    if lower.contains("/examples/")
        || lower.contains("/benches/")
        || lower.contains("/tests/")
        || lower.contains("/fuzz/")
    {
        return 200;
    }
    if lower.contains("/sdk/") || lower.contains("-sdk/") || lower.starts_with("sdk/") {
        return 170;
    }
    // Common monorepo roots for the primary Rust crate tree.
    if lower.ends_with("-rs/cargo.toml")
        || lower.contains("/rust/")
        || lower.starts_with("rust/")
        || lower.contains("/crates/")
        || lower.starts_with("crates/")
    {
        return 10;
    }
    50
}

/// Load the best named Python manifest (`pyproject.toml` / `setup.py` /
/// `setup.cfg`) for command inference, preferring root then `python/` layouts.
pub(super) fn load_best_python_manifest(
    root: &Path,
    file_name: &str,
) -> Result<Option<ImportedFile>> {
    let mut matches = Vec::new();
    collect_files_named(root, root, file_name, 3, 1, &mut matches)?;
    matches.sort_by(|left, right| {
        python_manifest_path_preference(&left.0)
            .cmp(&python_manifest_path_preference(&right.0))
            .then_with(|| left.0.cmp(&right.0))
    });

    for (relative, path) in matches {
        let contents = read_input(root, path.strip_prefix(root)?)?;
        let file = ImportedFile {
            path: relative.clone(),
            contents,
        };
        let usable = match file_name {
            "pyproject.toml" => extraction::infer_pyproject_commands(&file).is_some(),
            "setup.py" => extraction::infer_setup_py_commands(&file).is_some(),
            "setup.cfg" => extraction::infer_setup_cfg_commands(&file).is_some(),
            _ => false,
        };
        if usable {
            return Ok(Some(file));
        }
    }
    // Fall back to root file even if scripts are incomplete (toolchain / metadata).
    let root_name: &'static str = match file_name {
        "pyproject.toml" => "pyproject.toml",
        "setup.py" => "setup.py",
        "setup.cfg" => "setup.cfg",
        _ => return Ok(None),
    };
    load_first_existing_file(root, &[root_name])
}

fn python_manifest_path_preference(path: &str) -> i32 {
    let lower = path.replace('\\', "/").to_ascii_lowercase();
    if lower == "pyproject.toml" || lower == "setup.py" || lower == "setup.cfg" {
        return 0;
    }
    if lower.contains("/examples/") || lower.contains("/samples/") || lower.contains("/benchmarks/")
    {
        return 200;
    }
    if lower.contains("/tests/") || lower.contains("/test/") {
        return 180;
    }
    // Secondary language SDKs in polyglot monorepos (e.g. openai/codex).
    if lower.contains("/sdk/")
        || lower.contains("-sdk/")
        || lower.contains("/sdks/")
        || lower.starts_with("sdk/")
    {
        return 170;
    }
    // Packaging/release helper trees are rarely the project entrypoint.
    if lower.starts_with("release/")
        || lower.contains("/release/")
        || lower.contains("/packaging/")
        || lower.contains("/ci/")
    {
        return 160;
    }
    // Prefer a top-level python/ package package, but not nested under sdk/.
    if lower == "python/pyproject.toml"
        || lower == "python/setup.py"
        || lower == "python/setup.cfg"
        || lower.starts_with("python/")
    {
        return 10;
    }
    if lower.starts_with("src/") {
        return 20;
    }
    if lower.contains("/packages/") {
        return 30;
    }
    50
}

/// Load the best `package.json` for command inference: root first when it has
/// usable scripts, otherwise a nested monorepo package preferred over SDKs /
/// examples / test harnesses.
pub(super) fn load_best_package_json(root: &Path) -> Result<Option<ImportedFile>> {
    let mut matches = Vec::new();
    collect_files_named(root, root, "package.json", 4, 1, &mut matches)?;
    matches.sort_by(|left, right| {
        package_json_path_preference(&left.0)
            .cmp(&package_json_path_preference(&right.0))
            .then_with(|| left.0.cmp(&right.0))
    });

    for (relative, path) in matches {
        let contents = read_input(root, path.strip_prefix(root)?)?;
        let file = ImportedFile {
            path: relative,
            contents,
        };
        if extraction::infer_package_json_commands(&file).is_some() {
            return Ok(Some(file));
        }
    }
    Ok(None)
}

/// Lower is better. Used for monorepo package.json selection.
pub(super) fn package_json_path_preference(path: &str) -> i32 {
    let lower = path.replace('\\', "/").to_ascii_lowercase();
    if lower == "package.json" {
        return 0;
    }
    if lower.contains("/examples/")
        || lower.contains("/samples/")
        || lower.contains("/fixtures/")
        || lower.contains("/example/")
    {
        return 200;
    }
    if lower.contains("test-suite")
        || lower.contains("test-site")
        || lower.contains("/tests/")
        || lower.contains("/__tests__/")
        || lower.contains("/e2e/")
    {
        return 180;
    }
    if lower.contains("/sdk/")
        || lower.contains("-sdk/")
        || lower.contains("/js-sdk/")
        || lower.contains("/python-sdk/")
    {
        return 150;
    }
    if lower.contains("/native/") {
        return 140;
    }
    if lower == "server/package.json" || lower.ends_with("/server/package.json") {
        return 10;
    }
    if lower == "api/package.json"
        || lower.ends_with("/api/package.json")
        || lower.contains("/apps/api/")
    {
        return 11;
    }
    if lower == "web/package.json" || lower.ends_with("/web/package.json") {
        return 12;
    }
    if lower.contains("/apps/") {
        return 20;
    }
    if lower.contains("/packages/") {
        return 25;
    }
    50
}

fn collect_files_named(
    root: &Path,
    dir: &Path,
    file_name: &str,
    max_depth: usize,
    depth: usize,
    out: &mut Vec<(String, PathBuf)>,
) -> Result<()> {
    if depth > max_depth {
        return Ok(());
    }
    let entries =
        fs::read_dir(dir).map_err(|err| anyhow!("failed to read {}: {}", dir.display(), err))?;
    for entry in entries.filter_map(|entry| entry.ok()) {
        let path = entry.path();
        if path.is_dir() {
            let name = path
                .file_name()
                .and_then(|value| value.to_str())
                .unwrap_or("");
            if name.starts_with('.')
                || name.eq_ignore_ascii_case("node_modules")
                || name.eq_ignore_ascii_case("dist")
                || name.eq_ignore_ascii_case("build")
                || name.eq_ignore_ascii_case("target")
            {
                continue;
            }
            check_input_path(root, path.strip_prefix(root)?)?;
            collect_files_named(root, &path, file_name, max_depth, depth + 1, out)?;
            continue;
        }
        if !path.is_file() {
            continue;
        }
        if !path
            .file_name()
            .and_then(|value| value.to_str())
            .is_some_and(|name| name.eq_ignore_ascii_case(file_name))
        {
            continue;
        }
        check_input_path(root, path.strip_prefix(root)?)?;
        let relative = path
            .strip_prefix(root)
            .map(|value| value.to_string_lossy().replace('\\', "/"))
            .unwrap_or_else(|_| file_name.to_string());
        out.push((relative, path));
    }
    Ok(())
}

/// Find the first file with `extension` within `max_depth` directory levels
/// (depth 1 = root only). Prefers non-test paths when ranking. Relative path
/// is preserved so monorepo layouts (e.g. `src/Foo/Foo.csproj`) remain honest.
pub(super) fn load_first_file_with_extension(
    root: &Path,
    extension: &str,
    max_depth: usize,
) -> Result<Option<ImportedFile>> {
    let mut matches = Vec::new();
    collect_files_with_extension(root, root, extension, max_depth, 1, &mut matches)?;
    matches.sort_by(|left, right| {
        let left_test = is_likely_test_project_path(&left.0);
        let right_test = is_likely_test_project_path(&right.0);
        left_test
            .cmp(&right_test)
            .then_with(|| left.0.cmp(&right.0))
    });

    let Some((relative, path)) = matches.into_iter().next() else {
        return Ok(None);
    };
    let contents = read_input(root, path.strip_prefix(root)?)?;
    Ok(Some(ImportedFile {
        path: relative,
        contents,
    }))
}

fn is_likely_test_project_path(relative: &str) -> bool {
    let lower = relative.to_ascii_lowercase();
    lower.contains(".tests.")
        || lower.contains(".test.")
        || lower.contains("/tests/")
        || lower.contains("/test/")
        || lower.ends_with("tests.csproj")
        || lower.ends_with("test.csproj")
}

fn collect_files_with_extension(
    root: &Path,
    dir: &Path,
    extension: &str,
    max_depth: usize,
    depth: usize,
    out: &mut Vec<(String, PathBuf)>,
) -> Result<()> {
    if depth > max_depth {
        return Ok(());
    }
    let entries = match fs::read_dir(dir) {
        Ok(entries) => entries,
        Err(err) => {
            return Err(anyhow!("failed to read {}: {}", dir.display(), err));
        }
    };
    for entry in entries.filter_map(|entry| entry.ok()) {
        let path = entry.path();
        if path.is_dir() {
            let name = path
                .file_name()
                .and_then(|value| value.to_str())
                .unwrap_or("");
            if name.starts_with('.') || name.eq_ignore_ascii_case("node_modules") {
                continue;
            }
            check_input_path(root, path.strip_prefix(root)?)?;
            collect_files_with_extension(root, &path, extension, max_depth, depth + 1, out)?;
            continue;
        }
        if !path.is_file() {
            continue;
        }
        let matches_extension = path
            .extension()
            .and_then(|value| value.to_str())
            .is_some_and(|value| value.eq_ignore_ascii_case(extension));
        if !matches_extension {
            continue;
        }
        check_input_path(root, path.strip_prefix(root)?)?;
        let relative = path
            .strip_prefix(root)
            .map(|value| value.to_string_lossy().replace('\\', "/"))
            .unwrap_or_else(|_| {
                path.file_name()
                    .and_then(|value| value.to_str())
                    .unwrap_or("unknown")
                    .to_string()
            });
        out.push((relative, path));
    }
    Ok(())
}

pub(super) fn load_workflow_import_files(root: &Path) -> Result<Vec<ImportedFile>> {
    let workflows_root = root.join(".github").join("workflows");
    if fs::symlink_metadata(&workflows_root).is_err() {
        return Ok(Vec::new());
    }

    check_input_path(root, Path::new(".github/workflows"))?;
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
        let contents = read_input(root, path.strip_prefix(root)?)?;
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
    if let Some(candidate) = sources.tox_ini.and_then(infer_tox_ini_commands) {
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
    if let Some(candidate) = sources
        .pom_xml
        .and_then(|file| infer_maven_commands(file, sources.maven_wrapper))
    {
        candidates.push(candidate);
    }
    if let Some(candidate) = sources
        .build_gradle
        .and_then(|file| infer_gradle_commands(file, sources.gradle_wrapper))
    {
        candidates.push(candidate);
    }
    if let Some(candidate) = sources.composer_json.and_then(infer_composer_commands) {
        candidates.push(candidate);
    }
    // Prefer solution files when present (monorepo entrypoint); otherwise csproj.
    if let Some(candidate) = sources.solution.and_then(infer_dotnet_commands) {
        candidates.push(candidate);
    } else if let Some(candidate) = sources.csproj.and_then(infer_dotnet_commands) {
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
    if let Some(candidate) = sources.readme.and_then(infer_readme_commands) {
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
    // Legacy scalar fields describe commands from the repository root. A nested
    // manifest only describes its own component; ranking cannot establish that
    // it is the repository's primary entrypoint.
    candidates.retain(|candidate| {
        let path = candidate.source_path.replace('\\', "/");
        let root_scoped = !path.contains('/')
            || path.starts_with(".github/workflows/")
            || path == ".github/CONTRIBUTING.md";
        if !root_scoped {
            let note =
                format!("Ignored component-scoped commands from `{path}` as repository defaults.");
            metadata.notes.push(note.clone());
            metadata.evidence_bullets.push(note);
        }
        root_scoped
    });

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

#[cfg(test)]
mod tests;
