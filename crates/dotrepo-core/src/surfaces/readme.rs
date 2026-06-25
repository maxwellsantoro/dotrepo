use std::fs;
use std::path::Path;

use anyhow::{anyhow, bail, Result};
use dotrepo_schema::{Manifest, ReadmeCustomSection};

use crate::claims::resolve_repository_local_path;
use crate::render::{generated_banner, CommentStyle};
use crate::util::source_digest;

use super::render_managed_markdown;

pub fn render_readme_body(root: &Path, manifest: &Manifest) -> Result<String> {
    let mut out = String::new();

    let title = manifest
        .readme
        .as_ref()
        .and_then(|r| r.title.clone())
        .unwrap_or_else(|| manifest.repo.name.clone());
    out.push_str(&format!("# {}\n\n", title));

    if let Some(tagline) = manifest.readme.as_ref().and_then(|r| r.tagline.clone()) {
        out.push_str(&format!("> {}\n\n", tagline));
    }

    let sections = manifest
        .readme
        .as_ref()
        .map(|r| r.sections.clone())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| {
            vec![
                "overview".into(),
                "docs".into(),
                "contributing".into(),
                "security".into(),
            ]
        });

    for section in sections {
        match section.as_str() {
            "overview" => {
                out.push_str("## Overview\n\n");
                out.push_str(&format!("{}\n\n", manifest.repo.description));
            }
            "docs" => {
                out.push_str("## Documentation\n\n");
                if let Some(docs) = &manifest.docs {
                    if let Some(path) = &docs.getting_started {
                        out.push_str(&format!("- Getting started: `{}`\n", path));
                    }
                    if let Some(path) = &docs.architecture {
                        out.push_str(&format!("- Architecture: `{}`\n", path));
                    }
                    if let Some(path) = &docs.api {
                        out.push_str(&format!("- API: `{}`\n", path));
                    }
                }
                out.push('\n');
            }
            "contributing" => {
                out.push_str("## Contributing\n\n");
                out.push_str("See project contribution guidance and repository policies.\n\n");
            }
            "security" => {
                out.push_str("## Security\n\n");
                if let Some(contact) = manifest
                    .owners
                    .as_ref()
                    .and_then(|o| o.security_contact.clone())
                {
                    out.push_str(&format!("Report vulnerabilities to {}.\n\n", contact));
                } else {
                    out.push_str("Report vulnerabilities to the listed maintainers.\n\n");
                }
            }
            _ => {
                out.push_str(&format!("## {}\n\n", section_heading(&section)));
                if let Some(custom) = manifest
                    .readme
                    .as_ref()
                    .and_then(|readme| readme.custom_sections.get(&section))
                {
                    out.push_str(&render_custom_section(root, &section, custom)?);
                    out.push_str("\n\n");
                } else {
                    out.push_str("_section reserved_\n\n");
                }
            }
        }
    }

    Ok(out)
}

pub fn render_readme(root: &Path, manifest: &Manifest, source_bytes: &[u8]) -> Result<String> {
    let digest = source_digest(source_bytes);
    Ok(render_managed_markdown(
        generated_banner(CommentStyle::Html, manifest, &digest),
        &render_readme_body(root, manifest)?,
    ))
}

fn render_custom_section(
    root: &Path,
    section_name: &str,
    custom: &ReadmeCustomSection,
) -> Result<String> {
    if let Some(content) = &custom.content {
        return Ok(content.trim().to_string());
    }

    if let Some(path) = &custom.path {
        let target = resolve_repository_local_path(root, path).map_err(|err| {
            anyhow!(
                "custom README section `{}` uses an invalid path `{}`: {}",
                section_name,
                path,
                err
            )
        })?;
        return fs::read_to_string(&target)
            .map(|content| content.trim().to_string())
            .map_err(|err| {
                anyhow!(
                    "failed to read custom README section `{}` from {}: {}",
                    section_name,
                    target.display(),
                    err
                )
            });
    }

    bail!(
        "custom README section `{}` must declare either `content` or `path`",
        section_name
    )
}

fn section_heading(input: &str) -> String {
    input
        .split(['-', '_', ' '])
        .filter(|segment| !segment.is_empty())
        .map(capitalize)
        .collect::<Vec<_>>()
        .join(" ")
}

fn capitalize(input: &str) -> String {
    let mut chars = input.chars();
    match chars.next() {
        None => String::new(),
        Some(first) => first.to_uppercase().collect::<String>() + chars.as_str(),
    }
}
