use anyhow::{anyhow, bail, Result};
use dotrepo_schema::{parse_manifest, CompatMode, Manifest, ReadmeCustomSection, RecordMode};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};

const SUPPORTED_SCHEMA: &str = "dotrepo/v0.1";
const GENERATOR_NAME: &str = "dotrepo";
const GENERATOR_VERSION: &str = env!("CARGO_PKG_VERSION");

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DoctorFinding {
    pub path: PathBuf,
    pub message: String,
}

#[derive(Debug, Clone)]
pub struct LoadedManifest {
    pub path: PathBuf,
    pub raw: Vec<u8>,
    pub manifest: Manifest,
}

pub fn load_manifest_document(root: &Path) -> Result<LoadedManifest> {
    let path = manifest_path(root);
    let raw = fs::read(&path).map_err(|e| anyhow!("failed to read {}: {}", path.display(), e))?;
    let text = std::str::from_utf8(&raw)
        .map_err(|e| anyhow!("failed to decode {} as UTF-8: {}", path.display(), e))?;
    let manifest = parse_manifest(text)?;
    Ok(LoadedManifest {
        path,
        raw,
        manifest,
    })
}

pub fn load_manifest_from_root(root: &Path) -> Result<Manifest> {
    Ok(load_manifest_document(root)?.manifest)
}

pub fn validate_manifest(root: &Path, manifest: &Manifest) -> Result<()> {
    if manifest.schema.trim() != SUPPORTED_SCHEMA {
        bail!("unsupported schema: {}", manifest.schema);
    }

    if manifest.repo.name.trim().is_empty() {
        bail!("repo.name must not be empty");
    }

    validate_readme_sections(manifest)?;

    if matches!(manifest.record.mode, RecordMode::Native) {
        validate_native_paths(root, manifest)?;
    }

    if matches!(manifest.record.mode, RecordMode::Overlay) {
        let source = manifest.record.source.as_deref().unwrap_or("").trim();
        if source.is_empty() {
            bail!("record.source must be set for overlay records");
        }

        let trust = manifest
            .record
            .trust
            .as_ref()
            .ok_or_else(|| anyhow!("record.trust must be set for overlay records"))?;
        if trust.provenance.is_empty() {
            bail!("record.trust.provenance must list at least one provenance entry for overlay records");
        }
    }

    Ok(())
}

fn validate_native_paths(root: &Path, manifest: &Manifest) -> Result<()> {
    if let Some(docs) = &manifest.docs {
        for path in [
            &docs.root,
            &docs.getting_started,
            &docs.architecture,
            &docs.api,
        ]
        .into_iter()
        .flatten()
        {
            let target = root.join(path);
            if !target.exists() {
                bail!("referenced path does not exist: {}", target.display());
            }
        }
    }

    if let Some(readme) = &manifest.readme {
        for (name, section) in &readme.custom_sections {
            if let Some(path) = &section.path {
                let target = root.join(path);
                if !target.exists() {
                    bail!(
                        "custom README section `{}` references a missing path: {}",
                        name,
                        target.display()
                    );
                }
            }
        }
    }

    Ok(())
}

pub fn query_manifest_value(manifest: &Manifest, key: &str) -> Result<Value> {
    let document = serde_json::to_value(manifest)?;
    let canonical_key = normalize_query_path(key);
    let value = query_value(&document, &canonical_key).or_else(|_| {
        if canonical_key != key {
            query_value(&document, key)
        } else {
            bail!("query path not found: {}", key)
        }
    })?;
    Ok(value.clone())
}

pub fn query_manifest(manifest: &Manifest, key: &str) -> Result<String> {
    Ok(serde_json::to_string_pretty(&query_manifest_value(
        manifest, key,
    )?)?)
}

