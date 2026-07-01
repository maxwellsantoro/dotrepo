//! Server state, open-document tracking, and manifest text indexing.
//!
//! `ServerState` and `OpenDocument` hold the mutable state the dispatch loop
//! threads through request/notification handling. `DocumentIndex` builds a
//! byte/UTF-16 aware map from dotted TOML paths to source ranges, which
//! diagnostics, completions, hover, and code actions all query.

use crate::protocol::{LspPosition, LspRange};
use anyhow::{anyhow, bail, Context, Result};
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use toml_span::{parse as parse_toml_spanned, Span as TomlSpan, Value as TomlValue};
use url::Url;

#[derive(Default)]
pub(crate) struct ServerState {
    pub(crate) initialized: bool,
    pub(crate) shutdown_requested: bool,
    pub(crate) exit_requested: bool,
    pub(crate) workspace_roots: Vec<PathBuf>,
    pub(crate) documents: BTreeMap<String, OpenDocument>,
}

#[derive(Clone)]
pub(crate) struct OpenDocument {
    pub(crate) uri: String,
    pub(crate) path: PathBuf,
    pub(crate) version: Option<i64>,
    pub(crate) text: String,
}

#[derive(Default)]
pub(crate) struct DocumentIndex {
    pub(crate) fields: BTreeMap<String, LspRange>,
    pub(crate) values: BTreeMap<String, LspRange>,
    pub(crate) sections: BTreeMap<String, LspRange>,
    pub(crate) lines: Vec<String>,
}

impl DocumentIndex {
    pub(crate) fn from_text(text: &str) -> Self {
        let mut index = Self {
            fields: BTreeMap::new(),
            values: BTreeMap::new(),
            sections: BTreeMap::new(),
            lines: text.lines().map(str::to_string).collect::<Vec<_>>(),
        };

        match parse_toml_spanned(text) {
            Ok(parsed) => index.populate_from_spanned(text, None, &parsed),
            Err(_) => index.populate_from_line_scan(),
        }

        index
    }

    pub(crate) fn field_range(&self, path: &str) -> Option<LspRange> {
        self.fields.get(path).copied()
    }

    pub(crate) fn value_range(&self, path: &str) -> Option<LspRange> {
        self.values.get(path).copied()
    }

    pub(crate) fn section_range(&self, path: &str) -> Option<LspRange> {
        self.sections.get(path).copied()
    }

    pub(crate) fn find_line_containing_any(&self, candidates: &[String]) -> Option<LspRange> {
        self.lines
            .iter()
            .enumerate()
            .find(|(_, line)| {
                candidates
                    .iter()
                    .any(|candidate| !candidate.is_empty() && line.contains(candidate))
            })
            .map(|(line_idx, line)| whole_line_range(line_idx as u32, line))
    }

    pub(crate) fn default_range(&self) -> LspRange {
        let first_line = self.lines.first().map(String::as_str).unwrap_or("");
        whole_line_range(0, first_line)
    }

    pub(crate) fn line(&self, line: u32) -> &str {
        self.lines
            .get(line as usize)
            .map(String::as_str)
            .unwrap_or("")
    }

    pub(crate) fn range_for_path(&self, path: &str) -> Option<LspRange> {
        self.field_range(path)
            .or_else(|| self.section_range(path))
            .or_else(|| self.value_range(path))
    }

    pub(crate) fn path_at(&self, position: LspPosition) -> Option<&str> {
        narrowest_path_match(&self.fields, position)
            .or_else(|| narrowest_path_match(&self.values, position))
            .or_else(|| narrowest_path_match(&self.sections, position))
    }

    pub(crate) fn section_path_at(&self, position: LspPosition) -> Option<&str> {
        narrowest_path_match(&self.sections, position)
    }

    pub(crate) fn field_path_at(&self, position: LspPosition) -> Option<&str> {
        narrowest_path_match(&self.fields, position)
    }

    pub(crate) fn value_path_at(&self, position: LspPosition) -> Option<&str> {
        narrowest_path_match(&self.values, position)
    }

