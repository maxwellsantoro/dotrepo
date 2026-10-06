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
fn import_refuses_manifest_and_workflow_links() {
    use std::os::unix::fs::symlink;
    for (link, external_name, contents) in [
        (
            "Cargo.toml",
            "Cargo.toml",
            "[package]\nname = 'outside'\nversion = '1.0.0'\n",
        ),
        (
            "package.json",
            "package.json",
            r#"{"scripts":{"test":"vitest run"}}"#,
        ),
        (
            "pyproject.toml",
            "pyproject.toml",
            "[tool.poetry]\nname = 'outside'\n",
        ),
    ] {
        let f = Fixture::new();
        let external = f.0.join(external_name);
        fs::write(&external, contents).unwrap();
        symlink(&external, f.root().join(link)).unwrap();
        assert!(import(&f.root()).is_err(), "manifest {link} escaped");
    }
    for directory in [".github", ".github/workflows"] {
        let f = Fixture::new();
        let external = f.0.join("outside");
        let source = if directory == ".github" {
            external.join("workflows")
        } else {
            external.clone()
        };
        fs::create_dir_all(&source).unwrap();
        fs::write(source.join("test.yml"), "name: outside\n").unwrap();
        fs::create_dir_all(f.root().join(directory).parent().unwrap()).unwrap();
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
        "task :test if false\n",
        "task :test unless true\n",
        "task :test => '#not-a-comment' if false\n",
        "if false\ntask :test\nend\n",
    ] {
        let f = Fixture::new();
        fs::write(f.root().join("Rakefile"), contents).unwrap();
        let plan = import(&f.root()).unwrap();
        assert_ne!(plan.manifest.repo.test.as_deref(), Some("rake test"));
        assert!(plan.manifest.repo.build.is_none());
    }
}

#[cfg(unix)]
#[test]
fn forced_import_plans_refuse_links_without_changing_external_or_other_outputs() {
    use dotrepo_core::write_import_outputs;
    use std::os::unix::fs::symlink;
    for mode in [ImportMode::Native, ImportMode::Overlay] {
        for hardlink in [false, true] {
            let f = Fixture::new();
            fs::write(
                f.root().join("README.md"),
                "# Fixture\n\nContained project.\n",
            )
            .unwrap();
            let source = if mode == ImportMode::Overlay {
                Some("https://github.com/example/fixture")
            } else {
                None
            };
            let plan = import_repository(&f.root(), mode, source).unwrap();
            let outside = f.0.join("outside.txt");
            fs::write(&outside, "outside sentinel").unwrap();
            let linked_output = plan.evidence_path.as_ref().unwrap_or(&plan.manifest_path);
            if hardlink {
                fs::hard_link(&outside, linked_output).unwrap();
            } else {
                symlink(&outside, linked_output).unwrap();
            }
            let mut outputs = vec![(plan.manifest_path.clone(), plan.manifest_text)];
            if let (Some(path), Some(text)) = (plan.evidence_path, plan.evidence_text) {
                fs::write(&plan.manifest_path, "original manifest").unwrap();
                outputs.push((path, text));
            }
            assert!(write_import_outputs(outputs, true, "--force").is_err());
            assert_eq!(fs::read_to_string(&outside).unwrap(), "outside sentinel");
            if mode == ImportMode::Overlay {
                assert_eq!(
                    fs::read_to_string(&plan.manifest_path).unwrap(),
                    "original manifest"
                );
            }
        }
    }
}
