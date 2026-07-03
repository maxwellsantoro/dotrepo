//! Consolidated tests for the `dotrepo-mcp` stdio JSON-RPC server, covering
//! MCP lifecycle dispatch (`crate::dispatch`), tool handler behavior
//! (`crate::handlers`), and message framing.

use crate::dispatch::{handle_request, JsonRpcRequest, ServerState};
use crate::handlers::write_import_plan;
use crate::test_support::mcp_env_test_lock;
use dotrepo_core::{
    adoption_status_repository, current_timestamp_rfc3339, generate_check_repository,
    import_preview_repository, import_repository_with_options, inspect_claim_directory,
    query_repository, trust_repository, validate_repository, write_import_outputs, ImportMode,
    ImportOptions,
};
use dotrepo_transport::{
    read_jsonrpc_message as read_message, write_jsonrpc_message as write_message, JSONRPC_VERSION,
};
use serde_json::{json, to_value, Value};
use std::fs;
use std::io::{BufReader, Read, Write};
use std::net::TcpListener;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, OnceLock};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

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
        .any(|tool| tool["name"] == Value::String("dotrepo.adoption_status".into())));
    assert!(tools
        .iter()
        .any(|tool| tool["name"] == Value::String("dotrepo.lookup".into())));
    assert!(tools
        .iter()
        .any(|tool| tool["name"] == Value::String("dotrepo.import_preview".into())));
    assert!(tools
        .iter()
        .any(|tool| tool["name"] == Value::String("dotrepo.claim_inspect".into())));
}

#[test]
fn validate_tool_rejects_relative_root_escape() {
    let _cwd_guard = cwd_test_lock().lock().expect("cwd test lock");
    let workspace = temp_dir("root-escape-workspace");
    let outside = temp_dir("root-escape-outside");
    fs::write(
        outside.join(".repo"),
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
    .expect("outside manifest written");

    let previous = std::env::current_dir().unwrap_or_else(|e| panic!("cwd: {e}"));
    std::env::set_current_dir(&workspace).expect("chdir into workspace");

    let outside_name = outside
        .file_name()
        .and_then(|name| name.to_str())
        .expect("outside dir name");
    let response = call_tool(
        "dotrepo.validate",
        json!({
            "root": format!("../{outside_name}")
        }),
    );

    std::env::set_current_dir(&previous).expect("restore cwd");
    fs::remove_dir_all(workspace).expect("workspace removed");
    fs::remove_dir_all(outside).expect("outside removed");

    assert_eq!(response["result"]["isError"], Value::Bool(true));
    assert!(response["result"]["structuredContent"]["error"]
        .as_str()
        .expect("error text")
        .contains("working directory"));
}

#[test]
fn validate_tool_rejects_absolute_root_without_opt_in() {
    let unique = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("clock works")
        .as_nanos();
    let root = std::env::temp_dir().join(format!(
        "dotrepo-mcp-absolute-root-{}-{}",
        std::process::id(),
        unique
    ));
    fs::create_dir_all(&root).expect("temp dir created");
    fs::write(
        root.join(".repo"),
        r#"
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "draft"

[repo]
name = "orbit"
description = "Fast local-first sync engine"
"#,
    )
    .expect("manifest written");

    let absolute = root.canonicalize().expect("canonical root");
    let _env_guard = env_test_lock().lock().expect("env test lock");
    std::env::remove_var("DOTREPO_MCP_ALLOW_ABSOLUTE_ROOT");
    let (mut state, _) = initialized_state();
    let response = handle_request(
        &mut state,
        request(
            2,
            "tools/call",
            json!({
                "name": "dotrepo.validate",
                "arguments": {
                    "root": absolute.display().to_string()
                }
            }),
        ),
    )
    .expect("tool call responds");

    fs::remove_dir_all(root).expect("temp dir removed");

    assert_eq!(response["result"]["isError"], Value::Bool(true));
    assert!(response["result"]["structuredContent"]["error"]
        .as_str()
        .expect("error text")
        .contains("DOTREPO_MCP_ALLOW_ABSOLUTE_ROOT"));
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
    .unwrap_or_else(|e| panic!("manifest written: {e}"));

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

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
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

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
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
    .unwrap_or_else(|e| panic!("manifest written: {e}"));

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

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
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
        Value::String("server must receive notifications/initialized before calling tools".into())
    );
}

