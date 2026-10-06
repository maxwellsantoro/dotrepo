//! Safe import artifact writes shared by CLI import, adoption, and MCP.

use anyhow::{anyhow, Result};
use std::fs;
use std::path::{Path, PathBuf};

struct ReservedImportOutput {
    path: PathBuf,
    contents: String,
    file: std::fs::File,
}

pub fn write_import_outputs(
    outputs: Vec<(PathBuf, String)>,
    force: bool,
    force_hint: &str,
) -> Result<()> {
    use std::fs::OpenOptions;
    use std::io::{ErrorKind, Write};

    if force {
        return write_forced_import_outputs(outputs);
    }

    let mut reserved: Vec<ReservedImportOutput> = Vec::new();
    for (path, contents) in outputs {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }

        let file = match OpenOptions::new().write(true).create_new(true).open(&path) {
            Ok(file) => file,
            Err(err) => {
                for reserved in reserved {
                    let _ = fs::remove_file(reserved.path);
                }
                return Err(match err.kind() {
                    ErrorKind::AlreadyExists => anyhow::anyhow!(
                        "{} already exists; rerun with {} to overwrite imported artifacts",
                        path.display(),
                        force_hint
                    ),
                    _ => err.into(),
                });
            }
        };

        reserved.push(ReservedImportOutput {
            path,
            contents,
            file,
        });
    }

    for output in &mut reserved {
        if let Err(err) = output
            .file
            .write_all(output.contents.as_bytes())
            .and_then(|_| output.file.flush())
        {
            for item in &reserved {
                let _ = fs::remove_file(&item.path);
            }
            return Err(err.into());
        }
    }

    Ok(())
}

struct PreparedForcedImportOutput {
    path: PathBuf,
    contents: String,
    file: fs::File,
    created: bool,
}

impl Drop for PreparedForcedImportOutput {
    fn drop(&mut self) {
        if self.created {
            let _ = fs::remove_file(&self.path);
        }
    }
}

fn import_output_open_options() -> fs::OpenOptions {
    let mut options = fs::OpenOptions::new();
    options.write(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        // Do not follow a symlink inserted after preflight. Nonblocking open
        // also prevents a substituted FIFO from hanging before the type check.
        options.custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK);
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        use windows_sys::Win32::Storage::FileSystem::FILE_FLAG_OPEN_REPARSE_POINT;
        options.custom_flags(FILE_FLAG_OPEN_REPARSE_POINT);
    }
    options
}

fn import_output_link_count(file: &fs::File) -> Result<u64> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        Ok(file.metadata()?.nlink())
    }
    #[cfg(windows)]
    {
        use std::mem::MaybeUninit;
        use std::os::windows::io::AsRawHandle;
        use windows_sys::Win32::Storage::FileSystem::{
            GetFileInformationByHandle, BY_HANDLE_FILE_INFORMATION,
        };
        let mut information = MaybeUninit::<BY_HANDLE_FILE_INFORMATION>::uninit();
        // SAFETY: File owns a valid live handle, and the output buffer has the
        // exact layout required by the API. Success initializes the buffer.
        let success = unsafe {
            GetFileInformationByHandle(file.as_raw_handle() as _, information.as_mut_ptr())
        };
        if success == 0 {
            return Err(std::io::Error::last_os_error().into());
        }
        // SAFETY: a successful GetFileInformationByHandle initializes all fields.
        Ok(unsafe { information.assume_init() }.nNumberOfLinks.into())
    }
    #[cfg(not(any(unix, windows)))]
    {
        let _ = file;
        Err(anyhow!(
            "forced import writes require file link-count support on this platform"
        ))
    }
}

fn verify_import_output_file(path: &Path, file: &fs::File) -> Result<()> {
    if !file.metadata()?.is_file() {
        return Err(anyhow!(
            "import output {} must be a regular file, not a symlink or directory",
            path.display()
        ));
    }
    if import_output_link_count(file)? != 1 {
        return Err(anyhow!(
            "import output {} must not be a shared hardlink",
            path.display()
        ));
    }
    Ok(())
}

