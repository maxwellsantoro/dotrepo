//! Shared output planning for generation, drift checks, and GitHub previews.
use crate::render::{
    generated_banner, render_contributing, render_contributing_body, render_pull_request_template,
    render_security_body, CommentStyle,
};
use crate::surfaces::{
    ensure_native_managed_surface_record, inspect_managed_surface, merge_managed_region,
    render_managed_markdown, render_managed_output, render_readme, render_readme_body,
    ManagedOutput, ManagedSurface,
};
use crate::util::{display_path, display_root, source_digest};
use crate::{
    load_manifest_document, validate_manifest, GenerateCheckOutput, GenerateCheckReport,
    ManagedFileState,
};
use anyhow::{anyhow, Result};
use dotrepo_schema::{CompatMode, Manifest};
use std::fs;
use std::path::{Path, PathBuf};

struct GithubOutput {
    path: PathBuf,
    contents: String,
    managed_surface: Option<ManagedSurface>,
}

pub fn generate_check_repository(root: &Path) -> Result<GenerateCheckReport> {
    let document = load_manifest_document(root)?;
    validate_manifest(root, &document.manifest)?;
    ensure_native_managed_surface_record(&document.manifest, "generate-check")?;
    let mut rendered_outputs = Vec::new();
    let mut stale = Vec::new();

    rendered_outputs.push(generate_check_managed_surface(
        root,
        ManagedSurface::Readme,
        &document.manifest,
        &document.raw,
    )?);

    for output in github_output_plan(&document.manifest, &document.raw) {
        rendered_outputs.push(match output.managed_surface {
            Some(surface) => {
                generate_check_managed_surface(root, surface, &document.manifest, &document.raw)?
            }
            None => generate_check_output(root, root.join(output.path), output.contents)?,
        });
    }

    for output in &rendered_outputs {
        if output.stale {
            stale.push(output.path.clone());
        }
    }

    Ok(GenerateCheckReport {
        root: display_root(root)?,
        checked: rendered_outputs.len(),
        stale,
        outputs: rendered_outputs,
    })
}

pub fn managed_outputs(
    root: &Path,
    manifest: &Manifest,
    source_bytes: &[u8],
) -> Result<Vec<(PathBuf, String)>> {
    ensure_native_managed_surface_record(manifest, "generate")?;
    let mut outputs = Vec::new();
    if let Some(output) =
        render_managed_output(root, ManagedSurface::Readme, manifest, source_bytes)?
    {
        outputs.push(output);
    }

    for output in github_output_plan(manifest, source_bytes) {
        match output.managed_surface {
            Some(surface) => {
                if let Some(output) = render_managed_output(root, surface, manifest, source_bytes)?
                {
                    outputs.push(output);
                }
            }
            None => {
                let path = root.join(output.path);
                outputs.push(ManagedOutput {
                    contents: preserve_matching_generated_output(&path, output.contents)?,
                    path,
                });
            }
        }
    }

    Ok(outputs
        .into_iter()
        .map(|output| (output.path, output.contents))
        .collect())
}

fn preserve_matching_generated_output(path: &Path, expected: String) -> Result<String> {
    match fs::read_to_string(path) {
        Ok(current) if crate::render::generated_output_matches(&current, &expected) => Ok(current),
        Ok(_) => Ok(expected),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(expected),
        Err(error) => Err(anyhow!("failed to read {}: {}", path.display(), error)),
    }
}

pub fn github_outputs(manifest: &Manifest, source_bytes: &[u8]) -> Vec<(PathBuf, String)> {
    github_output_plan(manifest, source_bytes)
        .into_iter()
        .map(|output| (output.path, output.contents))
        .collect()
}

