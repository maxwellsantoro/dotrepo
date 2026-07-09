//! Import-time build/test command inference: orchestrates loading
//! candidate files from disk, ecosystem-specific extraction (`extraction`),
//! and safety/ranking policy (`policy`) into a single resolved
//! `ImportedCommandMetadata`.
use anyhow::{anyhow, Result};
use std::fs;
use std::path::{Path, PathBuf};

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
    infer_workflow_commands,
};
use policy::resolve_command_field;

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
    let contents = fs::read_to_string(&path)
        .map_err(|err| anyhow!("failed to read {}: {}", path.display(), err))?;
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
mod tests {
    use super::policy::sanitize_import_command;

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
    fn resolve_unique_command_candidate_prefers_primary_ci_workflow() {
        use super::super::types::{CommandSourceTier, ImportedCommandCandidate};
        use super::policy::resolve_unique_command_candidate;

        let candidates = [
            ImportedCommandCandidate {
                source_path: ".github/workflows/build-release-apk.yml".into(),
                source_tier: CommandSourceTier::Workflow,
                build: Some("./gradlew assembleRelease".into()),
                test: Some("./gradlew testReleaseUnitTest".into()),
            },
            ImportedCommandCandidate {
                source_path: ".github/workflows/ci.yml".into(),
                source_tier: CommandSourceTier::Workflow,
                build: Some("npm run build".into()),
                test: Some("npm test".into()),
            },
        ];
        let refs: Vec<&ImportedCommandCandidate> = candidates.iter().collect();

        let build = resolve_unique_command_candidate(&refs, true);
        match build {
            super::policy::UniqueCommandResolution::Unique {
                command,
                source_path,
            } => {
                assert_eq!(command, "npm run build");
                assert_eq!(source_path, ".github/workflows/ci.yml");
            }
            other => panic!("expected unique build resolution, got {other:?}"),
        }

        let test = resolve_unique_command_candidate(&refs, false);
        match test {
            super::policy::UniqueCommandResolution::Unique {
                command,
                source_path,
            } => {
                assert_eq!(command, "npm test");
                assert_eq!(source_path, ".github/workflows/ci.yml");
            }
            other => panic!("expected unique test resolution, got {other:?}"),
        }
    }

    #[test]
    fn resolve_unique_command_candidate_prefers_generic_over_monorepo_slice_workflows() {
        use super::super::types::{CommandSourceTier, ImportedCommandCandidate};
        use super::policy::resolve_unique_command_candidate;

        // MQTTX-style: CLI vs desktop unit workflows at equal (non-ci.yml) rank.
        let test_candidates = [
            ImportedCommandCandidate {
                source_path: ".github/workflows/units_test_desktop.yaml".into(),
                source_tier: CommandSourceTier::Workflow,
                build: None,
                test: Some("npm run test:e2e".into()),
            },
            ImportedCommandCandidate {
                source_path: ".github/workflows/units_test_cli.yaml".into(),
                source_tier: CommandSourceTier::Workflow,
                build: None,
                test: Some("npm run test:cli".into()),
            },
        ];
        let test_refs: Vec<&ImportedCommandCandidate> = test_candidates.iter().collect();
        match resolve_unique_command_candidate(&test_refs, false) {
            super::policy::UniqueCommandResolution::Unique {
                command,
                source_path,
            } => {
                assert_eq!(command, "npm run test:cli");
                assert_eq!(source_path, ".github/workflows/units_test_cli.yaml");
            }
            other => panic!("expected CLI workflow preferred over desktop, got {other:?}"),
        }

        // Serverless-style: framework CI vs binary-installer CI.
        let build_candidates = [
            ImportedCommandCandidate {
                source_path: ".github/workflows/ci-binary-installer.yml".into(),
                source_tier: CommandSourceTier::Workflow,
                build: Some("npm run build:binary".into()),
                test: None,
            },
            ImportedCommandCandidate {
                source_path: ".github/workflows/ci-framework.yml".into(),
                source_tier: CommandSourceTier::Workflow,
                build: Some("npm run build".into()),
                test: None,
            },
        ];
        let build_refs: Vec<&ImportedCommandCandidate> = build_candidates.iter().collect();
        match resolve_unique_command_candidate(&build_refs, true) {
            super::policy::UniqueCommandResolution::Unique {
                command,
                source_path,
            } => {
                assert_eq!(command, "npm run build");
                assert_eq!(source_path, ".github/workflows/ci-framework.yml");
            }
            other => {
                panic!("expected framework workflow preferred over binary-installer, got {other:?}")
            }
        }
    }