    fn populate_from_spanned<'a>(
        &mut self,
        text: &str,
        prefix: Option<&str>,
        value: &TomlValue<'a>,
    ) {
        let Some(table) = value.as_table() else {
            return;
        };

        for (key, child) in table {
            let path = prefix
                .map(|prefix| format!("{prefix}.{}", key.name))
                .unwrap_or_else(|| key.name.to_string());

            self.fields
                .entry(path.clone())
                .or_insert_with(|| byte_span_to_range(text, key.span.start, key.span.end));
            self.values
                .entry(path.clone())
                .or_insert_with(|| byte_span_to_range(text, child.span.start, child.span.end));

            if child.as_table().is_some() {
                if let Some(range) = section_header_range(text, key.span, child.span) {
                    self.sections.entry(path.clone()).or_insert(range);
                }
                self.populate_from_spanned(text, Some(&path), child);
            }
        }
    }

    fn populate_from_line_scan(&mut self) {
        let mut current_section: Option<String> = None;

        for (line_idx, line) in self.lines.iter().enumerate() {
            let trimmed = line.trim();
            if trimmed.starts_with('[') && trimmed.ends_with(']') && !trimmed.starts_with("[[") {
                let section = trimmed.trim_matches(|ch| ch == '[' || ch == ']').trim();
                if !section.is_empty() {
                    current_section = Some(section.to_string());
                    self.sections
                        .insert(section.to_string(), whole_line_range(line_idx as u32, line));
                }
                continue;
            }

            let Some(eq_idx) = line.find('=') else {
                continue;
            };
            let key = line[..eq_idx].trim();
            if key.is_empty() || key.contains(' ') {
                continue;
            }
            let full_path = match &current_section {
                Some(section) => format!("{section}.{key}"),
                None => key.to_string(),
            };
            let key_col = line.find(key).unwrap_or(0);
            let value_start = eq_idx.saturating_add(1);
            self.fields.insert(
                full_path.clone(),
                LspRange {
                    start: LspPosition {
                        line: line_idx as u32,
                        character: utf16_len(&line[..key_col]),
                    },
                    end: LspPosition {
                        line: line_idx as u32,
                        character: utf16_len(&line[..key_col + key.len()]),
                    },
                },
            );
            self.values.insert(
                full_path,
                LspRange {
                    start: LspPosition {
                        line: line_idx as u32,
                        character: utf16_len(&line[..value_start]),
                    },
                    end: LspPosition {
                        line: line_idx as u32,
                        character: utf16_len(line),
                    },
                },
            );
        }
    }
}

fn section_header_range(text: &str, key_span: TomlSpan, value_span: TomlSpan) -> Option<LspRange> {
    if value_span.start > key_span.start {
        return None;
    }

    let line_start = text[..key_span.start]
        .rfind('\n')
        .map(|idx| idx + 1)
        .unwrap_or(0);
    let line_end = text[key_span.end..]
        .find('\n')
        .map(|idx| key_span.end + idx)
        .unwrap_or(text.len());
    let line = &text[line_start..line_end];
    let trimmed = line.trim();
    if trimmed.starts_with('[') && trimmed.ends_with(']') {
        Some(byte_span_to_range(text, line_start, line_end))
    } else {
        None
    }
}

fn narrowest_path_match(paths: &BTreeMap<String, LspRange>, position: LspPosition) -> Option<&str> {
    paths
        .iter()
        .filter(|(_, range)| position_in_range(position, **range))
        .min_by_key(|(_, range)| range_weight(**range))
        .map(|(path, _)| path.as_str())
}

fn range_weight(range: LspRange) -> (u32, u32) {
    (
        range.end.line.saturating_sub(range.start.line),
        range.end.character.saturating_sub(range.start.character),
    )
}

pub(crate) fn position_in_range(position: LspPosition, range: LspRange) -> bool {
    if position.line < range.start.line || position.line > range.end.line {
        return false;
    }

    if position.line == range.start.line && position.character < range.start.character {
        return false;
    }
    if position.line == range.end.line && position.character > range.end.character {
        return false;
    }

    true
}

pub(crate) fn whole_line_range(line: u32, contents: &str) -> LspRange {
    LspRange {
        start: LspPosition { line, character: 0 },
        end: LspPosition {
            line,
            character: utf16_len(contents),
        },
    }
}

pub(crate) fn byte_span_to_range(text: &str, start: usize, end: usize) -> LspRange {
    LspRange {
        start: byte_offset_to_position(text, start),
        end: byte_offset_to_position(text, end.max(start)),
    }
}

pub(crate) fn byte_offset_to_position(text: &str, offset: usize) -> LspPosition {
    let mut line = 0u32;
    let mut line_start = 0usize;
    let clamped = offset.min(text.len());

    for (byte_idx, ch) in text.char_indices() {
        if byte_idx >= clamped {
            break;
        }
        if ch == '\n' {
            line += 1;
            line_start = byte_idx + ch.len_utf8();
        }
    }

    let character = text[line_start..clamped]
        .chars()
        .map(char::len_utf16)
        .sum::<usize>() as u32;

    LspPosition { line, character }
}

