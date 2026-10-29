use super::*;
#[cfg(unix)]
use std::os::unix::fs::{symlink as symlink_dir, symlink as symlink_file};
#[cfg(windows)]
use std::os::windows::fs::{symlink_dir, symlink_file};
use std::sync::atomic::{AtomicU64, Ordering};

static NEXT: AtomicU64 = AtomicU64::new(0);

#[cfg(target_os = "macos")]
#[test]
fn rooted_overwrite_preserves_deny_read_acl() {
    use std::process::Command;
    let root = fixture();
    let path = root.join("private");
    fs::write(&path, "before").unwrap();
    assert!(Command::new("chmod")
        .args(["+a", "group:everyone deny read"])
        .arg(&path)
        .status()
        .unwrap()
        .success());
    let result =
        write_repository_outputs(&root, vec![(path.clone(), "after".into())], true, "--force");
    let read = fs::read_to_string(&path);
    assert!(Command::new("chmod")
        .arg("-N")
        .arg(&path)
        .status()
        .unwrap()
        .success());
    result.unwrap();
    assert_eq!(
        read.unwrap_err().kind(),
        std::io::ErrorKind::PermissionDenied
    );
    assert_eq!(fs::read_to_string(&path).unwrap(), "after");
    fs::remove_dir_all(root).unwrap();
}
fn fixture() -> PathBuf {
    let root = std::env::temp_dir().join(format!(
        "dotrepo-output-{}-{}",
        std::process::id(),
        NEXT.fetch_add(1, Ordering::Relaxed)
    ));
    fs::create_dir_all(&root).unwrap();
    root
}

#[test]
fn rejects_parent_components_and_creates_ordinary_outputs() {
    let root = fixture();
    let writer = RepositoryWriter::new(&root).unwrap();
    assert!(writer
        .write(vec![RepositoryOutput {
            path: root.join("../outside"),
            contents: "bad".into(),
            overwrite: true
        }])
        .is_err());
    write_repository_outputs(
        &root,
        vec![(root.join("nested/output"), "good".into())],
        false,
        "--force",
    )
    .unwrap();
    assert_eq!(
        fs::read_to_string(root.join("nested/output")).unwrap(),
        "good"
    );
    drop(writer);
    fs::remove_dir_all(root).unwrap();
}

#[test]
fn rejects_leaf_parent_dangling_and_hard_links_before_any_truncation() {
    for kind in ["leaf", "parent", "dangling", "hardlink"] {
        let base = fixture();
        let root = base.join("checkout");
        let outside = base.join("outside");
        fs::create_dir_all(&root).unwrap();
        fs::create_dir_all(&outside).unwrap();
        fs::write(root.join("first"), "original").unwrap();
        let sentinel = outside.join("output");
        if kind != "dangling" {
            fs::write(&sentinel, "sentinel").unwrap();
        }
        if kind == "parent" {
            symlink_dir(&outside, root.join("nested")).unwrap();
        } else {
            fs::create_dir(root.join("nested")).unwrap();
            if kind == "hardlink" {
                fs::hard_link(&sentinel, root.join("nested/output")).unwrap();
            } else {
                symlink_file(&sentinel, root.join("nested/output")).unwrap();
            }
        }
        assert!(write_repository_outputs(
            &root,
            vec![
                (root.join("first"), "changed".into()),
                (root.join("new"), "new".into()),
                (root.join("nested/output"), "bad".into())
            ],
            true,
            "--force"
        )
        .is_err());
        assert_eq!(fs::read_to_string(root.join("first")).unwrap(), "original");
        assert!(!root.join("new").exists());
        if kind == "dangling" {
            assert!(!sentinel.exists());
        } else {
            assert_eq!(fs::read_to_string(sentinel).unwrap(), "sentinel");
        }
        fs::remove_dir_all(base).unwrap();
    }
}

