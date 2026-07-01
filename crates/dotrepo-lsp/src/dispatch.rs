//! JSON-RPC dispatch: routes incoming messages to request/notification
//! handlers and publishes diagnostics for open documents.
//!
//! The stdio read/write loop itself lives in `main.rs`; this module only
//! covers per-message handling.

use crate::code_actions::code_actions;
use crate::completions::{completion_items, hover_response};
use crate::diagnostics::diagnostics_for_document;
use crate::protocol::{
    CodeActionParams, DidChangeTextDocumentParams, DidCloseTextDocumentParams,
    DidOpenTextDocumentParams, DidSaveTextDocumentParams, JsonRpcMessage, LspDiagnostic,
    PublishDiagnosticsParams, TextDocumentPositionParams,
};
use crate::state::{
    ensure_manifest_in_workspace, is_supported_manifest_path, manifest_path_from_uri,
    workspace_roots_from_initialize, OpenDocument, ServerState,
};
use anyhow::{Context, Result};
use dotrepo_transport::{jsonrpc_error_response, jsonrpc_response, JSONRPC_VERSION};
use serde_json::{json, Value};
use std::fs;
use std::path::PathBuf;

const SERVER_NAME: &str = "dotrepo-lsp";
const TEXT_DOCUMENT_SYNC_FULL: i64 = 1;

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct DiagnosticSnapshot {
    pub(crate) uri: String,
    pub(crate) version: Option<i64>,
    pub(crate) diagnostics: Vec<LspDiagnostic>,
}

pub(crate) fn handle_message(state: &mut ServerState, payload: &[u8]) -> Result<Vec<Value>> {
    let message =
        serde_json::from_slice::<JsonRpcMessage>(payload).context("failed to parse LSP message")?;
    if message.jsonrpc != JSONRPC_VERSION {
        return Ok(message
            .id
            .map(|id| {
                vec![jsonrpc_error_response(
                    id,
                    -32600,
                    format!("unsupported jsonrpc version: {}", message.jsonrpc),
                    None,
                )]
            })
            .unwrap_or_default());
    }

    match message.id {
        Some(id) => handle_request(state, id, &message.method, message.params),
        None => handle_notification(state, &message.method, message.params),
    }
}

pub(crate) fn handle_request(
    state: &mut ServerState,
    id: Value,
    method: &str,
    params: Value,
) -> Result<Vec<Value>> {
    let response = match method {
        "initialize" => {
            state.initialized = true;
            state.workspace_roots = workspace_roots_from_initialize(&params)?;
            jsonrpc_response(
                id,
                json!({
                    "capabilities": {
                        "textDocumentSync": {
                            "openClose": true,
                            "change": TEXT_DOCUMENT_SYNC_FULL,
                            "save": { "includeText": true }
                        },
                        "completionProvider": {},
                        "hoverProvider": true,
                        "codeActionProvider": true
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
            jsonrpc_response(id, Value::Null)
        }
        "textDocument/completion" => {
            let params: TextDocumentPositionParams = serde_json::from_value(params)?;
            jsonrpc_response(id, serde_json::to_value(completion_items(state, &params)?)?)
        }
        "textDocument/hover" => {
            let params: TextDocumentPositionParams = serde_json::from_value(params)?;
            match serde_json::to_value(hover_response(state, &params)?) {
                Ok(value) => jsonrpc_response(id, value),
                Err(err) => jsonrpc_error_response(
                    id,
                    -32603,
                    format!("failed to serialize hover response: {err}"),
                    None,
                ),
            }
        }
        "textDocument/codeAction" => {
            let params: CodeActionParams = serde_json::from_value(params)?;
            jsonrpc_response(id, serde_json::to_value(code_actions(state, &params)?)?)
        }
        _ => jsonrpc_error_response(id, -32601, format!("method not found: {}", method), None),
    };

    Ok(vec![response])
}

pub(crate) fn handle_notification(
    state: &mut ServerState,
    method: &str,
    params: Value,
) -> Result<Vec<Value>> {
    match method {
        "initialized" => Ok(Vec::new()),
        "exit" => {
            state.exit_requested = true;
            Ok(Vec::new())
        }
        "textDocument/didOpen" => {
            let params: DidOpenTextDocumentParams = serde_json::from_value(params)?;
            let path = manifest_path_from_uri(&params.text_document.uri)?;
            if !is_supported_manifest_path(&path)
                || ensure_manifest_in_workspace(&path, &state.workspace_roots, state.initialized)
                    .is_err()
            {
                return Ok(Vec::new());
            }
            let document = OpenDocument {
                uri: params.text_document.uri.clone(),
                path,
                version: Some(params.text_document.version),
                text: params.text_document.text,
            };
            let publish = publish_for_document(&document, &state.workspace_roots);
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
            let publish = publish_for_document(document, &state.workspace_roots);
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
                    if !is_supported_manifest_path(&path)
                        || ensure_manifest_in_workspace(
                            &path,
                            &state.workspace_roots,
                            state.initialized,
                        )
                        .is_err()
                    {
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
            let publish = publish_for_document(&document, &state.workspace_roots);
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

fn publish_for_document(
    document: &OpenDocument,
    workspace_roots: &[PathBuf],
) -> DiagnosticSnapshot {
    DiagnosticSnapshot {
        uri: document.uri.clone(),
        version: document.version,
        diagnostics: diagnostics_for_document(&document.path, &document.text, workspace_roots),
    }
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