#[test]
fn validate_accepts_missing_repository_subdirectory() {
    let cwd = std::env::current_dir().expect("cwd available");
    let parent = cwd.join(format!(
        "dotrepo-mcp-validate-missing-root-{}-{}",
        std::process::id(),
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock works")
            .as_nanos()
    ));
    let root = parent.join("nested/new-repo");
    fs::create_dir_all(parent.join("nested")).expect("parent nested dir created");
    let relative = root
        .strip_prefix(&cwd)
        .expect("path stays within cwd")
        .to_str()
        .expect("utf-8 path");

    let response = call_tool(
        "dotrepo.validate",
        json!({
            "root": relative
        }),
    );
    assert_ne!(response["result"]["isError"], Value::Bool(true));
    let structured = &response["result"]["structuredContent"];
    assert_eq!(structured["valid"], Value::Bool(false));
    assert!(
        structured["diagnostics"]
            .as_array()
            .expect("diagnostics array")
            .iter()
            .any(|diagnostic| diagnostic["message"]
                .as_str()
                .is_some_and(|message| message.contains("no .repo or record.toml"))),
        "expected missing-manifest diagnostics, not root resolution failure"
    );

    fs::remove_dir_all(parent).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
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

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
}

#[test]
fn write_import_output_refuses_to_clobber_existing_file_without_force() {
    let root = temp_dir("import-write-helper");
    let path = root.join(".repo");
    fs::write(&path, "existing\n").expect("existing file written");

    let err = write_import_outputs(
        vec![(path.clone(), "replacement\n".into())],
        false,
        "force=true",
    )
    .expect_err("existing file should be preserved");
    assert!(err.to_string().contains("already exists"));
    assert_eq!(
        fs::read_to_string(&path).expect("file readable"),
        "existing\n"
    );

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
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
            github: None,
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

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
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
        to_value(trust_repository(&root).expect("trust report")).expect("trust report serializes")
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

    let adoption = call_tool(
        "dotrepo.adoption_status",
        json!({ "root": root.display().to_string() }),
    );
    assert_eq!(
        adoption["result"]["structuredContent"],
        to_value(adoption_status_repository(&root)).expect("adoption report serializes")
    );

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
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

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
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

    fs::remove_dir_all(root).unwrap_or_else(|e| panic!("temp dir removed: {e}"));
}

