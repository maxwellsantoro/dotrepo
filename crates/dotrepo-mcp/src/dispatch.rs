//! JSON-RPC dispatch: request/notification routing, MCP lifecycle
//! (`initialize`, `notifications/initialized`), and `tools/list` /
//! `tools/call` handling.
//!
//! The stdio read/write loop itself lives in `main.rs`; this module only
//! covers per-message handling. Tool schema declarations live in
//! [`crate::tools`] and tool handler bodies live in [`crate::handlers`].

use crate::handlers::{
    tool_adoption_status, tool_claim_inspect, tool_generate_check, tool_import_preview,
    tool_import_write, tool_lookup, tool_query, tool_trust, tool_validate,
};
use crate::tools::tool_definitions;
use anyhow::{anyhow, bail, Result};
use dotrepo_transport::{jsonrpc_error_response, jsonrpc_response, JSONRPC_VERSION};
use serde::Deserialize;
use serde_json::{json, Value};

const SUPPORTED_PROTOCOL_VERSIONS: &[&str] = &["2025-11-25", "2025-06-18", "2024-11-05"];
const SERVER_NAME: &str = "dotrepo-mcp";

#[derive(Debug, Default)]
pub(crate) struct ServerState {
    pub(crate) initialized: bool,
    pub(crate) protocol_version: Option<&'static str>,
}

#[derive(Debug, Deserialize)]
pub(crate) struct JsonRpcRequest {
    pub(crate) jsonrpc: String,
    #[serde(default)]
    pub(crate) id: Option<Value>,
    pub(crate) method: String,
    #[serde(default)]
    pub(crate) params: Value,
}

pub(crate) fn handle_request(state: &mut ServerState, request: JsonRpcRequest) -> Option<Value> {
    if request.jsonrpc != JSONRPC_VERSION {
        return request.id.map(|id| {
            jsonrpc_error_response(
                id,
                -32600,
                format!("unsupported jsonrpc version: {}", request.jsonrpc),
                None,
            )
        });
    }

    let JsonRpcRequest {
        id, method, params, ..
    } = request;

    let Some(id) = id else {
        handle_notification(state, method, params);
        return None;
    };

    let result = match dispatch_request(state, &method, params) {
        Ok(result) => jsonrpc_response(id, result),
        Err(err) => jsonrpc_error_response(id, -32603, err.to_string(), None),
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
        "instructions": "Use dotrepo.query for trust-aware field lookups, dotrepo.trust for record provenance, dotrepo.adoption_status for native maintainer readiness, and dotrepo.import_preview before dotrepo.import_write."
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
        "dotrepo.adoption_status" => tool_adoption_status(arguments),
        "dotrepo.lookup" => tool_lookup(arguments),
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

fn structured_tool_text(summary: &str, structured: &Value) -> String {
    match serde_json::to_string_pretty(structured) {
        Ok(body) => format!("{summary}\n\n{body}"),
        Err(err) => format!("{summary}\n\n(structured content unavailable: {err})"),
    }
}

fn tool_success(summary: String, structured: Value) -> Value {
    let text = structured_tool_text(&summary, &structured);
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
    let text = structured_tool_text(&summary, &structured);
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
