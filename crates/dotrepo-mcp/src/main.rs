use anyhow::{anyhow, bail, Result};
use dotrepo_core::{
    current_timestamp_rfc3339, display_path, generate_check_repository, import_preview_repository,
    import_repository_with_options, inspect_claim_directory, query_repository, record_summary,
    trust_repository, validate_repository, ImportMode, ImportOptions,
};
use dotrepo_transport::{
    read_jsonrpc_message as read_message, write_jsonrpc_message as write_message,
};
use serde::Deserialize;
use serde_json::{json, to_value, Value};
use std::fs;
use std::fs::{File, OpenOptions};
use std::io::{self, BufReader};
use std::io::{ErrorKind, Write};
use std::path::{Path, PathBuf};

const JSONRPC_VERSION: &str = "2.0";
const SUPPORTED_PROTOCOL_VERSIONS: &[&str] = &["2025-11-25", "2025-06-18", "2024-11-05"];
const SERVER_NAME: &str = "dotrepo-mcp";

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
        let request = match serde_json::from_slice::<JsonRpcRequest>(&message) {
            Ok(request) => request,
            Err(err) => {
                write_message(
                    &mut writer,
                    &error_response(
                        Value::Null,
                        -32700,
                        format!("failed to parse request: {}", err),
                        None,
                    ),
                )?;
                continue;
            }
        };

        if let Some(response) = handle_request(&mut state, request) {
            write_message(&mut writer, &response)?;
        }
    }

    Ok(())
}

#[derive(Debug, Default)]
struct ServerState {
    initialized: bool,
    protocol_version: Option<&'static str>,
}

#[derive(Debug, Deserialize)]
struct JsonRpcRequest {
    jsonrpc: String,
    #[serde(default)]
    id: Option<Value>,
    method: String,
    #[serde(default)]
    params: Value,
}

fn handle_request(state: &mut ServerState, request: JsonRpcRequest) -> Option<Value> {
    if request.jsonrpc != JSONRPC_VERSION {
        return request.id.map(|id| {
            error_response(
                id,
                -32600,
                format!("unsupported jsonrpc version: {}", request.jsonrpc),
                None,
            )
        });
    }

    if request.id.is_none() {
        handle_notification(state, request.method, request.params);
        return None;
    }

    let id = request.id.expect("id checked above");

    let result = match dispatch_request(state, &request.method, request.params) {
        Ok(result) => response(id, result),
        Err(err) => error_response(id, -32603, err.to_string(), None),
    };

    Some(result)
}

fn handle_notification(state: &mut ServerState, method: String, _params: Value) {
    if method == "notifications/initialized" {
        state.initialized = true;
    }
}

fn dispatch_request(state: &mut ServerState, method: &str, params: Value) -> Result<Value> {
    match method {
        "initialize" => handle_initialize(state, params),
        "ping" => Ok(json!({})),
        "tools/list" => {
            ensure_initialized(state)?;
            Ok(json!({ "tools": tool_definitions() }))
        }
        "tools/call" => {
            ensure_initialized(state)?;
            handle_tool_call(params)
        }
        _ => bail!("method not found: {}", method),
    }
}

fn handle_initialize(state: &mut ServerState, params: Value) -> Result<Value> {
    let requested = params
        .get("protocolVersion")
        .and_then(Value::as_str)
        .unwrap_or(SUPPORTED_PROTOCOL_VERSIONS[0]);
    let negotiated = negotiate_protocol_version(requested);
    state.protocol_version = Some(negotiated);

    Ok(json!({
        "protocolVersion": negotiated,
        "capabilities": {
            "tools": {
                "listChanged": false
            }
        },
        "serverInfo": {
            "name": SERVER_NAME,
            "title": "dotrepo MCP Server",
            "version": env!("CARGO_PKG_VERSION")
        },
        "instructions": "Use dotrepo.query for trust-aware field lookups, dotrepo.trust for record provenance, and dotrepo.import_preview before dotrepo.import_write."
    }))
}

