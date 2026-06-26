use anyhow::{anyhow, bail, Result};
use dotrepo_schema::{Manifest, RecordMode};
use serde::Serialize;
use std::fs;
use std::path::{Path, PathBuf};

use crate::claims::resolve_repository_local_path_for_read;
use crate::claims::{
    claim_directory_identity, load_claim_directory, validate_claim_event_history,
    validate_claim_identity_alignment, validate_claim_resolution_consistency,
};
use crate::selection::{candidate_from_document, sort_candidates};
use crate::synthesis::{load_synthesis_document, validate_synthesis};
use crate::util::{display_path, parse_rfc3339, repository_identity, validate_shell_safe_command};
use crate::{load_manifest_document, load_manifest_file, record_summary, RecordSummary};

pub(crate) const SUPPORTED_SCHEMA: &str = "dotrepo/v0.1";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidationDiagnostic {
    pub severity: ValidationDiagnosticSeverity,
    pub code: &'static str,
    pub source: &'static str,
    pub message: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ValidationDiagnosticSeverity {
    Error,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IndexFinding {
    pub path: PathBuf,
    pub severity: IndexFindingSeverity,
    pub message: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IndexFindingSeverity {
    Warning,
    Error,
}
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RepositoryDiagnostic {
    pub severity: &'static str,
    pub source: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub manifest_path: Option<String>,
}
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ValidateReport {
    pub valid: bool,
    pub root: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub manifest_path: Option<String>,
    pub diagnostics: Vec<RepositoryDiagnostic>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub record: Option<RecordSummary>,
}
pub fn validate_repository(root: &Path) -> ValidateReport {
    let mut diagnostics = Vec::new();
    let mut loaded = Vec::new();

    match collect_root_manifest_targets(root) {
        Ok(targets) if targets.is_empty() => {
            diagnostics.push(RepositoryDiagnostic {
                severity: "error",
                source: "load_manifest_document".into(),
                message: format!(
                    "failed to read {}: no .repo or record.toml found at the repository root",
                    crate::util::manifest_path(root).display()
                ),
                manifest_path: None,
            });
        }
        Ok(targets) => {
            for path in targets {
                let manifest_path = display_path(root, &path);
                match load_manifest_file(&path) {
                    Ok(document) => loaded.push(document),
                    Err(err) => diagnostics.push(RepositoryDiagnostic {
                        severity: "error",
                        source: "load_manifest_document".into(),
                        message: err.to_string(),
                        manifest_path: Some(manifest_path),
                    }),
                }
            }

            for document in &loaded {
                let manifest_path = display_path(root, &document.path);
                for item in validate_manifest_diagnostics(root, &document.manifest) {
                    diagnostics.push(RepositoryDiagnostic {
                        severity: "error",
                        source: item.source.to_string(),
                        message: item.message,
                        manifest_path: Some(manifest_path.clone()),
                    });
                }
            }
        }
        Err(err) => {
            diagnostics.push(RepositoryDiagnostic {
                severity: "error",
                source: "collect_root_manifest_targets".into(),
                message: err.to_string(),
                manifest_path: None,
            });
        }
    }

    let mut candidates = Vec::new();
    for document in &loaded {
        match candidate_from_document(root, document) {
            Ok(candidate) => candidates.push(candidate),
            Err(err) => diagnostics.push(RepositoryDiagnostic {
                severity: "error",
                source: "candidate_from_document".into(),
                message: err.to_string(),
                manifest_path: Some(display_path(root, &document.path)),
            }),
        }
    }
    sort_candidates(&mut candidates, root);

    let selected = candidates.first();
    ValidateReport {
        valid: diagnostics.is_empty(),
        root: root.display().to_string(),
        manifest_path: selected.map(|candidate| candidate.manifest_path.clone()),
        diagnostics,
        record: selected.map(|candidate| record_summary(&candidate.manifest)),
    }
}

fn collect_root_manifest_targets(root: &Path) -> Result<Vec<PathBuf>> {
    let mut targets = Vec::new();
    for name in [".repo", "record.toml"] {
        let path = root.join(name);
        if path.exists() {
            targets.push(path);
        }
    }

    Ok(targets)
}
pub(crate) fn collect_record_paths(dir: &Path, out: &mut Vec<PathBuf>) -> Result<()> {
    collect_record_paths_recursive(dir, out, 0)
}

fn collect_record_paths_recursive(dir: &Path, out: &mut Vec<PathBuf>, depth: u32) -> Result<()> {
    if depth > 20 {
        bail!(
            "directory traversal depth exceeded at {} — possible symlink cycle",
            dir.display()
        );
    }
    for entry in
        fs::read_dir(dir).map_err(|err| anyhow!("failed to read {}: {}", dir.display(), err))?
    {
        let entry = entry?;
        let path = entry.path();
        if path.is_dir() {
            collect_record_paths_recursive(&path, out, depth + 1)?;
        } else if path
            .file_name()
            .map(|n| n == "record.toml")
            .unwrap_or(false)
        {
            out.push(path);
        }
    }
    Ok(())
}

pub fn validate_manifest(root: &Path, manifest: &Manifest) -> Result<()> {
    let diagnostics = validate_manifest_diagnostics(root, manifest);
    if diagnostics.is_empty() {
        return Ok(());
    }

    bail!(
        "{}",
        diagnostics
            .into_iter()
            .map(|diagnostic| diagnostic.message)
            .collect::<Vec<_>>()
            .join("\n")
    )
}

pub fn validate_manifest_diagnostics(
    root: &Path,
    manifest: &Manifest,
) -> Vec<ValidationDiagnostic> {
    let mut diagnostics = Vec::new();

    if manifest.schema.trim() != SUPPORTED_SCHEMA {
        diagnostics.push(validation_error(
            "unsupported_schema",
            "validate_manifest",
            format!("unsupported schema: {}", manifest.schema),
        ));
    }

    if let Some(generated_at) = manifest.record.generated_at.as_deref() {
        if let Err(err) = parse_rfc3339("record.generated_at", generated_at) {
            diagnostics.push(validation_error(
                "invalid_generated_at",
                "validate_manifest",
                err.to_string(),
            ));
        }
    }

    if manifest.repo.name.trim().is_empty() {
        diagnostics.push(validation_error(
            "repo_name_empty",
            "validate_manifest",
            "repo.name must not be empty",
        ));
    }

    if let Some(build) = manifest.repo.build.as_deref() {
        if let Err(err) = validate_shell_safe_command("repo.build", build) {
            diagnostics.push(validation_error(
                "unsafe_shell_command",
                "validate_manifest",
                err.to_string(),
            ));
        }
    }
    if let Some(test) = manifest.repo.test.as_deref() {
        if let Err(err) = validate_shell_safe_command("repo.test", test) {
            diagnostics.push(validation_error(
                "unsafe_shell_command",
                "validate_manifest",
                err.to_string(),
            ));
        }
    }

    diagnostics.extend(validate_readme_sections(manifest));

    if matches!(manifest.record.mode, RecordMode::Native) {
        diagnostics.extend(validate_native_paths(root, manifest));
    }

    if matches!(manifest.record.mode, RecordMode::Overlay) {
        let source = manifest.record.source.as_deref().unwrap_or("").trim();
        if source.is_empty() {
            diagnostics.push(validation_error(
                "overlay_source_required",
                "validate_manifest",
                "record.source must be set for overlay records",
            ));
        }

        match manifest.record.trust.as_ref() {
            Some(trust) => {
                if trust.provenance.is_empty() {
                    diagnostics.push(validation_error(
                        "overlay_trust_provenance_required",
                        "validate_manifest",
                        "record.trust.provenance must list at least one provenance entry for overlay records",
                    ));
                }
            }
            None => diagnostics.push(validation_error(
                "overlay_trust_required",
                "validate_manifest",
                "record.trust must be set for overlay records",
            )),
        }
    }

    diagnostics
}

fn validate_native_paths(root: &Path, manifest: &Manifest) -> Vec<ValidationDiagnostic> {
    let mut diagnostics = Vec::new();

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
            match resolve_repository_local_path_for_read(root, path) {
                Ok(target) => {
                    if !target.exists() {
                        diagnostics.push(validation_error(
                            "missing_referenced_path",
                            "validate_native_paths",
                            format!("referenced path does not exist: {}", target.display()),
                        ));
                    }
                }
                Err(err) => {
                    diagnostics.push(validation_error(
                        "invalid_referenced_path",
                        "validate_native_paths",
                        format!("referenced path `{}` is invalid: {}", path, err),
                    ));
                }
            }
        }
    }

    if let Some(readme) = &manifest.readme {
        for (name, section) in &readme.custom_sections {
            if let Some(path) = &section.path {
                match resolve_repository_local_path_for_read(root, path) {
                    Ok(target) => {
                        if !target.exists() {
                            diagnostics.push(validation_error(
                                "readme_section_missing_path",
                                "validate_native_paths",
                                format!(
                                    "custom README section `{}` references a missing path: {}",
                                    name,
                                    target.display()
                                ),
                            ));
                        }
                    }
                    Err(err) => {
                        diagnostics.push(validation_error(
                            "readme_section_invalid_path",
                            "validate_native_paths",
                            format!(
                                "custom README section `{}` uses an invalid path `{}`: {}",
                                name, path, err
                            ),
                        ));
                    }
                }
            }
        }
    }

    diagnostics
}
pub fn validate_index_root(index_root: &Path) -> Result<Vec<IndexFinding>> {
    let repos_root = index_root.join("repos");
    if !repos_root.exists() {
        bail!(
            "index root does not contain a repos/ directory: {}",
            repos_root.display()
        );
    }

    let mut record_dirs = Vec::new();
    collect_record_dirs(&repos_root, &mut record_dirs)?;
    record_dirs.sort();
    let mut claim_dirs = Vec::new();
    collect_claim_dirs(&repos_root, &mut claim_dirs)?;
    claim_dirs.sort();

    let mut findings = Vec::new();
    for record_dir in record_dirs {
        let display_path = record_dir
            .strip_prefix(index_root)
            .unwrap_or(&record_dir)
            .join("record.toml");
        let synthesis_display_path = record_dir
            .strip_prefix(index_root)
            .unwrap_or(&record_dir)
            .join("synthesis.toml");

        let document = match load_manifest_document(&record_dir) {
            Ok(document) => document,
            Err(err) => {
                findings.push(index_error(display_path, err.to_string()));
                continue;
            }
        };

        for diagnostic in validate_manifest_diagnostics(&record_dir, &document.manifest) {
            findings.push(index_error(
                display_path.clone(),
                format!("[{}] {}", diagnostic.source, diagnostic.message),
            ));
        }

        let synthesis_file = record_dir.join("synthesis.toml");
        if synthesis_file.is_file() {
            match load_synthesis_document(&record_dir) {
                Ok(synthesis) => {
                    if let Err(err) = validate_synthesis(&document.manifest, &synthesis.synthesis) {
                        findings.push(index_error(synthesis_display_path.clone(), err.to_string()));
                    }
                }
                Err(err) => {
                    findings.push(index_error(synthesis_display_path.clone(), err.to_string()))
                }
            }
        }

        findings.extend(validate_index_entry(
            index_root,
            &record_dir,
            &document.manifest,
        ));
    }

    for claim_dir in claim_dirs {
        findings.extend(validate_claim_directory(index_root, &claim_dir));
    }

    Ok(findings)
}
fn validate_readme_sections(manifest: &Manifest) -> Vec<ValidationDiagnostic> {
    let mut diagnostics = Vec::new();
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
                    diagnostics.push(validation_error(
                        "readme_section_content_or_path_required",
                        "validate_readme_sections",
                        format!(
                            "custom README section `{}` must declare either `content` or `path`",
                            name
                        ),
                    ));
                }
                (true, true) => {
                    diagnostics.push(validation_error(
                        "readme_section_content_and_path_conflict",
                        "validate_readme_sections",
                        format!(
                            "custom README section `{}` must not declare both `content` and `path`",
                            name
                        ),
                    ));
                }
                _ => {}
            }
        }
    }

    diagnostics
}

