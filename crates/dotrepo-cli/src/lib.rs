pub mod cli;
pub mod commands;
pub mod error;
pub mod format;

#[cfg(test)]
mod tests;

use anyhow::Result;
use clap::Parser;
use cli::{Cli, Command};
use commands::{
    cmd_adopt_overlay, cmd_adoption_status, cmd_ci, cmd_claim, cmd_claim_event, cmd_claim_init,
    cmd_doctor, cmd_generate, cmd_import, cmd_init, cmd_manage, cmd_preview, cmd_promotion_report,
    cmd_public, cmd_query, cmd_trust, cmd_validate, cmd_validate_index, ClaimAcceptNativeArgs,
    ClaimEventArgs, ClaimFromNativeArgs, ClaimInitArgs, ClaimSubmitNativeArgs,
};
use error::CliExit;
use std::process;

/// Shared CLI entrypoint for the workspace `dotrepo` binary and the installable
/// `dotrepo` alias package. Both binaries must call this so subcommand dispatch
/// cannot drift.
pub fn run() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::Init { force } => cmd_init(cli.root, force),
        Command::Import {
            mode,
            source,
            force,
        } => cmd_import(cli.root, mode, source, force),
        Command::AdoptOverlay {
            overlay_record,
            force,
        } => cmd_adopt_overlay(cli.root, overlay_record, force),
        Command::Validate => cmd_validate(cli.root),
        Command::ValidateIndex { index_root } => cmd_validate_index(index_root),
        Command::PromotionReport {
            index_root,
            apply,
            limit,
            json,
            verbose,
        } => cmd_promotion_report(index_root, apply, limit, json, verbose),
        Command::Query { path, json, raw } => cmd_query(cli.root, &path, json, raw),
        Command::Generate { check } => cmd_generate(cli.root, check),
        Command::Doctor { json } => cmd_doctor(cli.root, json),
        Command::Manage { surface, adopt } => cmd_manage(cli.root, surface, adopt),
        Command::Preview { surface, all, json } => cmd_preview(cli.root, surface, all, json),
        Command::Trust { json } => cmd_trust(cli.root, json),
        Command::AdoptionStatus { json } => cmd_adoption_status(cli.root, json),
        Command::Ci { command } => cmd_ci(cli.root, command),
        Command::Claim { path, json } => cmd_claim(cli.root, path, json),
        Command::ClaimInit {
            host,
            owner,
            repo,
            claim_id,
            claimant_name,
            asserted_role,
            contact,
            record_sources,
            canonical_repo_url,
            review_md,
            force,
        } => cmd_claim_init(
            cli.root,
            ClaimInitArgs {
                host,
                owner,
                repo,
                claim_id,
                claimant_name,
                asserted_role,
                contact,
                record_sources,
                canonical_repo_url,
                review_md,
                force,
            },
        ),
        Command::ClaimFromNative {
            index_root,
            claim_id,
            claimant_name,
            asserted_role,
            contact,
            review_md,
            force,
        } => commands::cmd_claim_from_native(
            cli.root,
            ClaimFromNativeArgs {
                index_root,
                claim_id,
                claimant_name,
                asserted_role,
                contact,
                review_md,
                force,
            },
        ),
        Command::ClaimEvent {
            path,
            kind,
            actor,
            summary,
            corrected_state,
            canonical_record_path,
            canonical_mirror_path,
        } => cmd_claim_event(
            cli.root,
            ClaimEventArgs {
                path,
                kind,
                actor,
                summary,
                corrected_state,
                canonical_record_path,
                canonical_mirror_path,
            },
        ),
        Command::ClaimSubmitNative {
            index_root,
            claim_id,
            actor,
            summary,
        } => commands::cmd_claim_submit_native(
            cli.root,
            ClaimSubmitNativeArgs {
                index_root,
                claim_id,
                actor,
                summary,
            },
        ),
        Command::ClaimAcceptNative {
            index_root,
            path,
            claim_id,
            actor,
            summary,
        } => commands::cmd_claim_accept_native(
            cli.root,
            ClaimAcceptNativeArgs {
                index_root,
                path,
                claim_id,
                actor,
                summary,
            },
        ),
        Command::Public { command } => cmd_public(command),
    }
}

/// Process entry used by both `dotrepo-cli` and the installable `dotrepo` alias.
pub fn main() {
    if let Err(err) = run() {
        if let Some(err) = err.downcast_ref::<CliExit>() {
            if !err.message.is_empty() {
                eprintln!("{}", err.message);
            }
            process::exit(err.code);
        }
        eprintln!("{err}");
        process::exit(1);
    }
}