fn handle_tool_call(params: Value) -> Result<Value> {
    let name = params
        .get("name")
        .and_then(Value::as_str)
        .ok_or_else(|| anyhow!("tools/call requires a tool name"))?;
    let arguments = params
        .get("arguments")
        .cloned()
        .unwrap_or_else(|| Value::Object(Default::default()));

    let result = match name {
        "dotrepo.validate" => tool_validate(arguments),
        "dotrepo.query" => tool_query(arguments),
        "dotrepo.trust" => tool_trust(arguments),
        "dotrepo.claim_inspect" => tool_claim_inspect(arguments),
        "dotrepo.generate_check" => tool_generate_check(arguments),
        "dotrepo.import_preview" => tool_import_preview(arguments),
        "dotrepo.import_write" => tool_import_write(arguments),
        _ => bail!("unknown tool: {}", name),
    };

    match result {
        Ok((summary, structured)) => Ok(tool_success(summary, structured)),
        Err(err) => Ok(tool_failure(
            format!("tool `{}` failed", name),
            json!({ "error": err.to_string() }),
        )),
    }
}

fn tool_validate(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments);
    let report = validate_repository(&root);
    let summary = if report.valid {
        "manifest valid"
    } else {
        "manifest invalid"
    };
    Ok((summary.into(), to_value(report)?))
}

fn tool_query(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments);
    let path = required_string(&arguments, "path")?;
    let report = query_repository(&root, path)?;
    Ok((format!("queried {}", path), to_value(report)?))
}

fn tool_trust(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments);
    let report = trust_repository(&root)?;
    Ok(("trust metadata loaded".into(), to_value(report)?))
}

fn tool_claim_inspect(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments);
    let claim_path = required_string(&arguments, "claimPath")?;
    let claim_dir = if Path::new(claim_path).is_absolute() {
        PathBuf::from(claim_path)
    } else {
        root.join(claim_path)
    };
    let report = inspect_claim_directory(&root, &claim_dir)?;
    Ok(("claim history loaded".into(), to_value(report)?))
}

fn tool_generate_check(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments);
    let report = generate_check_repository(&root)?;
    Ok((
        format!(
            "checked {} generated outputs; {} stale",
            report.checked,
            report.stale.len()
        ),
        to_value(report)?,
    ))
}

fn tool_import_preview(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments);
    let mode = import_mode(&arguments)?;
    let source = optional_string(&arguments, "source");
    let report = import_preview_repository(&root, mode, source.as_deref())?;
    Ok(("import preview ready".into(), to_value(report)?))
}

fn tool_import_write(arguments: Value) -> Result<(String, Value)> {
    let root = resolve_root(&arguments);
    let mode = import_mode(&arguments)?;
    let source = optional_string(&arguments, "source");
    let force = arguments
        .get("force")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let plan = import_repository_with_options(
        &root,
        mode,
        source.as_deref(),
        &ImportOptions {
            generated_at: Some(current_timestamp_rfc3339()?),
        },
    )?;
    let written_paths = write_import_plan(&root, &plan, force)?;

    let structured = json!({
        "root": root.display().to_string(),
        "mode": import_mode_name(mode),
        "writtenPaths": written_paths,
        "importedSources": plan.imported_sources,
        "inferredFields": plan.inferred_fields,
        "record": record_summary(&plan.manifest),
    });
    Ok(("imported repository metadata".into(), structured))
}

fn write_import_plan(
    root: &Path,
    plan: &dotrepo_core::ImportPlan,
    force: bool,
) -> Result<Vec<String>> {
    let mut outputs = vec![(plan.manifest_path.clone(), plan.manifest_text.clone())];
    if let (Some(path), Some(contents)) = (&plan.evidence_path, &plan.evidence_text) {
        outputs.push((path.clone(), contents.clone()));
    }

    let written_paths = outputs
        .iter()
        .map(|(path, _)| display_path(root, path))
        .collect::<Vec<_>>();
    write_import_outputs(outputs, force)?;

    Ok(written_paths)
}

struct ReservedImportOutput {
    path: PathBuf,
    contents: String,
    file: File,
}

