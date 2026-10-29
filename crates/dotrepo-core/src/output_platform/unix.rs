use anyhow::{bail, Result};
use std::ffi::{CString, OsStr};
use std::fs::File;
use std::io;
use std::os::fd::{AsRawFd, FromRawFd};
use std::os::unix::ffi::OsStrExt;
use std::os::unix::fs::MetadataExt;
use std::path::Path;

pub(super) struct Directory(File);

fn directory_flags() -> i32 {
    #[cfg(any(target_os = "linux", target_os = "android"))]
    let access = libc::O_PATH;
    #[cfg(target_os = "macos")]
    let access = libc::O_SEARCH;
    #[cfg(not(any(target_os = "linux", target_os = "android", target_os = "macos")))]
    let access = libc::O_RDONLY;
    access | libc::O_DIRECTORY | libc::O_NOFOLLOW | libc::O_CLOEXEC
}

fn owned_fd(fd: i32) -> io::Result<File> {
    if fd < 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: a successful open/openat returns a new owned descriptor.
    Ok(unsafe { File::from_raw_fd(fd) })
}

pub(super) fn validate_name(name: &OsStr) -> Result<()> {
    CString::new(name.as_bytes())?;
    Ok(())
}

impl Directory {
    pub(super) fn root(path: &Path) -> Result<Self> {
        let name = CString::new(path.as_os_str().as_bytes())?;
        // SAFETY: NUL-terminated path; no creation flags.
        let file = owned_fd(unsafe { libc::open(name.as_ptr(), directory_flags()) })?;
        Ok(Self(file))
    }

    pub(super) fn clone_handle(&self) -> Result<Self> {
        Ok(Self(self.0.try_clone()?))
    }

    pub(super) fn child(&self, name: &OsStr, create: bool) -> Result<Self> {
        let name = CString::new(name.as_bytes())?;
        // SAFETY: live directory descriptor and a single NUL-terminated component.
        let mut file =
            owned_fd(unsafe { libc::openat(self.0.as_raw_fd(), name.as_ptr(), directory_flags()) });
        if create
            && file
                .as_ref()
                .is_err_and(|e| e.kind() == io::ErrorKind::NotFound)
        {
            // SAFETY: same pinned directory and single component; mode honors umask.
            let result = unsafe { libc::mkdirat(self.0.as_raw_fd(), name.as_ptr(), 0o777) };
            if result < 0 && io::Error::last_os_error().kind() != io::ErrorKind::AlreadyExists {
                return Err(io::Error::last_os_error().into());
            }
            // Reopen with NOFOLLOW even after creating: another actor may replace it.
            file = owned_fd(unsafe {
                libc::openat(self.0.as_raw_fd(), name.as_ptr(), directory_flags())
            });
        }
        Ok(Self(file?))
    }

    pub(super) fn open_output(&self, name: &OsStr, overwrite: bool) -> Result<(File, bool)> {
        let name = CString::new(name.as_bytes())?;
        let flags = libc::O_WRONLY | libc::O_NOFOLLOW | libc::O_NONBLOCK | libc::O_CLOEXEC;
        if overwrite {
            // Never truncate until the opened inode and the entire batch are checked.
            let file = owned_fd(unsafe { libc::openat(self.0.as_raw_fd(), name.as_ptr(), flags) });
            match file {
                Ok(file) => return Ok((file, false)),
                Err(e) if e.kind() == io::ErrorKind::NotFound => {}
                Err(e) => return Err(e.into()),
            }
        }
        // SAFETY: live parent; exclusive creation refuses any concurrently inserted leaf.
        let file = owned_fd(unsafe {
            libc::openat(
                self.0.as_raw_fd(),
                name.as_ptr(),
                flags | libc::O_CREAT | libc::O_EXCL,
                0o666,
            )
        })?;
        Ok((file, true))
    }

    pub(super) fn remove_created(&self, name: &OsStr, file: &File) {
        let Ok(name) = CString::new(name.as_bytes()) else {
            return;
        };
        let Ok(metadata) = file.metadata() else {
            return;
        };
        let mut current = std::mem::MaybeUninit::<libc::stat>::uninit();
        // SAFETY: valid output stat buffer and pinned parent/component.
        let ok = unsafe {
            libc::fstatat(
                self.0.as_raw_fd(),
                name.as_ptr(),
                current.as_mut_ptr(),
                libc::AT_SYMLINK_NOFOLLOW,
            )
        };
        if ok == 0 {
            let current = unsafe { current.assume_init() };
            // libc's inode/device widths differ between Unix targets.
            #[allow(clippy::unnecessary_cast)]
            if current.st_ino as u64 == metadata.ino() && current.st_dev as u64 == metadata.dev() {
                // unlinkat removes the leaf name itself, never follows a replacement link.
                unsafe { libc::unlinkat(self.0.as_raw_fd(), name.as_ptr(), 0) };
            }
        }
    }

    pub(super) fn remove_file(&self, name: &OsStr) -> Result<()> {
        let name = CString::new(name.as_bytes())?;
        let mut metadata = std::mem::MaybeUninit::<libc::stat>::uninit();
        // SAFETY: valid output stat buffer and pinned parent/component.
        if unsafe {
            libc::fstatat(
                self.0.as_raw_fd(),
                name.as_ptr(),
                metadata.as_mut_ptr(),
                libc::AT_SYMLINK_NOFOLLOW,
            )
        } < 0
        {
            let error = io::Error::last_os_error();
            return if error.kind() == io::ErrorKind::NotFound {
                Ok(())
            } else {
                Err(error.into())
            };
        }
        let metadata = unsafe { metadata.assume_init() };
        if metadata.st_mode & libc::S_IFMT != libc::S_IFREG {
            bail!("refusing to remove a nonregular output")
        }
        if unsafe { libc::unlinkat(self.0.as_raw_fd(), name.as_ptr(), 0) } < 0 {
            return Err(io::Error::last_os_error().into());
        }
        Ok(())
    }
}

pub(super) fn verify_file(file: &File) -> Result<()> {
    let metadata = file.metadata()?;
    if !metadata.is_file() {
        bail!("output must be a regular file, not a symlink or directory");
    }
    if metadata.nlink() != 1 {
        bail!("output must not be a shared hardlink");
    }
    Ok(())
}