    #[test]
    fn workflow_inference_skips_shell_assignments_and_prefers_bazel_build() {
        use super::super::types::ImportedFile;
        use super::extraction::{
            extract_workflow_run_commands, first_matching_workflow_command, infer_workflow_commands,
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
    fn readme_doc_commands_extract_development_build_and_test() {
        use super::super::types::{CommandSourceTier, ImportedFile};
        use super::extraction::infer_readme_commands;

        let readme = ImportedFile {
            path: "README.md".into(),
            contents: r#"
# bat

## Development

```bash
# Recursive clone to retrieve all submodules
git clone --recursive https://github.com/sharkdp/bat

# Build (debug version)
cd bat
cargo build --bins

# Run unit tests and integration tests
cargo test
```
"#
            .into(),
        };

        let candidate = infer_readme_commands(&readme).expect("README commands");
        assert_eq!(candidate.source_tier, CommandSourceTier::ContribDoc);
        assert_eq!(candidate.build.as_deref(), Some("cargo build --bins"));
        assert_eq!(candidate.test.as_deref(), Some("cargo test"));
    }

    #[test]
    fn docs_nextest_examples_publish_runner_not_specific_selector() {
        use super::super::types::ImportedFile;
        use super::extraction::infer_contributing_commands;

        let contributing = ImportedFile {
            path: "CONTRIBUTING.md".into(),
            contents: r#"
# Contributing

For running tests, we recommend nextest.

```shell
cargo nextest run -E 'test(test_name)'
```
"#
            .into(),
        };

        let candidate = infer_contributing_commands(&contributing).expect("CONTRIBUTING commands");
        assert_eq!(candidate.test.as_deref(), Some("cargo nextest run"));
    }

    #[test]
    fn workflow_cargo_selectors_do_not_outrank_workspace_defaults() {
        use super::super::types::{CommandSourceTier, ImportedCommandCandidate};
        use super::policy::resolve_command_field;

        let candidates = [
            ImportedCommandCandidate {
                source_path: "Cargo.toml".into(),
                source_tier: CommandSourceTier::EcosystemDefault,
                build: Some("cargo build --workspace".into()),
                test: Some("cargo test --workspace".into()),
            },
            ImportedCommandCandidate {
                source_path: ".github/workflows/main.yml".into(),
                source_tier: CommandSourceTier::Workflow,
                build: Some("cargo build".into()),
                test: Some("'cargo test -p cargo --test testsuite -- fix::'".into()),
            },
        ];
        let mut notes = Vec::new();
        let mut evidence = Vec::new();
        let mut inferred = Vec::new();

        let build = resolve_command_field(
            &candidates,
            "repo.build",
            true,
            &mut notes,
            &mut evidence,
            &mut inferred,
        )
        .expect("build resolves");
        assert_eq!(build.command, "cargo build --workspace");
        assert_eq!(build.source_path, "Cargo.toml");

        let test = resolve_command_field(
            &candidates,
            "repo.test",
            false,
            &mut notes,
            &mut evidence,
            &mut inferred,
        )
        .expect("test resolves");
        assert_eq!(test.command, "cargo test --workspace");
        assert_eq!(test.source_path, "Cargo.toml");
    }

    #[test]
    fn workflow_go_selectors_do_not_outrank_module_defaults() {
        use super::super::types::{CommandSourceTier, ImportedCommandCandidate};
        use super::policy::resolve_command_field;

        let candidates = [
            ImportedCommandCandidate {
                source_path: "go.mod".into(),
                source_tier: CommandSourceTier::EcosystemDefault,
                build: Some("go build ./...".into()),
                test: Some("go test ./...".into()),
            },
            ImportedCommandCandidate {
                source_path: ".github/workflows/ci.yml".into(),
                source_tier: CommandSourceTier::Workflow,
                build: None,
                test: Some(
                    "go test -race -coverprofile=coverage.txt -covermode=atomic ./...".into(),
                ),
            },
        ];
        let mut notes = Vec::new();
        let mut evidence = Vec::new();
        let mut inferred = Vec::new();

        let test = resolve_command_field(
            &candidates,
            "repo.test",
            false,
            &mut notes,
            &mut evidence,
            &mut inferred,
        )
        .expect("test resolves");
        assert_eq!(test.command, "go test ./...");
        assert_eq!(test.source_path, "go.mod");
    }

    #[test]
    fn workflow_gradle_tasks_defer_to_wrapper_defaults() {
        use super::super::types::{CommandSourceTier, ImportedCommandCandidate};
        use super::policy::resolve_command_field;

        let candidates = [
            ImportedCommandCandidate {
                source_path: "build.gradle".into(),
                source_tier: CommandSourceTier::EcosystemDefault,
                build: Some("./gradlew build".into()),
                test: Some("./gradlew test".into()),
            },
            ImportedCommandCandidate {
                source_path: ".github/workflows/ci.yml".into(),
                source_tier: CommandSourceTier::Workflow,
                build: Some("./gradlew clean publish --stacktrace".into()),
                test: Some("./gradlew systemTest".into()),
            },
        ];
        let mut notes = Vec::new();
        let mut evidence = Vec::new();
        let mut inferred = Vec::new();

        let build = resolve_command_field(
            &candidates,
            "repo.build",
            true,
            &mut notes,
            &mut evidence,
            &mut inferred,
        )
        .expect("build resolves");
        assert_eq!(build.command, "./gradlew build");
        assert_eq!(build.source_path, "build.gradle");

        let test = resolve_command_field(
            &candidates,
            "repo.test",
            false,
            &mut notes,
            &mut evidence,
            &mut inferred,
        )
        .expect("test resolves");
        assert_eq!(test.command, "./gradlew test");
    }

    #[test]
    fn workflow_wrapper_chmod_is_not_a_build_command() {
        use super::extraction::first_matching_workflow_command;

        let chmod = vec!["chmod +x gradlew".to_string()];
        assert_eq!(first_matching_workflow_command(&chmod, true), None);

        let echoed_runner = vec!["echo go test -test.run=DontRunTests -fuzz=$ff".to_string()];
        assert_eq!(first_matching_workflow_command(&echoed_runner, false), None);

        let compile_only = vec!["echo compile step done".to_string()];
        assert_eq!(first_matching_workflow_command(&compile_only, true), None);

        let real_gradle = vec!["./gradlew assembleDebug".to_string()];
        assert_eq!(
            first_matching_workflow_command(&real_gradle, true).as_deref(),
            Some("./gradlew assembleDebug")
        );
    }

    #[test]
    fn docs_reject_package_narrowed_go_test_examples() {
        use super::super::types::ImportedFile;
        use super::extraction::infer_contributing_commands;

        // Shaped like milvus-io/milvus: the contributor doc walks through
        // testing one package; that example is not the repository test command.
        let contributing = ImportedFile {
            path: "CONTRIBUTING.md".into(),
            contents: "# Contributing\n\n## Testing\n\n```shell\ngo test ./internal/datanode -cover\n```\n"
                .into(),
        };
        assert!(infer_contributing_commands(&contributing).is_none());

        // The module-wide form is still accepted.
        let module_wide = ImportedFile {
            path: "CONTRIBUTING.md".into(),
            contents: "# Contributing\n\n## Testing\n\n```shell\ngo test ./...\n```\n".into(),
        };
        let candidate = infer_contributing_commands(&module_wide).expect("CONTRIBUTING commands");
        assert_eq!(candidate.test.as_deref(), Some("go test ./..."));
    }

    #[test]
    fn workflow_run_commands_shed_inline_yaml_quotes() {
        use super::super::types::ImportedFile;
        use super::extraction::infer_workflow_commands;

        let workflow = ImportedFile {
            path: ".github/workflows/ci.yml".into(),
            contents: "jobs:\n  test:\n    steps:\n      - run: 'go test ./...'\n".into(),
        };
        let candidate = infer_workflow_commands(&workflow).expect("workflow commands");
        assert_eq!(candidate.test.as_deref(), Some("go test ./..."));
    }

    #[test]
    fn package_json_test_conflicts_with_python_test_default() {
        use super::super::types::{CommandSourceTier, ImportedCommandCandidate};
        use super::policy::resolve_command_field;

        let candidates = [
            ImportedCommandCandidate {
                source_path: "package.json".into(),
                source_tier: CommandSourceTier::Manifest,
                build: None,
                test: Some("npm test".into()),
            },
            ImportedCommandCandidate {
                source_path: "pyproject.toml".into(),
                source_tier: CommandSourceTier::EcosystemDefault,
                build: Some("python -m build".into()),
                test: Some("tox".into()),
            },
        ];
        let mut notes = Vec::new();
        let mut evidence = Vec::new();
        let mut inferred = Vec::new();

        let test = resolve_command_field(
            &candidates,
            "repo.test",
            false,
            &mut notes,
            &mut evidence,
            &mut inferred,
        );

        assert!(test.is_none());
        assert!(
            notes
                .iter()
                .any(|note| note.contains("package.json") && note.contains("pyproject.toml")),
            "expected cross-ecosystem conflict note, got: {notes:?}",
        );
    }

    #[test]
    fn makefile_commands_name_only_targets_that_exist() {
        use super::super::types::ImportedFile;
        use super::extraction::infer_makefile_commands;

        // Shaped like psf/requests: `ci` and `test-readme` targets exist, but
        // there is no `build` target, so no build command may be published.
        let makefile = ImportedFile {
            path: "Makefile".into(),
            contents: ".PHONY: docs\ninit:\n\tpython -m pip install -r requirements-dev.txt\ntest:\n\tpython -m pytest tests\n\nci:\n\tpython -m pytest tests --junitxml=report.xml\n\ntest-readme:\n\techo check\n".into(),
        };
        let candidate = infer_makefile_commands(&makefile).expect("Makefile commands");
        assert_eq!(candidate.build, None);
        assert_eq!(candidate.test.as_deref(), Some("python -m pytest tests"));

        // A Makefile whose only build-ish target is `all` publishes `make all`
        // when the recipe is project-specific rather than a canonical
        // developer command that can stand alone.
        let all_only = ImportedFile {
            path: "Makefile".into(),
            contents: "all:\n\tgcc -o app main.c\n\ncheck:\n\t./run-tests.sh\n".into(),
        };
        let candidate = infer_makefile_commands(&all_only).expect("Makefile commands");
        assert_eq!(candidate.build.as_deref(), Some("make all"));
        assert_eq!(candidate.test.as_deref(), Some("make check"));

        // Multi-step recipes remain wrapper commands because the target is the
        // audited entrypoint for the sequence.
        let multi_step = ImportedFile {
            path: "Makefile".into(),
            contents: "test:\n\tpython -m pip install -e .\n\tpython -m pytest tests\n".into(),
        };
        let candidate = infer_makefile_commands(&multi_step).expect("Makefile commands");
        assert_eq!(candidate.test.as_deref(), Some("make test"));
    }

    #[test]
    fn docs_accept_cargo_toolchain_override_and_keep_it_in_the_command() {
        use super::super::types::ImportedFile;
        use super::extraction::infer_contributing_commands;

        // Shaped like serde-rs/serde: the full-suite command pins a toolchain
        // and lives under a directory-specific subheading of the test section.
        let contributing = ImportedFile {
            path: "CONTRIBUTING.md".into(),
            contents: r#"
# Contributing

## Running the test suite

##### In the [`test_suite`] directory

```sh
# Run the full test suite, including tests of unstable functionality
cargo +nightly test --features unstable
```
"#
            .into(),
        };

        let candidate = infer_contributing_commands(&contributing).expect("CONTRIBUTING commands");
        assert_eq!(
            candidate.test.as_deref(),
            Some("cargo +nightly test --features unstable")
        );
        assert_eq!(candidate.build, None);
    }

    #[test]
    fn docs_strip_leading_env_assignments_from_test_commands() {
        use super::super::types::ImportedFile;
        use super::extraction::infer_contributing_commands;

        let contributing = ImportedFile {
            path: "CONTRIBUTING.md".into(),
            contents: r#"
# Contributing

```shell
RUFF_UPDATE_SCHEMA=1 cargo test
```
"#
            .into(),
        };

        let candidate = infer_contributing_commands(&contributing).expect("CONTRIBUTING commands");
        assert_eq!(candidate.test.as_deref(), Some("cargo test"));
    }

    #[test]
    fn workflow_inference_ignores_specialized_cargo_commands() {
        use super::super::types::ImportedFile;
        use super::extraction::first_matching_workflow_command;
        use super::extraction::infer_workflow_commands;

        let target_specific = vec!["cargo build --bin ruff".to_string()];
        assert_eq!(
            first_matching_workflow_command(&target_specific, true),
            None
        );

        let equals_target_specific = vec!["cargo build --profile=profiling --bin=ty".to_string()];
        assert_eq!(
            first_matching_workflow_command(&equals_target_specific, true),
            None
        );

        let release_build = vec!["cargo build --release".to_string()];
        assert_eq!(
            first_matching_workflow_command(&release_build, true).as_deref(),
            Some("cargo build --release")
        );

        let target_features_build =
            vec!["cargo build --target x86_64-fortanix-unknown-sgx --features rt,sync".to_string()];
        assert_eq!(
            first_matching_workflow_command(&target_features_build, true),
            None
        );

        let doc_only_test = vec!["cargo test --doc --features full".to_string()];
        assert_eq!(first_matching_workflow_command(&doc_only_test, false), None);

        let fuzz_workflow = ImportedFile {
            path: ".github/workflows/daily_fuzz.yaml".into(),
            contents: "jobs:\n  fuzz:\n    steps:\n      - run: cargo build --locked\n".into(),
        };
        assert!(infer_workflow_commands(&fuzz_workflow).is_none());

        let format_workflow = ImportedFile {
            path: ".github/workflows/format-workflow.yml".into(),
            contents: "jobs:\n  format:\n    steps:\n      - run: npm run build\n".into(),
        };
        assert!(infer_workflow_commands(&format_workflow).is_none());

        let release_workflow = ImportedFile {
            path: ".github/workflows/release.yml".into(),
            contents: "jobs:\n  release:\n    steps:\n      - run: npm run build\n".into(),
        };
        assert!(infer_workflow_commands(&release_workflow).is_none());
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
    fn infer_gradle_commands_uses_wrapper_only_when_present() {
        use super::super::types::ImportedFile;
        use super::extraction::infer_gradle_commands;
        let groovy = ImportedFile {
            path: "build.gradle".into(),
            contents: "plugins { id 'java' }".into(),
        };
        let kts = ImportedFile {
            path: "build.gradle.kts".into(),
            contents: "plugins { java }".into(),
        };
        let g1 = infer_gradle_commands(&groovy, true).expect("groovy");
        let g2 = infer_gradle_commands(&kts, false).expect("kts");
        assert_eq!(g1.build.as_deref(), Some("./gradlew build"));
        assert_eq!(g2.test.as_deref(), Some("gradle test"));
    }

    #[test]
    fn infer_setup_commands_provide_pytest_for_classic_python() {
        use super::super::types::ImportedFile;
        use super::extraction::{infer_setup_cfg_commands, infer_setup_py_commands};
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
        use super::super::types::ImportedFile;
        use super::extraction::{infer_setup_py_commands, infer_setup_py_test_command};
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
        use super::super::types::ImportedFile;
        use super::extraction::infer_setup_py_commands;
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
        use super::super::types::ImportedFile;
        use super::extraction::{infer_setup_cfg_commands, infer_setup_cfg_test_command};
        let metadata_only = ImportedFile {
            path: "setup.cfg".into(),
            contents: "[metadata]\nname = latest-contest-kit\n".into(),
        };
        assert!(infer_setup_cfg_test_command(&metadata_only.contents).is_none());
        assert!(infer_setup_cfg_commands(&metadata_only).is_none());
    }

    #[test]
    fn infer_setup_cfg_detects_extras_require_test_pytest() {
        use super::super::types::ImportedFile;
        use super::extraction::infer_setup_cfg_commands;
        let setup_cfg = ImportedFile {
            path: "setup.cfg".into(),
            contents: "[options.extras_require]\ntest = pytest>=7\n".into(),
        };
        let candidate = infer_setup_cfg_commands(&setup_cfg).expect("setup.cfg");
        assert_eq!(candidate.test.as_deref(), Some("python -m pytest"));
    }

    #[test]
    fn pyproject_tox_conflicts_with_setup_py_pytest_instead_of_losing() {
        use super::super::types::ImportedFile;
        use super::infer_imported_commands;
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
            readme: None,
            cargo_toml: None,
            rust_toolchain_toml: None,
            rust_toolchain: None,
            package_json: None,
            pyproject_toml: Some(&pyproject),
            setup_py: Some(&setup_py),
            setup_cfg: None,
            go_mod: None,
            pom_xml: None,
            maven_wrapper: false,
            build_gradle: None,
            gradle_wrapper: false,
            composer_json: None,
            csproj: None,
            solution: None,
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