fn validate_index_entry(
    index_root: &Path,
    record_dir: &Path,
    manifest: &Manifest,
) -> Vec<IndexFinding> {
    let mut findings = Vec::new();
    let relative_record = record_dir
        .strip_prefix(index_root)
        .unwrap_or(record_dir)
        .join("record.toml");

    let relative = match record_dir.strip_prefix(index_root.join("repos")) {
        Ok(relative) => relative,
        Err(_) => {
            findings.push(IndexFinding {
                path: relative_record,
                severity: IndexFindingSeverity::Error,
                message:
                    "index records must live under index_root/repos/<host>/<owner>/<repo>/record.toml"
                        .into(),
            });
            return findings;
        }
    };

    let segments = relative
        .iter()
        .map(|segment| segment.to_string_lossy().to_string())
        .collect::<Vec<_>>();
    if segments.len() != 3 {
        findings.push(IndexFinding {
            path: relative_record.clone(),
            severity: IndexFindingSeverity::Error,
            message: "index path must be exactly repos/<host>/<owner>/<repo>/record.toml".into(),
        });
        return findings;
    }

    if manifest.record.mode != RecordMode::Overlay {
        findings.push(index_error(
            relative_record.clone(),
            "v0.1 index entries must use record.mode = \"overlay\"",
        ));
    }

    let evidence_path = record_dir.join("evidence.md");
    let evidence = match fs::read_to_string(&evidence_path) {
        Ok(contents) => {
            if contents.trim().is_empty() {
                findings.push(index_error(
                    relative_record.clone(),
                    "evidence.md must not be empty",
                ));
            }
            Some(contents)
        }
        Err(_) => {
            findings.push(index_error(
                relative_record.clone(),
                "index entries must include a sibling evidence.md file",
            ));
            None
        }
    };

    let expected = (
        segments[0].clone(),
        segments[1].clone(),
        segments[2].clone(),
    );

    match repository_identity(manifest.record.source.as_deref().unwrap_or_default()) {
        Some(identity) if identity == expected => {}
        Some(identity) => findings.push(index_error(
            relative_record.clone(),
            format!(
                "record.source resolves to {}/{}/{}, but index path is {}/{}/{}",
                identity.0, identity.1, identity.2, expected.0, expected.1, expected.2
            ),
        )),
        None => findings.push(index_error(
            relative_record.clone(),
            "record.source must be an absolute repository URL with host/owner/repo segments",
        )),
    }

    if let Some(homepage) = &manifest.repo.homepage {
        if let Some(identity) = repository_identity(homepage) {
            let code_hosts = ["github.com", "gitlab.com", "bitbucket.org"];
            if code_hosts.contains(&identity.0.as_str()) && identity != expected {
                findings.push(index_error(
                    relative_record.clone(),
                    format!(
                        "repo.homepage resolves to {}/{}/{}, but index path is {}/{}/{}",
                        identity.0, identity.1, identity.2, expected.0, expected.1, expected.2
                    ),
                ));
            }
        }
    }

    findings.extend(lint_index_entry(
        relative_record,
        manifest,
        evidence.as_deref().unwrap_or(""),
    ));

    findings
}
fn validate_claim_directory(index_root: &Path, claim_dir: &Path) -> Vec<IndexFinding> {
    let mut findings = Vec::new();
    let claim_path = claim_dir.join("claim.toml");
    let relative_claim = claim_path
        .strip_prefix(index_root)
        .unwrap_or(&claim_path)
        .to_path_buf();

    let directory_identity = match claim_directory_identity(index_root, claim_dir) {
        Ok(identity) => identity,
        Err(message) => {
            findings.push(index_error(relative_claim, message.to_string()));
            return findings;
        }
    };

    let loaded = match load_claim_directory(index_root, claim_dir) {
        Ok(loaded) => loaded,
        Err(err) => {
            findings.push(index_error(relative_claim, err.to_string()));
            return findings;
        }
    };

    findings.extend(validate_claim_identity_alignment(
        &relative_claim,
        &directory_identity,
        &loaded.claim,
    ));
    findings.extend(validate_claim_event_history(
        &relative_claim,
        &loaded.claim,
        &loaded.events,
    ));
    findings.extend(validate_claim_resolution_consistency(
        &relative_claim,
        &loaded.claim,
    ));

    findings
}
pub(crate) fn collect_record_dirs(root: &Path, out: &mut Vec<PathBuf>) -> Result<()> {
    collect_record_dirs_recursive(root, out, 0)
}