fn write_import_outputs(outputs: Vec<(PathBuf, String)>, force: bool) -> Result<()> {
    if force {
        for (path, contents) in outputs {
            if let Some(parent) = path.parent() {
                fs::create_dir_all(parent)?;
            }
            fs::write(path, contents)?;
        }
        return Ok(());
    }

    let mut reserved = Vec::new();
    for (path, contents) in outputs {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }

        let file = match OpenOptions::new().write(true).create_new(true).open(&path) {
            Ok(file) => file,
            Err(err) => {
                cleanup_reserved_import_outputs(reserved);
                return Err(match err.kind() {
                    ErrorKind::AlreadyExists => anyhow!(
                        "{} already exists; rerun with force=true to overwrite imported artifacts",
                        path.display()
                    ),
                    _ => err.into(),
                });
            }
        };

        reserved.push(ReservedImportOutput {
            path,
            contents,
            file,
        });
    }

    for idx in 0..reserved.len() {
        let write_result = {
            let reserved_output = &mut reserved[idx];
            reserved_output
                .file
                .write_all(reserved_output.contents.as_bytes())
                .and_then(|_| reserved_output.file.flush())
        };
        if let Err(err) = write_result {
            cleanup_reserved_import_outputs(reserved);
            return Err(err.into());
        }
    }

    Ok(())
}

fn cleanup_reserved_import_outputs(outputs: Vec<ReservedImportOutput>) {
    let paths = outputs
        .into_iter()
        .map(|reserved| reserved.path)
        .collect::<Vec<_>>();
    for path in paths {
        let _ = fs::remove_file(path);
    }
}

fn resolve_root(arguments: &Value) -> PathBuf {
    optional_string(arguments, "root")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}

fn required_string<'a>(arguments: &'a Value, field: &str) -> Result<&'a str> {
    arguments
        .get(field)
        .and_then(Value::as_str)
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| anyhow!("missing required string argument `{}`", field))
}

fn optional_string(arguments: &Value, field: &str) -> Option<String> {
    arguments
        .get(field)
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(str::to_string)
}

fn import_mode(arguments: &Value) -> Result<ImportMode> {
    match optional_string(arguments, "mode")
        .as_deref()
        .unwrap_or("native")
    {
        "native" => Ok(ImportMode::Native),
        "overlay" => Ok(ImportMode::Overlay),
        other => bail!("unsupported import mode: {}", other),
    }
}

fn import_mode_name(mode: ImportMode) -> &'static str {
    match mode {
        ImportMode::Native => "native",
        ImportMode::Overlay => "overlay",
    }
}

fn ensure_initialized(state: &ServerState) -> Result<()> {
    if state.protocol_version.is_none() {
        bail!("server must receive initialize before calling tools");
    }
    if !state.initialized {
        bail!("server must receive notifications/initialized before calling tools");
    }
    Ok(())
}

fn negotiate_protocol_version(requested: &str) -> &'static str {
    SUPPORTED_PROTOCOL_VERSIONS
        .iter()
        .copied()
        .find(|version| *version == requested)
        .unwrap_or(SUPPORTED_PROTOCOL_VERSIONS[0])
}

