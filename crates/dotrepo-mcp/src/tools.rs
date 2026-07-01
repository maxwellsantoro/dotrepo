//! MCP tool schema declarations: name, title, description, and JSON input
//! schema for each `dotrepo.*` tool exposed over `tools/list`.
//!
//! Tool handler bodies live in [`crate::handlers`]; JSON-RPC dispatch lives
//! in [`crate::dispatch`].

use serde_json::{json, Value};

pub(crate) fn tool_definitions() -> Vec<Value> {
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
            "name": "dotrepo.adoption_status",
            "title": "Inspect native adoption readiness",
            "description": "Summarize native-record readiness for validation, claim identity, CI onboarding, and managed-surface drift.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "root": { "type": "string", "description": "Repository root containing the native .repo to inspect." }
                },
                "additionalProperties": false
            }
        }),
        json!({
            "name": "dotrepo.lookup",
            "title": "Lookup hosted public repository",
            "description": "Resolve a repository URL or identity against the hosted public surface and return summary, trust, and query entrypoints without cloning.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "repositoryUrl": { "type": "string", "description": "Repository URL such as https://github.com/owner/repo or a hosted dotrepo repository URL." },
                    "host": { "type": "string", "description": "Repository host when resolving by identity." },
                    "owner": { "type": "string", "description": "Repository owner when resolving by identity." },
                    "repo": { "type": "string", "description": "Repository name when resolving by identity." },
                    "path": { "type": "string", "description": "Optional dot-path to resolve immediately through the hosted query route." },
                    "baseUrl": { "type": "string", "description": "Hosted public origin; defaults to https://dotrepo.org." }
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
