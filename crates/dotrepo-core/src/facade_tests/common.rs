pub(crate) use super::super::*;
pub(crate) use crate::import::{
    clean_project_description, extract_markdown_links, infer_imported_commands,
    infer_pyproject_commands, is_non_project_heading, normalize_description_line,
    parse_codeowners_metadata, parse_contributing_security, parse_issue_template_security,
    parse_readme_docs_signal, parse_readme_metadata, parse_readme_title_line,
    parse_security_contact, parse_security_import_metadata, try_parse_multiline_html_heading,
    ImportSources, ImportedFile,
};
pub(crate) use crate::surfaces::parse_managed_marker;
pub(crate) use dotrepo_schema::{parse_manifest, CompatMode, RelationKind};
pub(crate) use std::fs;
pub(crate) use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

pub(crate) fn temp_dir(label: &str) -> PathBuf {
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

pub(crate) fn sample_public_freshness() -> PublicFreshness {
    PublicFreshness {
        generated_at: "2026-03-10T18:30:00Z".into(),
        snapshot_digest: "snapshot-123".into(),
        stale_after: Some("2026-03-11T18:30:00Z".into()),
    }
}
