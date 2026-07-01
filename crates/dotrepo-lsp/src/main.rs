//! `dotrepo-lsp`: a stdio JSON-RPC language server for `.repo` / `record.toml`
//! manifests.
//!
//! This binary is a thin entry point over focused modules:
//! - [`protocol`]: JSON-RPC / LSP wire message and type definitions.
//! - [`state`]: server state, open-document tracking, and the
//!   byte/UTF-16-aware `DocumentIndex` used to map manifest paths to ranges.
//! - [`diagnostics`]: diagnostics generation from parsing, validation, and
//!   adoption-status checks.
//! - [`completions`]: completion and hover support driven by the schema
//!   catalog.
//! - [`code_actions`]: quick-fix code actions for adoption-status hints.
//! - [`dispatch`]: JSON-RPC request/notification routing and diagnostics
//!   publishing.
//!
//! `main` and `run` own the stdio read/write loop; all message handling is
//! delegated to [`dispatch::handle_message`].

use anyhow::Result;
use dotrepo_transport::{
    read_jsonrpc_message as read_message, write_jsonrpc_message as write_message,
};
use std::io::{self, BufReader};

mod code_actions;
mod completions;
mod diagnostics;
mod dispatch;
mod protocol;
mod state;

#[cfg(test)]
mod tests;

use dispatch::handle_message;
use state::ServerState;

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
        let outgoing = handle_message(&mut state, &message)?;
        for entry in outgoing {
            write_message(&mut writer, &entry)?;
        }
        if state.exit_requested {
            break;
        }
    }

    Ok(())
}
