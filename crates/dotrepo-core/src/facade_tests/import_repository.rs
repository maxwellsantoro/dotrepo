use super::common::*;

#[test]
fn import_repository_accepts_readme_variants_and_preserves_their_paths() {
    let root = temp_dir("import-readme-variant");
    fs::write(
        root.join("README.mdx"),
        "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
    )
    .expect("README variant written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit"),
    )
    .expect("import succeeds");

    assert!(plan
        .imported_sources
        .iter()
        .any(|path| path == "README.mdx"));
    assert_eq!(plan.manifest.repo.name, "Orbit");
    assert_eq!(
        plan.manifest.repo.description,
        "Policy-aware release orchestration for multi-service deploys."
    );
    assert!(plan.evidence_text.as_deref().is_some_and(
        |text| text.contains("Imported repository name and description from README.mdx.")
    ));

    // absent discovery (no github facts) must leave relations absent (no spurious empty table)
    assert!(
        plan.manifest.relations.is_none(),
        "overlay import without discovery evidence must not emit relations table"
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_imports_cargo_workspace_build_and_test_commands() {
    let root = temp_dir("import-cargo-commands");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
    )
    .expect("README written");
    fs::write(
        root.join("Cargo.toml"),
        "[workspace]\nmembers = [\"crates/orbit\"]\n",
    )
    .expect("Cargo.toml written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit"),
    )
    .expect("import succeeds");

    assert_eq!(
        plan.manifest.repo.build.as_deref(),
        Some("cargo build --workspace")
    );
    assert_eq!(
        plan.manifest.repo.test.as_deref(),
        Some("cargo test --workspace")
    );
    assert!(plan
        .imported_sources
        .iter()
        .any(|path| path == "Cargo.toml"));
    assert!(plan
        .manifest
        .record
        .trust
        .as_ref()
        .and_then(|trust| trust.notes.as_deref())
        .is_some_and(|text| text.contains("Inferred `repo.build` from `Cargo.toml`.")));
    assert!(plan
        .evidence_text
        .as_deref()
        .is_some_and(|text| text
            .contains("Inferred repo.build from Cargo.toml as `cargo build --workspace`.")));
    assert!(plan.evidence_text.as_deref().is_some_and(
        |text| text.contains("Inferred repo.test from Cargo.toml as `cargo test --workspace`.")
    ));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_imports_package_json_commands_with_runner_detection() {
    let root = temp_dir("import-package-json-commands");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
    )
    .expect("README written");
    fs::write(
        root.join("package.json"),
        r#"{
  "name": "orbit",
  "packageManager": "pnpm@9.1.0",
  "scripts": {
    "build": "vite build",
    "test": "vitest run"
  }
}
"#,
    )
    .expect("package.json written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build.as_deref(), Some("pnpm build"));
    assert_eq!(plan.manifest.repo.test.as_deref(), Some("pnpm test"));
    assert!(plan
        .imported_sources
        .iter()
        .any(|path| path == "package.json"));
    assert!(plan
        .evidence_text
        .as_deref()
        .is_some_and(|text| text.contains("Imported repo.test from package.json as `pnpm test`.")));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_imports_pyproject_build_and_test_defaults() {
    let root = temp_dir("import-pyproject-commands");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
    )
    .expect("README written");
    fs::write(
        root.join("pyproject.toml"),
        r#"[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
"#,
    )
    .expect("pyproject written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build.as_deref(), Some("python -m build"));
    assert_eq!(plan.manifest.repo.test.as_deref(), Some("python -m pytest"));
    assert!(plan
        .imported_sources
        .iter()
        .any(|path| path == "pyproject.toml"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_imports_go_module_build_and_test_defaults() {
    let root = temp_dir("import-go-mod-commands");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
    )
    .expect("README written");
    fs::write(
        root.join("go.mod"),
        "module github.com/example/orbit\n\ngo 1.24\n",
    )
    .expect("go.mod written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build.as_deref(), Some("go build ./..."));
    assert_eq!(plan.manifest.repo.test.as_deref(), Some("go test ./..."));
    assert!(plan.imported_sources.iter().any(|path| path == "go.mod"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_imports_maven_build_and_test_defaults() {
    let root = temp_dir("import-maven-commands");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
    )
    .expect("README written");
    fs::write(
        root.join("pom.xml"),
        r#"<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>orbit</artifactId>
  <version>1.0.0</version>
</project>
"#,
    )
    .expect("pom.xml written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build.as_deref(), Some("mvn package"));
    assert_eq!(plan.manifest.repo.test.as_deref(), Some("mvn test"));
    assert!(plan.imported_sources.iter().any(|path| path == "pom.xml"));
    assert!(plan
        .evidence_text
        .as_deref()
        .is_some_and(|text| text.contains("Inferred repo.test from pom.xml as `mvn test`.")));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_ignores_non_maven_xml_named_pom() {
    let root = temp_dir("import-invalid-maven-pom");
    fs::write(root.join("pom.xml"), "<not-a-project />\n").expect("pom.xml written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build, None);
    assert_eq!(plan.manifest.repo.test, None);
    assert!(!plan.imported_sources.iter().any(|path| path == "pom.xml"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_imports_composer_build_and_test_scripts() {
    let root = temp_dir("import-composer-commands");
    fs::write(
        root.join("README.md"),
        "# Orbit PHP\n\nPolicy-aware release orchestration for PHP services.\n",
    )
    .expect("README written");
    fs::write(
        root.join("composer.json"),
        r#"{
  "name": "example/orbit",
  "scripts": {
    "build": "@php bin/build.php",
    "test": ["@php vendor/bin/phpunit", "@php vendor/bin/phpstan"]
  }
}
"#,
    )
    .expect("composer.json written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit-php"),
    )
    .expect("import succeeds");

    assert_eq!(
        plan.manifest.repo.build.as_deref(),
        Some("composer run-script build")
    );
    assert_eq!(
        plan.manifest.repo.test.as_deref(),
        Some("composer run-script test")
    );
    assert!(plan
        .imported_sources
        .iter()
        .any(|path| path == "composer.json"));
    assert!(plan.evidence_text.as_deref().is_some_and(|text| text
        .contains("Imported repo.test from composer.json as `composer run-script test`.")));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_ignores_empty_or_invalid_composer_scripts() {
    let root = temp_dir("import-empty-composer-commands");
    fs::write(
        root.join("composer.json"),
        r#"{"scripts":{"build":"  ","test":["",42]}}"#,
    )
    .expect("composer.json written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit-php"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build, None);
    assert_eq!(plan.manifest.repo.test, None);
    assert!(!plan
        .imported_sources
        .iter()
        .any(|path| path == "composer.json"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_imports_explicit_dotnet_test_project_commands() {
    let root = temp_dir("import-dotnet-test-project");
    fs::write(
        root.join("README.md"),
        "# Orbit Tests\n\nIntegration tests for the Orbit service.\n",
    )
    .expect("README written");
    fs::write(
        root.join("Orbit.Tests.csproj"),
        r#"<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <IsTestProject>true</IsTestProject>
  </PropertyGroup>
</Project>
"#,
    )
    .expect("csproj written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit-tests"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build.as_deref(), Some("dotnet build"));
    assert_eq!(plan.manifest.repo.test.as_deref(), Some("dotnet test"));
    assert!(plan
        .imported_sources
        .iter()
        .any(|path| path == "Orbit.Tests.csproj"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_only_builds_non_test_dotnet_project() {
    let root = temp_dir("import-dotnet-library-project");
    fs::write(
        root.join("Orbit.csproj"),
        r#"<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup>
</Project>
"#,
    )
    .expect("csproj written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build.as_deref(), Some("dotnet build"));
    assert_eq!(plan.manifest.repo.test, None);

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_imports_mix_project_commands() {
    let root = temp_dir("import-mix-project");
    fs::write(
        root.join("README.md"),
        "# Orbit Elixir\n\nA small concurrent service for release orchestration.\n",
    )
    .expect("README written");
    fs::write(
        root.join("mix.exs"),
        r#"defmodule Orbit.MixProject do
  use Mix.Project

  def project do
    [app: :orbit, version: "1.0.0", elixir: "~> 1.16"]
  end
end
"#,
    )
    .expect("mix.exs written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit-elixir"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build.as_deref(), Some("mix compile"));
    assert_eq!(plan.manifest.repo.test.as_deref(), Some("mix test"));
    assert!(plan.imported_sources.iter().any(|path| path == "mix.exs"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_ignores_comment_only_mix_project_signals() {
    let root = temp_dir("import-invalid-mix-project");
    fs::write(
        root.join("mix.exs"),
        "# defmodule Fake.MixProject do\n# use Mix.Project\n# def project do\n",
    )
    .expect("mix.exs written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/not-mix"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build, None);
    assert_eq!(plan.manifest.repo.test, None);
    assert!(!plan.imported_sources.iter().any(|path| path == "mix.exs"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_imports_rebar_project_commands() {
    let root = temp_dir("import-rebar-project");
    fs::write(
        root.join("README.md"),
        "# Orbit Erlang\n\nA small fault-tolerant release coordinator.\n",
    )
    .expect("README written");
    fs::write(
        root.join("rebar.config"),
        "{erl_opts, [debug_info]}.\n{deps, []}.\n",
    )
    .expect("rebar.config written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit-erlang"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build.as_deref(), Some("rebar3 compile"));
    assert_eq!(plan.manifest.repo.test.as_deref(), Some("rebar3 eunit"));
    assert!(plan
        .imported_sources
        .iter()
        .any(|path| path == "rebar.config"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_ignores_comment_only_rebar_terms() {
    let root = temp_dir("import-invalid-rebar-project");
    fs::write(
        root.join("rebar.config"),
        "% {erl_opts, [debug_info]}.\nnot an Erlang configuration term\n",
    )
    .expect("rebar.config written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/not-rebar"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build, None);
    assert_eq!(plan.manifest.repo.test, None);
    assert!(!plan
        .imported_sources
        .iter()
        .any(|path| path == "rebar.config"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_imports_explicit_rake_tasks() {
    let root = temp_dir("import-rake-tasks");
    fs::write(
        root.join("README.md"),
        "# Orbit Ruby\n\nA compact release orchestration library for Ruby.\n",
    )
    .expect("README written");
    fs::write(
        root.join("Rakefile"),
        "task :build do\nend\n\ntask \"test\" => :build do\nend\n",
    )
    .expect("Rakefile written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit-ruby"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build.as_deref(), Some("rake build"));
    assert_eq!(plan.manifest.repo.test.as_deref(), Some("rake test"));
    assert!(plan.imported_sources.iter().any(|path| path == "Rakefile"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_ignores_comments_and_prefixed_rake_tasks() {
    let root = temp_dir("import-invalid-rake-tasks");
    fs::write(
        root.join("Rakefile"),
        "# task :build do\ntask :test_helper do\nend\n",
    )
    .expect("Rakefile written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/not-rake"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build, None);
    assert_eq!(plan.manifest.repo.test, None);
    assert!(!plan.imported_sources.iter().any(|path| path == "Rakefile"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_imports_cmake_workflow_presets() {
    let root = temp_dir("import-cmake-workflows");
    fs::write(
        root.join("README.md"),
        "# Orbit C++\n\nA compact native release orchestration library.\n",
    )
    .expect("README written");
    fs::write(
        root.join("CMakePresets.json"),
        r#"{
  "version": 6,
  "workflowPresets": [
    {
      "name": "build-ci",
      "steps": [
        {"type": "configure", "name": "ci"},
        {"type": "build", "name": "ci"}
      ]
    },
    {
      "name": "test-ci",
      "steps": [
        {"type": "configure", "name": "ci"},
        {"type": "build", "name": "ci"},
        {"type": "test", "name": "ci"}
      ]
    }
  ]
}
"#,
    )
    .expect("CMakePresets.json written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit-cpp"),
    )
    .expect("import succeeds");

    assert_eq!(
        plan.manifest.repo.build.as_deref(),
        Some("cmake --workflow --preset build-ci")
    );
    assert_eq!(
        plan.manifest.repo.test.as_deref(),
        Some("cmake --workflow --preset test-ci")
    );
    assert!(plan
        .imported_sources
        .iter()
        .any(|path| path == "CMakePresets.json"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_ignores_unsafe_or_incomplete_cmake_workflows() {
    let root = temp_dir("import-invalid-cmake-workflows");
    fs::write(
        root.join("CMakePresets.json"),
        r#"{
  "version": 6,
  "workflowPresets": [
    {"name": "unsafe workflow", "steps": [
      {"type": "configure", "name": "ci"},
      {"type": "build", "name": "ci"}
    ]},
    {"name": "test-only", "steps": [{"type": "test", "name": "ci"}]}
  ]
}
"#,
    )
    .expect("CMakePresets.json written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/not-cmake"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build, None);
    assert_eq!(plan.manifest.repo.test, None);
    assert!(!plan
        .imported_sources
        .iter()
        .any(|path| path == "CMakePresets.json"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn declared_package_commands_beat_cargo_ecosystem_defaults() {
    let root = temp_dir("import-conflicting-commands");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
    )
    .expect("README written");
    fs::write(
        root.join("Cargo.toml"),
        "[workspace]\nmembers = [\"crates/orbit\"]\n",
    )
    .expect("Cargo.toml written");
    fs::write(
        root.join("package.json"),
        r#"{
  "name": "orbit",
  "scripts": {
    "build": "vite build",
    "test": "vitest run"
  }
}
"#,
    )
    .expect("package.json written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build.as_deref(), Some("npm run build"));
    assert_eq!(plan.manifest.repo.test.as_deref(), Some("npm test"));
    assert!(plan
        .imported_sources
        .iter()
        .any(|path| path == "package.json"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_falls_back_to_workflow_commands_when_manifests_are_absent() {
    let root = temp_dir("import-workflow-commands");
    fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir created");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
    )
    .expect("README written");
    fs::write(
        root.join(".github/workflows/ci.yml"),
        r#"name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cargo build --workspace
      - run: cargo test --workspace
"#,
    )
    .expect("workflow written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit"),
    )
    .expect("import succeeds");

    assert_eq!(
        plan.manifest.repo.build.as_deref(),
        Some("cargo build --workspace")
    );
    assert_eq!(
        plan.manifest.repo.test.as_deref(),
        Some("cargo test --workspace")
    );
    assert_eq!(
        plan.inferred_fields,
        vec!["repo.build".to_string(), "repo.test".to_string()]
    );
    assert_eq!(plan.manifest.record.status, RecordStatus::Inferred);
    assert!(plan
        .imported_sources
        .iter()
        .any(|path| path == ".github/workflows/ci.yml"));
    assert!(plan
        .manifest
        .record
        .trust
        .as_ref()
        .and_then(|trust| trust.notes.as_deref())
        .is_some_and(
            |text| text.contains("Inferred `repo.build` from `.github/workflows/ci.yml`.")
        ));
    assert!(plan
        .evidence_text
        .as_deref()
        .is_some_and(|text| text.contains(
            "Inferred repo.build from .github/workflows/ci.yml as `cargo build --workspace`."
        )));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_keeps_manifest_commands_imported_when_workflow_agrees() {
    let root = temp_dir("import-manifest-workflow-agree");
    fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir created");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
    )
    .expect("README written");
    fs::write(
        root.join("Cargo.toml"),
        "[workspace]\nmembers = [\"crates/orbit\"]\n",
    )
    .expect("Cargo.toml written");
    fs::write(
        root.join(".github/workflows/ci.yml"),
        r#"name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: cargo build --workspace
      - run: cargo test --workspace
"#,
    )
    .expect("workflow written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit"),
    )
    .expect("import succeeds");

    assert_eq!(
        plan.manifest.repo.build.as_deref(),
        Some("cargo build --workspace")
    );
    assert_eq!(
        plan.manifest.repo.test.as_deref(),
        Some("cargo test --workspace")
    );
    assert!(plan.inferred_fields.contains(&"repo.build".to_string()));
    assert!(plan.inferred_fields.contains(&"repo.test".to_string()));
    assert!(!plan
        .imported_sources
        .iter()
        .any(|path| path == "Cargo.toml"));
    assert!(plan
        .imported_sources
        .iter()
        .any(|path| path == ".github/workflows/ci.yml"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn observed_workflow_beats_ecosystem_default() {
    let root = temp_dir("import-manifest-workflow-conflict");
    fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir created");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
    )
    .expect("README written");
    fs::write(
        root.join("Cargo.toml"),
        "[workspace]\nmembers = [\"crates/orbit\"]\n",
    )
    .expect("Cargo.toml written");
    fs::write(
        root.join(".github/workflows/ci.yml"),
        r#"name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: cargo build
      - run: cargo test
"#,
    )
    .expect("workflow written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build.as_deref(), Some("cargo build"));
    assert_eq!(plan.manifest.repo.test.as_deref(), Some("cargo test"));
    assert!(plan.inferred_fields.contains(&"repo.build".to_string()));
    assert!(plan.inferred_fields.contains(&"repo.test".to_string()));
    assert!(plan
        .imported_sources
        .iter()
        .any(|path| path == ".github/workflows/ci.yml"));
    assert!(
        plan.manifest
            .record
            .trust
            .as_ref()
            .and_then(|trust| trust.notes.as_deref())
            .is_some_and(
                |text| text.contains("Inferred `repo.build` from `.github/workflows/ci.yml`")
            )
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_prefers_primary_ci_workflow_over_release_workflow() {
    let root = temp_dir("import-workflow-conflict");
    fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir created");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nPolicy-aware release orchestration for multi-service deploys.\n",
    )
    .expect("README written");
    fs::write(
        root.join(".github/workflows/ci.yml"),
        r#"name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: cargo build --workspace
      - run: cargo test --workspace
"#,
    )
    .expect("ci workflow written");
    fs::write(
        root.join(".github/workflows/release.yml"),
        r#"name: Release
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: cargo build
      - run: cargo test
"#,
    )
    .expect("release workflow written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit"),
    )
    .expect("import succeeds");

    assert_eq!(
        plan.manifest.repo.build.as_deref(),
        Some("cargo build --workspace")
    );
    assert_eq!(
        plan.manifest.repo.test.as_deref(),
        Some("cargo test --workspace")
    );
    assert!(plan
        .inferred_fields
        .iter()
        .any(|field| field == "repo.build" || field == "repo.test"));
    assert!(plan
        .manifest
        .record
        .trust
        .as_ref()
        .and_then(|trust| trust.notes.as_deref())
        .is_some_and(
            |text| text.contains("Inferred `repo.build` from `.github/workflows/ci.yml`.")
        ));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn declared_package_commands_beat_other_ecosystem_defaults() {
    let root = temp_dir("import-manifest-manifest-conflict");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nPolicy-aware release orchestration.\n",
    )
    .expect("README written");
    fs::write(
        root.join("Cargo.toml"),
        "[workspace]\nmembers = [\"crates/orbit\"]\n",
    )
    .expect("Cargo.toml written");
    fs::write(
        root.join("package.json"),
        r#"{"scripts":{"build":"npm run build","test":"npm test"}}"#,
    )
    .expect("package.json written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build.as_deref(), Some("npm run build"));
    assert_eq!(plan.manifest.repo.test.as_deref(), Some("npm test"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn workflow_only_fallback() {
    let root = temp_dir("import-workflow-only");
    fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir created");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nPolicy-aware release orchestration.\n",
    )
    .expect("README written");
    fs::write(
        root.join(".github/workflows/ci.yml"),
        r#"name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: cargo build
      - run: cargo test
"#,
    )
    .expect("workflow written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build.as_deref(), Some("cargo build"));
    assert_eq!(plan.manifest.repo.test.as_deref(), Some("cargo test"));
    assert!(plan.inferred_fields.contains(&"repo.build".to_string()));
    assert!(plan.inferred_fields.contains(&"repo.test".to_string()));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn manifest_workflow_agree() {
    let root = temp_dir("import-manifest-workflow-agree");
    fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir created");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nPolicy-aware release orchestration.\n",
    )
    .expect("README written");
    fs::write(
        root.join("Cargo.toml"),
        "[workspace]\nmembers = [\"crates/orbit\"]\n",
    )
    .expect("Cargo.toml written");
    fs::write(
        root.join(".github/workflows/ci.yml"),
        r#"name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: cargo build --workspace
      - run: cargo test --workspace
"#,
    )
    .expect("workflow written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/orbit"),
    )
    .expect("import succeeds");

    assert_eq!(
        plan.manifest.repo.build.as_deref(),
        Some("cargo build --workspace")
    );
    assert_eq!(
        plan.manifest.repo.test.as_deref(),
        Some("cargo test --workspace")
    );
    assert!(plan.inferred_fields.contains(&"repo.build".to_string()));
    assert!(plan.inferred_fields.contains(&"repo.test".to_string()));
    assert!(!plan
        .imported_sources
        .iter()
        .any(|path| path == "Cargo.toml"));
    assert!(plan
        .imported_sources
        .iter()
        .any(|path| path == ".github/workflows/ci.yml"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn makefile_produces_taskscript_candidates() {
    let root = temp_dir("import-makefile");
    fs::write(
        root.join("README.md"),
        "# MakeProj\n\nA project with a Makefile.\n",
    )
    .expect("README written");
    fs::write(
        root.join("Makefile"),
        "build:\n\tgo build ./...\n\ntest:\n\tgo test ./...\n",
    )
    .expect("Makefile written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/makeproj"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build.as_deref(), Some("make build"));
    assert_eq!(plan.manifest.repo.test.as_deref(), Some("make test"));
    assert!(plan.inferred_fields.is_empty());

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn justfile_produces_taskscript_candidates() {
    let root = temp_dir("import-justfile");
    fs::write(
        root.join("README.md"),
        "# JustProj\n\nA project with a Justfile.\n",
    )
    .expect("README written");
    fs::write(
        root.join("justfile"),
        "build:\n    cargo build\n\ntest:\n    cargo test\n",
    )
    .expect("justfile written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/justproj"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build.as_deref(), Some("just build"));
    assert_eq!(plan.manifest.repo.test.as_deref(), Some("just test"));
    assert!(plan.inferred_fields.is_empty());

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn justfile_assignments_do_not_produce_taskscript_candidates() {
    let root = temp_dir("import-justfile-assignments");
    fs::write(
        root.join("README.md"),
        "# JustVars\n\nA project with justfile variables only.\n",
    )
    .expect("README written");
    fs::write(
        root.join("justfile"),
        "build := \"cargo build\"\n\
             test := \"cargo test\"\n",
    )
    .expect("justfile written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/justvars"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build, None);
    assert_eq!(plan.manifest.repo.test, None);

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn contributing_md_produces_contribdoc_candidates() {
    let root = temp_dir("import-contributing");
    fs::write(
        root.join("README.md"),
        "# ContribProj\n\nA project with CONTRIBUTING.md.\n",
    )
    .expect("README written");
    fs::write(
            root.join("CONTRIBUTING.md"),
            "# Contributing\n\n## Build\n\n```bash\ncargo build\n```\n\n## Test\n\n```bash\ncargo test\n```\n",
        )
        .expect("CONTRIBUTING.md written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/contribproj"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build.as_deref(), Some("cargo build"));
    assert_eq!(plan.manifest.repo.test.as_deref(), Some("cargo test"));
    assert!(plan.inferred_fields.is_empty());

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn contributing_md_does_not_treat_make_lint_as_build_command() {
    let root = temp_dir("import-contributing-lint");
    fs::write(
        root.join("README.md"),
        "# ContribLint\n\nA project with CONTRIBUTING.md.\n",
    )
    .expect("README written");
    fs::write(
        root.join("CONTRIBUTING.md"),
        "# Contributing\n\n```bash\nmake lint\nmake test\n```\n",
    )
    .expect("CONTRIBUTING.md written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/contriblint"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build, None);
    assert_eq!(plan.manifest.repo.test.as_deref(), Some("make test"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn declared_makefile_beats_ecosystem_default() {
    let root = temp_dir("import-manifest-beats-makefile");
    fs::write(
        root.join("README.md"),
        "# Tiers\n\nDeclared commands should win over ecosystem defaults.\n",
    )
    .expect("README written");
    fs::write(
        root.join("Cargo.toml"),
        "[package]\nname = \"tiers\"\nversion = \"0.1.0\"\n",
    )
    .expect("Cargo.toml written");
    fs::write(
        root.join("Makefile"),
        "build:\n\techo building\n\ntest:\n\techo testing\n",
    )
    .expect("Makefile written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/tiers"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build.as_deref(), Some("make build"));
    assert_eq!(plan.manifest.repo.test.as_deref(), Some("make test"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn makefile_beats_workflow() {
    let root = temp_dir("import-makefile-beats-workflow");
    fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir");
    fs::write(
        root.join("README.md"),
        "# Tiered\n\nMakefile beats workflow.\n",
    )
    .expect("README written");
    fs::write(
        root.join("Makefile"),
        "build:\n\tgo build ./...\n\ntest:\n\tgo test ./...\n",
    )
    .expect("Makefile written");
    fs::write(
            root.join(".github/workflows/ci.yml"),
            "name: CI\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: go build\n      - run: go test\n",
        )
        .expect("workflow written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/tiered"),
    )
    .expect("import succeeds");

    assert_eq!(plan.manifest.repo.build.as_deref(), Some("make build"));
    assert_eq!(plan.manifest.repo.test.as_deref(), Some("make test"));
    assert!(plan.inferred_fields.is_empty());

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_bootstraps_native_manifest_from_conventional_files() {
    let root = temp_dir("import-native");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nFast local-first sync engine.\n",
    )
    .expect("README written");
    fs::create_dir_all(root.join(".github")).expect(".github created");
    fs::write(root.join(".github/CODEOWNERS"), "* @orbit-maintainer\n")
        .expect("CODEOWNERS written");
    fs::write(
        root.join(".github/SECURITY.md"),
        "Report vulnerabilities to security@example.com.\n",
    )
    .expect("SECURITY written");

    let plan = import_repository(&root, ImportMode::Native, None).expect("native import succeeds");

    assert_eq!(plan.manifest.record.mode, RecordMode::Native);
    assert_eq!(plan.manifest.record.status, RecordStatus::Draft);
    assert_eq!(plan.manifest.repo.name, "Orbit");
    assert_eq!(
        plan.manifest.repo.description,
        "Fast local-first sync engine."
    );
    assert_eq!(
        plan.manifest
            .owners
            .as_ref()
            .expect("owners imported")
            .maintainers,
        vec!["@orbit-maintainer"]
    );
    assert_eq!(
        plan.manifest
            .owners
            .as_ref()
            .and_then(|owners| owners.security_contact.as_deref()),
        Some("security@example.com")
    );
    assert_eq!(plan.imported_sources.len(), 3);
    assert!(plan.evidence_text.is_none());
    let github = plan
        .manifest
        .compat
        .as_ref()
        .and_then(|compat| compat.github.as_ref())
        .expect("github compat present");
    assert_eq!(github.codeowners, Some(CompatMode::Generate));
    assert_eq!(github.security, Some(CompatMode::Skip));
    assert_eq!(github.contributing, Some(CompatMode::Skip));
    assert_eq!(github.pull_request_template, Some(CompatMode::Skip));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_enables_generate_only_for_reproducible_surfaces() {
    let root = temp_dir("import-native-reproducible");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nFast local-first sync engine.\n",
    )
    .expect("README written");
    fs::create_dir_all(root.join(".github")).expect(".github created");
    fs::write(root.join(".github/CODEOWNERS"), "* @orbit-maintainer\n")
        .expect("CODEOWNERS written");
    fs::write(
        root.join(".github/SECURITY.md"),
        "# Security\n\nPlease report vulnerabilities to security@example.com.\n",
    )
    .expect("SECURITY written");
    fs::write(
            root.join("CONTRIBUTING.md"),
            "# Contributing\n\nThanks for contributing to Orbit.\n\n## Before you open a change\n\n- Review the repository documentation and policies.\n\n## Security\n\nReport suspected vulnerabilities to security@example.com instead of opening a public issue.\n",
        )
        .expect("CONTRIBUTING written");
    fs::write(
            root.join(".github/pull_request_template.md"),
            "## Summary\n\n- Describe the user-visible change.\n\n## Validation\n\n- [ ] Describe how you validated this change.\n\n## Checklist\n\n- [ ] Documentation updated where needed.\n- [ ] Ownership, policy, and security impacts considered.\n",
        )
        .expect("PR template written");

    let plan = import_repository(&root, ImportMode::Native, None).expect("native import succeeds");

    let github = plan
        .manifest
        .compat
        .as_ref()
        .and_then(|compat| compat.github.as_ref())
        .expect("github compat present");
    assert_eq!(github.codeowners, Some(CompatMode::Generate));
    assert_eq!(github.security, Some(CompatMode::Generate));
    assert_eq!(github.contributing, Some(CompatMode::Generate));
    assert_eq!(github.pull_request_template, Some(CompatMode::Generate));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_keeps_richer_surfaces_at_skip() {
    let root = temp_dir("import-native-rich");
    fs::write(
        root.join("README.md"),
        "# Orbit\n\nFast local-first sync engine.\n",
    )
    .expect("README written");
    fs::create_dir_all(root.join(".github")).expect(".github created");
    fs::write(
        root.join(".github/CODEOWNERS"),
        "* @orbit-maintainer\n/docs/ @docs-team\n",
    )
    .expect("CODEOWNERS written");
    fs::write(
            root.join(".github/SECURITY.md"),
            "# Security\n\nReport vulnerabilities to security@example.com.\n\nSee docs/security.md for the full disclosure policy.\n",
        )
        .expect("SECURITY written");
    fs::write(
            root.join("CONTRIBUTING.md"),
            "# Contributing\n\nUse the repository-specific release checklist before opening a change.\n",
        )
        .expect("CONTRIBUTING written");
    fs::write(
        root.join(".github/pull_request_template.md"),
        "## Type of change\n\n- [ ] Feature\n- [ ] Fix\n",
    )
    .expect("PR template written");

    let plan = import_repository(&root, ImportMode::Native, None).expect("native import succeeds");

    let github = plan
        .manifest
        .compat
        .as_ref()
        .and_then(|compat| compat.github.as_ref())
        .expect("github compat present");
    assert_eq!(github.codeowners, Some(CompatMode::Skip));
    assert_eq!(github.security, Some(CompatMode::Skip));
    assert_eq!(github.contributing, Some(CompatMode::Skip));
    assert_eq!(github.pull_request_template, Some(CompatMode::Skip));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_marks_overlay_fallbacks_as_inferred() {
    let root = temp_dir("import-overlay");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/project"),
    )
    .expect("overlay import succeeds");

    assert_eq!(plan.manifest.record.mode, RecordMode::Overlay);
    assert_eq!(plan.manifest.record.status, RecordStatus::Inferred);
    assert_eq!(
        plan.manifest
            .record
            .trust
            .as_ref()
            .expect("trust present")
            .provenance,
        vec!["inferred"]
    );
    assert!(plan
        .evidence_text
        .as_deref()
        .expect("evidence present")
        .contains("Inferred fallback values"));
    assert!(plan
        .inferred_fields
        .iter()
        .any(|field| field == "repo.name"));
    assert!(plan.manifest.compat.is_none());

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_extracts_security_from_contributing_when_no_security_md() {
    let root = temp_dir("import-security-from-contributing");
    fs::write(root.join("README.md"), "# TestProj\n\nA project.\n").expect("README written");
    fs::write(
        root.join("CONTRIBUTING.md"),
        "# Contributing\n\n## Security\n\nEmail sec@example.com for vulnerabilities.\n",
    )
    .expect("CONTRIBUTING.md written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/testproj"),
    )
    .expect("import succeeds");

    assert_eq!(
        plan.manifest
            .owners
            .as_ref()
            .and_then(|o| o.security_contact.as_deref()),
        Some("sec@example.com")
    );
    assert!(plan.imported_sources.iter().any(|s| s == "CONTRIBUTING.md"));

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_extracts_security_from_issue_template() {
    let root = temp_dir("import-security-from-template");
    fs::create_dir_all(root.join(".github/ISSUE_TEMPLATE")).expect("template dir");
    fs::write(root.join("README.md"), "# TestProj\n\nA project.\n").expect("README written");
    fs::write(
        root.join(".github/ISSUE_TEMPLATE/security.md"),
        "---\ntitle: Security Issue\n---\n\nContact security@example.com.\n",
    )
    .expect("security template written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/testproj"),
    )
    .expect("import succeeds");

    assert_eq!(
        plan.manifest
            .owners
            .as_ref()
            .and_then(|o| o.security_contact.as_deref()),
        Some("security@example.com")
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}

#[test]
fn import_repository_prefers_security_md_over_contributing() {
    let root = temp_dir("import-security-priority");
    fs::write(root.join("README.md"), "# TestProj\n\nA project.\n").expect("README written");
    fs::write(root.join("SECURITY.md"), "Report to direct@example.com.\n")
        .expect("SECURITY.md written");
    fs::write(
        root.join("CONTRIBUTING.md"),
        "# Contributing\n\n## Security\n\nContact fallback@example.com.\n",
    )
    .expect("CONTRIBUTING.md written");

    let plan = import_repository(
        &root,
        ImportMode::Overlay,
        Some("https://github.com/example/testproj"),
    )
    .expect("import succeeds");

    assert_eq!(
        plan.manifest
            .owners
            .as_ref()
            .and_then(|o| o.security_contact.as_deref()),
        Some("direct@example.com")
    );

    fs::remove_dir_all(root).expect("temp dir removed");
}