pub(crate) fn utf16_len(text: &str) -> u32 {
    text.chars().map(char::len_utf16).sum::<usize>() as u32
}

pub(crate) fn manifest_path_from_uri(uri: &str) -> Result<PathBuf> {
    let url = Url::parse(uri).with_context(|| format!("invalid uri: {uri}"))?;
    url.to_file_path()
        .map_err(|_| anyhow!("uri is not a file path: {uri}"))
}

pub(crate) fn workspace_uri_to_path(uri: &str) -> Result<PathBuf> {
    let url = Url::parse(uri).with_context(|| format!("invalid workspace uri: {uri}"))?;
    url.to_file_path()
        .map_err(|_| anyhow!("workspace uri is not a file path: {uri}"))
}

pub(crate) fn workspace_roots_from_initialize(params: &serde_json::Value) -> Result<Vec<PathBuf>> {
    let mut roots = Vec::new();

    if let Some(folders) = params
        .get("workspaceFolders")
        .and_then(serde_json::Value::as_array)
    {
        for folder in folders {
            if let Some(uri) = folder.get("uri").and_then(serde_json::Value::as_str) {
                roots.push(workspace_uri_to_path(uri)?);
            }
        }
    }

    if roots.is_empty() {
        if let Some(uri) = params.get("rootUri").and_then(serde_json::Value::as_str) {
            roots.push(workspace_uri_to_path(uri)?);
        } else if let Some(path) = params.get("rootPath").and_then(serde_json::Value::as_str) {
            roots.push(PathBuf::from(path));
        }
    }

    Ok(roots)
}

pub(crate) fn ensure_manifest_in_workspace(
    path: &Path,
    workspace_roots: &[PathBuf],
    initialized: bool,
) -> Result<()> {
    let canonical_path = canonical_manifest_path(path)?;
    if workspace_roots.is_empty() {
        if !initialized {
            return Ok(());
        }
        let cwd = std::env::current_dir()
            .map_err(|err| anyhow!("failed to resolve process working directory: {}", err))?;
        let canonical_cwd = fs::canonicalize(&cwd).unwrap_or(cwd);
        if canonical_path.starts_with(&canonical_cwd) {
            return Ok(());
        }
        bail!("manifest path is outside the process working directory");
    }

    for root in workspace_roots {
        let canonical_root = fs::canonicalize(root).unwrap_or_else(|_| root.clone());
        if canonical_path.starts_with(&canonical_root) {
            return Ok(());
        }
    }

    bail!("manifest path is outside workspace folders");
}

pub(crate) fn is_supported_manifest_path(path: &Path) -> bool {
    matches!(
        path.file_name().and_then(|name| name.to_str()),
        Some(".repo") | Some("record.toml")
    )
}

pub(crate) fn document_for_request<'a>(
    state: &'a ServerState,
    uri: &str,
) -> Result<&'a OpenDocument> {
    state
        .documents
        .get(uri)
        .ok_or_else(|| anyhow!("document not open: {uri}"))
}

pub(crate) fn canonical_manifest_path(path: &Path) -> Result<PathBuf> {
    if path.exists() {
        return fs::canonicalize(path).map_err(Into::into);
    }
    if let Some(parent) = path.parent() {
        if parent.as_os_str().is_empty() || !parent.exists() {
            return Ok(path.to_path_buf());
        }
        let canonical_parent = fs::canonicalize(parent)?;
        return Ok(canonical_parent.join(
            path.file_name()
                .ok_or_else(|| anyhow!("manifest path has no file name"))?,
        ));
    }
    Ok(path.to_path_buf())
}

pub(crate) fn validation_root_for_manifest(path: &Path, workspace_roots: &[PathBuf]) -> PathBuf {
    if workspace_roots.is_empty() {
        return path
            .parent()
            .unwrap_or_else(|| Path::new("."))
            .to_path_buf();
    }

    if let Ok(canonical_path) = canonical_manifest_path(path) {
        for root in workspace_roots {
            let canonical_root = fs::canonicalize(root).unwrap_or_else(|_| root.clone());
            if canonical_path.starts_with(&canonical_root) {
                return root.clone();
            }
        }
    }

    path.parent()
        .unwrap_or_else(|| Path::new("."))
        .to_path_buf()
}