fn github_output_plan(manifest: &Manifest, source_bytes: &[u8]) -> Vec<GithubOutput> {
    let mut outputs = Vec::new();
    let digest = source_digest(source_bytes);
    if let Some(compat) = &manifest.compat {
        if let Some(github) = &compat.github {
            if matches!(github.codeowners, Some(CompatMode::Generate)) {
                let owners = manifest
                    .owners
                    .as_ref()
                    .map(|o| o.maintainers.join(" "))
                    .unwrap_or_else(|| "@maintainers".into());
                outputs.push(GithubOutput {
                    path: PathBuf::from(".github/CODEOWNERS"),
                    managed_surface: None,
                    contents: format!(
                        "{}\n* {}\n",
                        generated_banner(CommentStyle::Hash, manifest, &digest),
                        owners
                    ),
                });
            }
            if matches!(github.security, Some(CompatMode::Generate)) {
                outputs.push(GithubOutput {
                    path: PathBuf::from(".github/SECURITY.md"),
                    managed_surface: Some(ManagedSurface::Security),
                    contents: render_managed_markdown(
                        generated_banner(CommentStyle::Html, manifest, &digest),
                        &render_security_body(manifest),
                    ),
                });
            }
            if matches!(github.contributing, Some(CompatMode::Generate)) {
                outputs.push(GithubOutput {
                    path: PathBuf::from("CONTRIBUTING.md"),
                    managed_surface: Some(ManagedSurface::Contributing),
                    contents: render_contributing(manifest, &digest),
                });
            }
            if matches!(github.pull_request_template, Some(CompatMode::Generate)) {
                outputs.push(GithubOutput {
                    path: PathBuf::from(".github/pull_request_template.md"),
                    managed_surface: None,
                    contents: render_pull_request_template(manifest, &digest),
                });
            }
        }
    }
    outputs
}

fn generate_check_output(
    root: &Path,
    path: PathBuf,
    expected: String,
) -> Result<GenerateCheckOutput> {
    let (current, missing) = match fs::read_to_string(&path) {
        Ok(content) => (content, false),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => (String::new(), true),
        Err(e) => return Err(anyhow!("failed to read {}: {}", path.display(), e)),
    };
    let relative = display_path(root, &path)?;
    let is_stale = !crate::render::generated_output_matches(&current, &expected);
    let expected = if is_stale { expected } else { current.clone() };
    Ok(GenerateCheckOutput {
        path: relative,
        state: if missing {
            ManagedFileState::Missing
        } else {
            ManagedFileState::FullyGenerated
        },
        stale: is_stale,
        expected,
        current: if is_stale { Some(current) } else { None },
        message: None,
    })
}

fn generate_check_managed_surface(
    root: &Path,
    surface: ManagedSurface,
    manifest: &Manifest,
    source_bytes: &[u8],
) -> Result<GenerateCheckOutput> {
    let digest = source_digest(source_bytes);
    let status = inspect_managed_surface(root, surface)?;
    let body = match surface {
        ManagedSurface::Readme => render_readme_body(root, manifest)?,
        ManagedSurface::Security => render_security_body(manifest),
        ManagedSurface::Contributing => render_contributing_body(manifest),
    };
    let full_expected = match surface {
        ManagedSurface::Readme => render_readme(root, manifest, source_bytes)?,
        ManagedSurface::Security => render_managed_markdown(
            generated_banner(CommentStyle::Html, manifest, &digest),
            &body,
        ),
        ManagedSurface::Contributing => render_managed_markdown(
            generated_banner(CommentStyle::Html, manifest, &digest),
            &body,
        ),
    };
    let expected = match status.state {
        ManagedFileState::PartiallyManaged => {
            let current = status.current.as_deref().ok_or_else(|| {
                anyhow!(
                    "partially managed file {} is missing current contents",
                    status.path.display()
                )
            })?;
            merge_managed_region(&status.path, surface, current, &body)?
        }
        ManagedFileState::Unmanaged => status.current.clone().ok_or_else(|| {
            anyhow!(
                "unmanaged file {} is missing current contents",
                status.path.display()
            )
        })?,
        _ => full_expected,
    };
    let current = status.current.clone();
    let stale = match status.state {
        ManagedFileState::Missing => true,
        ManagedFileState::FullyGenerated | ManagedFileState::PartiallyManaged => {
            match current.as_deref() {
                None => true,
                Some(current) => !crate::render::generated_output_matches(current, &expected),
            }
        }
        ManagedFileState::Unmanaged => false,
        ManagedFileState::MalformedManaged | ManagedFileState::Unsupported => true,
    };
    let expected = if stale {
        expected
    } else {
        current.clone().unwrap_or(expected)
    };

    Ok(GenerateCheckOutput {
        path: display_path(root, &status.path)?,
        state: status.state,
        stale,
        expected,
        current: if stale { current } else { None },
        message: status.message,
    })
}
