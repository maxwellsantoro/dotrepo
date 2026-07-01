//! Quick-fix code actions surfaced alongside adoption-status diagnostics.

use crate::protocol::{
    CodeAction, CodeActionParams, CreateFileChange, CreateFileOptions, CreateFileOpts,
    DocumentChange, LspDiagnostic, LspPosition, LspRange, TextDocumentEdit, TextEdit,
    WorkspaceEdit, WorkspaceTextDocumentIdentifier,
};
use crate::state::{document_for_request, DocumentIndex, OpenDocument, ServerState};
use anyhow::Result;
use dotrepo_core::render_dotrepo_ci_workflow;
use std::collections::BTreeMap;
use std::path::Path;
use url::Url;

pub(crate) fn code_actions(
    state: &ServerState,
    params: &CodeActionParams,
) -> Result<Vec<CodeAction>> {
    let document = document_for_request(state, &params.text_document.uri)?;
    let index = DocumentIndex::from_text(&document.text);
    let mut actions = Vec::new();

    for diagnostic in &params.context.diagnostics {
        if diagnostic.source == "adoption_status"
            && diagnostic.message.contains("set repo.homepage")
            && ranges_overlap(params.range, diagnostic.range)
        {
            actions.push(homepage_placeholder_code_action(
                &document.uri,
                &index,
                diagnostic.clone(),
            ));
        }
        if diagnostic.source == "adoption_status"
            && diagnostic.message.contains("dotrepo ci init")
            && ranges_overlap(params.range, diagnostic.range)
        {
            actions.push(ci_workflow_code_action(document, diagnostic.clone()));
        }
    }

    Ok(actions)
}

fn homepage_placeholder_code_action(
    uri: &str,
    index: &DocumentIndex,
    diagnostic: LspDiagnostic,
) -> CodeAction {
    let (range, new_text) = homepage_insert_edit(index);
    let mut changes = BTreeMap::new();
    changes.insert(uri.to_string(), vec![TextEdit { range, new_text }]);
    CodeAction {
        title: "Add repo.homepage placeholder".into(),
        kind: "quickfix".into(),
        diagnostics: vec![diagnostic],
        edit: WorkspaceEdit {
            changes,
            document_changes: None,
        },
    }
}

fn ci_workflow_code_action(document: &OpenDocument, diagnostic: LspDiagnostic) -> CodeAction {
    let workflow_path = document
        .path
        .parent()
        .unwrap_or_else(|| Path::new("."))
        .join(".github/workflows/dotrepo-check.yml");
    let workflow_uri = Url::from_file_path(&workflow_path)
        .map(|url| url.to_string())
        .unwrap_or_else(|_| workflow_path.display().to_string());
    CodeAction {
        title: "Create dotrepo CI workflow".into(),
        kind: "quickfix".into(),
        diagnostics: vec![diagnostic],
        edit: WorkspaceEdit {
            changes: BTreeMap::new(),
            document_changes: Some(vec![
                DocumentChange::Create(CreateFileChange {
                    create_file: CreateFileOptions {
                        uri: workflow_uri.clone(),
                        options: Some(CreateFileOpts {
                            overwrite: Some(false),
                            ignore_if_exists: Some(false),
                        }),
                    },
                }),
                DocumentChange::Edit(TextDocumentEdit {
                    text_document: WorkspaceTextDocumentIdentifier {
                        uri: workflow_uri,
                        version: None,
                    },
                    edits: vec![TextEdit {
                        range: insertion_range(0),
                        new_text: render_dotrepo_ci_workflow(env!("CARGO_PKG_VERSION")),
                    }],
                }),
            ]),
        },
    }
}

fn homepage_insert_edit(index: &DocumentIndex) -> (LspRange, String) {
    if let Some(line) = index
        .fields
        .iter()
        .filter(|(path, _)| path.starts_with("repo."))
        .map(|(_, range)| range.end.line)
        .max()
    {
        return (
            insertion_range(line.saturating_add(1)),
            "homepage = \"https://github.com/owner/repo\"\n".into(),
        );
    }

    if let Some(section) = index.section_range("repo") {
        return (
            insertion_range(section.end.line.saturating_add(1)),
            "homepage = \"https://github.com/owner/repo\"\n".into(),
        );
    }

    let line = index.lines.len() as u32;
    let prefix = if index.lines.is_empty() { "" } else { "\n" };
    (
        insertion_range(line),
        format!("{prefix}[repo]\nhomepage = \"https://github.com/owner/repo\"\n"),
    )
}

fn insertion_range(line: u32) -> LspRange {
    LspRange {
        start: LspPosition { line, character: 0 },
        end: LspPosition { line, character: 0 },
    }
}

fn ranges_overlap(a: LspRange, b: LspRange) -> bool {
    position_le(a.start, b.end) && position_le(b.start, a.end)
}

fn position_le(a: LspPosition, b: LspPosition) -> bool {
    a.line < b.line || (a.line == b.line && a.character <= b.character)
}
