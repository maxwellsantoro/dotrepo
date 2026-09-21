//! Load repository inputs once and expose a borrowed view for command/toolchain inference.
use super::commands::{
    load_best_cargo_toml, load_best_package_json, load_best_python_manifest,
    load_first_existing_file, load_first_file_with_extension, load_workflow_import_files,
};
use super::types::{ImportSources, ImportedFile};
use super::IMPORT_README_CANDIDATES;
use anyhow::Result;
use std::path::Path;

pub(super) struct ImportInputs {
    pub(super) readme: Option<ImportedFile>,
    pub(super) codeowners: Option<ImportedFile>,
    pub(super) security: Option<ImportedFile>,
    pub(super) cargo_toml: Option<ImportedFile>,
    pub(super) rust_toolchain_toml: Option<ImportedFile>,
    pub(super) rust_toolchain: Option<ImportedFile>,
    pub(super) package_json: Option<ImportedFile>,
    pub(super) pyproject_toml: Option<ImportedFile>,
    pub(super) setup_py: Option<ImportedFile>,
    pub(super) setup_cfg: Option<ImportedFile>,
    pub(super) tox_ini: Option<ImportedFile>,
    pub(super) go_mod: Option<ImportedFile>,
    pub(super) pom_xml: Option<ImportedFile>,
    pub(super) maven_wrapper: bool,
    pub(super) build_gradle: Option<ImportedFile>,
    pub(super) gradle_wrapper: bool,
    pub(super) composer_json: Option<ImportedFile>,
    pub(super) csproj: Option<ImportedFile>,
    pub(super) solution: Option<ImportedFile>,
    pub(super) mix_exs: Option<ImportedFile>,
    pub(super) rebar_config: Option<ImportedFile>,
    pub(super) cmake_presets_json: Option<ImportedFile>,
    pub(super) workflow_files: Vec<ImportedFile>,
    pub(super) contributing: Option<ImportedFile>,
    pub(super) makefile: Option<ImportedFile>,
    pub(super) justfile: Option<ImportedFile>,
    pub(super) rakefile: Option<ImportedFile>,
    pub(super) security_issue_template: Option<ImportedFile>,
    pub(super) pull_request_template: Option<ImportedFile>,
}

impl ImportInputs {
    pub(super) fn load(root: &Path) -> Result<Self> {
        let readme = load_first_existing_file(root, IMPORT_README_CANDIDATES)?;
        let codeowners = load_first_existing_file(root, &[".github/CODEOWNERS", "CODEOWNERS"])?;
        let security = load_first_existing_file(root, &[".github/SECURITY.md", "SECURITY.md"])?;
        let cargo_toml = load_best_cargo_toml(root)?;
        let rust_toolchain_toml = load_first_existing_file(root, &["rust-toolchain.toml"])?;
        let rust_toolchain = load_first_existing_file(root, &["rust-toolchain"])?;
        // Prefer a monorepo package with real build/test scripts over a root
        // workspace package.json that only hosts format scripts.
        let package_json = load_best_package_json(root)?;
        let pyproject_toml = load_best_python_manifest(root, "pyproject.toml")?;
        let setup_py = load_best_python_manifest(root, "setup.py")?;
        let setup_cfg = load_best_python_manifest(root, "setup.cfg")?;
        let tox_ini = load_first_existing_file(root, &["tox.ini"])?;
        let go_mod = load_first_existing_file(root, &["go.mod"])?;
        let pom_xml = load_first_existing_file(root, &["pom.xml"])?;
        let maven_wrapper = root.join("mvnw").is_file();
        let build_gradle = load_first_existing_file(root, &["build.gradle", "build.gradle.kts"])?;
        let gradle_wrapper = root.join("gradlew").is_file();
        let composer_json = load_first_existing_file(root, &["composer.json"])?;
        // Prefer root .csproj, then shallow monorepo layout (src/**/*.csproj).
        let csproj = load_first_file_with_extension(root, "csproj", 4)?;
        let solution = load_first_file_with_extension(root, "sln", 2)?;
        let mix_exs = load_first_existing_file(root, &["mix.exs"])?;
        let rebar_config = load_first_existing_file(root, &["rebar.config"])?;
        let cmake_presets_json = load_first_existing_file(root, &["CMakePresets.json"])?;
        let workflow_files = load_workflow_import_files(root)?;
        let contributing =
            load_first_existing_file(root, &["CONTRIBUTING.md", ".github/CONTRIBUTING.md"])?;
        let makefile = load_first_existing_file(root, &["GNUmakefile", "Makefile", "makefile"])?;
        let justfile = load_first_existing_file(root, &["justfile", "Justfile"])?;
        let rakefile = load_first_existing_file(root, &["Rakefile", "rakefile"])?;
        let security_issue_template = load_first_existing_file(
            root,
            &[
                ".github/ISSUE_TEMPLATE/security.md",
                ".github/ISSUE_TEMPLATE/SECURITY.md",
                ".github/ISSUE_TEMPLATE/security.yml",
            ],
        )?;
        let pull_request_template = load_first_existing_file(
            root,
            &[
                ".github/pull_request_template.md",
                ".github/PULL_REQUEST_TEMPLATE.md",
                "pull_request_template.md",
                "PULL_REQUEST_TEMPLATE.md",
            ],
        )?;

        Ok(Self {
            readme,
            codeowners,
            security,
            cargo_toml,
            rust_toolchain_toml,
            rust_toolchain,
            package_json,
            pyproject_toml,
            setup_py,
            setup_cfg,
            tox_ini,
            go_mod,
            pom_xml,
            maven_wrapper,
            build_gradle,
            gradle_wrapper,
            composer_json,
            csproj,
            solution,
            mix_exs,
            rebar_config,
            cmake_presets_json,
            workflow_files,
            contributing,
            makefile,
            justfile,
            rakefile,
            security_issue_template,
            pull_request_template,
        })
    }

    pub(super) fn command_sources(&self) -> ImportSources<'_> {
        ImportSources {
            readme: self.readme.as_ref(),
            cargo_toml: self.cargo_toml.as_ref(),
            rust_toolchain_toml: self.rust_toolchain_toml.as_ref(),
            rust_toolchain: self.rust_toolchain.as_ref(),
            package_json: self.package_json.as_ref(),
            pyproject_toml: self.pyproject_toml.as_ref(),
            setup_py: self.setup_py.as_ref(),
            setup_cfg: self.setup_cfg.as_ref(),
            tox_ini: self.tox_ini.as_ref(),
            go_mod: self.go_mod.as_ref(),
            pom_xml: self.pom_xml.as_ref(),
            maven_wrapper: self.maven_wrapper,
            build_gradle: self.build_gradle.as_ref(),
            gradle_wrapper: self.gradle_wrapper,
            composer_json: self.composer_json.as_ref(),
            csproj: self.csproj.as_ref(),
            solution: self.solution.as_ref(),
            mix_exs: self.mix_exs.as_ref(),
            rebar_config: self.rebar_config.as_ref(),
            cmake_presets_json: self.cmake_presets_json.as_ref(),
            makefile: self.makefile.as_ref(),
            justfile: self.justfile.as_ref(),
            rakefile: self.rakefile.as_ref(),
            contributing: self.contributing.as_ref(),
            workflow_files: &self.workflow_files,
        }
    }
}
