//! Import-time text parsing: README metadata extraction, URL quality gates,
//! markdown/text normalization, CODEOWNERS parsing, and security-contact
//! extraction. Split into focused submodules; this file only wires them
//! together and re-exports the surface the rest of `import` depends on.

mod codeowners;
mod markdown;
mod readme;
mod security;
mod urls;

pub(crate) use codeowners::parse_codeowners_metadata;
pub(crate) use markdown::{extract_markdown_links, parse_readme_docs_signal};
pub(crate) use readme::clean_project_name;
pub(crate) use readme::{
    clean_project_description, is_non_project_heading, normalize_description_line,
    parse_readme_metadata, parse_readme_title_line, try_parse_multiline_html_heading,
};
pub(crate) use security::{
    parse_contributing_security, parse_issue_template_security, parse_readme_security,
    parse_security_contact, parse_security_import_metadata,
};
pub(crate) use urls::{is_actionable_security_url, is_quality_url};