#[cfg(windows)]
#[test]
fn pinned_parent_cannot_be_replaced_and_reserved_outputs_are_cleaned_up() {
    let root = fixture();
    let writer = RepositoryWriter::new(&root).unwrap();
    let prepared = writer
        .prepare(vec![RepositoryOutput {
            path: root.join("nested/output"),
            contents: "content".into(),
            overwrite: true,
        }])
        .unwrap();
    assert!(fs::rename(root.join("nested"), root.join("moved")).is_err());
    drop(prepared);
    assert!(!root.join("nested/output").exists());
    drop(writer);
    fs::rename(root.join("nested"), root.join("moved")).unwrap();
    fs::remove_dir_all(root).unwrap();
}

#[cfg(windows)]
#[test]
fn rejects_device_names_and_alternate_data_streams() {
    let root = fixture();
    let writer = RepositoryWriter::new(&root).unwrap();
    for name in [
        "NUL",
        "CON.txt",
        "COM1",
        "output:stream",
        "output.",
        "output ",
    ] {
        assert!(
            writer
                .write(vec![RepositoryOutput {
                    path: root.join(name),
                    contents: "content".into(),
                    overwrite: true,
                }])
                .is_err(),
            "{name}"
        );
    }
    drop(writer);
    fs::remove_dir_all(root).unwrap();
}

#[cfg(unix)]
#[test]
fn parent_and_leaf_replacement_cannot_redirect_opened_outputs_or_cleanup() {
    use std::os::unix::fs::symlink;
    let base = fixture();
    let root = base.join("checkout");
    let outside = base.join("outside");
    fs::create_dir_all(root.join("nested")).unwrap();
    fs::create_dir_all(&outside).unwrap();
    fs::write(outside.join("output"), "sentinel").unwrap();
    let writer = RepositoryWriter::new(&root).unwrap();
    let mut prepared = writer
        .prepare(vec![RepositoryOutput {
            path: root.join("nested/output"),
            contents: "content".into(),
            overwrite: true,
        }])
        .unwrap();
    // Deterministically exercise replacement at the open/write boundary.
    fs::rename(root.join("nested"), root.join("old")).unwrap();
    symlink(&outside, root.join("nested")).unwrap();
    let output = &mut prepared[0];
    output.file.write_all(b"content").unwrap();
    assert_eq!(
        fs::read_to_string(outside.join("output")).unwrap(),
        "sentinel"
    );
    drop(prepared); // rollback removes only the newly reserved file in old/.
    assert!(!root.join("old/output").exists());
    fs::remove_file(root.join("nested")).unwrap();
    fs::write(root.join("old/output"), "old").unwrap();
    let mut prepared = writer
        .prepare(vec![RepositoryOutput {
            path: root.join("old/output"),
            contents: "content".into(),
            overwrite: true,
        }])
        .unwrap();
    fs::remove_file(root.join("old/output")).unwrap();
    symlink(outside.join("output"), root.join("old/output")).unwrap();
    prepared[0].file.write_all(b"content").unwrap();
    assert_eq!(
        fs::read_to_string(outside.join("output")).unwrap(),
        "sentinel"
    );
    drop(prepared);
    fs::remove_dir_all(base).unwrap();
}

#[cfg(unix)]
#[test]
fn root_alias_permissions_and_inode_survive_overwrite() {
    use std::os::unix::fs::{symlink, MetadataExt, PermissionsExt};
    let base = fixture();
    let root = base.join("checkout");
    fs::create_dir(&root).unwrap();
    let alias = base.join("alias");
    symlink(&root, &alias).unwrap();
    let path = alias.join("output");
    fs::write(&path, "before").unwrap();
    fs::set_permissions(&path, fs::Permissions::from_mode(0o640)).unwrap();
    let before = fs::metadata(&path).unwrap();
    fs::set_permissions(&root, fs::Permissions::from_mode(0o111)).unwrap();
    let result = write_repository_outputs(
        &alias,
        vec![(path.clone(), "after".into())],
        true,
        "--force",
    );
    fs::set_permissions(&root, fs::Permissions::from_mode(0o755)).unwrap();
    result.unwrap();
    let after = fs::metadata(&path).unwrap();
    assert_eq!(
        (before.ino(), before.uid(), before.gid(), before.mode()),
        (after.ino(), after.uid(), after.gid(), after.mode())
    );
    assert_eq!(fs::read_to_string(path).unwrap(), "after");
    fs::remove_dir_all(base).unwrap();
}
