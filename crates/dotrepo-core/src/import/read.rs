//! Bounded import inputs. Symlinks (even contained ones) are unsupported.
use anyhow::{anyhow, Result};
use std::fs::{self, File};
use std::io::Read;
use std::path::{Component, Path};

pub(super) const MAX_INPUT_BYTES: u64 = 2 * 1024 * 1024;

pub(super) fn read_input(root: &Path, relative: &Path) -> Result<String> {
    let file = open_input(root, relative)?;
    if !file.metadata()?.is_file() {
        return Err(anyhow!(
            "import input {} must be a regular file",
            relative.display()
        ));
    }
    let mut bytes = Vec::new();
    file.take(MAX_INPUT_BYTES + 1).read_to_end(&mut bytes)?;
    if bytes.len() as u64 > MAX_INPUT_BYTES {
        return Err(anyhow!(
            "import input {} exceeds {} bytes",
            relative.display(),
            MAX_INPUT_BYTES
        ));
    }
    Ok(String::from_utf8(bytes)?)
}

// Discovery also refuses links before descending. Reads independently pin each
// directory handle on Unix, so replacing a checked ancestor with a link cannot
// redirect the subsequent open. The selected root must itself be a directory.
pub(super) fn check_input_path(root: &Path, relative: &Path) -> Result<()> {
    let root = fs::canonicalize(root)?;
    let mut path = root.clone();
    for part in relative.components() {
        let Component::Normal(part) = part else {
            return Err(anyhow!(
                "invalid repository input path {}",
                relative.display()
            ));
        };
        path.push(part);
        let metadata = fs::symlink_metadata(&path)?;
        if metadata.file_type().is_symlink() {
            return Err(anyhow!(
                "import input symlinks are unsupported: {}",
                relative.display()
            ));
        }
        #[cfg(windows)]
        {
            use std::os::windows::fs::MetadataExt;
            if metadata.file_attributes() & 0x400 != 0 {
                return Err(anyhow!("import input reparse points are unsupported"));
            }
        }
    }
    if !fs::canonicalize(path)?.starts_with(root) {
        return Err(anyhow!("import input escapes repository"));
    }
    Ok(())
}

#[cfg(unix)]
fn open_input(root: &Path, relative: &Path) -> Result<File> {
    use std::ffi::CString;
    use std::os::fd::{AsRawFd, FromRawFd};
    use std::os::unix::ffi::OsStrExt;
    use std::os::unix::fs::OpenOptionsExt;
    let mut handle = fs::OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_DIRECTORY | libc::O_NOFOLLOW | libc::O_CLOEXEC)
        .open(root)?;
    let mut parts = relative.components().peekable();
    if parts.peek().is_none() {
        return Err(anyhow!("empty import input path"));
    }
    while let Some(part) = parts.next() {
        let Component::Normal(part) = part else {
            return Err(anyhow!(
                "invalid repository input path {}",
                relative.display()
            ));
        };
        let name = CString::new(part.as_bytes())?;
        let flags = libc::O_RDONLY
            | libc::O_NOFOLLOW
            | libc::O_CLOEXEC
            | libc::O_NONBLOCK
            | if parts.peek().is_some() {
                libc::O_DIRECTORY
            } else {
                0
            };
        // SAFETY: live directory fd, NUL-terminated name, no creation flags.
        let fd = unsafe { libc::openat(handle.as_raw_fd(), name.as_ptr(), flags) };
        if fd < 0 {
            return Err(anyhow!(
                "refused import input {}: {}",
                relative.display(),
                std::io::Error::last_os_error()
            ));
        }
        // SAFETY: successful openat transfers this new fd's ownership to File.
        handle = unsafe { File::from_raw_fd(fd) };
    }
    Ok(handle)
}

#[cfg(not(unix))]
fn open_input(root: &Path, relative: &Path) -> Result<File> {
    // Windows checks reparse ancestors and opens the leaf without following it.
    // Concurrent ancestor replacement remains a documented best-effort limit.
    check_input_path(root, relative)?;
    let mut options = fs::OpenOptions::new();
    options.read(true);
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        options.custom_flags(windows_sys::Win32::Storage::FileSystem::FILE_FLAG_OPEN_REPARSE_POINT);
    }
    let file = options.open(root.join(relative))?;
    check_input_path(root, relative)?;
    Ok(file)
}
