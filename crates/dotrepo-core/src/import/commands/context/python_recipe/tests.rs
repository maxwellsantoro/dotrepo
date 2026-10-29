use std::fs;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};

use super::*;

struct Root(PathBuf);

impl Root {
    fn new() -> Self {
        static NEXT: AtomicU64 = AtomicU64::new(0);
        let root = Self(std::env::temp_dir().join(format!(
            "dotrepo-natural-context-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        )));
        fs::create_dir_all(root.0.join("keras/api")).unwrap();
        fs::create_dir_all(root.0.join("keras/src")).unwrap();
        for (name, contents) in [
            ("README.md", include_str!("testdata/README.md")),
            ("CONTRIBUTING.md", include_str!("testdata/CONTRIBUTING.md")),
            ("pyproject.toml", include_str!("testdata/pyproject.toml")),
            (
                "requirements.txt",
                include_str!("testdata/requirements.txt"),
            ),
            (
                "requirements-common.txt",
                include_str!("testdata/requirements-common.txt"),
            ),
        ] {
            fs::write(root.0.join(name), contents).unwrap();
        }
        root
    }

    fn change(&self, path: &str, before: &str, after: &str) {
        let path = self.0.join(path);
        let old = fs::read_to_string(&path).unwrap();
        assert!(old.contains(before));
        fs::write(path, old.replace(before, after)).unwrap();
    }

    fn infer(&self) -> Option<(BuildTestCandidate, toml::Value)> {
        let load = |path: &str| ImportedFile {
            path: path.to_string(),
            contents: fs::read_to_string(self.0.join(path)).unwrap(),
        };
        let readme = load("README.md");
        let contributing = load("CONTRIBUTING.md");
        let pyproject = load("pyproject.toml");
        infer(
            &self.0,
            &ImportSources {
                readme: Some(&readme),
                contributing: Some(&contributing),
                pyproject_toml: Some(&pyproject),
                ..Default::default()
            },
        )
    }
}

impl Drop for Root {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.0).unwrap();
    }
}

#[test]
fn natural_python_recipe_recovers_real_source_tuple_with_medium_bound_evidence() {
    let root = Root::new();
    let (candidate, evidence) = root.infer().expect("retained Keras recipe");
    assert_eq!(candidate.command, "pytest keras");
    assert_eq!(candidate.source, "CONTRIBUTING.md");
    let context = candidate.context.as_ref().unwrap();
    assert_eq!(context.command, candidate.command);
    assert_eq!(context.working_directory, ".");
    assert_eq!(context.scope, ExecutionScope::Repository);
    assert_eq!(context.component, None);
    let prerequisites = context.prerequisites.join(" ");
    for retained in [
        "Python >=3.11",
        "weaker minimum 3.10",
        "pip install -r requirements.txt",
        "python pip_build.py --install",
        "Linux and macOS",
        "WSL2",
        "CPU-only",
        "backend must be configured before importing",
        "inference-only",
        "SKIP_APPLICATIONS_TESTS",
        "requirements-common.txt",
    ] {
        assert!(prerequisites.contains(retained), "{retained}");
    }
    assert_eq!(evidence["confidence"].as_str(), Some("medium"));
    let value: serde_json::Value =
        serde_json::from_str(evidence["valueJson"].as_str().unwrap()).unwrap();
    assert_eq!(value, serde_json::to_value(&candidate).unwrap());
    let bindings: Vec<serde_json::Value> =
        serde_json::from_str(evidence["sourceBindingsJson"].as_str().unwrap()).unwrap();
    assert_eq!(bindings.len(), 8);
    for binding in bindings {
        let text = fs::read(root.0.join(binding["path"].as_str().unwrap())).unwrap();
        assert_eq!(binding["sha256"], sha256(&text));
        assert!(binding["startLine"].as_u64().unwrap() <= binding["endLine"].as_u64().unwrap());
    }
}

#[test]
fn natural_python_recipe_import_preserves_candidate_assessment_without_scalar_promotion() {
    let root = Root::new();
    let mut plan = crate::import_repository_with_options(
        &root.0,
        crate::ImportMode::Overlay,
        Some("https://github.com/keras-team/keras"),
        &crate::ImportOptions {
            generated_at: Some("2026-10-29T06:00:00Z".into()),
            github: None,
        },
    )
    .unwrap();
    assert!(plan.manifest.repo.test_context.is_none());
    assert_eq!(plan.manifest.repo.test_candidates.len(), 1);
    let candidate = &plan.manifest.repo.test_candidates[0];
    let assessment = &plan.manifest.x["dotrepo"]["field_evidence"]["repo.test_candidates.0"];
    assert_eq!(assessment["confidence"].as_str(), Some("medium"));
    assert!(assessment["sourceBindingsJson"]
        .as_str()
        .unwrap()
        .contains("requirements-common.txt"));
    let verification =
        crate::verify_import_plan(&root.0, &plan, "https://github.com/keras-team/keras");
    let report = crate::score_import_fields(&plan, &verification);
    let score = report
        .scores
        .iter()
        .find(|score| score.field == "repo.test_candidates.0")
        .unwrap();
    assert_eq!(
        score.confidence,
        crate::FieldConfidence::MediumConfidencePresent
    );
    assert_eq!(
        serde_json::from_str::<serde_json::Value>(score.value.as_deref().unwrap()).unwrap(),
        serde_json::to_value(candidate).unwrap()
    );
    assert!(!report.summary.eligible_for_auto_publish);
    assert_eq!(
        crate::public::field_evidence(&plan.manifest)["repo.test_candidates.0"]
            ["sourceBindingsJson"],
        assessment["sourceBindingsJson"].as_str().unwrap()
    );
    plan.manifest.repo.test_candidates[0]
        .context
        .as_mut()
        .unwrap()
        .prerequisites
        .clear();
    let report = crate::score_import_fields(&plan, &verification);
    assert_eq!(
        report
            .scores
            .iter()
            .find(|score| score.field == "repo.test_candidates.0")
            .unwrap()
            .confidence,
        crate::FieldConfidence::Unresolved
    );
    assert!(!crate::public::field_evidence(&plan.manifest).contains_key("repo.test_candidates.0"));
}

#[test]
fn natural_python_recipe_rejects_wrong_scope_directory_conditions_and_missing_chain() {
    for (path, before, after) in [
        ("CONTRIBUTING.md", "## Run tests", "## Windows only"),
        (
            "CONTRIBUTING.md",
            "repo\nroot directory",
            "component\nroot directory",
        ),
        ("CONTRIBUTING.md", "cd keras", "cd other"),
        (
            "CONTRIBUTING.md",
            "pytest keras\n",
            "SKIP_APPLICATIONS_TESTS=True pytest keras\n",
        ),
        (
            "CONTRIBUTING.md",
            "To set up your local dev environment",
            "If using Windows, to set up your local dev environment",
        ),
        (
            "CONTRIBUTING.md",
            "requires at least Python 3.10",
            "requires at least Python 3.12",
        ),
        (
            "CONTRIBUTING.md",
            "## Run tests",
            "## Requirements\n\nPostgreSQL 16\n\n## Run tests",
        ),
        (
            "CONTRIBUTING.md",
            "To set up your local dev environment",
            "Read setup.md first. To set up your local dev environment",
        ),
        (
            "README.md",
            "## Backwards compatibility",
            "Before testing, this requires PostgreSQL 16.\n\n## Backwards compatibility",
        ),
        (
            "CONTRIBUTING.md",
            "README.md#configuring-your-backend",
            "SETUP.md#configuring-your-backend",
        ),
        (
            "README.md",
            "## Configuring your backend",
            "## Optional backend setup",
        ),
        ("README.md", "root directory.", "package directory."),
        ("README.md", "CPU-only version", "GPU version"),
        (
            "pyproject.toml",
            "requires-python = \">=3.11\"",
            "requires-python = \">=3.11,<3.12\"",
        ),
        (
            "pyproject.toml",
            "\"keras\" = \"keras/api\"",
            "\"keras\" = \"other/api\"",
        ),
        (
            "requirements.txt",
            "-r requirements-common.txt",
            "-r missing.txt",
        ),
        (
            "requirements.txt",
            "-r requirements-common.txt",
            "-r ../outside.txt",
        ),
        ("requirements-common.txt", "pytest\n", "pytest-cov\n"),
        (
            "requirements-common.txt",
            "pytest\n",
            "-r requirements.txt\npytest\n",
        ),
        (
            "requirements-common.txt",
            "pytest\n",
            "-e ../outside\npytest\n",
        ),
    ] {
        let root = Root::new();
        root.change(path, before, after);
        assert!(root.infer().is_none(), "{path}: {before} -> {after}");
    }
}

#[cfg(unix)]
#[test]
fn natural_python_recipe_rejects_even_contained_requirement_symlinks() {
    let root = Root::new();
    fs::rename(
        root.0.join("requirements-common.txt"),
        root.0.join("inside.txt"),
    )
    .unwrap();
    std::os::unix::fs::symlink("inside.txt", root.0.join("requirements-common.txt")).unwrap();
    assert!(root.infer().is_none());
}

#[test]
fn natural_python_recipe_rejects_hidden_indented_and_external_pretest_setup() {
    for (before, after) in [
        ("### Run all tests", "<!--\n### Run all tests"),
        (
            "## Run tests",
            "Before testing, install PostgreSQL 16.\n\n## Run tests",
        ),
        (
            "## Run tests",
            "Before running tests,\ninstall PostgreSQL 16.\n\n## Run tests",
        ),
    ] {
        let root = Root::new();
        root.change("CONTRIBUTING.md", before, after);
        assert!(root.infer().is_none(), "{after}");
    }
    let root = Root::new();
    let path = root.0.join("CONTRIBUTING.md");
    let text = fs::read_to_string(&path).unwrap();
    let start = text.find("### Run all tests").unwrap();
    let end = text[start..].find("## Backend-agnostic").unwrap() + start;
    let section = &text[start..end];
    let indented = section
        .lines()
        .map(|line| format!("    {line}\n"))
        .collect::<String>();
    root.change("CONTRIBUTING.md", section, &indented);
    assert!(root.infer().is_none());

    let root = Root::new();
    root.change(
        "CONTRIBUTING.md",
        "```shell\npytest keras\n```",
        "    ```shell\n    pytest keras\n    ```",
    );
    assert!(root.infer().is_none());
}