fn write_forced_import_outputs(outputs: Vec<(PathBuf, String)>) -> Result<()> {
    use std::io::{ErrorKind, Write};

    // Reserve and verify every handle before changing existing contents. Opening
    // without truncation and without following links pins the approved leaf and
    // preserves its owner, group, permissions and ACLs during forced overwrite.
    let mut prepared = Vec::new();
    for (path, contents) in outputs {
        let parent = path
            .parent()
            .filter(|parent| !parent.as_os_str().is_empty())
            .unwrap_or_else(|| Path::new("."));
        fs::create_dir_all(parent)?;
        let parent = fs::canonicalize(parent)?;
        let name = path
            .file_name()
            .ok_or_else(|| anyhow!("invalid import output path {}", path.display()))?;
        let path = parent.join(name);
        let created = match fs::symlink_metadata(&path) {
            Ok(metadata) if metadata.file_type().is_file() => false,
            Ok(_) => {
                return Err(anyhow!(
                    "import output {} must be a regular file, not a symlink or directory",
                    path.display()
                ))
            }
            Err(err) if err.kind() == ErrorKind::NotFound => true,
            Err(err) => return Err(err.into()),
        };
        let mut options = import_output_open_options();
        if created {
            options.create_new(true);
        }
        let file = options.open(&path)?;
        let output = PreparedForcedImportOutput {
            path,
            contents,
            file,
            created,
        };
        verify_import_output_file(&output.path, &output.file)?;
        prepared.push(output);
    }
    for output in &prepared {
        verify_import_output_file(&output.path, &output.file)?;
    }
    for output in &mut prepared {
        output.file.set_len(0)?;
        output.file.write_all(output.contents.as_bytes())?;
        output.file.flush()?;
    }
    for output in &mut prepared {
        output.created = false;
    }
    Ok(())
}

#[cfg(test)]
mod write_import_output_tests {
    use super::write_import_outputs;
    use std::fs;
    use std::path::PathBuf;

    fn temp_dir(label: &str) -> PathBuf {
        let unique = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        let path = std::env::temp_dir().join(format!("dotrepo-import-write-{label}-{unique}"));
        fs::create_dir_all(&path).expect("temp dir created");
        path
    }

    #[cfg(unix)]
    #[test]
    fn forced_import_rejects_existing_and_dangling_symlink_outputs() {
        use std::os::unix::fs::symlink;

        for name in [".repo", "record.toml", "evidence.md"] {
            for dangling in [false, true] {
                let root = temp_dir("symlink");
                let repository = root.join("repository");
                fs::create_dir(&repository).expect("repository created");
                let external = root.join("external");
                if !dangling {
                    fs::write(&external, "outside sentinel").expect("sentinel written");
                }
                let output = repository.join(name);
                symlink(&external, &output).expect("output symlink created");
                let err = write_import_outputs(
                    vec![(output.clone(), "metadata".into())],
                    true,
                    "--force",
                )
                .expect_err("forced import rejects symlink");
                assert!(err.to_string().contains("regular file"));
                assert!(fs::symlink_metadata(output)
                    .expect("symlink retained")
                    .file_type()
                    .is_symlink());
                if dangling {
                    assert!(!external.exists(), "dangling target must not be created");
                } else {
                    assert_eq!(
                        fs::read_to_string(external).expect("sentinel retained"),
                        "outside sentinel"
                    );
                }
                fs::remove_dir_all(root).expect("temp dir removed");
            }
        }
    }