pub fn render_readme(root: &Path, manifest: &Manifest, source_bytes: &[u8]) -> Result<String> {
    let mut out = String::new();
    let digest = source_digest(source_bytes);

    out.push_str(&generated_banner(CommentStyle::Html, manifest, &digest));
    out.push('\n');

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

pub fn managed_outputs(
    root: &Path,
    manifest: &Manifest,
    source_bytes: &[u8],
) -> Result<Vec<(PathBuf, String)>> {
    let mut outputs = vec![(
        root.join("README.md"),
        render_readme(root, manifest, source_bytes)?,
    )];
    for (relative, contents) in github_outputs(manifest, source_bytes) {
        outputs.push((root.join(relative), contents));
    }
    Ok(outputs)
}

pub fn github_outputs(manifest: &Manifest, source_bytes: &[u8]) -> Vec<(PathBuf, String)> {
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
                outputs.push((
                    PathBuf::from(".github/CODEOWNERS"),
                    format!(
                        "{}\n* {}\n",
                        generated_banner(CommentStyle::Hash, manifest, &digest),
                        owners
                    ),
                ));
            }
            if matches!(github.security, Some(CompatMode::Generate)) {
                let contact = manifest
                    .owners
                    .as_ref()
                    .and_then(|o| o.security_contact.clone())
                    .unwrap_or_else(|| "the maintainers".into());
                outputs.push((
                    PathBuf::from(".github/SECURITY.md"),
                    format!(
                        "{}\n# Security\n\nPlease report vulnerabilities to {}.\n",
                        generated_banner(CommentStyle::Html, manifest, &digest),
                        contact
                    ),
                ));
            }
            if matches!(github.contributing, Some(CompatMode::Generate)) {
                outputs.push((
                    PathBuf::from("CONTRIBUTING.md"),
                    render_contributing(manifest, &digest),
                ));
            }
            if matches!(github.pull_request_template, Some(CompatMode::Generate)) {
                outputs.push((
                    PathBuf::from(".github/pull_request_template.md"),
                    render_pull_request_template(manifest, &digest),
                ));
            }
        }
    }
    outputs
}

pub fn detect_unmanaged_files(root: &Path) -> Vec<DoctorFinding> {
    const CANDIDATES: [&str; 11] = [
        "README.md",
        "CODEOWNERS",
        ".github/CODEOWNERS",
        "SECURITY.md",
        ".github/SECURITY.md",
        "CONTRIBUTING.md",
        ".github/CONTRIBUTING.md",
        "PULL_REQUEST_TEMPLATE.md",
        ".github/PULL_REQUEST_TEMPLATE.md",
        "pull_request_template.md",
        ".github/pull_request_template.md",
    ];

    let mut findings = Vec::new();
    for relative in CANDIDATES {
        let path = root.join(relative);
        if !path.exists() {
            continue;
        }

        match fs::read_to_string(&path) {
            Ok(contents) => {
                if !is_dotrepo_generated(&contents) {
                    findings.push(DoctorFinding {
                        path: PathBuf::from(relative),
                        message: "conventional surface is not managed by dotrepo; import or normalize it before enabling sync"
                            .into(),
                    });
                }
            }
            Err(err) => findings.push(DoctorFinding {
                path: PathBuf::from(relative),
                message: format!("could not be read during doctor scan: {}", err),
            }),
        }
    }

    findings
}

pub fn source_digest(source_bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(source_bytes);
    format!("{:x}", hasher.finalize())
}

fn validate_readme_sections(manifest: &Manifest) -> Result<()> {
    if let Some(readme) = &manifest.readme {
        for (name, section) in &readme.custom_sections {
            let has_content = section
                .content
                .as_deref()
                .map(|value| !value.trim().is_empty())
                .unwrap_or(false);
            let has_path = section
                .path
                .as_deref()
                .map(|value| !value.trim().is_empty())
                .unwrap_or(false);

            match (has_content, has_path) {
                (false, false) => {
                    bail!(
                        "custom README section `{}` must declare either `content` or `path`",
                        name
                    );
                }
                (true, true) => {
                    bail!(
                        "custom README section `{}` must not declare both `content` and `path`",
                        name
                    );
                }
                _ => {}
            }
        }
    }

    Ok(())
}

