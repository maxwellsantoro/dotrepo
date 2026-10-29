use anyhow::{bail, Result};
use std::ffi::OsStr;
use std::fs::{self, File, OpenOptions};
use std::os::windows::fs::{MetadataExt, OpenOptionsExt};
use std::path::{Path, PathBuf};
use windows_sys::Win32::Storage::FileSystem::{
    FILE_ATTRIBUTE_REPARSE_POINT, FILE_FLAG_BACKUP_SEMANTICS, FILE_FLAG_OPEN_REPARSE_POINT,
    FILE_SHARE_READ, FILE_SHARE_WRITE,
};

// Retain every ancestor handle without FILE_SHARE_DELETE. Windows then refuses
// ancestor rename/delete while pathname-based descendant opens are in progress.
pub(super) struct Directory {
    path: PathBuf,
    handles: Vec<File>,
}

pub(super) fn validate_name(name: &OsStr) -> Result<()> {
    let text = name
        .to_str()
        .ok_or_else(|| anyhow::anyhow!("invalid output name"))?;
    let stem = text.split('.').next().unwrap_or("").to_ascii_uppercase();
    if text.contains(':')
        || text.ends_with([' ', '.'])
        || matches!(stem.as_str(), "CON" | "PRN" | "AUX" | "NUL")
        || ((stem.starts_with("COM") || stem.starts_with("LPT"))
            && stem.len() == 4
            && stem.as_bytes()[3].is_ascii_digit())
    {
        bail!("unsupported Windows output name");
    }
    Ok(())
}

fn open_directory(path: &Path) -> Result<File> {
    let file = OpenOptions::new()
        .access_mode(0)
        .share_mode(FILE_SHARE_READ | FILE_SHARE_WRITE)
        .custom_flags(FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT)
        .open(path)?;
    let metadata = file.metadata()?;
    if !metadata.is_dir() || metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0 {
        bail!("output parent must be a directory without reparse points");
    }
    Ok(file)
}

impl Directory {
    pub(super) fn root(path: &Path) -> Result<Self> {
        Ok(Self {
            path: path.to_path_buf(),
            handles: vec![open_directory(path)?],
        })
    }
    pub(super) fn clone_handle(&self) -> Result<Self> {
        Ok(Self {
            path: self.path.clone(),
            handles: self
                .handles
                .iter()
                .map(File::try_clone)
                .collect::<std::io::Result<_>>()?,
        })
    }
    pub(super) fn child(&self, name: &OsStr, create: bool) -> Result<Self> {
        let mut child = self.clone_handle()?;
        child.path.push(name);
        if create {
            match fs::create_dir(&child.path) {
                Ok(()) => {}
                Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => {}
                Err(e) => return Err(e.into()),
            }
        }
        child.handles.push(open_directory(&child.path)?);
        Ok(child)
    }
    pub(super) fn open_output(&self, name: &OsStr, overwrite: bool) -> Result<(File, bool)> {
        let path = self.path.join(name);
        let mut options = OpenOptions::new();
        options
            .write(true)
            .custom_flags(FILE_FLAG_OPEN_REPARSE_POINT);
        if overwrite {
            match options.open(&path) {
                Ok(file) => return Ok((file, false)),
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
                Err(e) => return Err(e.into()),
            }
        }
        Ok((options.create_new(true).open(path)?, true))
    }
    pub(super) fn remove_created(&self, name: &OsStr, _file: &File) {
        let _ = fs::remove_file(self.path.join(name));
    }
    pub(super) fn remove_file(&self, name: &OsStr) -> Result<()> {
        let path = self.path.join(name);
        match fs::symlink_metadata(&path) {
            Ok(metadata)
                if metadata.is_file()
                    && metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT == 0 =>
            {
                fs::remove_file(path)?
            }
            Ok(_) => bail!("refusing to remove a nonregular output"),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => return Err(e.into()),
        }
        Ok(())
    }
}

pub(super) fn verify_file(file: &File) -> Result<()> {
    use std::os::windows::io::AsRawHandle;
    use windows_sys::Win32::Storage::FileSystem::{
        GetFileInformationByHandle, BY_HANDLE_FILE_INFORMATION,
    };
    let metadata = file.metadata()?;
    if !metadata.is_file() || metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0 {
        bail!("output must be a regular file, not a reparse point");
    }
    let mut information = std::mem::MaybeUninit::<BY_HANDLE_FILE_INFORMATION>::uninit();
    // SAFETY: valid file handle and correctly sized output buffer.
    if unsafe { GetFileInformationByHandle(file.as_raw_handle() as _, information.as_mut_ptr()) }
        == 0
    {
        return Err(std::io::Error::last_os_error().into());
    }
    if unsafe { information.assume_init() }.nNumberOfLinks != 1 {
        bail!("output must not be a shared hardlink");
    }
    Ok(())
}