fn tool_definitions() -> Vec<Value> {
    vec![
        json!({
            "name": "dotrepo.validate",
            "title": "Validate dotrepo record",
            "description": "Validate the manifest at the given repository root and return trust-aware diagnostics.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "root": { "type": "string", "description": "Repository root containing .repo or record.toml." }
                },
                "additionalProperties": false
            }
        }),
        json!({
            "name": "dotrepo.query",
            "title": "Query manifest path",
            "description": "Query a dot-path such as repo.name or record.trust.provenance and return the value with record trust context.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "root": { "type": "string", "description": "Repository root containing .repo or record.toml." },
                    "path": { "type": "string", "description": "Dot-path to query." }
                },
                "required": ["path"],
                "additionalProperties": false
            }
        }),
        json!({
            "name": "dotrepo.trust",
            "title": "Read trust metadata",
            "description": "Return record status, mode, source, and trust metadata for the manifest at the given root.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "root": { "type": "string", "description": "Repository root containing .repo or record.toml." }
                },
                "additionalProperties": false
            }
        }),
        json!({
            "name": "dotrepo.claim_inspect",
            "title": "Inspect maintainer claim",
            "description": "Inspect one maintainer-claim directory and return current state, target context, derived handoff, and ordered event history.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "root": { "type": "string", "description": "Index root containing repos/<host>/<owner>/<repo>/claims/..." },
                    "claimPath": { "type": "string", "description": "Claim directory relative to root or an absolute path." }
                },
                "required": ["claimPath"],
                "additionalProperties": false
            }
        }),
        json!({
            "name": "dotrepo.generate_check",
            "title": "Preview generated outputs",
            "description": "Check dotrepo-managed outputs and report which generated files are stale without writing files.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "root": { "type": "string", "description": "Repository root containing .repo or record.toml." }
                },
                "additionalProperties": false
            }
        }),
        json!({
            "name": "dotrepo.import_preview",
            "title": "Preview imported manifest",
            "description": "Preview a native or overlay import derived from README.md, CODEOWNERS, and SECURITY.md.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "root": { "type": "string", "description": "Repository root to import from." },
                    "mode": { "type": "string", "enum": ["native", "overlay"], "description": "Import mode; defaults to native." },
                    "source": { "type": "string", "description": "Absolute repository URL required for overlay imports." }
                },
                "additionalProperties": false
            }
        }),
        json!({
            "name": "dotrepo.import_write",
            "title": "Write imported manifest",
            "description": "Write a native .repo or overlay record.toml plus evidence.md using the same import pipeline as import_preview.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "root": { "type": "string", "description": "Repository root to import from." },
                    "mode": { "type": "string", "enum": ["native", "overlay"], "description": "Import mode; defaults to native." },
                    "source": { "type": "string", "description": "Absolute repository URL required for overlay imports." },
                    "force": { "type": "boolean", "description": "Overwrite existing import artifacts when true." }
                },
                "additionalProperties": false
            }
        }),
    ]
}

fn tool_success(summary: String, structured: Value) -> Value {
    let text = format!(
        "{}\n\n{}",
        summary,
        serde_json::to_string_pretty(&structured).expect("structured content serializes")
    );
    json!({
        "content": [
            {
                "type": "text",
                "text": text
            }
        ],
        "structuredContent": structured,
        "isError": false
    })
}

fn tool_failure(summary: String, structured: Value) -> Value {
    let text = format!(
        "{}\n\n{}",
        summary,
        serde_json::to_string_pretty(&structured).expect("structured content serializes")
    );
    json!({
        "content": [
            {
                "type": "text",
                "text": text
            }
        ],
        "structuredContent": structured,
        "isError": true
    })
}

fn response(id: Value, result: Value) -> Value {
    json!({
        "jsonrpc": JSONRPC_VERSION,
        "id": id,
        "result": result
    })
}

