use dotrepo_core::{import_repository, ImportMode};
use std::fs;
use std::path::{Path, PathBuf};

struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        let id = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path =
            std::env::temp_dir().join(format!("dotrepo-import-input-{}-{id}", std::process::id()));
        fs::create_dir_all(path.join("repo")).unwrap();
        Self(path)
    }
    fn root(&self) -> PathBuf {
        self.0.join("repo")
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
fn import(root: &Path) -> anyhow::Result<dotrepo_core::ImportPlan> {
    import_repository(
        root,
        ImportMode::Overlay,
        Some("https://github.com/example/fixture"),
    )
}

#[test]
fn ordinary_import_inputs_remain_usable() {
    let f = Fixture::new();
    fs::write(
        f.root().join("README.md"),
        "# Fixture\n\nAn ordinary contained repository.\n",
    )
    .unwrap();
    fs::write(
        f.root().join("package.json"),
        r#"{"scripts":{"build":"vite build","test":"vitest run"}}"#,
    )
    .unwrap();
    let plan = import(&f.root()).unwrap();
    assert_eq!(plan.manifest.repo.name, "Fixture");
    assert_eq!(plan.manifest.repo.build.as_deref(), Some("npm run build"));
}

#[cfg(unix)]
#[test]
fn import_refuses_escaping_and_contained_readme_links() {
    use std::os::unix::fs::symlink;
    for contained in [false, true] {
        let f = Fixture::new();
        let outside = if contained {
            f.root().join("source.md")
        } else {
            f.0.join("outside.md")
        };
        fs::write(
            &outside,
            "# External sentinel\n\nNever publish this evidence.",
        )
        .unwrap();
        symlink(outside, f.root().join("README.md")).unwrap();
        assert!(import(&f.root()).is_err());
    }
}

#[cfg(unix)]
#[test]
fn import_refuses_manifest_and_workflow_directory_links() {
    use std::os::unix::fs::symlink;
    for (directory, name, contents) in [
        (
            "packages",
            "package.json",
            r#"{"scripts":{"test":"vitest run"}}"#,
        ),
        (
            "rust",
            "Cargo.toml",
            "[package]\nname = 'outside'\nversion = '1.0.0'\n",
        ),
        (
            "python",
            "pyproject.toml",
            "[tool.poetry]\nname = 'outside'\n",
        ),
        (".github", "workflows/test.yml", "name: outside\n"),
    ] {
        let f = Fixture::new();
        let external = f.0.join("outside");
        fs::create_dir_all(external.join(name).parent().unwrap()).unwrap();
        fs::write(external.join(name), contents).unwrap();
        symlink(&external, f.root().join(directory)).unwrap();
        assert!(import(&f.root()).is_err(), "directory {directory} escaped");
    }
}

#[test]
fn import_refuses_directory_and_oversized_conventional_inputs() {
    let f = Fixture::new();
    fs::create_dir(f.root().join("README.md")).unwrap();
    assert!(import(&f.root()).is_err());
    fs::remove_dir(f.root().join("README.md")).unwrap();
    fs::write(f.root().join("README.md"), vec![b'a'; 2 * 1024 * 1024 + 1]).unwrap();
    assert!(import(&f.root())
        .unwrap_err()
        .to_string()
        .contains("exceeds"));
}

#[cfg(unix)]
#[test]
fn import_refuses_fifo_without_waiting_for_a_writer() {
    use std::os::unix::ffi::OsStrExt;
    let f = Fixture::new();
    let path = std::ffi::CString::new(f.root().join("README.md").as_os_str().as_bytes()).unwrap();
    // SAFETY: NUL terminated test path in an isolated directory.
    assert_eq!(unsafe { libc::mkfifo(path.as_ptr(), 0o600) }, 0);
    assert!(import(&f.root())
        .unwrap_err()
        .to_string()
        .contains("regular file"));
}

#[test]
fn namespaced_rake_tasks_never_become_root_commands() {
    for contents in [
        "namespace :component do\n  task :test do\n    puts 'ok'\n  end\nend\n",
        "namespace :outer do\nnamespace :inner do\ntask :test do\nend\nend\nend\n",
        "task :build do\nend\nnamespace :component do\ntask :test do\nend\nend\n",
        "namespace(:component) { task :test }\n",
    ] {
        let f = Fixture::new();
        fs::write(f.root().join("Rakefile"), contents).unwrap();
        let plan = import(&f.root()).unwrap();
        assert_ne!(plan.manifest.repo.test.as_deref(), Some("rake test"));
        assert!(plan.manifest.repo.build.is_none());
    }
}
