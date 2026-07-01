//! Completion and hover support driven by the static manifest schema
//! catalog and the current document's `DocumentIndex`.

use crate::protocol::{
    CompletionItem, Hover, LspPosition, MarkupContent, TextDocumentPositionParams,
};
use crate::state::{document_for_request, DocumentIndex, ServerState};
use anyhow::Result;
use dotrepo_core::{manifest_to_json, query_manifest_value_from_json};
use dotrepo_schema::parse_manifest;

const COMPLETION_KIND_FIELD: u8 = 5;
const COMPLETION_KIND_VALUE: u8 = 12;
const COMPLETION_KIND_MODULE: u8 = 9;

pub(crate) fn completion_items(
    state: &ServerState,
    params: &TextDocumentPositionParams,
) -> Result<Vec<CompletionItem>> {
    let document = document_for_request(state, &params.text_document.uri)?;
    let index = DocumentIndex::from_text(&document.text);
    let line = index.line(params.position.line);
    let context = completion_context(
        &index,
        params.position.line,
        line,
        params.position.character,
    );

    Ok(schema_catalog()
        .iter()
        .filter(|entry| completion_matches(entry, &context))
        .map(catalog_completion_item)
        .collect())
}

pub(crate) fn hover_response(
    state: &ServerState,
    params: &TextDocumentPositionParams,
) -> Result<Option<Hover>> {
    let document = document_for_request(state, &params.text_document.uri)?;
    let index = DocumentIndex::from_text(&document.text);
    let Some(path) = index.path_at(params.position) else {
        return Ok(None);
    };
    if let Some(entry) = schema_catalog().iter().find(|entry| entry.path == path) {
        return Ok(Some(Hover {
            contents: markup_content(entry.documentation),
            range: index.range_for_path(path),
        }));
    }

    if path.starts_with("repo.") {
        if let Ok(manifest) = parse_manifest(&document.text) {
            if let Ok(document_json) = manifest_to_json(&manifest) {
                if let Ok(value) = query_manifest_value_from_json(&document_json, path) {
                    let rendered =
                        serde_json::to_string_pretty(&value).unwrap_or_else(|_| value.to_string());
                    return Ok(Some(Hover {
                        contents: markup_content(&format!(
                            "`{path}` resolves to:\n\n```json\n{rendered}\n```"
                        )),
                        range: index.range_for_path(path),
                    }));
                }
            }
        }
    }

    Ok(None)
}

#[derive(Debug, Clone)]
pub(crate) enum CompletionContext {
    Section,
    Key,
    Value { path: Option<String> },
}

fn completion_context(
    index: &DocumentIndex,
    line_number: u32,
    line: &str,
    character: u32,
) -> CompletionContext {
    let position = LspPosition {
        line: line_number,
        character,
    };
    if index.section_path_at(position).is_some()
        && prefix_at_utf16(line, character)
            .trim_start()
            .starts_with('[')
    {
        return CompletionContext::Section;
    }
    if index.field_path_at(position).is_some() {
        return CompletionContext::Key;
    }
    if let Some(path) = index.value_path_at(position) {
        return CompletionContext::Value {
            path: Some(path.to_string()),
        };
    }

    legacy_completion_context(index, line_number, line, character)
}

fn legacy_completion_context(
    index: &DocumentIndex,
    line_number: u32,
    line: &str,
    character: u32,
) -> CompletionContext {
    let slice = prefix_at_utf16(line, character);
    let trimmed = slice.trim_start();
    if trimmed.starts_with('[') {
        return CompletionContext::Section;
    }

    if let Some(eq_idx) = slice.find('=') {
        let key = slice[..eq_idx].trim();
        let path = if key.is_empty() {
            None
        } else if key.contains('.') {
            Some(key.to_string())
        } else {
            section_prefix_for_line(index, line_number)
                .map(|section| format!("{section}.{key}"))
                .or_else(|| Some(key.to_string()))
        };
        return CompletionContext::Value { path };
    }

    CompletionContext::Key
}

fn section_prefix_for_line(index: &DocumentIndex, line_number: u32) -> Option<&str> {
    let current_index = (line_number as usize).min(index.lines.len().saturating_sub(1));
    for candidate in (0..=current_index).rev() {
        let trimmed = index.lines[candidate].trim();
        if trimmed.starts_with('[') && trimmed.ends_with(']') && !trimmed.starts_with("[[") {
            let section = trimmed.trim_matches(|ch| ch == '[' || ch == ']').trim();
            if !section.is_empty() {
                return Some(
                    index
                        .sections
                        .keys()
                        .find(|existing| existing.as_str() == section)?
                        .as_str(),
                );
            }
        }
    }
    None
}