fn error_response(id: Value, code: i64, message: String, data: Option<Value>) -> Value {
    let mut error = json!({
        "code": code,
        "message": message,
    });
    if let Some(data) = data {
        error["data"] = data;
    }
    json!({
        "jsonrpc": JSONRPC_VERSION,
        "id": id,
        "error": error
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn initialize_and_list_tools() {
        let (mut state, init_response) = initialized_state();
        assert_eq!(init_response["result"]["protocolVersion"], "2025-11-25");

        let tools_response = handle_request(&mut state, request(2, "tools/list", json!({})))
            .expect("tools/list responds");
        let tools = tools_response["result"]["tools"]
            .as_array()
            .expect("tool list");
        assert!(tools
            .iter()
            .any(|tool| tool["name"] == Value::String("dotrepo.query".into())));
        assert!(tools
            .iter()
            .any(|tool| tool["name"] == Value::String("dotrepo.import_preview".into())));
        assert!(tools
            .iter()
            .any(|tool| tool["name"] == Value::String("dotrepo.claim_inspect".into())));
    }

    #[test]
    fn query_tool_returns_trust_context() {
        let root = temp_dir("query");
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[record.trust]
confidence = "high"
provenance = ["declared"]

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
        )
        .expect("manifest written");

        let response = call_tool(
            "dotrepo.query",
            json!({
                "root": root.display().to_string(),
                "path": "repo.name"
            }),
        );
        assert_eq!(
            response["result"]["structuredContent"]["value"],
            Value::String("orbit".into())
        );
        assert_eq!(
            response["result"]["structuredContent"]["selection"]["reason"],
            Value::String("only_matching_record".into())
        );
        assert_eq!(
            response["result"]["structuredContent"]["selection"]["record"]["record"]["status"],
            Value::String("canonical".into())
        );
        assert_eq!(
            response["result"]["structuredContent"]["conflicts"],
            Value::Array(Vec::new())
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn import_preview_reports_inferred_overlay_fallbacks() {
        let root = temp_dir("import-preview");

        let response = call_tool(
            "dotrepo.import_preview",
            json!({
                "root": root.display().to_string(),
                "mode": "overlay",
                "source": "https://github.com/example/project"
            }),
        );
        assert_eq!(
            response["result"]["structuredContent"]["record"]["status"],
            Value::String("inferred".into())
        );
        assert!(response["result"]["structuredContent"]["inferredFields"]
            .as_array()
            .expect("inferred fields")
            .iter()
            .any(|field| field == "repo.name"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn validate_tool_returns_structured_diagnostics() {
        let root = temp_dir("validate");
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "overlay"
status = "imported"

[repo]
name = "broken"
description = "Missing source and trust"
"#,
        )
        .expect("manifest written");

        let response = call_tool(
            "dotrepo.validate",
            json!({
                "root": root.display().to_string()
            }),
        );
        let structured = &response["result"]["structuredContent"];
        assert_eq!(structured["valid"], Value::Bool(false));
        assert!(
            structured["diagnostics"]
                .as_array()
                .expect("diagnostics array")
                .len()
                >= 2
        );
        assert_eq!(
            structured["diagnostics"][0]["severity"],
            Value::String("error".into())
        );
        assert!(structured["diagnostics"]
            .as_array()
            .expect("diagnostics array")
            .iter()
            .any(|diagnostic| diagnostic["source"] == Value::String("validate_manifest".into())));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn tools_require_initialized_notification() {
        let mut state = ServerState::default();
        let _ = handle_request(
            &mut state,
            request(
                1,
                "initialize",
                json!({
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": { "name": "test", "version": "0" }
                }),
            ),
        );

        let response = handle_request(&mut state, request(2, "tools/list", json!({})))
            .expect("tools/list responds");
        assert_eq!(
            response["error"]["message"],
            Value::String(
                "server must receive notifications/initialized before calling tools".into()
            )
        );
    }

    #[test]
    fn import_write_respects_force_flag() {
        let root = temp_dir("import-write");
        fs::write(
            root.join("README.md"),
            "# Example\n\nImported description.\n",
        )
        .expect("README written");
        fs::write(root.join(".repo"), "preexisting\n").expect(".repo written");

        let response = call_tool(
            "dotrepo.import_write",
            json!({
                "root": root.display().to_string(),
                "mode": "native"
            }),
        );
        assert_eq!(response["result"]["isError"], Value::Bool(true));
        assert!(response["result"]["structuredContent"]["error"]
            .as_str()
            .expect("error string")
            .contains("already exists"));

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn write_import_output_refuses_to_clobber_existing_file_without_force() {
        let root = temp_dir("import-write-helper");
        let path = root.join(".repo");
        fs::write(&path, "existing\n").expect("existing file written");

        let err = write_import_outputs(vec![(path.clone(), "replacement\n".into())], false)
            .expect_err("existing file should be preserved");
        assert!(err.to_string().contains("already exists"));
        assert_eq!(fs::read_to_string(&path).expect("file readable"), "existing\n");

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn import_write_refuses_existing_evidence_without_leaving_partial_manifest() {
        let root = temp_dir("import-write-no-partial");
        fs::write(
            root.join("README.md"),
            "# Example Project\n\nProject summary from the README.\n",
        )
        .expect("README written");
        fs::write(root.join("evidence.md"), "preexisting evidence\n").expect("evidence written");

        let plan = import_repository_with_options(
            &root,
            ImportMode::Overlay,
            Some("https://github.com/example/project"),
            &ImportOptions {
                generated_at: Some(current_timestamp_rfc3339().expect("timestamp")),
            },
        )
        .expect("import plan builds");
        let err = write_import_plan(&root, &plan, false).expect_err("write should fail");

        assert!(err.to_string().contains("already exists"));
        assert!(!root.join("record.toml").exists());
        assert_eq!(
            fs::read_to_string(root.join("evidence.md")).expect("evidence readable"),
            "preexisting evidence\n"
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn maintainer_path_tools_match_core_reports() {
        let root = temp_dir("parity-native");
        write_native_parity_repo(&root);

        let validate = call_tool(
            "dotrepo.validate",
            json!({ "root": root.display().to_string() }),
        );
        assert_eq!(
            validate["result"]["structuredContent"],
            to_value(validate_repository(&root)).expect("validate report serializes")
        );

        let query = call_tool(
            "dotrepo.query",
            json!({
                "root": root.display().to_string(),
                "path": "repo.build"
            }),
        );
        assert_eq!(
            query["result"]["structuredContent"],
            to_value(query_repository(&root, "repo.build").expect("query report"))
                .expect("query report serializes")
        );

        let trust = call_tool(
            "dotrepo.trust",
            json!({ "root": root.display().to_string() }),
        );
        assert_eq!(
            trust["result"]["structuredContent"],
            to_value(trust_repository(&root).expect("trust report"))
                .expect("trust report serializes")
        );

        let generate = call_tool(
            "dotrepo.generate_check",
            json!({ "root": root.display().to_string() }),
        );
        assert_eq!(
            generate["result"]["structuredContent"],
            to_value(generate_check_repository(&root).expect("generate-check report"))
                .expect("generate-check report serializes")
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn claim_inspect_tool_matches_core_report() {
        let root = temp_dir("claim-inspect");
        let record_dir = root.join("repos/github.com/acme/widget");
        let claim_dir = record_dir.join("claims/2026-03-10-maintainer-claim-01");
        fs::create_dir_all(claim_dir.join("events")).expect("claim events dir created");
        fs::write(
            claim_dir.join("claim.toml"),
            r#"
schema = "dotrepo-claim/v0"

[claim]
id = "github.com/acme/widget/2026-03-10-maintainer-claim-01"
kind = "maintainer_authority"
state = "accepted"
created_at = "2026-03-10T14:30:00Z"
updated_at = "2026-03-12T09:15:00Z"

[identity]
host = "github.com"
owner = "acme"
repo = "widget"

[claimant]
display_name = "Acme maintainers"
asserted_role = "maintainer"

[target]
index_paths = ["repos/github.com/acme/widget/record.toml"]
record_sources = ["https://github.com/acme/widget"]
canonical_repo_url = "https://github.com/acme/widget"

[resolution]
canonical_record_path = ".repo"
canonical_mirror_path = "repos/github.com/acme/widget/record.toml"
result_event = "events/0002-accepted.toml"
"#,
        )
        .expect("claim written");
        fs::write(
            claim_dir.join("events/0001-submitted.toml"),
            r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 1
kind = "submitted"
timestamp = "2026-03-10T14:30:00Z"
actor = "claimant"

[transition]
from = "draft"
to = "submitted"

[summary]
text = "Submitted claim."
"#,
        )
        .expect("submitted event written");
        fs::write(
            claim_dir.join("events/0002-accepted.toml"),
            r#"
schema = "dotrepo-claim-event/v0"

[event]
sequence = 2
kind = "accepted"
timestamp = "2026-03-12T09:15:00Z"
actor = "index-reviewer"

[transition]
from = "submitted"
to = "accepted"

[summary]
text = "Accepted claim."
"#,
        )
        .expect("accepted event written");

        let response = call_tool(
            "dotrepo.claim_inspect",
            json!({
                "root": root.display().to_string(),
                "claimPath": "repos/github.com/acme/widget/claims/2026-03-10-maintainer-claim-01"
            }),
        );
        assert_eq!(
            response["result"]["structuredContent"],
            to_value(inspect_claim_directory(&root, &claim_dir).expect("claim report"))
                .expect("claim report serializes")
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn import_preview_tool_matches_core_report() {
        let root = temp_dir("parity-import-preview");
        fs::write(
            root.join("README.md"),
            "# Example\n\nImported description.\n",
        )
        .expect("README written");

        let response = call_tool(
            "dotrepo.import_preview",
            json!({
                "root": root.display().to_string(),
                "mode": "overlay",
                "source": "https://github.com/example/project"
            }),
        );
        assert_eq!(
            response["result"]["structuredContent"],
            to_value(
                import_preview_repository(
                    &root,
                    ImportMode::Overlay,
                    Some("https://github.com/example/project"),
                )
                .expect("import preview report"),
            )
            .expect("import preview report serializes")
        );

        fs::remove_dir_all(root).expect("temp dir removed");
    }

    #[test]
    fn message_framing_round_trips() {
        let message = json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "ping"
        });
        let mut bytes = Vec::new();
        write_message(&mut bytes, &message).expect("message written");

        let mut reader = BufReader::new(std::io::Cursor::new(bytes));
        let payload = read_message(&mut reader)
            .expect("message read")
            .expect("payload present");
        let decoded: Value = serde_json::from_slice(&payload).expect("payload decodes");
        assert_eq!(decoded, message);
    }

    fn call_tool(name: &str, arguments: Value) -> Value {
        let (mut state, _) = initialized_state();
        handle_request(
            &mut state,
            request(
                2,
                "tools/call",
                json!({
                    "name": name,
                    "arguments": arguments
                }),
            ),
        )
        .expect("tool call responds")
    }

    fn initialized_state() -> (ServerState, Value) {
        let mut state = ServerState::default();
        let init_response = handle_request(
            &mut state,
            request(
                1,
                "initialize",
                json!({
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": { "name": "test", "version": "0" }
                }),
            ),
        )
        .expect("initialize responds");
        handle_request(
            &mut state,
            notification("notifications/initialized", json!({})),
        );
        (state, init_response)
    }

    fn request(id: i64, method: &str, params: Value) -> JsonRpcRequest {
        JsonRpcRequest {
            jsonrpc: JSONRPC_VERSION.into(),
            id: Some(Value::Number(id.into())),
            method: method.into(),
            params,
        }
    }

    fn notification(method: &str, params: Value) -> JsonRpcRequest {
        JsonRpcRequest {
            jsonrpc: JSONRPC_VERSION.into(),
            id: None,
            method: method.into(),
            params,
        }
    }

    fn temp_dir(label: &str) -> PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock works")
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "dotrepo-mcp-{}-{}-{}",
            label,
            std::process::id(),
            unique
        ));
        fs::create_dir_all(&path).expect("temp dir created");
        path
    }

    fn write_native_parity_repo(root: &Path) {
        fs::write(
            root.join(".repo"),
            r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[record.trust]
confidence = "high"
provenance = ["declared", "verified"]
notes = "Maintainer-controlled source of truth."

[repo]
name = "orbit"
description = "Fast local-first sync engine"
build = "cargo build"
test = "cargo test"

[owners]
security_contact = "security@example.com"

[readme]
title = "Orbit"
sections = ["overview", "security"]

[compat.github]
codeowners = "skip"
security = "skip"
contributing = "skip"
pull_request_template = "skip"
"#,
        )
        .expect("manifest written");

        let document = dotrepo_core::load_manifest_document(root).expect("manifest loads");
        let outputs = dotrepo_core::managed_outputs(root, &document.manifest, &document.raw)
            .expect("outputs");
        for (path, contents) in outputs {
            if let Some(parent) = path.parent() {
                fs::create_dir_all(parent).expect("output parent exists");
            }
            fs::write(path, contents).expect("output written");
        }
    }
}
