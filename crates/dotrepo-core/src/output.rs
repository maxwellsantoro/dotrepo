//! Root-relative output writes shared by user-facing mutation commands.
//!
//! Pin directories and open leaves without truncation or link traversal. Verify
//! every leaf before changing any existing contents. Existing inodes (and their
//! ownership, permissions and ACLs) are retained. This is not isolation from a
//! same-user process moving opened directories or adding hardlinks after checks.
use anyhow::{anyhow, bail, Context, Result};
use std::collections::HashSet;
use std::fs::{self, File};
use std::io::Write;
use std::path::{Component, Path, PathBuf};

#[cfg(unix)]
#[path = "output_platform/unix.rs"]
mod platform;
#[cfg(windows)]
#[path = "output_platform/windows.rs"]
mod platform;

/// One planned output; `overwrite = false` reserves a new name exclusively.
pub struct RepositoryOutput {
    pub path: PathBuf,
    pub contents: String,
    pub overwrite: bool,
}

/// A pinned, explicitly selected root. Descendant links are never followed.
pub struct RepositoryWriter {
    root: PathBuf,
    canonical: PathBuf,
    directory: platform::Directory,
}

struct PreparedOutput {
    parent: platform::Directory,
    name: std::ffi::OsString,
    file: File,
    contents: String,
    created: bool,
}

impl Drop for PreparedOutput {
    fn drop(&mut self) {
        if self.created {
            // Cleanup is relative to the same pinned parent, never the original
            // pathname (whose ancestors may since have been replaced).
            self.parent.remove_created(&self.name, &self.file);
        }
    }
}

impl RepositoryWriter {
    pub fn new(root: &Path) -> Result<Self> {
        let canonical = fs::canonicalize(root)
            .with_context(|| format!("failed to open output root {}", root.display()))?;
        let directory = platform::Directory::root(&canonical)?;
        Ok(Self {
            root: root.to_path_buf(),
            canonical,
            directory,
        })
    }

    fn relative(&self, path: &Path) -> Result<PathBuf> {
        let relative = path
            .strip_prefix(&self.root)
            .or_else(|_| path.strip_prefix(&self.canonical))
            .map_err(|_| {
                anyhow!(
                    "output {} must be beneath {}",
                    path.display(),
                    self.root.display()
                )
            })?;
        let mut clean = PathBuf::new();
        for component in relative.components() {
            match component {
                Component::Normal(name) => {
                    platform::validate_name(name)?;
                    clean.push(name);
                }
                Component::CurDir => {}
                _ => bail!(
                    "output {} must stay within the repository root",
                    path.display()
                ),
            }
        }
        if clean.as_os_str().is_empty() {
            bail!("an output must name a descendant of the repository root");
        }
        Ok(clean)
    }

    fn directory(&self, relative: &Path, create: bool) -> Result<platform::Directory> {
        let mut directory = self.directory.clone_handle()?;
        for part in relative.components() {
            let Component::Normal(name) = part else {
                bail!("invalid output directory")
            };
            directory = directory.child(name, create)?;
        }
        Ok(directory)
    }

    /// Create a conventional empty directory without traversing descendant links.
    pub fn create_directory(&self, path: &Path) -> Result<()> {
        self.directory(&self.relative(path)?, true)?;
        Ok(())
    }

    /// Remove only an explicitly named regular file, never a directory tree.
    pub fn remove_file(&self, path: &Path) -> Result<()> {
        let relative = self.relative(path)?;
        let parent = self.directory(relative.parent().unwrap(), false)?;
        parent.remove_file(relative.file_name().unwrap())
    }

    fn prepare(&self, outputs: Vec<RepositoryOutput>) -> Result<Vec<PreparedOutput>> {
        let mut prepared = Vec::new();
        let mut seen = HashSet::new();
        for output in outputs {
            let relative = self.relative(&output.path)?;
            if !seen.insert(relative.clone()) {
                bail!("duplicate output {}", output.path.display());
            }
            let parent = self.directory(relative.parent().unwrap(), true)?;
            let name = relative.file_name().unwrap().to_os_string();
            let (file, created) = parent.open_output(&name, output.overwrite)
                .map_err(|error| anyhow!("refused output {}: requires a regular file; if it already exists, request overwrite: {error:#}", output.path.display()))?;
            let output = PreparedOutput {
                parent,
                name,
                file,
                contents: output.contents,
                created,
            };
            platform::verify_file(&output.file)?;
            prepared.push(output);
        }
        Ok(prepared)
    }

    pub fn write(&self, outputs: Vec<RepositoryOutput>) -> Result<()> {
        let mut prepared = self.prepare(outputs)?;
        for output in &prepared {
            platform::verify_file(&output.file)?;
        }
        for output in &mut prepared {
            platform::verify_file(&output.file)?;
            output.file.set_len(0)?;
            output.file.write_all(output.contents.as_bytes())?;
            output.file.flush()?;
        }
        for output in &mut prepared {
            output.created = false;
        }
        Ok(())
    }

    /// Bounded-descriptor preflight for large exports. Each subsequent write
    /// must still use this writer, which safely reopens and checks its target.
    /// Newly reserved names are rolled back after each check.
    pub fn check(&self, outputs: &[RepositoryOutput]) -> Result<()> {
        let mut seen = HashSet::new();
        for output in outputs {
            if !seen.insert(self.relative(&output.path)?) {
                bail!("duplicate output {}", output.path.display());
            }
            drop(self.prepare(vec![RepositoryOutput {
                path: output.path.clone(),
                contents: String::new(),
                overwrite: output.overwrite,
            }])?);
        }
        Ok(())
    }
}

/// Root-aware counterpart to the legacy caller-selected import-output API.
pub fn write_repository_outputs(
    root: &Path,
    outputs: Vec<(PathBuf, String)>,
    overwrite: bool,
    force_hint: &str,
) -> Result<()> {
    RepositoryWriter::new(root)?
        .write(
            outputs
                .into_iter()
                .map(|(path, contents)| RepositoryOutput {
                    path,
                    contents,
                    overwrite,
                })
                .collect(),
        )
        .map_err(|error| {
            anyhow!("output write refused; existing artifacts require {force_hint}: {error:#}")
        })
}

#[cfg(test)]
#[path = "output_platform/tests.rs"]
mod tests;