fn prefix_at_utf16(line: &str, character: u32) -> &str {
    let mut utf16_count = 0u32;
    for (idx, ch) in line.char_indices() {
        if utf16_count >= character {
            return &line[..idx];
        }
        utf16_count += ch.len_utf16() as u32;
    }
    line
}

fn completion_matches(entry: &CatalogEntry, context: &CompletionContext) -> bool {
    match (entry.kind, context) {
        (CatalogEntryKind::Section, CompletionContext::Section) => true,
        (CatalogEntryKind::Field, CompletionContext::Key) => true,
        (CatalogEntryKind::Value, CompletionContext::Value { path }) => path
            .as_deref()
            .is_some_and(|candidate| candidate == entry.path),
        _ => false,
    }
}

fn catalog_completion_item(entry: &CatalogEntry) -> CompletionItem {
    CompletionItem {
        label: match entry.kind {
            CatalogEntryKind::Section => format!("[{}]", entry.path),
            CatalogEntryKind::Field | CatalogEntryKind::Value => entry.insert_text.to_string(),
        },
        kind: match entry.kind {
            CatalogEntryKind::Section => COMPLETION_KIND_MODULE,
            CatalogEntryKind::Field => COMPLETION_KIND_FIELD,
            CatalogEntryKind::Value => COMPLETION_KIND_VALUE,
        },
        detail: Some(entry.detail.to_string()),
        documentation: Some(markup_content(entry.documentation)),
        insert_text: Some(entry.insert_text.to_string()),
    }
}

