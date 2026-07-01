//! Consolidated behavioral tests for the LSP server's dispatch loop,
//! diagnostics, completions, hover, and code actions.

use crate::code_actions::code_actions;
use crate::completions::{completion_items, hover_response};
use crate::diagnostics::diagnostics_for_document;
use crate::dispatch::{handle_message, handle_request};
use crate::protocol::{
    CodeActionContext, CodeActionParams, DocumentChange, LspPosition, TextDocumentIdentifier,
    TextDocumentPositionParams,
};
use crate::state::{OpenDocument, ServerState};
use dotrepo_transport::JSONRPC_VERSION;
use serde_json::json;
use serde_json::Value;
use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};
use url::Url;

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
        &[],
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

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
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
        &[],
    );

    assert_eq!(diagnostics.len(), 1);
    assert_eq!(diagnostics[0].source, "parse_manifest");
    assert!(diagnostics[0].message.contains("failed to parse manifest"));
    assert!(diagnostics[0].range.start.line > 0);

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
}

#[test]
fn diagnostics_for_native_manifest_include_adoption_hints() {
    let root = temp_dir("lsp-adoption-hints");
    let path = root.join(".repo");
    let diagnostics = diagnostics_for_document(
        &path,
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "draft"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
        &[],
    );

    let messages = diagnostics
        .iter()
        .filter(|diagnostic| diagnostic.source == "adoption_status")
        .map(|diagnostic| diagnostic.message.as_str())
        .collect::<Vec<_>>();
    assert!(messages
        .iter()
        .any(|message| message.contains("set repo.homepage")));
    assert!(messages
        .iter()
        .any(|message| message.contains("dotrepo ci init")));
    assert!(diagnostics
        .iter()
        .filter(|diagnostic| diagnostic.source == "adoption_status")
        .all(|diagnostic| diagnostic.severity == 4));

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
}

#[test]
fn diagnostics_warn_when_homepage_does_not_resolve_to_identity() {
    let root = temp_dir("lsp-adoption-homepage-invalid");
    let path = root.join(".repo");
    let diagnostics = diagnostics_for_document(
        &path,
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "draft"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
homepage = "not-a-repo-url"
"#,
        &[],
    );

    assert!(diagnostics.iter().any(|diagnostic| {
        diagnostic.source == "adoption_status"
            && diagnostic
                .message
                .contains("repo.homepage must resolve to a host/owner/repo URL")
    }));

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
}

