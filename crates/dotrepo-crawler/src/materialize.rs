use crate::{CrawlDiagnostic, RepositoryRef};
use anyhow::{Context, Result};
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Default)]
pub(crate) struct ConventionalRepositoryFiles {
    pub readme: Option<String>,
    pub root_codeowners: Option<String>,
    pub github_codeowners: Option<String>,
    pub root_security: Option<String>,
    pub github_security: Option<String>,
}

#[derive(Debug, Clone)]
pub(crate) struct MaterializeRepositoryInput {
    pub repository: RepositoryRef,
    pub files: ConventionalRepositoryFiles,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum MaterializedSurface {
    Readme,
    Codeowners,
    Security,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct MaterializedFile {
    pub surface: MaterializedSurface,
    pub relative_path: PathBuf,
}

#[derive(Debug, Clone)]
pub(crate) struct MaterializedRepository {
    pub temp_root: PathBuf,
    pub repository_root: PathBuf,
    pub written_files: Vec<MaterializedFile>,
    pub diagnostics: Vec<CrawlDiagnostic>,
}

pub(crate) fn materialize_repository(
    input: &MaterializeRepositoryInput,
) -> Result<MaterializedRepository> {
    let temp_root = temp_root("materialize");
    let repository_root = temp_root.join(&input.repository.repo);
    fs::create_dir_all(&repository_root)
        .with_context(|| format!("failed to create {}", repository_root.display()))?;

    let mut written_files = Vec::new();
    let mut diagnostics = Vec::new();

    if let Some(readme) = input.files.readme.as_deref() {
        write_surface(
            &repository_root,
            MaterializedSurface::Readme,
            Path::new("README.md"),
            readme,
            &mut written_files,
        )?;
    } else {
        diagnostics.push(CrawlDiagnostic::warning(
            "materialize.missing_readme",
            "README.md was not available for materialization",
        ));
    }

    match (
        input.files.github_codeowners.as_deref(),
        input.files.root_codeowners.as_deref(),
    ) {
        (Some(contents), Some(_)) => {
            write_surface(
                &repository_root,
                MaterializedSurface::Codeowners,
                Path::new(".github/CODEOWNERS"),
                contents,
                &mut written_files,
            )?;
            diagnostics.push(CrawlDiagnostic::info(
                "materialize.preferred_github_codeowners",
                "preferred .github/CODEOWNERS over root CODEOWNERS during materialization",
            ));
        }
        (Some(contents), None) => {
            write_surface(
                &repository_root,
                MaterializedSurface::Codeowners,
                Path::new(".github/CODEOWNERS"),
                contents,
                &mut written_files,
            )?;
        }
        (None, Some(contents)) => {
            write_surface(
                &repository_root,
                MaterializedSurface::Codeowners,
                Path::new("CODEOWNERS"),
                contents,
                &mut written_files,
            )?;
        }
        (None, None) => diagnostics.push(CrawlDiagnostic::info(
            "materialize.missing_codeowners",
            "CODEOWNERS was not available for materialization",
        )),
    }

    match (
        input.files.github_security.as_deref(),
        input.files.root_security.as_deref(),
    ) {
        (Some(contents), Some(_)) => {
            write_surface(
                &repository_root,
                MaterializedSurface::Security,
                Path::new(".github/SECURITY.md"),
                contents,
                &mut written_files,
            )?;
            diagnostics.push(CrawlDiagnostic::info(
                "materialize.preferred_github_security",
                "preferred .github/SECURITY.md over root SECURITY.md during materialization",
            ));
        }
        (Some(contents), None) => {
            write_surface(
                &repository_root,
                MaterializedSurface::Security,
                Path::new(".github/SECURITY.md"),
                contents,
                &mut written_files,
            )?;
        }
        (None, Some(contents)) => {
            write_surface(
                &repository_root,
                MaterializedSurface::Security,
                Path::new("SECURITY.md"),
                contents,
                &mut written_files,
            )?;
        }
        (None, None) => diagnostics.push(CrawlDiagnostic::info(
            "materialize.missing_security",
            "SECURITY.md was not available for materialization",
        )),
    }

    Ok(MaterializedRepository {
        temp_root,
        repository_root,
        written_files,
        diagnostics,
    })
}

fn write_surface(
    repository_root: &Path,
    surface: MaterializedSurface,
    relative_path: &Path,
    contents: &str,
    written_files: &mut Vec<MaterializedFile>,
) -> Result<()> {
    let path = repository_root.join(relative_path);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("failed to create {}", parent.display()))?;
    }
    fs::write(&path, contents).with_context(|| format!("failed to write {}", path.display()))?;
    written_files.push(MaterializedFile {
        surface,
        relative_path: relative_path.to_path_buf(),
    });
    Ok(())
}

fn temp_root(label: &str) -> PathBuf {
    let unique = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("clock works")
        .as_nanos();
    std::env::temp_dir().join(format!(
        "dotrepo-crawler-{}-{}-{}",
        label,
        std::process::id(),
        unique
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn repository() -> RepositoryRef {
        RepositoryRef {
            host: "github.com".into(),
            owner: "example".into(),
            repo: "orbit".into(),
        }
    }

    #[test]
    fn materialize_repository_writes_preferred_conventional_surfaces() {
        let materialized = materialize_repository(&MaterializeRepositoryInput {
            repository: repository(),
            files: ConventionalRepositoryFiles {
                readme: Some("# Orbit\n".into()),
                root_codeowners: Some("* @root\n".into()),
                github_codeowners: Some("* @github\n".into()),
                root_security: Some("root security\n".into()),
                github_security: Some("github security\n".into()),
            },
        })
        .expect("materialization succeeds");

        assert!(materialized.repository_root.join("README.md").is_file());
        assert!(materialized
            .repository_root
            .join(".github/CODEOWNERS")
            .is_file());
        assert!(materialized
            .repository_root
            .join(".github/SECURITY.md")
            .is_file());
        assert!(!materialized.repository_root.join("CODEOWNERS").exists());
        assert!(!materialized.repository_root.join("SECURITY.md").exists());
        assert!(materialized
            .diagnostics
            .iter()
            .any(|diagnostic| { diagnostic.code == "materialize.preferred_github_codeowners" }));
        assert!(materialized.repository_root.ends_with(Path::new("orbit")));

        fs::remove_dir_all(materialized.temp_root).expect("temp dir removed");
    }

    #[test]
    fn materialize_repository_reports_absent_optional_surfaces() {
        let materialized = materialize_repository(&MaterializeRepositoryInput {
            repository: repository(),
            files: ConventionalRepositoryFiles::default(),
        })
        .expect("materialization succeeds");

        let codes: Vec<_> = materialized
            .diagnostics
            .iter()
            .map(|diagnostic| diagnostic.code.as_str())
            .collect();
        assert!(codes.contains(&"materialize.missing_readme"));
        assert!(codes.contains(&"materialize.missing_codeowners"));
        assert!(codes.contains(&"materialize.missing_security"));

        fs::remove_dir_all(materialized.temp_root).expect("temp dir removed");
    }
}