#[test]
fn lookup_tool_fetches_hosted_summary_trust_and_query() {
    let _env_guard = env_test_lock().lock().expect("env test lock");
    // SAFETY: test-only env flags for the local mock HTTP server.
    unsafe {
        std::env::set_var("DOTREPO_MCP_ALLOW_CUSTOM_BASE_URL", "1");
        std::env::set_var("DOTREPO_MCP_UNSAFE_ALLOW_LOCAL_BASE_URL", "1");
    }

    let routes = vec![
        (
            "/v0/meta.json",
            json!({
                "apiVersion": "v0",
                "generatedAt": "2026-04-18T03:02:00Z",
                "snapshotDigest": "abc123",
                "staleAfter": "2026-04-19T03:02:00Z",
                "strategy": "content_addressed_summary_trust_and_profile",
                "snapshotId": "abc123",
                "paths": {
                    "root": "/v0/snapshots/abc123",
                    "inventory": "/v0/snapshots/abc123/repos/index.json",
                    "files": "/v0/snapshots/abc123/files.json",
                    "queryInputRoot": "/v0/snapshots/abc123/query-input/",
                },
            }),
        ),
        (
            "/v0/snapshots/abc123/repos/github.com/example/orbit/index.json",
            json!({
                "apiVersion": "v0",
                "freshness": {
                    "generatedAt": "2026-04-18T03:02:00Z",
                    "snapshotDigest": "abc123",
                    "staleAfter": "2026-04-19T03:02:00Z",
                },
                "identity": {
                    "host": "github.com",
                    "owner": "example",
                    "repo": "orbit",
                    "source": "https://github.com/example/orbit",
                },
                "repository": {
                    "name": "orbit",
                    "description": "Fast local-first sync engine",
                },
                "selection": {
                    "reason": "only_matching_record",
                    "record": {
                        "manifestPath": "repos/github.com/example/orbit/record.toml",
                        "record": {
                            "mode": "overlay",
                            "status": "reviewed",
                        },
                    },
                },
                "conflicts": [],
                "links": {
                    "self": "/v0/repos/github.com/example/orbit/index.json",
                    "trust": "/v0/repos/github.com/example/orbit/trust.json",
                    "queryTemplate": "/v0/repos/github.com/example/orbit/query?path={dot_path}",
                    "indexPath": "repos/github.com/example/orbit/",
                },
            }),
        ),
        (
            "/v0/snapshots/abc123/repos/github.com/example/orbit/trust.json",
            json!({
                "apiVersion": "v0",
                "freshness": {
                    "generatedAt": "2026-04-18T03:02:00Z",
                    "snapshotDigest": "abc123",
                    "staleAfter": "2026-04-19T03:02:00Z",
                },
                "identity": {
                    "host": "github.com",
                    "owner": "example",
                    "repo": "orbit",
                    "source": "https://github.com/example/orbit",
                },
                "selection": {
                    "reason": "only_matching_record",
                    "record": {
                        "manifestPath": "repos/github.com/example/orbit/record.toml",
                        "record": {
                            "mode": "overlay",
                            "status": "reviewed",
                        },
                    },
                },
                "conflicts": [],
                "links": {
                    "self": "/v0/repos/github.com/example/orbit/trust.json",
                    "repository": "/v0/repos/github.com/example/orbit/index.json",
                    "queryTemplate": "/v0/repos/github.com/example/orbit/query?path={dot_path}",
                    "indexPath": "repos/github.com/example/orbit/",
                },
            }),
        ),
        (
            "/v0/repos/github.com/example/orbit/query?path=repo.description",
            json!({
                "apiVersion": "v0",
                "freshness": {
                    "generatedAt": "2026-04-18T03:02:00Z",
                    "snapshotDigest": "abc123",
                    "staleAfter": "2026-04-19T03:02:00Z",
                },
                "identity": {
                    "host": "github.com",
                    "owner": "example",
                    "repo": "orbit",
                    "source": "https://github.com/example/orbit",
                },
                "path": "repo.description",
                "value": "Fast local-first sync engine",
                "selection": {
                    "reason": "only_matching_record",
                    "record": {
                        "manifestPath": "repos/github.com/example/orbit/record.toml",
                        "record": {
                            "mode": "overlay",
                            "status": "reviewed",
                        },
                    },
                },
                "conflicts": [],
                "links": {
                    "self": "/v0/repos/github.com/example/orbit/query?path=repo.description",
                    "repository": "/v0/repos/github.com/example/orbit/index.json",
                    "trust": "/v0/repos/github.com/example/orbit/trust.json",
                    "queryTemplate": "/v0/repos/github.com/example/orbit/query?path={dot_path}",
                    "indexPath": "repos/github.com/example/orbit/",
                },
            }),
        ),
    ];
    let (_server, base_url) = start_json_server(routes);

    let response = call_tool_unlocked(
        "dotrepo.lookup",
        json!({
            "repositoryUrl": "https://github.com/example/orbit",
            "path": "repo.description",
            "baseUrl": base_url,
        }),
    );
    let structured = &response["result"]["structuredContent"];
    assert_eq!(
        structured["identity"],
        json!({
            "host": "github.com",
            "owner": "example",
            "repo": "orbit",
        })
    );
    assert_eq!(
        structured["lookup"]["source"],
        Value::String("repository_url".into())
    );
    assert_eq!(
        structured["query"]["value"],
        Value::String("Fast local-first sync engine".into())
    );
    assert_eq!(
        structured["links"]["queryTemplate"],
        Value::String("/v0/repos/github.com/example/orbit/query?path={dot_path}".into())
    );
    assert_eq!(
        structured["summary"]["repository"]["name"],
        Value::String("orbit".into())
    );
    assert_eq!(
        structured["links"]["inventory"],
        Value::String(format!("{base_url}/v0/snapshots/abc123/repos/index.json"))
    );
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
    let _env_guard = env_test_lock().lock().expect("env test lock");
    call_tool_unlocked(name, arguments)
}