    #[cfg(unix)]
    #[test]
    fn forced_overlay_preflights_evidence_before_replacing_manifest() {
        use std::os::unix::fs::symlink;

        let root = temp_dir("overlay-symlink");
        let manifest = root.join("record.toml");
        fs::write(&manifest, "original manifest").expect("manifest written");
        let evidence = root.join("evidence.md");
        symlink(root.join("missing-target"), &evidence).expect("dangling evidence symlink");
        write_import_outputs(
            vec![
                (manifest.clone(), "new manifest".into()),
                (evidence, "new evidence".into()),
            ],
            true,
            "--force",
        )
        .expect_err("unsafe evidence destination rejected");
        assert_eq!(
            fs::read_to_string(manifest).expect("manifest retained"),
            "original manifest"
        );
        assert_eq!(
            fs::read_dir(&root).expect("directory entries").count(),
            2,
            "no partial outputs remain"
        );
        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn forced_import_rejects_hardlinks_without_changing_external_inode() {
        let root = temp_dir("hardlink");
        let external = root.join("external");
        let output = root.join(".repo");
        fs::write(&external, "outside sentinel").expect("sentinel written");
        fs::hard_link(&external, &output).expect("hardlink created");
        write_import_outputs(
            vec![(output.clone(), "imported metadata".into())],
            true,
            "--force",
        )
        .expect_err("shared hardlink rejected");
        assert_eq!(
            fs::read_to_string(external).expect("sentinel retained"),
            "outside sentinel"
        );
        assert_eq!(
            fs::read_to_string(output).expect("hardlink retained"),
            "outside sentinel"
        );
        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[cfg(unix)]
    #[test]
    fn forced_import_preserves_regular_file_permissions_and_root_aliases() {
        use std::os::unix::fs::{symlink, MetadataExt, PermissionsExt};

        let root = temp_dir("regular");
        let repository = root.join("repository");
        fs::create_dir(&repository).expect("repository created");
        let alias = root.join("alias");
        symlink(&repository, &alias).expect("root alias created");
        let manifest = alias.join("record.toml");
        let evidence = alias.join("evidence.md");
        fs::write(&manifest, "old manifest").expect("manifest written");
        fs::set_permissions(&manifest, fs::Permissions::from_mode(0o640)).expect("permissions set");
        let original = fs::metadata(&manifest).expect("original metadata");
        write_import_outputs(
            vec![
                (manifest.clone(), "new manifest".into()),
                (evidence.clone(), "new evidence".into()),
            ],
            true,
            "--force",
        )
        .expect("forced regular outputs succeed");
        assert_eq!(
            fs::read_to_string(&manifest).expect("manifest loaded"),
            "new manifest"
        );
        assert_eq!(
            fs::read_to_string(evidence).expect("evidence loaded"),
            "new evidence"
        );
        let replaced = fs::metadata(manifest).expect("metadata loaded");
        assert_eq!(replaced.permissions().mode() & 0o777, 0o640);
        assert_eq!(
            (replaced.ino(), replaced.uid(), replaced.gid()),
            (original.ino(), original.uid(), original.gid())
        );
        assert_eq!(
            fs::read_dir(repository).expect("directory entries").count(),
            2,
            "only imported artifacts exist"
        );
        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[cfg(unix)]
    #[test]
    fn forced_import_updates_writable_file_in_unwritable_directory() {
        use std::os::unix::fs::PermissionsExt;

        let root = temp_dir("unwritable-directory");
        let output = root.join(".repo");
        fs::write(&output, "old manifest").expect("manifest written");
        fs::set_permissions(&root, fs::Permissions::from_mode(0o555))
            .expect("directory made unwritable");
        let result = write_import_outputs(
            vec![(output.clone(), "new manifest".into())],
            true,
            "--force",
        );
        fs::set_permissions(&root, fs::Permissions::from_mode(0o755))
            .expect("directory permissions restored");
        result.expect("existing writable file updated");
        assert_eq!(
            fs::read_to_string(output).expect("manifest loaded"),
            "new manifest"
        );
        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn forced_import_preserves_explicit_deny_read_acl() {
        use std::process::Command;

        let root = temp_dir("acl");
        let output = root.join(".repo");
        fs::write(&output, "old private manifest").expect("manifest written");
        assert!(Command::new("chmod")
            .args(["+a", "group:everyone deny read"])
            .arg(&output)
            .status()
            .expect("ACL command runs")
            .success());
        assert_eq!(
            fs::read_to_string(&output)
                .expect_err("ACL prevents read")
                .kind(),
            std::io::ErrorKind::PermissionDenied
        );
        let result = write_import_outputs(
            vec![(output.clone(), "new private manifest".into())],
            true,
            "--force",
        );
        let after = fs::read_to_string(&output);
        assert!(Command::new("chmod")
            .arg("-N")
            .arg(&output)
            .status()
            .expect("ACL cleanup command runs")
            .success());
        result.expect("ACL permits write");
        assert_eq!(
            after.expect_err("deny-read ACL retained").kind(),
            std::io::ErrorKind::PermissionDenied
        );
        assert_eq!(
            fs::read_to_string(output).expect("manifest loaded after ACL removal"),
            "new private manifest"
        );
        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[cfg(unix)]
    #[test]
    fn write_import_outputs_rolls_back_when_second_write_fails() {
        use std::os::unix::fs::PermissionsExt;

        let root = temp_dir("rollback");
        let first = root.join("record.toml");
        let readonly_dir = root.join("readonly_dir");
        fs::create_dir(&readonly_dir).expect("readonly dir created");
        let mut permissions = fs::metadata(&readonly_dir)
            .expect("readonly dir metadata")
            .permissions();
        permissions.set_mode(0o555);
        fs::set_permissions(&readonly_dir, permissions).expect("readonly dir permissions set");

        let err = write_import_outputs(
            vec![
                (first.clone(), "manifest\n".into()),
                (readonly_dir.join("evidence.md"), "evidence\n".into()),
            ],
            false,
            "--force",
        )
        .expect_err("second write should fail");

        assert!(
            !first.exists(),
            "partial manifest should be rolled back: {err}"
        );

        let mut permissions = fs::metadata(&readonly_dir)
            .expect("readonly dir metadata")
            .permissions();
        permissions.set_mode(0o755);
        fs::set_permissions(&readonly_dir, permissions).expect("readonly dir permissions reset");
        fs::remove_dir_all(root).expect("temp dir removed");
    }
}
