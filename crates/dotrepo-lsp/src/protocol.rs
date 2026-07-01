//! JSON-RPC and LSP wire-format message and type definitions.
//!
//! This module only defines the (de)serializable shapes exchanged over
//! stdio. It intentionally has no behavior of its own; dispatch, diagnostics,
//! completion, and code-action logic live in their respective sibling
//! modules.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;

#[derive(Debug, Deserialize)]
pub(crate) struct JsonRpcMessage {
    pub(crate) jsonrpc: String,
    #[serde(default)]
    pub(crate) id: Option<Value>,
    pub(crate) method: String,
    #[serde(default)]
    pub(crate) params: Value,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct DidOpenTextDocumentParams {
    pub(crate) text_document: VersionedTextDocumentItem,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct VersionedTextDocumentItem {
    pub(crate) uri: String,
    pub(crate) version: i64,
    pub(crate) text: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct DidChangeTextDocumentParams {
    pub(crate) text_document: VersionedTextDocumentIdentifier,
    pub(crate) content_changes: Vec<TextDocumentContentChangeEvent>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct VersionedTextDocumentIdentifier {
    pub(crate) uri: String,
    pub(crate) version: i64,
}

#[derive(Debug, Deserialize)]
pub(crate) struct TextDocumentContentChangeEvent {
    pub(crate) text: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct DidSaveTextDocumentParams {
    pub(crate) text_document: TextDocumentIdentifier,
    #[serde(default)]
    pub(crate) text: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct DidCloseTextDocumentParams {
    pub(crate) text_document: TextDocumentIdentifier,
}

#[derive(Debug, Deserialize)]
pub(crate) struct TextDocumentIdentifier {
    pub(crate) uri: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct TextDocumentPositionParams {
    pub(crate) text_document: TextDocumentIdentifier,
    pub(crate) position: LspPosition,
}

#[derive(Debug, Serialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub(crate) struct PublishDiagnosticsParams {
    pub(crate) uri: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) version: Option<i64>,
    pub(crate) diagnostics: Vec<LspDiagnostic>,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub(crate) struct LspDiagnostic {
    pub(crate) range: LspRange,
    pub(crate) severity: u8,
    pub(crate) source: String,
    pub(crate) message: String,
}

#[derive(Debug, Serialize, Deserialize, Clone, Copy, PartialEq, Eq)]
pub(crate) struct LspRange {
    pub(crate) start: LspPosition,
    pub(crate) end: LspPosition,
}

#[derive(Debug, Serialize, Deserialize, Clone, Copy, PartialEq, Eq)]
pub(crate) struct LspPosition {
    pub(crate) line: u32,
    pub(crate) character: u32,
}

#[derive(Debug, Serialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub(crate) struct CompletionItem {
    pub(crate) label: String,
    pub(crate) kind: u8,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) detail: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) documentation: Option<MarkupContent>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) insert_text: Option<String>,
}

#[derive(Debug, Serialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub(crate) struct Hover {
    pub(crate) contents: MarkupContent,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) range: Option<LspRange>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct CodeActionParams {
    pub(crate) text_document: TextDocumentIdentifier,
    pub(crate) range: LspRange,
    pub(crate) context: CodeActionContext,
}

#[derive(Debug, Deserialize)]
pub(crate) struct CodeActionContext {
    #[serde(default)]
    pub(crate) diagnostics: Vec<LspDiagnostic>,
}

#[derive(Debug, Serialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub(crate) struct CodeAction {
    pub(crate) title: String,
    pub(crate) kind: String,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub(crate) diagnostics: Vec<LspDiagnostic>,
    pub(crate) edit: WorkspaceEdit,
}

#[derive(Debug, Serialize, Clone, PartialEq, Eq)]
pub(crate) struct WorkspaceEdit {
    #[serde(skip_serializing_if = "BTreeMap::is_empty", default)]
    pub(crate) changes: BTreeMap<String, Vec<TextEdit>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) document_changes: Option<Vec<DocumentChange>>,
}

#[derive(Debug, Serialize, Clone, PartialEq, Eq)]
#[serde(untagged)]
pub(crate) enum DocumentChange {
    Create(CreateFileChange),
    Edit(TextDocumentEdit),
}

#[derive(Debug, Serialize, Clone, PartialEq, Eq)]
pub(crate) struct CreateFileChange {
    #[serde(rename = "createFile")]
    pub(crate) create_file: CreateFileOptions,
}

#[derive(Debug, Serialize, Clone, PartialEq, Eq)]
pub(crate) struct CreateFileOptions {
    pub(crate) uri: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) options: Option<CreateFileOpts>,
}

#[derive(Debug, Serialize, Clone, PartialEq, Eq)]
pub(crate) struct CreateFileOpts {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) overwrite: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) ignore_if_exists: Option<bool>,
}

#[derive(Debug, Serialize, Clone, PartialEq, Eq)]
pub(crate) struct TextDocumentEdit {
    pub(crate) text_document: WorkspaceTextDocumentIdentifier,
    pub(crate) edits: Vec<TextEdit>,
}

#[derive(Debug, Serialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub(crate) struct WorkspaceTextDocumentIdentifier {
    pub(crate) uri: String,
    pub(crate) version: Option<i32>,
}

#[derive(Debug, Serialize, Clone, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub(crate) struct TextEdit {
    pub(crate) range: LspRange,
    pub(crate) new_text: String,
}

#[derive(Debug, Serialize, Clone, PartialEq, Eq)]
pub(crate) struct MarkupContent {
    pub(crate) kind: String,
    pub(crate) value: String,
}