fn collect_record_dirs_recursive(root: &Path, out: &mut Vec<PathBuf>, depth: u32) -> Result<()> {
    if depth > 20 {
        bail!(
            "directory traversal depth exceeded at {} — possible symlink cycle",
            root.display()
        );
    }
    for entry in
        fs::read_dir(root).map_err(|err| anyhow!("failed to read {}: {}", root.display(), err))?
    {
        let entry = entry?;
        let path = entry.path();
        let file_type = entry.file_type()?;
        if file_type.is_dir() {
            collect_record_dirs_recursive(&path, out, depth + 1)?;
        } else if file_type.is_file()
            && path.file_name().and_then(|name| name.to_str()) == Some("record.toml")
        {
            if let Some(parent) = path.parent() {
                out.push(parent.to_path_buf());
            }
        }
    }
    Ok(())
}

fn collect_claim_dirs(root: &Path, out: &mut Vec<PathBuf>) -> Result<()> {
    collect_claim_dirs_recursive(root, out, 0)
}

fn collect_claim_dirs_recursive(root: &Path, out: &mut Vec<PathBuf>, depth: u32) -> Result<()> {
    if depth > 20 {
        bail!(
            "directory traversal depth exceeded at {} — possible symlink cycle",
            root.display()
        );
    }
    for entry in
        fs::read_dir(root).map_err(|err| anyhow!("failed to read {}: {}", root.display(), err))?
    {
        let entry = entry?;
        let path = entry.path();
        let file_type = entry.file_type()?;
        if file_type.is_dir() {
            if path.file_name().and_then(|name| name.to_str()) == Some("claims") {
                for claim_entry in fs::read_dir(&path)
                    .map_err(|err| anyhow!("failed to read {}: {}", path.display(), err))?
                {
                    let claim_entry = claim_entry?;
                    if claim_entry.file_type()?.is_dir() {
                        out.push(claim_entry.path());
                    }
                }
            } else {
                collect_claim_dirs_recursive(&path, out, depth + 1)?;
            }
        }
    }
    Ok(())
}
fn lint_index_entry(path: PathBuf, manifest: &Manifest, evidence: &str) -> Vec<IndexFinding> {
    let mut findings = Vec::new();
    let evidence_lower = evidence.to_lowercase();

    if let Some(confidence) = manifest
        .record
        .trust
        .as_ref()
        .and_then(|trust| trust.confidence.as_deref())
    {
        if !matches!(confidence, "low" | "medium" | "high") {
            findings.push(index_warning(
                path.clone(),
                format!(
                    "record.trust.confidence uses non-reference vocabulary `{}`; preserve it, but prefer low/medium/high in the public index",
                    confidence
                ),
            ));
        }
    }

    if let Some(trust) = &manifest.record.trust {
        for provenance in &trust.provenance {
            if !matches!(
                provenance.as_str(),
                "declared" | "imported" | "inferred" | "verified"
            ) {
                findings.push(index_warning(
                    path.clone(),
                    format!(
                        "record.trust.provenance includes non-reference value `{}`; preserve it, but prefer declared/imported/inferred/verified in the public index",
                        provenance
                    ),
                ));
            }
        }
    }

    for expected in expected_provenance_for_status(&manifest.record.status) {
        let has_expected = manifest
            .record
            .trust
            .as_ref()
            .map(|trust| trust.provenance.iter().any(|value| value == expected))
            .unwrap_or(false);
        if !has_expected {
            findings.push(index_warning(
                path.clone(),
                format!(
                    "record.status = {:?} should usually be accompanied by `{}` in record.trust.provenance",
                    manifest.record.status, expected
                ),
            ));
        }
    }

    for keyword in manifest
        .record
        .trust
        .as_ref()
        .map(|trust| trust.provenance.clone())
        .unwrap_or_default()
    {
        if matches!(
            keyword.as_str(),
            "declared" | "imported" | "inferred" | "verified"
        ) && !evidence_mentions(&evidence_lower, &keyword)
        {
            findings.push(index_warning(
                path.clone(),
                format!(
                    "evidence.md should mention `{}` so the trust story is visible to reviewers",
                    keyword
                ),
            ));
        }
    }

    if manifest.repo.build.is_some() && !evidence_mentions(&evidence_lower, "build") {
        findings.push(index_warning(
            path.clone(),
            "evidence.md should explain where the build command came from",
        ));
    }

    if manifest.repo.test.is_some() && !evidence_mentions(&evidence_lower, "test") {
        findings.push(index_warning(
            path.clone(),
            "evidence.md should explain where the test command came from",
        ));
    }

    if manifest
        .owners
        .as_ref()
        .and_then(|owners| owners.security_contact.as_deref())
        == Some("unknown")
        && !evidence_mentions(&evidence_lower, "unknown")
    {
        findings.push(index_warning(
            path,
            "evidence.md should explain why security_contact = \"unknown\" is intentional",
        ));
    }

    findings
}