#[test]
fn diagnostics_surface_other_root_manifest_validation_errors() {
    let root = temp_dir("lsp-dual-manifest");
    let path = root.join(".repo");
    fs::write(
        root.join("record.toml"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"

[repo]
name = ""
description = "overlay with missing name"
"#,
    )
    .expect("record.toml written");

    let diagnostics = diagnostics_for_document(
        &path,
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "draft"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
        &[],
    );

    assert!(diagnostics.iter().any(|diagnostic| {
        diagnostic.source == "validate_manifest"
            && diagnostic.message.contains("record.toml")
            && diagnostic.message.contains("repo.name")
    }));

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
}

#[test]
fn diagnostics_for_native_manifest_skip_adoption_hints_when_ready() {
    let root = temp_dir("lsp-adoption-ready");
    let path = root.join(".repo");
    fs::create_dir_all(root.join(".github/workflows")).expect("workflow dir created");
    fs::write(
        root.join(".github/workflows/dotrepo-check.yml"),
        "name: dotrepo-check\n",
    )
    .expect("workflow written");
    let diagnostics = diagnostics_for_document(
        &path,
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "draft"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
homepage = "https://github.com/acme/orbit"
"#,
        &[],
    );

    assert!(!diagnostics
        .iter()
        .any(|diagnostic| diagnostic.source == "adoption_status"));

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
}

#[test]
fn initialize_advertises_code_action_provider() {
    let mut state = ServerState::default();
    let response = handle_request(&mut state, Value::Number(1.into()), "initialize", json!({}))
        .expect("initialize handled");

    assert_eq!(
        response[0]["result"]["capabilities"]["codeActionProvider"],
        Value::Bool(true)
    );
}

#[test]
fn code_action_adds_homepage_placeholder_for_adoption_hint() {
    let root = temp_dir("lsp-code-action-homepage");
    let path = root.join(".repo");
    let uri = Url::from_file_path(&path)
        .expect("file path uri")
        .to_string();
    let text = r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "draft"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#
    .to_string();
    let diagnostics = diagnostics_for_document(&path, &text, &[]);
    let diagnostic = diagnostics
        .into_iter()
        .find(|diagnostic| {
            diagnostic.source == "adoption_status"
                && diagnostic.message.contains("set repo.homepage")
        })
        .expect("homepage adoption diagnostic");
    let mut state = ServerState::default();
    state.documents.insert(
        uri.clone(),
        OpenDocument {
            uri: uri.clone(),
            path,
            version: Some(1),
            text,
        },
    );

    let actions = code_actions(
        &state,
        &CodeActionParams {
            text_document: TextDocumentIdentifier { uri: uri.clone() },
            range: diagnostic.range,
            context: CodeActionContext {
                diagnostics: vec![diagnostic],
            },
        },
    )
    .expect("code actions computed");

    assert_eq!(actions.len(), 1);
    assert_eq!(actions[0].title, "Add repo.homepage placeholder");
    let edits = actions[0]
        .edit
        .changes
        .get(&uri)
        .expect("edit for document uri");
    assert_eq!(edits.len(), 1);
    assert_eq!(
        edits[0].new_text,
        "homepage = \"https://github.com/owner/repo\"\n"
    );
    assert!(
        edits[0].range.start.line > 0,
        "homepage should be inserted inside the repo section"
    );

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
}

#[test]
fn code_action_creates_ci_workflow_for_adoption_hint() {
    let root = temp_dir("lsp-code-action-ci");
    let path = root.join(".repo");
    let uri = Url::from_file_path(&path)
        .expect("file path uri")
        .to_string();
    let text = r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "draft"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
homepage = "https://github.com/acme/orbit"
"#
    .to_string();
    let diagnostic = diagnostics_for_document(&path, &text, &[])
        .into_iter()
        .find(|diagnostic| {
            diagnostic.source == "adoption_status" && diagnostic.message.contains("dotrepo ci init")
        })
        .expect("ci adoption diagnostic");
    let mut state = ServerState::default();
    state.documents.insert(
        uri.clone(),
        OpenDocument {
            uri,
            path,
            version: Some(1),
            text,
        },
    );

    let actions = code_actions(
        &state,
        &CodeActionParams {
            text_document: TextDocumentIdentifier {
                uri: Url::from_file_path(root.join(".repo"))
                    .expect("file uri")
                    .to_string(),
            },
            range: diagnostic.range,
            context: CodeActionContext {
                diagnostics: vec![diagnostic],
            },
        },
    )
    .expect("code actions computed");

    assert_eq!(actions.len(), 1);
    assert_eq!(actions[0].title, "Create dotrepo CI workflow");
    let workflow_uri = Url::from_file_path(root.join(".github/workflows/dotrepo-check.yml"))
        .expect("workflow uri")
        .to_string();
    let document_changes = actions[0]
        .edit
        .document_changes
        .as_ref()
        .expect("workflow document changes");
    assert_eq!(document_changes.len(), 2);
    let DocumentChange::Edit(text_edit) = &document_changes[1] else {
        panic!("second document change should be a text edit");
    };
    assert_eq!(text_edit.text_document.uri, workflow_uri);
    assert_eq!(text_edit.edits.len(), 1);
    assert!(text_edit.edits[0]
        .new_text
        .contains("dotrepo --root . adoption-status"));
    assert!(text_edit.edits[0].new_text.contains("DOTREPO_VERSION"));

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
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
        .unwrap_or_else(|e| panic!("message handled: {e}"));

    assert_eq!(outputs.len(), 1);
    assert_eq!(outputs[0]["method"], "textDocument/publishDiagnostics");
    assert!(outputs[0]["params"]["diagnostics"]
        .as_array()
        .expect("diagnostics array")
        .iter()
        .any(|diagnostic| diagnostic["message"]
            == Value::String("record.source must be set for overlay records".into())));

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
}

#[test]
fn did_open_ignores_manifest_outside_workspace_folders() {
    let workspace = temp_dir("lsp-workspace");
    let outside = temp_dir("lsp-outside");
    let manifest_path = outside.join(".repo");
    fs::write(
        &manifest_path,
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "draft"

[repo]
name = "outside"
description = "Outside workspace"
"#,
    )
    .expect("manifest written");
    let uri = Url::from_file_path(&manifest_path)
        .expect("file path uri")
        .to_string();
    let workspace_uri = Url::from_file_path(&workspace)
        .expect("workspace uri")
        .to_string();

    let mut state = ServerState::default();
    let init = json!({
        "jsonrpc": JSONRPC_VERSION,
        "id": 1,
        "method": "initialize",
        "params": {
            "workspaceFolders": [
                { "uri": workspace_uri, "name": "workspace" }
            ]
        }
    });
    handle_request(
        &mut state,
        init["id"].clone(),
        "initialize",
        init["params"].clone(),
    )
    .expect("initialize handled");

    let open = json!({
        "jsonrpc": JSONRPC_VERSION,
        "method": "textDocument/didOpen",
        "params": {
            "textDocument": {
                "uri": uri.clone(),
                "languageId": "toml",
                "version": 1,
                "text": fs::read_to_string(&manifest_path).expect("manifest read"),
            }
        }
    });
    let outputs = handle_message(&mut state, &serde_json::to_vec(&open).expect("message"))
        .expect("open handled");

    assert!(outputs.is_empty());
    assert!(!state.documents.contains_key(&uri));

    fs::remove_dir_all(workspace).unwrap_or_else(|e| panic!("workspace removed: {e}"));
    fs::remove_dir_all(outside).unwrap_or_else(|e| panic!("outside removed: {e}"));
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

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
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

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
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

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
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

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
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
    handle_message(state, &serde_json::to_vec(&message).expect("message")).expect("open handled");
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