fn markup_content(value: &str) -> MarkupContent {
    MarkupContent {
        kind: "markdown".into(),
        value: value.to_string(),
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum CatalogEntryKind {
    Section,
    Field,
    Value,
}

#[derive(Debug, Clone, Copy)]
struct CatalogEntry {
    path: &'static str,
    kind: CatalogEntryKind,
    detail: &'static str,
    documentation: &'static str,
    insert_text: &'static str,
}

fn schema_catalog() -> &'static [CatalogEntry] {
    &[
        CatalogEntry {
            path: "record",
            kind: CatalogEntryKind::Section,
            detail: "Core record metadata",
            documentation: "### `[record]`\nMode, status, source, and trust entry point for the manifest.",
            insert_text: "[record]",
        },
        CatalogEntry {
            path: "record.trust",
            kind: CatalogEntryKind::Section,
            detail: "Trust metadata",
            documentation: "### `[record.trust]`\nConfidence, provenance, and notes that explain how this record was derived.",
            insert_text: "[record.trust]",
        },
        CatalogEntry {
            path: "repo",
            kind: CatalogEntryKind::Section,
            detail: "Repository facts",
            documentation: "### `[repo]`\nCanonical repository facts such as name, description, build, and test commands.",
            insert_text: "[repo]",
        },
        CatalogEntry {
            path: "owners",
            kind: CatalogEntryKind::Section,
            detail: "Ownership metadata",
            documentation: "### `[owners]`\nBootstrap maintainer, team, and security contact metadata.",
            insert_text: "[owners]",
        },
        CatalogEntry {
            path: "docs",
            kind: CatalogEntryKind::Section,
            detail: "Docs entry points",
            documentation: "### `[docs]`\nStructured documentation entry points such as root docs and getting started.",
            insert_text: "[docs]",
        },
        CatalogEntry {
            path: "readme",
            kind: CatalogEntryKind::Section,
            detail: "README generation hints",
            documentation: "### `[readme]`\nOptional title, tagline, and section ordering for generated README content.",
            insert_text: "[readme]",
        },
        CatalogEntry {
            path: "compat.github",
            kind: CatalogEntryKind::Section,
            detail: "GitHub compatibility surfaces",
            documentation: "### `[compat.github]`\nGeneration modes for `CODEOWNERS`, `SECURITY.md`, `CONTRIBUTING.md`, and PR templates.",
            insert_text: "[compat.github]",
        },
        CatalogEntry {
            path: "relations",
            kind: CatalogEntryKind::Section,
            detail: "Cross-repository relation assertions",
            documentation: "### `[relations]`\nDirected, identity-scoped relation assertions with independent trust metadata.",
            insert_text: "[relations]",
        },
        CatalogEntry {
            path: "schema",
            kind: CatalogEntryKind::Field,
            detail: "Manifest schema version",
            documentation: "`schema` selects the dotrepo protocol version. The current supported value is `dotrepo/v0.1`.",
            insert_text: "schema = ",
        },
        CatalogEntry {
            path: "record.mode",
            kind: CatalogEntryKind::Field,
            detail: "Record mode",
            documentation: "`record.mode` is `native` for canonical in-repo manifests and `overlay` for index or external records.",
            insert_text: "mode = ",
        },
        CatalogEntry {
            path: "record.status",
            kind: CatalogEntryKind::Field,
            detail: "Record status",
            documentation: "`record.status` expresses authority and review level, from `draft` through `canonical`.",
            insert_text: "status = ",
        },
        CatalogEntry {
            path: "record.source",
            kind: CatalogEntryKind::Field,
            detail: "Overlay source URL",
            documentation: "`record.source` is required for overlays and should point at the upstream repository or authoritative source being described.",
            insert_text: "source = ",
        },
        CatalogEntry {
            path: "record.trust.confidence",
            kind: CatalogEntryKind::Field,
            detail: "Confidence hint",
            documentation: "`record.trust.confidence` is a human hint about how strongly to trust the record, but precedence should still come from mode, status, and provenance.",
            insert_text: "confidence = ",
        },
        CatalogEntry {
            path: "record.trust.provenance",
            kind: CatalogEntryKind::Field,
            detail: "Provenance list",
            documentation: "`record.trust.provenance` is an ordered list of provenance terms such as `declared`, `imported`, or `inferred`.",
            insert_text: "provenance = ",
        },
        CatalogEntry {
            path: "record.trust.notes",
            kind: CatalogEntryKind::Field,
            detail: "Trust notes",
            documentation: "`record.trust.notes` explains imports, inferred fallbacks, authority handoff, or other context that should stay visible to humans and agents.",
            insert_text: "notes = ",
        },
        CatalogEntry {
            path: "repo.name",
            kind: CatalogEntryKind::Field,
            detail: "Repository name",
            documentation: "`repo.name` is the canonical repository name used for display and identification.",
            insert_text: "name = ",
        },
        CatalogEntry {
            path: "repo.description",
            kind: CatalogEntryKind::Field,
            detail: "Repository description",
            documentation: "`repo.description` is the short human-readable summary that query and generated surfaces expose.",
            insert_text: "description = ",
        },
        CatalogEntry {
            path: "repo.build",
            kind: CatalogEntryKind::Field,
            detail: "Build command",
            documentation: "`repo.build` stores the maintainer-endorsed build command when the project wants to expose one.",
            insert_text: "build = ",
        },
        CatalogEntry {
            path: "repo.test",
            kind: CatalogEntryKind::Field,
            detail: "Test command",
            documentation: "`repo.test` stores the maintainer-endorsed test command when the project wants to expose one.",
            insert_text: "test = ",
        },
        CatalogEntry {
            path: "owners.maintainers",
            kind: CatalogEntryKind::Field,
            detail: "Maintainer candidates",
            documentation: "`owners.maintainers` is a list of imported or declared maintainer candidates. Imported values are bootstrap metadata, not maintainer-verified truth.",
            insert_text: "maintainers = ",
        },
        CatalogEntry {
            path: "owners.team",
            kind: CatalogEntryKind::Field,
            detail: "Primary team signal",
            documentation: "`owners.team` is the clearest imported or declared team signal when one exists. It should stay unset when ownership is genuinely ambiguous.",
            insert_text: "team = ",
        },
        CatalogEntry {
            path: "owners.security_contact",
            kind: CatalogEntryKind::Field,
            detail: "Security reporting channel",
            documentation: "`owners.security_contact` captures the imported or declared mailbox or policy URL for responsible disclosure.",
            insert_text: "security_contact = ",
        },
        CatalogEntry {
            path: "docs.root",
            kind: CatalogEntryKind::Field,
            detail: "Docs root path",
            documentation: "`docs.root` points at the primary documentation directory or entry file.",
            insert_text: "root = ",
        },
        CatalogEntry {
            path: "docs.getting_started",
            kind: CatalogEntryKind::Field,
            detail: "Getting started path",
            documentation: "`docs.getting_started` points at the primary onboarding or quickstart doc.",
            insert_text: "getting_started = ",
        },
        CatalogEntry {
            path: "readme.title",
            kind: CatalogEntryKind::Field,
            detail: "README title",
            documentation: "`readme.title` overrides the generated README title while keeping `.repo` as the source of truth.",
            insert_text: "title = ",
        },
        CatalogEntry {
            path: "readme.tagline",
            kind: CatalogEntryKind::Field,
            detail: "README tagline",
            documentation: "`readme.tagline` adds a short quote-style tagline near the top of generated README output.",
            insert_text: "tagline = ",
        },
        CatalogEntry {
            path: "readme.sections",
            kind: CatalogEntryKind::Field,
            detail: "README section order",
            documentation: "`readme.sections` orders generated README sections such as `overview`, `docs`, `contributing`, and `security`.",
            insert_text: "sections = ",
        },
        CatalogEntry {
            path: "compat.github.codeowners",
            kind: CatalogEntryKind::Field,
            detail: "CODEOWNERS generation mode",
            documentation: "`compat.github.codeowners` controls whether dotrepo generates or skips the GitHub `CODEOWNERS` surface.",
            insert_text: "codeowners = ",
        },
        CatalogEntry {
            path: "compat.github.security",
            kind: CatalogEntryKind::Field,
            detail: "SECURITY.md generation mode",
            documentation: "`compat.github.security` controls whether dotrepo generates or skips `SECURITY.md`.",
            insert_text: "security = ",
        },
        CatalogEntry {
            path: "compat.github.contributing",
            kind: CatalogEntryKind::Field,
            detail: "CONTRIBUTING.md generation mode",
            documentation: "`compat.github.contributing` controls whether dotrepo generates or skips `CONTRIBUTING.md`.",
            insert_text: "contributing = ",
        },
        CatalogEntry {
            path: "compat.github.pull_request_template",
            kind: CatalogEntryKind::Field,
            detail: "PR template generation mode",
            documentation: "`compat.github.pull_request_template` controls whether dotrepo generates or skips the GitHub pull request template.",
            insert_text: "pull_request_template = ",
        },
        CatalogEntry {
            path: "relations.references",
            kind: CatalogEntryKind::Field,
            detail: "Legacy reference list",
            documentation: "`relations.references` preserves untyped cross-repository references. Prefer trust-bearing `relations.links` for new metadata.",
            insert_text: "references = ",
        },
        CatalogEntry {
            path: "relations.links",
            kind: CatalogEntryKind::Section,
            detail: "Typed relation assertion",
            documentation: "`[[relations.links]]` declares a directed relation with `kind`, `target`, optional `notes`, and required relation-level trust.",
            insert_text: "[[relations.links]]",
        },
        CatalogEntry {
            path: "relations.links.kind",
            kind: CatalogEntryKind::Field,
            detail: "Relation kind",
            documentation: "Recognized kinds are `reference`, `alternative`, `dependency`, `predecessor`, `fork`, and `related`.",
            insert_text: "kind = ",
        },
        CatalogEntry {
            path: "relations.links.target",
            kind: CatalogEntryKind::Field,
            detail: "Repository identity target",
            documentation: "Target as `host/owner/repo` or an HTTP(S) repository URL.",
            insert_text: "target = ",
        },
        CatalogEntry {
            path: "relations.links.trust",
            kind: CatalogEntryKind::Section,
            detail: "Relation-specific trust",
            documentation: "`[relations.links.trust]` records confidence, provenance, and optional notes for this edge independently of record trust.",
            insert_text: "[relations.links.trust]",
        },
        CatalogEntry {
            path: "record.mode",
            kind: CatalogEntryKind::Value,
            detail: "Mode value",
            documentation: "`native` means the manifest is canonical and maintained in the repository itself.",
            insert_text: "\"native\"",
        },
        CatalogEntry {
            path: "record.mode",
            kind: CatalogEntryKind::Value,
            detail: "Mode value",
            documentation: "`overlay` means the manifest is an external or index record, not a maintainer-controlled canonical manifest.",
            insert_text: "\"overlay\"",
        },
        CatalogEntry {
            path: "record.status",
            kind: CatalogEntryKind::Value,
            detail: "Status value",
            documentation: "`draft` is an early or maintainer-local state with minimal implied review.",
            insert_text: "\"draft\"",
        },
        CatalogEntry {
            path: "record.status",
            kind: CatalogEntryKind::Value,
            detail: "Status value",
            documentation: "`imported` means the record was bootstrapped from repository materials without stronger review claims.",
            insert_text: "\"imported\"",
        },
        CatalogEntry {
            path: "record.status",
            kind: CatalogEntryKind::Value,
            detail: "Status value",
            documentation: "`inferred` means fallback values were introduced because imported sources were incomplete.",
            insert_text: "\"inferred\"",
        },
        CatalogEntry {
            path: "record.status",
            kind: CatalogEntryKind::Value,
            detail: "Status value",
            documentation: "`reviewed` means a human review strengthened the record beyond raw import.",
            insert_text: "\"reviewed\"",
        },
        CatalogEntry {
            path: "record.status",
            kind: CatalogEntryKind::Value,
            detail: "Status value",
            documentation: "`verified` means the record carries stronger verification claims than a reviewed overlay.",
            insert_text: "\"verified\"",
        },
        CatalogEntry {
            path: "record.status",
            kind: CatalogEntryKind::Value,
            detail: "Status value",
            documentation: "`canonical` is the strongest status and normally belongs to maintainer-controlled native records.",
            insert_text: "\"canonical\"",
        },
        CatalogEntry {
            path: "record.trust.provenance",
            kind: CatalogEntryKind::Value,
            detail: "Provenance value",
            documentation: "`declared` means the value was written directly into the record by an authoritative source.",
            insert_text: "\"declared\"",
        },
        CatalogEntry {
            path: "record.trust.provenance",
            kind: CatalogEntryKind::Value,
            detail: "Provenance value",
            documentation: "`imported` means the value was imported from conventional repository surfaces such as README, CODEOWNERS, or SECURITY.md.",
            insert_text: "\"imported\"",
        },
        CatalogEntry {
            path: "record.trust.provenance",
            kind: CatalogEntryKind::Value,
            detail: "Provenance value",
            documentation: "`inferred` means the value was filled with a fallback because the imported surfaces did not provide enough structure.",
            insert_text: "\"inferred\"",
        },
        CatalogEntry {
            path: "compat.github.codeowners",
            kind: CatalogEntryKind::Value,
            detail: "Compat mode",
            documentation: "`generate` means dotrepo owns and writes this compatibility surface.",
            insert_text: "\"generate\"",
        },
        CatalogEntry {
            path: "compat.github.codeowners",
            kind: CatalogEntryKind::Value,
            detail: "Compat mode",
            documentation: "`skip` means dotrepo leaves this compatibility surface alone.",
            insert_text: "\"skip\"",
        },
        CatalogEntry {
            path: "compat.github.security",
            kind: CatalogEntryKind::Value,
            detail: "Compat mode",
            documentation: "`generate` means dotrepo owns and writes this compatibility surface.",
            insert_text: "\"generate\"",
        },
        CatalogEntry {
            path: "compat.github.security",
            kind: CatalogEntryKind::Value,
            detail: "Compat mode",
            documentation: "`skip` means dotrepo leaves this compatibility surface alone.",
            insert_text: "\"skip\"",
        },
        CatalogEntry {
            path: "compat.github.contributing",
            kind: CatalogEntryKind::Value,
            detail: "Compat mode",
            documentation: "`generate` means dotrepo owns and writes this compatibility surface.",
            insert_text: "\"generate\"",
        },
        CatalogEntry {
            path: "compat.github.contributing",
            kind: CatalogEntryKind::Value,
            detail: "Compat mode",
            documentation: "`skip` means dotrepo leaves this compatibility surface alone.",
            insert_text: "\"skip\"",
        },
        CatalogEntry {
            path: "compat.github.pull_request_template",
            kind: CatalogEntryKind::Value,
            detail: "Compat mode",
            documentation: "`generate` means dotrepo owns and writes this compatibility surface.",
            insert_text: "\"generate\"",
        },
        CatalogEntry {
            path: "compat.github.pull_request_template",
            kind: CatalogEntryKind::Value,
            detail: "Compat mode",
            documentation: "`skip` means dotrepo leaves this compatibility surface alone.",
            insert_text: "\"skip\"",
        },
    ]
}