fn expected_provenance_for_status(
    status: &dotrepo_schema::RecordStatus,
) -> &'static [&'static str] {
    match status {
        dotrepo_schema::RecordStatus::Imported => &["imported"],
        dotrepo_schema::RecordStatus::Inferred => &["inferred"],
        dotrepo_schema::RecordStatus::Verified => &["verified"],
        dotrepo_schema::RecordStatus::Canonical => &["declared"],
        _ => &[],
    }
}

fn validation_error(
    code: &'static str,
    source: &'static str,
    message: impl Into<String>,
) -> ValidationDiagnostic {
    ValidationDiagnostic {
        severity: ValidationDiagnosticSeverity::Error,
        code,
        source,
        message: message.into(),
    }
}

fn evidence_mentions(evidence_lower: &str, keyword: &str) -> bool {
    evidence_lower.contains(&keyword.to_lowercase())
}

pub(crate) fn index_error(path: PathBuf, message: impl Into<String>) -> IndexFinding {
    IndexFinding {
        path,
        severity: IndexFindingSeverity::Error,
        message: message.into(),
    }
}

fn index_warning(path: PathBuf, message: impl Into<String>) -> IndexFinding {
    IndexFinding {
        path,
        severity: IndexFindingSeverity::Warning,
        message: message.into(),
    }
}
