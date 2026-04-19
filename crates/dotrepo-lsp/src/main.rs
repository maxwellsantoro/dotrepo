use anyhow::{anyhow, Context, Result};
use dotrepo_core::{
    validate_manifest_diagnostics, ValidationDiagnostic, ValidationDiagnosticSeverity,
};
use dotrepo_schema::{parse_manifest, ParseError};
use dotrepo_transport::{
    read_jsonrpc_message as read_message, write_jsonrpc_message as write_message,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::fs;
use std::io::{self, BufReader};
use std::path::{Path, PathBuf};
use toml_span::{parse as parse_toml_spanned, Span as TomlSpan, Value as TomlValue};
use url::Url;

const JSONRPC_VERSION: &str = "2.0";
const SERVER_NAME: &str = "dotrepo-lsp";
const TEXT_DOCUMENT_SYNC_FULL: i64 = 1;
const COMPLETION_KIND_FIELD: u8 = 5;
const COMPLETION_KIND_VALUE: u8 = 12;
const COMPLETION_KIND_MODULE: u8 = 9;

fn main() {
    if let Err(err) = run() {
        eprintln!("{err}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut reader = BufReader::new(stdin.lock());
    let mut writer = stdout.lock();
    let mut state = ServerState::default();

    while let Some(message) = read_message(&mut reader)? {
        let outgoing = handle_message(&mut state, &message)?;
        for entry in outgoing {
            write_message(&mut writer, &entry)?;
        }
        if state.exit_requested {
            break;
        }
    }

    Ok(())
}

#[derive(Default)]
struct ServerState {
    initialized: bool,
    shutdown_requested: bool,
    exit_requested: bool,
    documents: BTreeMap<String, OpenDocument>,
}

#[derive(Clone)]
struct OpenDocument {
    uri: String,
    path: PathBuf,
    version: Option<i64>,
    text: String,
}

#[derive(Debug, Deserialize)]
struct JsonRpcMessage {
    jsonrpc: String,
    #[serde(default)]
    id: Option<Value>,
    method: String,
    #[serde(default)]
    params: Value,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct DidOpenTextDocumentParams {
    text_document: VersionedTextDocumentItem,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct VersionedTextDocumentItem {
    uri: String,
    version: i64,
    text: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct DidChangeTextDocumentParams {
    text_document: VersionedTextDocumentIdentifier,
    content_changes: Vec<TextDocumentContentChangeEvent>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct VersionedTextDocumentIdentifier {
    uri: String,
    version: i64,
}

#[derive(Debug, Deserialize)]
struct TextDocumentContentChangeEvent {
    text: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct DidSaveTextDocumentParams {
    text_document: TextDocumentIdentifier,
    #[serde(default)]
    text: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct DidCloseTextDocumentParams {
    text_document: TextDocumentIdentifier,
}

#[derive(Debug, Deserialize)]
struct TextDocumentIdentifier {
    uri: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct TextDocumentPositionParams {
    text_document: TextDocumentIdentifier,
    position: LspPosition,
}

#[derive(Debug, Serialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
struct PublishDiagnosticsParams {
    uri: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    version: Option<i64>,
    diagnostics: Vec<LspDiagnostic>,
}

#[derive(Debug, Serialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
struct LspDiagnostic {
    range: LspRange,
    severity: u8,
    source: String,
    message: String,
}

#[derive(Debug, Serialize, Clone, Copy, PartialEq, Eq)]
struct LspRange {
    start: LspPosition,
    end: LspPosition,
}

#[derive(Debug, Serialize, Deserialize, Clone, Copy, PartialEq, Eq)]
struct LspPosition {
    line: u32,
    character: u32,
}

#[derive(Debug, Serialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
struct CompletionItem {
    label: String,
    kind: u8,
    #[serde(skip_serializing_if = "Option::is_none")]
    detail: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    documentation: Option<MarkupContent>,
    #[serde(skip_serializing_if = "Option::is_none")]
    insert_text: Option<String>,
}

#[derive(Debug, Serialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
struct Hover {
    contents: MarkupContent,
    #[serde(skip_serializing_if = "Option::is_none")]
    range: Option<LspRange>,
}

#[derive(Debug, Serialize, Clone, PartialEq, Eq)]
struct MarkupContent {
    kind: String,
    value: String,
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

#[derive(Default)]
struct DocumentIndex {
    fields: BTreeMap<String, LspRange>,
    values: BTreeMap<String, LspRange>,
    sections: BTreeMap<String, LspRange>,
    lines: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct DiagnosticSnapshot {
    uri: String,
    version: Option<i64>,
    diagnostics: Vec<LspDiagnostic>,
}

fn handle_message(state: &mut ServerState, payload: &[u8]) -> Result<Vec<Value>> {
    let message =
        serde_json::from_slice::<JsonRpcMessage>(payload).context("failed to parse LSP message")?;
    if message.jsonrpc != JSONRPC_VERSION {
        return Ok(message
            .id
            .map(|id| {
                vec![error_response(
                    id,
                    -32600,
                    format!("unsupported jsonrpc version: {}", message.jsonrpc),
                )]
            })
            .unwrap_or_default());
    }

    match message.id {
        Some(id) => handle_request(state, id, &message.method, message.params),
        None => handle_notification(state, &message.method, message.params),
    }
}

fn handle_request(
    state: &mut ServerState,
    id: Value,
    method: &str,
    _params: Value,
) -> Result<Vec<Value>> {
    let response = match method {
        "initialize" => {
            state.initialized = true;
            response(
                id,
                json!({
                    "capabilities": {
                        "textDocumentSync": {
                            "openClose": true,
                            "change": TEXT_DOCUMENT_SYNC_FULL,
                            "save": { "includeText": true }
                        },
                        "completionProvider": {},
                        "hoverProvider": true
                    },
                    "serverInfo": {
                        "name": SERVER_NAME,
                        "version": env!("CARGO_PKG_VERSION")
                    }
                }),
            )
        }
        "shutdown" => {
            state.shutdown_requested = true;
            response(id, Value::Null)
        }
        "textDocument/completion" => {
            let params: TextDocumentPositionParams = serde_json::from_value(_params)?;
            response(id, serde_json::to_value(completion_items(state, &params)?)?)
        }
        "textDocument/hover" => {
            let params: TextDocumentPositionParams = serde_json::from_value(_params)?;
            response(
                id,
                serde_json::to_value(hover_response(state, &params)?).unwrap_or(Value::Null),
            )
        }
        _ => error_response(id, -32601, format!("method not found: {}", method)),
    };

    Ok(vec![response])
}

fn handle_notification(state: &mut ServerState, method: &str, params: Value) -> Result<Vec<Value>> {
    match method {
        "initialized" => Ok(Vec::new()),
        "exit" => {
            state.exit_requested = true;
            Ok(Vec::new())
        }
        "textDocument/didOpen" => {
            let params: DidOpenTextDocumentParams = serde_json::from_value(params)?;
            let path = manifest_path_from_uri(&params.text_document.uri)?;
            if !is_supported_manifest_path(&path) {
                return Ok(Vec::new());
            }
            let document = OpenDocument {
                uri: params.text_document.uri.clone(),
                path,
                version: Some(params.text_document.version),
                text: params.text_document.text,
            };
            let publish = publish_for_document(&document);
            state
                .documents
                .insert(params.text_document.uri.clone(), document);
            Ok(vec![publish_diagnostics_notification(&publish)])
        }
        "textDocument/didChange" => {
            let params: DidChangeTextDocumentParams = serde_json::from_value(params)?;
            let Some(document) = state.documents.get_mut(&params.text_document.uri) else {
                return Ok(Vec::new());
            };
            let Some(change) = params.content_changes.last() else {
                return Ok(Vec::new());
            };
            document.text = change.text.clone();
            document.version = Some(params.text_document.version);
            let publish = publish_for_document(document);
            Ok(vec![publish_diagnostics_notification(&publish)])
        }
        "textDocument/didSave" => {
            let params: DidSaveTextDocumentParams = serde_json::from_value(params)?;
            let document =
                if let Some(document) = state.documents.get_mut(&params.text_document.uri) {
                    if let Some(text) = params.text {
                        document.text = text;
                    } else if let Ok(path) = manifest_path_from_uri(&params.text_document.uri) {
                        if path.exists() {
                            document.text = fs::read_to_string(&path)?;
                        }
                    }
                    document.clone()
                } else {
                    let path = manifest_path_from_uri(&params.text_document.uri)?;
                    if !is_supported_manifest_path(&path) {
                        return Ok(Vec::new());
                    }
                    OpenDocument {
                        uri: params.text_document.uri,
                        path: path.clone(),
                        version: None,
                        text: if let Some(text) = params.text {
                            text
                        } else {
                            fs::read_to_string(path)?
                        },
                    }
                };
            let publish = publish_for_document(&document);
            state.documents.insert(document.uri.clone(), document);
            Ok(vec![publish_diagnostics_notification(&publish)])
        }
        "textDocument/didClose" => {
            let params: DidCloseTextDocumentParams = serde_json::from_value(params)?;
            state.documents.remove(&params.text_document.uri);
            Ok(vec![publish_diagnostics_notification(
                &DiagnosticSnapshot {
                    uri: params.text_document.uri,
                    version: None,
                    diagnostics: Vec::new(),
                },
            )])
        }
        _ => Ok(Vec::new()),
    }
}

fn publish_for_document(document: &OpenDocument) -> DiagnosticSnapshot {
    DiagnosticSnapshot {
        uri: document.uri.clone(),
        version: document.version,
        diagnostics: diagnostics_for_document(&document.path, &document.text),
    }
}

fn completion_items(
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

fn hover_response(
    state: &ServerState,
    params: &TextDocumentPositionParams,
) -> Result<Option<Hover>> {
    let document = document_for_request(state, &params.text_document.uri)?;
    let index = DocumentIndex::from_text(&document.text);
    let Some(path) = index.path_at(params.position) else {
        return Ok(None);
    };
    let Some(entry) = schema_catalog().iter().find(|entry| entry.path == path) else {
        return Ok(None);
    };

    Ok(Some(Hover {
        contents: markup_content(entry.documentation),
        range: index.range_for_path(path),
    }))
}

fn diagnostics_for_document(path: &Path, text: &str) -> Vec<LspDiagnostic> {
    let index = DocumentIndex::from_text(text);
    let root = path.parent().unwrap_or_else(|| Path::new("."));

    match parse_manifest(text) {
        Ok(manifest) => validate_manifest_diagnostics(root, &manifest)
            .into_iter()
            .map(|diagnostic| map_validation_diagnostic(&index, root, &diagnostic))
            .collect(),
        Err(ParseError::Toml(err)) => vec![LspDiagnostic {
            range: err
                .span()
                .map(|span| byte_span_to_range(text, span.start, span.end))
                .unwrap_or_else(|| index.default_range()),
            severity: 1,
            source: "parse_manifest".into(),
            message: ParseError::Toml(err).to_string(),
        }],
        Err(ParseError::ConflictingTrustPlacement) => vec![LspDiagnostic {
            range: index
                .section_range("trust")
                .or_else(|| index.section_range("record.trust"))
                .or_else(|| index.section_range("record"))
                .unwrap_or_else(|| index.default_range()),
            severity: 1,
            source: "parse_manifest".into(),
            message: ParseError::ConflictingTrustPlacement.to_string(),
        }],
    }
}

fn map_validation_diagnostic(
    index: &DocumentIndex,
    root: &Path,
    diagnostic: &ValidationDiagnostic,
) -> LspDiagnostic {
    let range = if diagnostic.message.starts_with("unsupported schema:") {
        index.field_range("schema")
    } else if diagnostic.message == "repo.name must not be empty" {
        index.field_range("repo.name")
    } else if diagnostic
        .message
        .contains("record.source must be set for overlay records")
    {
        index
            .field_range("record.source")
            .or_else(|| index.section_range("record"))
    } else if diagnostic
        .message
        .contains("record.trust.provenance must list at least one provenance entry")
    {
        index
            .field_range("record.trust.provenance")
            .or_else(|| index.section_range("record.trust"))
    } else if diagnostic
        .message
        .contains("record.trust must be set for overlay records")
    {
        index
            .section_range("record.trust")
            .or_else(|| index.section_range("trust"))
            .or_else(|| index.section_range("record"))
    } else if let Some(section_name) = missing_custom_section_name(&diagnostic.message) {
        index
            .section_range(&format!("readme.custom_sections.{section_name}"))
            .or_else(|| index.field_range("readme.custom_sections.path"))
    } else if let Some(target) = missing_path_target(&diagnostic.message) {
        range_for_missing_path(index, root, &target)
    } else {
        None
    }
    .unwrap_or_else(|| index.default_range());

    LspDiagnostic {
        range,
        severity: severity_code(diagnostic.severity),
        source: diagnostic.source.into(),
        message: diagnostic.message.clone(),
    }
}

fn severity_code(severity: ValidationDiagnosticSeverity) -> u8 {
    match severity {
        ValidationDiagnosticSeverity::Error => 1,
    }
}

fn missing_custom_section_name(message: &str) -> Option<String> {
    let prefix = "custom README section `";
    let remainder = message.strip_prefix(prefix)?;
    let end = remainder.find('`')?;
    Some(remainder[..end].to_string())
}

fn missing_path_target(message: &str) -> Option<PathBuf> {
    let path = message.split(": ").last()?;
    Some(PathBuf::from(path))
}

fn range_for_missing_path(index: &DocumentIndex, root: &Path, target: &Path) -> Option<LspRange> {
    let relative = target.strip_prefix(root).ok();
    let mut candidates = Vec::new();
    if let Some(relative) = relative {
        let rel = relative.display().to_string();
        if !rel.is_empty() {
            candidates.push(rel.clone());
            if !rel.starts_with("./") {
                candidates.push(format!("./{rel}"));
            }
        }
    }
    candidates.push(target.display().to_string());

    index.find_line_containing_any(&candidates)
}

impl DocumentIndex {
    fn from_text(text: &str) -> Self {
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

    fn field_range(&self, path: &str) -> Option<LspRange> {
        self.fields.get(path).copied()
    }

    fn value_range(&self, path: &str) -> Option<LspRange> {
        self.values.get(path).copied()
    }

    fn section_range(&self, path: &str) -> Option<LspRange> {
        self.sections.get(path).copied()
    }

    fn find_line_containing_any(&self, candidates: &[String]) -> Option<LspRange> {
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

    fn default_range(&self) -> LspRange {
        let first_line = self.lines.first().map(String::as_str).unwrap_or("");
        whole_line_range(0, first_line)
    }

    fn line(&self, line: u32) -> &str {
        self.lines
            .get(line as usize)
            .map(String::as_str)
            .unwrap_or("")
    }

    fn range_for_path(&self, path: &str) -> Option<LspRange> {
        self.field_range(path)
            .or_else(|| self.section_range(path))
            .or_else(|| self.value_range(path))
    }

    fn path_at(&self, position: LspPosition) -> Option<&str> {
        narrowest_path_match(&self.fields, position)
            .or_else(|| narrowest_path_match(&self.values, position))
            .or_else(|| narrowest_path_match(&self.sections, position))
    }

    fn section_path_at(&self, position: LspPosition) -> Option<&str> {
        narrowest_path_match(&self.sections, position)
    }

    fn field_path_at(&self, position: LspPosition) -> Option<&str> {
        narrowest_path_match(&self.fields, position)
    }

    fn value_path_at(&self, position: LspPosition) -> Option<&str> {
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

fn narrowest_path_match(
    paths: &BTreeMap<String, LspRange>,
    position: LspPosition,
) -> Option<&str> {
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

fn whole_line_range(line: u32, contents: &str) -> LspRange {
    LspRange {
        start: LspPosition { line, character: 0 },
        end: LspPosition {
            line,
            character: utf16_len(contents),
        },
    }
}

fn position_in_range(position: LspPosition, range: LspRange) -> bool {
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

fn byte_span_to_range(text: &str, start: usize, end: usize) -> LspRange {
    LspRange {
        start: byte_offset_to_position(text, start),
        end: byte_offset_to_position(text, end.max(start)),
    }
}

fn byte_offset_to_position(text: &str, offset: usize) -> LspPosition {
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

fn utf16_len(text: &str) -> u32 {
    text.chars().map(char::len_utf16).sum::<usize>() as u32
}

fn manifest_path_from_uri(uri: &str) -> Result<PathBuf> {
    let url = Url::parse(uri).with_context(|| format!("invalid uri: {uri}"))?;
    url.to_file_path()
        .map_err(|_| anyhow!("uri is not a file path: {uri}"))
}

fn is_supported_manifest_path(path: &Path) -> bool {
    matches!(
        path.file_name().and_then(|name| name.to_str()),
        Some(".repo") | Some("record.toml")
    )
}

fn document_for_request<'a>(state: &'a ServerState, uri: &str) -> Result<&'a OpenDocument> {
    state
        .documents
        .get(uri)
        .ok_or_else(|| anyhow!("document not open: {uri}"))
}

#[derive(Debug, Clone)]
enum CompletionContext {
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
            detail: "Reserved relation metadata",
            documentation: "### `[relations]`\nReserved relationship surface for future workspace and bundle support.",
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
            detail: "Reference list",
            documentation: "`relations.references` is the reserved relation surface for future cross-repository references.",
            insert_text: "references = ",
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

fn publish_diagnostics_notification(snapshot: &DiagnosticSnapshot) -> Value {
    json!({
        "jsonrpc": JSONRPC_VERSION,
        "method": "textDocument/publishDiagnostics",
        "params": PublishDiagnosticsParams {
            uri: snapshot.uri.clone(),
            version: snapshot.version,
            diagnostics: snapshot.diagnostics.clone(),
        }
    })
}

fn response(id: Value, result: Value) -> Value {
    json!({
        "jsonrpc": JSONRPC_VERSION,
        "id": id,
        "result": result
    })
}

fn error_response(id: Value, code: i64, message: String) -> Value {
    json!({
        "jsonrpc": JSONRPC_VERSION,
        "id": id,
        "error": {
            "code": code,
            "message": message,
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn diagnostics_for_invalid_overlay_manifest_reuse_core_messages() {
        let root = temp_dir("lsp-overlay");
        let path = root.join("record.toml");
        let diagnostics = diagnostics_for_document(
            &path,
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
        );

        let messages = diagnostics
            .iter()
            .map(|diagnostic| diagnostic.message.as_str())
            .collect::<Vec<_>>();
        assert!(messages
            .iter()
            .any(|message| message.contains("record.source must be set for overlay records")));
        assert!(messages
            .iter()
            .any(|message| message.contains("record.trust must be set for overlay records")));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn diagnostics_for_parse_errors_use_toml_spans() {
        let root = temp_dir("lsp-parse");
        let path = root.join(".repo");
        let diagnostics = diagnostics_for_document(
            &path,
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native
status = "draft"
"#,
        );

        assert_eq!(diagnostics.len(), 1);
        assert_eq!(diagnostics[0].source, "parse_manifest");
        assert!(diagnostics[0].message.contains("failed to parse manifest"));
        assert!(diagnostics[0].range.start.line > 0);

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn did_open_publishes_diagnostics() {
        let root = temp_dir("lsp-open");
        let path = root.join(".repo");
        let uri = Url::from_file_path(&path)
            .expect("file path uri")
            .to_string();
        let message = json!({
            "jsonrpc": JSONRPC_VERSION,
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": uri,
                    "languageId": "toml",
                    "version": 1,
                    "text": r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#
                }
            }
        });

        let mut state = ServerState::default();
        let outputs = handle_message(&mut state, &serde_json::to_vec(&message).expect("message"))
            .expect("message handled");

        assert_eq!(outputs.len(), 1);
        assert_eq!(outputs[0]["method"], "textDocument/publishDiagnostics");
        assert!(outputs[0]["params"]["diagnostics"]
            .as_array()
            .expect("diagnostics array")
            .iter()
            .any(|diagnostic| diagnostic["message"]
                == Value::String("record.source must be set for overlay records".into())));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn completion_returns_core_fields_and_enum_values() {
        let root = temp_dir("lsp-completion");
        let path = root.join(".repo");
        let uri = Url::from_file_path(&path)
            .expect("file path uri")
            .to_string();
        let mut state = ServerState::default();
        open_document(
            &mut state,
            &uri,
            r#"
schema = "dotrepo/v0.1"

[record]
mode = 

[repo]

"#,
        );

        let field_items = completion_items(
            &state,
            &TextDocumentPositionParams {
                text_document: TextDocumentIdentifier { uri: uri.clone() },
                position: LspPosition {
                    line: 6,
                    character: 0,
                },
            },
        )
        .expect("completion succeeds");
        let field_labels = field_items
            .iter()
            .map(|item| item.label.as_str())
            .collect::<Vec<_>>();
        assert!(field_labels.contains(&"name = "));
        assert!(field_labels.contains(&"description = "));

        let value_items = completion_items(
            &state,
            &TextDocumentPositionParams {
                text_document: TextDocumentIdentifier { uri },
                position: LspPosition {
                    line: 4,
                    character: 7,
                },
            },
        )
        .expect("completion succeeds");
        let value_labels = value_items
            .iter()
            .map(|item| item.label.as_str())
            .collect::<Vec<_>>();
        assert!(value_labels.contains(&"\"native\""));
        assert!(value_labels.contains(&"\"overlay\""));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn hover_returns_schema_help_for_core_fields() {
        let root = temp_dir("lsp-hover");
        let path = root.join(".repo");
        let uri = Url::from_file_path(&path)
            .expect("file path uri")
            .to_string();
        let mut state = ServerState::default();
        open_document(
            &mut state,
            &uri,
            r#"
schema = "dotrepo/v0.1"

[record]
status = "draft"
"#,
        );

        let hover = hover_response(
            &state,
            &TextDocumentPositionParams {
                text_document: TextDocumentIdentifier { uri },
                position: LspPosition {
                    line: 4,
                    character: 2,
                },
            },
        )
        .expect("hover succeeds")
        .expect("hover present");

        assert!(hover.contents.value.contains("`record.status`"));
        assert!(hover.contents.value.contains("authority and review level"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn hover_resolves_nested_inline_table_fields() {
        let root = temp_dir("lsp-inline-hover");
        let path = root.join(".repo");
        let uri = Url::from_file_path(&path)
            .expect("file path uri")
            .to_string();
        let mut state = ServerState::default();
        open_document(
            &mut state,
            &uri,
            r#"
schema = "dotrepo/v0.1"

owners = { security_contact = "security@example.com" }
"#,
        );

        let hover = hover_response(
            &state,
            &TextDocumentPositionParams {
                text_document: TextDocumentIdentifier { uri },
                position: LspPosition {
                    line: 3,
                    character: 14,
                },
            },
        )
        .expect("hover succeeds")
        .expect("hover present");

        assert!(hover.contents.value.contains("`owners.security_contact`"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn hover_ignores_fake_toml_structure_inside_multiline_strings() {
        let root = temp_dir("lsp-multiline-hover");
        let path = root.join(".repo");
        let uri = Url::from_file_path(&path)
            .expect("file path uri")
            .to_string();
        let mut state = ServerState::default();
        open_document(
            &mut state,
            &uri,
            r#"
schema = "dotrepo/v0.1"

[repo]
description = """
[record]
status = "draft"
"""
"#,
        );

        let hover = hover_response(
            &state,
            &TextDocumentPositionParams {
                text_document: TextDocumentIdentifier { uri },
                position: LspPosition {
                    line: 5,
                    character: 2,
                },
            },
        )
        .expect("hover succeeds")
        .expect("hover present");

        assert!(hover.contents.value.contains("`repo.description`"));
        assert!(!hover.contents.value.contains("### `[record]`"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    fn open_document(state: &mut ServerState, uri: &str, text: &str) {
        let message = json!({
            "jsonrpc": JSONRPC_VERSION,
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": uri,
                    "languageId": "toml",
                    "version": 1,
                    "text": text,
                }
            }
        });
        handle_message(state, &serde_json::to_vec(&message).expect("message"))
            .expect("open handled");
    }

    fn temp_dir(label: &str) -> PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock works")
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "dotrepo-lsp-{}-{}-{}",
            label,
            std::process::id(),
            unique
        ));
        fs::create_dir_all(&path).expect("temp dir created");
        path
    }
}