fn manifest_path(root: &Path) -> PathBuf {
    let canonical = root.join(".repo");
    if canonical.exists() {
        canonical
    } else {
        root.join("record.toml")
    }
}

fn normalize_query_path(key: &str) -> String {
    match key {
        "" | "." => ".".into(),
        "trust" => "record.trust".into(),
        _ if key.starts_with("trust.") => format!("record.{}", key),
        _ => key.into(),
    }
}

fn query_value<'a>(value: &'a Value, key: &str) -> Result<&'a Value> {
    if key.is_empty() || key == "." {
        return Ok(value);
    }

    let mut current = value;
    for segment in key.split('.') {
        current = match current {
            Value::Object(map) => map
                .get(segment)
                .ok_or_else(|| anyhow!("query path not found: {}", key))?,
            Value::Array(items) => {
                let index = segment
                    .parse::<usize>()
                    .map_err(|_| anyhow!("query path not found: {}", key))?;
                items
                    .get(index)
                    .ok_or_else(|| anyhow!("query path not found: {}", key))?
            }
            _ => bail!("query path not found: {}", key),
        };
    }

    Ok(current)
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
        let target = root.join(path);
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

fn generated_banner(style: CommentStyle, manifest: &Manifest, digest: &str) -> String {
    let body = format!(
        "generated by {} {} | schema: {} | source: sha256:{}",
        GENERATOR_NAME, GENERATOR_VERSION, manifest.schema, digest
    );
    match style {
        CommentStyle::Html => format!("<!-- {} -->", body),
        CommentStyle::Hash => format!("# {}", body),
    }
}

fn render_contributing(manifest: &Manifest, digest: &str) -> String {
    let mut out = String::new();
    out.push_str(&generated_banner(CommentStyle::Html, manifest, digest));
    out.push('\n');
    out.push_str("# Contributing\n\n");
    out.push_str(&format!(
        "Thanks for contributing to {}.\n\n",
        manifest.repo.name
    ));
    out.push_str("## Before you open a change\n\n");
    out.push_str("- Review the repository documentation and policies.\n");
    if let Some(build) = &manifest.repo.build {
        out.push_str(&format!("- Run `{}` before submitting changes.\n", build));
    }
    if let Some(test) = &manifest.repo.test {
        out.push_str(&format!("- Run `{}` before submitting changes.\n", test));
    }
    out.push('\n');
    out.push_str("## Security\n\n");
    if let Some(contact) = manifest
        .owners
        .as_ref()
        .and_then(|owners| owners.security_contact.as_ref())
    {
        out.push_str(&format!(
            "Report suspected vulnerabilities to {} instead of opening a public issue.\n",
            contact
        ));
    } else {
        out.push_str(
            "Report suspected vulnerabilities privately to the maintainers instead of opening a public issue.\n",
        );
    }
    out
}

fn render_pull_request_template(manifest: &Manifest, digest: &str) -> String {
    let mut out = String::new();
    out.push_str(&generated_banner(CommentStyle::Html, manifest, digest));
    out.push('\n');
    out.push_str("## Summary\n\n");
    out.push_str("- Describe the user-visible change.\n\n");
    out.push_str("## Validation\n\n");
    if let Some(build) = &manifest.repo.build {
        out.push_str(&format!("- [ ] `{}`\n", build));
    }
    if let Some(test) = &manifest.repo.test {
        out.push_str(&format!("- [ ] `{}`\n", test));
    }
    if manifest.repo.build.is_none() && manifest.repo.test.is_none() {
        out.push_str("- [ ] Describe how you validated this change.\n");
    }
    out.push('\n');
    out.push_str("## Checklist\n\n");
    out.push_str("- [ ] Documentation updated where needed.\n");
    out.push_str("- [ ] Ownership, policy, and security impacts considered.\n");
    out
}

fn is_dotrepo_generated(contents: &str) -> bool {
    contents.lines().next().map(is_banner_line).unwrap_or(false)
}

