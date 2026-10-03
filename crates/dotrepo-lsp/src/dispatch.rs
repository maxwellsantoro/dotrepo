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
    document_for_request, ensure_manifest_in_workspace, is_supported_manifest_path,
    manifest_path_from_uri, workspace_roots_from_initialize, OpenDocument, ServerState,
};
use anyhow::Result;
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
    let value: Value = match serde_json::from_slice(payload) {
        Ok(value) => value,
        Err(err) => {
            return Ok(vec![jsonrpc_error_response(
                Value::Null,
                -32700,
                err.to_string(),
                None,
            )])
        }
    };
    let id = value.get("id").cloned();
    let valid_id = id
        .as_ref()
        .is_none_or(|id| id.is_null() || id.is_string() || id.is_i64() || id.is_u64());
    let mut message = match serde_json::from_value::<JsonRpcMessage>(value) {
        Ok(message) if message.jsonrpc == JSONRPC_VERSION && valid_id => message,
        _ => {
            return Ok(vec![jsonrpc_error_response(
                if valid_id {
                    id.unwrap_or(Value::Null)
                } else {
                    Value::Null
                },
                -32600,
                "invalid request".into(),
                None,
            )])
        }
    };
    // An explicit null id is still a request, not a notification.
    message.id = id;

    match message.id {
        Some(id) => handle_request(state, id, &message.method, message.params),
        None => match handle_notification(state, &message.method, message.params) {
            Ok(outgoing) => Ok(outgoing),
            Err(err) => {
                // Notifications never receive JSON-RPC error responses. A bad
                // document or failed file read must not terminate the session.
                eprintln!("LSP notification {} failed: {err}", message.method);
                Ok(Vec::new())
            }
        },
    }
}

#[derive(Debug)]
struct InvalidParams(String);

impl std::fmt::Display for InvalidParams {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for InvalidParams {}

fn invalid_params(err: impl std::fmt::Display) -> anyhow::Error {
    InvalidParams(err.to_string()).into()
}

fn request_params<T: serde::de::DeserializeOwned>(params: Value) -> Result<T> {
    serde_json::from_value(params).map_err(invalid_params)
}

pub(crate) fn handle_request(
    state: &mut ServerState,
    id: Value,
    method: &str,
    params: Value,
) -> Result<Vec<Value>> {
    match dispatch_request(state, id.clone(), method, params) {
        Ok(outgoing) => Ok(outgoing),
        Err(err) => Ok(vec![jsonrpc_error_response(
            id,
            if err.is::<InvalidParams>() {
                -32602
            } else {
                -32603
            },
            err.to_string(),
            None,
        )]),
    }
}

fn dispatch_request(
    state: &mut ServerState,
    id: Value,
    method: &str,
    params: Value,
) -> Result<Vec<Value>> {
    let response = match method {
        "initialize" => {
            let roots = workspace_roots_from_initialize(&params).map_err(invalid_params)?;
            state.workspace_roots = roots;
            state.initialized = true;
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
            let params: TextDocumentPositionParams = request_params(params)?;
            document_for_request(state, &params.text_document.uri).map_err(invalid_params)?;
            jsonrpc_response(id, serde_json::to_value(completion_items(state, &params)?)?)
        }
        "textDocument/hover" => {
            let params: TextDocumentPositionParams = request_params(params)?;
            document_for_request(state, &params.text_document.uri).map_err(invalid_params)?;
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
            let params: CodeActionParams = request_params(params)?;
            document_for_request(state, &params.text_document.uri).map_err(invalid_params)?;
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
