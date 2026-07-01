//! `dotrepo-mcp`: a stdio JSON-RPC MCP server exposing dotrepo manifest
//! tools.
//!
//! This binary is a thin entry point over focused modules:
//! - [`lookup`]: remote `dotrepo.lookup` policy, URL normalization, and SSRF
//!   protections.
//! - [`tools`]: MCP tool schema declarations (name, description, JSON input
//!   schema) for each `dotrepo.*` tool.
//! - [`handlers`]: tool handler bodies that execute each tool by calling
//!   into `dotrepo-core` and [`lookup`].
//! - [`dispatch`]: JSON-RPC request/notification routing and MCP lifecycle
//!   (`initialize`, `tools/list`, `tools/call`).
//!
//! `main` and `run` own the stdio read/write loop; all message handling is
//! delegated to [`dispatch::handle_request`].

use anyhow::Result;
use dotrepo_transport::{
    jsonrpc_error_response, read_jsonrpc_message as read_message,
    write_jsonrpc_message as write_message,
};
use std::io::{self, BufReader};

mod dispatch;
mod handlers;
mod lookup;
mod tools;

#[cfg(test)]
mod tests;

use dispatch::{handle_request, ServerState};

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
        let request = match serde_json::from_slice::<dispatch::JsonRpcRequest>(&message) {
            Ok(request) => request,
            Err(err) => {
                write_message(
                    &mut writer,
                    &jsonrpc_error_response(
                        serde_json::Value::Null,
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