fn is_banner_line(line: &str) -> bool {
    let trimmed = line.trim_start();
    trimmed.starts_with("<!-- generated by dotrepo")
        || trimmed.starts_with("# generated by dotrepo")
}

enum CommentStyle {
    Html,
    Hash,
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn query_manifest_walks_dynamic_paths() {
        let manifest = parse_manifest(
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[record.trust]
confidence = "high"
provenance = ["declared", "verified"]

[repo]
name = "orbit"
description = "Fast local-first sync engine"
languages = ["rust"]

[x.example]
internal_id = "orbit-prod"
"#,
        )
        .expect("manifest parses");

        assert_eq!(
            query_manifest(&manifest, "x.example.internal_id").expect("query succeeds"),
            "\"orbit-prod\""
        );
        assert_eq!(
            query_manifest(&manifest, "trust.provenance").expect("legacy trust alias works"),
            "[\n  \"declared\",\n  \"verified\"\n]"
        );
        assert_eq!(
            query_manifest_value(&manifest, "repo.name").expect("value query succeeds"),
            Value::String("orbit".into())
        );
    }

    #[test]
    fn render_readme_renders_custom_sections() {
        let root = temp_dir("custom-readme");
        let manifest = parse_manifest(
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"

[readme]
sections = ["overview", "quickstart"]

[readme.custom_sections.quickstart]
content = "Run `cargo build`."
"#,
        )
        .expect("manifest parses");

        let rendered =
            render_readme(&root, &manifest, b"schema = \"dotrepo/v0.1\"").expect("readme renders");

        assert!(rendered.contains("## Quickstart"));
        assert!(rendered.contains("Run `cargo build`."));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn detect_unmanaged_files_finds_conventional_surfaces() {
        let root = temp_dir("doctor");
        fs::write(root.join("README.md"), "# Existing README\n").expect("README written");
        fs::create_dir_all(root.join(".github")).expect(".github created");
        fs::write(
            root.join(".github/CODEOWNERS"),
            "# generated by dotrepo 0.1.0 | schema: dotrepo/v0.1 | source: sha256:abc\n* @alice\n",
        )
        .expect("CODEOWNERS written");

        let findings = detect_unmanaged_files(&root);
        assert_eq!(findings.len(), 1);
        assert_eq!(findings[0].path, PathBuf::from("README.md"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn load_manifest_from_root_falls_back_to_record_toml() {
        let root = temp_dir("overlay");
        fs::write(
            root.join("record.toml"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"
source = "https://example.com/repo"

[record.trust]
confidence = "medium"
provenance = ["imported"]

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
        )
        .expect("record written");

        let manifest = load_manifest_from_root(&root).expect("manifest loads from record.toml");
        assert_eq!(manifest.repo.name, "orbit");

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn load_manifest_document_returns_path_and_raw_bytes() {
        let root = temp_dir("document");
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
        )
        .expect("manifest written");

        let document = load_manifest_document(&root).expect("document loads");
        assert_eq!(document.path, root.join(".repo"));
        assert!(!document.raw.is_empty());
        assert_eq!(document.manifest.repo.name, "orbit");

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn github_outputs_generate_remaining_compat_files() {
        let manifest = parse_manifest(
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
build = "cargo build"
test = "cargo test"

[owners]
security_contact = "security@example.com"

[compat.github]
codeowners = "skip"
security = "skip"
contributing = "generate"
pull_request_template = "generate"
"#,
        )
        .expect("manifest parses");

        let outputs = github_outputs(&manifest, b"schema = \"dotrepo/v0.1\"");
        assert!(outputs
            .iter()
            .any(|(path, _)| path == Path::new("CONTRIBUTING.md")));
        assert!(outputs
            .iter()
            .any(|(path, _)| path == Path::new(".github/pull_request_template.md")));
    }

    fn temp_dir(label: &str) -> PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock works")
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "dotrepo-{}-{}-{}",
            label,
            std::process::id(),
            unique
        ));
        fs::create_dir_all(&path).expect("temp dir created");
        path
    }
}
