//! Quick-fix code actions surfaced alongside adoption-status diagnostics.

use crate::protocol::{
    CodeAction, CodeActionParams, CreateFileChange, CreateFileOptions, CreateFileOpts,
    DocumentChange, LspDiagnostic, LspPosition, LspRange, TextDocumentEdit, TextEdit,
    WorkspaceEdit, WorkspaceTextDocumentIdentifier,
};
use crate::state::{document_for_request, DocumentIndex, OpenDocument, ServerState};
use anyhow::Result;
use dotrepo_core::{render_dotrepo_ci_workflow, DEFAULT_CI_RELEASE_VERSION};
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
                &document.text,
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
    text: &str,
    diagnostic: LspDiagnostic,
) -> CodeAction {
    let (range, new_text) = homepage_insert_edit(index, text);
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
                    kind: "create".into(),
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
                        new_text: render_dotrepo_ci_workflow(DEFAULT_CI_RELEASE_VERSION),
                    }],
                }),
            ]),
        },
    }
}

fn homepage_insert_edit(index: &DocumentIndex, text: &str) -> (LspRange, String) {
    if let Some(section) = index.section_range("repo") {
        if section.end.line as usize + 1 == index.lines.len() && !text.ends_with('\n') {
            let position = LspPosition {
                line: section.end.line,
                character: index.line(section.end.line).encode_utf16().count() as u32,
            };
            return (
                LspRange {
                    start: position,
                    end: position,
                },
                "\nhomepage = \"https://github.com/owner/repo\"\n".into(),
            );
        }
        return (
            insertion_range(section.end.line.saturating_add(1)),
            "homepage = \"https://github.com/owner/repo\"\n".into(),
        );
    }

    // An implicit repo table (dotted keys or only [repo.toolchain]) has no
    // [repo] header. A dotted key at the start stays in the document root.
    if index.fields.contains_key("repo") || index.values.contains_key("repo") {
        if let Some(value) = index.value_range("repo") {
            let line = index.line(value.start.line);
            let start = line
                .char_indices()
                .scan(0_u32, |offset, (byte, ch)| {
                    let position = *offset;
                    *offset += ch.len_utf16() as u32;
                    Some((byte, position))
                })
                .find(|(_, position)| *position == value.start.character)
                .map(|(byte, _)| byte);
            if start.is_some_and(|start| line[start..].trim_start().starts_with('{')) {
                let mut position = value.end;
                position.character = position.character.saturating_sub(1);
                let separator = if index.fields.keys().any(|key| key.starts_with("repo.")) {
                    ", "
                } else {
                    ""
                };
                return (
                    LspRange {
                        start: position,
                        end: position,
                    },
                    format!("{separator}homepage = \"https://github.com/owner/repo\""),
                );
            }
        }
        return (
            insertion_range(0),
            "repo.homepage = \"https://github.com/owner/repo\"\n".into(),
        );
    }

    let position = if text.is_empty() || text.ends_with('\n') {
        LspPosition {
            line: index.lines.len() as u32,
            character: 0,
        }
    } else {
        LspPosition {
            line: index.lines.len().saturating_sub(1) as u32,
            character: index
                .lines
                .last()
                .map_or(0, |line| line.encode_utf16().count() as u32),
        }
    };
    let prefix = if text.is_empty() {
        ""
    } else if text.ends_with('\n') {
        "\n"
    } else {
        "\n\n"
    };
    (
        LspRange {
            start: position,
            end: position,
        },
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

#[cfg(test)]
mod tests {
    use super::homepage_insert_edit;
    use crate::state::DocumentIndex;
    use toml_span::parse;

    #[test]
    fn homepage_edit_keeps_nested_tables_multiline_values_and_toml_forms_valid() {
        for repo in [
            "[repo]\nname = \"orbit\"\ndescription = \"\"\"\nA multiline\ndescription\n\"\"\"\n\n[repo.toolchain]\nmin = \"1.90.0\"\necosystem = \"rust\"\n",
            "[repo]\nname = \"orbit\"\ndescription = \"Orbit\"\n\n[repo.toolchain]\nmin = \"1.90.0\"\necosystem = \"rust\"",
            "repo.name = \"orbit\"\nrepo.description = \"Orbit\"\n\n[repo.toolchain]\nmin = \"1.90.0\"\necosystem = \"rust\"\n",
            "repo = { name = \"orbit\", description = \"Orbit 🛰️\" }\n",
            "repo = {}\n",
            "[repo]",
            "",
        ] {
            // Put dotted and inline repo forms before any table headers.
            let text = format!(
                "schema = \"dotrepo/v0.1\"\n{repo}\n[record]\nmode = \"native\"\nstatus = \"draft\"\n"
            );
            let index = DocumentIndex::from_text(&text);
            let (range, insertion) = homepage_insert_edit(&index, &text);
            assert_eq!(range.start, range.end);
            let line_start = text
                .split_inclusive('\n')
                .take(range.start.line as usize)
                .map(str::len)
                .sum::<usize>();
            let line = &text[line_start..];
            let mut utf16 = 0;
            let column = line
                .char_indices()
                .find_map(|(byte, ch)| {
                    if utf16 == range.start.character {
                        return Some(byte);
                    }
                    utf16 += ch.len_utf16() as u32;
                    None
                })
                .unwrap_or(line.len());
            let mut edited = text.clone();
            edited.insert_str(line_start + column, &insertion);
            let manifest = parse(&edited).unwrap_or_else(|err| panic!("{err}: {edited}"));
            let repo_table = manifest
                .as_table()
                .expect("document table")
                .get("repo")
                .and_then(|value| value.as_table())
                .expect("repo table");
            assert_eq!(
                repo_table.get("homepage").and_then(|value| value.as_str()),
                Some("https://github.com/owner/repo"),
                "{edited}"
            );
            assert_eq!(
                repo_table
                    .get("description")
                    .and_then(|value| value.as_str()),
                if repo.contains("🛰️") {
                    Some("Orbit 🛰️")
                } else if repo.contains("multiline") {
                    Some("A multiline\ndescription\n")
                } else if repo.contains("description") {
                    Some("Orbit")
                } else {
                    None
                }
            );
        }
    }

    #[test]
    fn homepage_edit_handles_repo_header_at_end_without_newline() {
        let text =
            "schema = \"dotrepo/v0.1\"\n[record]\nmode = \"native\"\nstatus = \"draft\"\n[repo]";
        let index = DocumentIndex::from_text(text);
        let (range, insertion) = homepage_insert_edit(&index, text);
        assert_eq!(range.start.line, 4);
        assert_eq!(range.start.character, 6);
        let edited = format!("{text}{insertion}");
        assert_eq!(
            parse(&edited)
                .expect("valid edited manifest")
                .as_table()
                .expect("document table")
                .get("repo")
                .and_then(|value| value.as_table())
                .and_then(|table| table.get("homepage"))
                .and_then(|value| value.as_str()),
            Some("https://github.com/owner/repo")
        );
    }
}