fn call_tool_unlocked(name: &str, arguments: Value) -> Value {
    // SAFETY: test-only env flag for local repository roots.
    unsafe {
        std::env::set_var("DOTREPO_MCP_ALLOW_ABSOLUTE_ROOT", "1");
    }
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

fn cwd_test_lock() -> &'static Mutex<()> {
    static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
    LOCK.get_or_init(|| Mutex::new(()))
}

fn env_test_lock() -> &'static Mutex<()> {
    mcp_env_test_lock()
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
    .unwrap_or_else(|e| panic!("manifest written: {e}"));

    let document = dotrepo_core::load_manifest_document(root).expect("manifest loads");
    let outputs =
        dotrepo_core::managed_outputs(root, &document.manifest, &document.raw).expect("outputs");
    for (path, contents) in outputs {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).expect("output parent exists");
        }
        fs::write(path, contents).expect("output written");
    }
}

struct TestServer {
    join: Option<thread::JoinHandle<()>>,
    shutdown: Arc<AtomicBool>,
}

impl Drop for TestServer {
    fn drop(&mut self) {
        self.shutdown.store(true, Ordering::Relaxed);
        if let Some(join) = self.join.take() {
            join.join().expect("server thread joins");
        }
    }
}

fn start_json_server(routes: Vec<(&'static str, Value)>) -> (TestServer, String) {
    let listener = TcpListener::bind("127.0.0.1:0").expect("listener binds");
    listener
        .set_nonblocking(true)
        .expect("listener can be nonblocking");
    let address = listener.local_addr().expect("listener address");
    let shutdown = Arc::new(AtomicBool::new(false));
    let thread_shutdown = Arc::clone(&shutdown);
    let routes = routes
        .into_iter()
        .map(|(path, body)| {
            (
                path.to_string(),
                serde_json::to_string(&body).expect("route JSON serializes"),
            )
        })
        .collect::<Vec<_>>();
    let expected_requests = routes.len();
    let handle = thread::spawn(move || {
        let mut handled_requests = 0;
        while handled_requests < expected_requests && !thread_shutdown.load(Ordering::Relaxed) {
            let (mut stream, _) = match listener.accept() {
                Ok(accepted) => accepted,
                Err(err) if err.kind() == std::io::ErrorKind::WouldBlock => {
                    thread::sleep(Duration::from_millis(10));
                    continue;
                }
                Err(err) => panic!("client connects: {err}"),
            };
            stream
                .set_nonblocking(false)
                .expect("accepted stream can block for reads");
            handled_requests += 1;
            let mut buffer = [0_u8; 4096];
            let mut bytes_read = 0;
            let read_deadline = Duration::from_secs(5);
            let read_started = std::time::Instant::now();
            while bytes_read == 0 {
                match stream.read(&mut buffer) {
                    Ok(0) => panic!("client disconnected before sending request"),
                    Ok(n) => bytes_read = n,
                    Err(err) if err.kind() == std::io::ErrorKind::WouldBlock => {
                        if read_started.elapsed() >= read_deadline {
                            panic!("timed out waiting for request bytes");
                        }
                        thread::sleep(Duration::from_millis(10));
                    }
                    Err(err) => panic!("request readable: {err}"),
                }
            }
            let request = String::from_utf8_lossy(&buffer[..bytes_read]);
            let request_line = request.lines().next().expect("request line");
            let path = request_line
                .split_whitespace()
                .nth(1)
                .expect("request path")
                .to_string();
            let body = routes
                .iter()
                .find(|(candidate, _)| *candidate == path)
                .map(|(_, body)| body.clone());
            let (status_line, response_body) = if let Some(body) = body {
                ("HTTP/1.1 200 OK", body)
            } else {
                (
                    "HTTP/1.1 404 Not Found",
                    serde_json::to_string(&json!({ "error": "not found" }))
                        .expect("404 serializes"),
                )
            };
            let response = format!(
                "{status_line}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                response_body.len(),
                response_body
            );
            stream
                .write_all(response.as_bytes())
                .expect("response written");
        }
    });
    (
        TestServer {
            join: Some(handle),
            shutdown,
        },
        format!("http://{}", address),
    )
}
