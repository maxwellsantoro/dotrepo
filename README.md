# dotrepo

**dotrepo** is an open metadata protocol for software repositories, with a reference toolchain and a public index.

It is designed to help three sides at once:
- **maintainers** get a cleaner, more reliable way to describe and maintain repository metadata
- **users** get better discovery and a more consistent understanding of projects
- **agents and tools** get a structured way to query repository information instead of inferring it from scattered conventions and prose

The goal is not to replace the character of projects or flatten their documentation into machine sludge. The goal is to create a shared, trustworthy metadata layer that makes repositories easier to understand and work with, while respecting the source materials they come from.

## What dotrepo is

At day one, dotrepo has three inseparable parts:

1. **A protocol**
   A versioned `.repo` schema for essential repository metadata, provenance, trust, and synchronization hints.
2. **A reference toolchain**
   A Rust CLI, stdio MCP server, and related integrations for importing, validating, querying, syncing, and generating compatible repository surfaces.
3. **An index**
   A public, Git-backed collection of canonical records and overlays that makes public repositories mechanically visible whether or not maintainers have adopted dotrepo yet.

## Why now

Repository metadata is fragmented. Some facts live in README files. Some live in `CODEOWNERS`, `SECURITY.md`, CI config, or platform settings. Some are nowhere except tribal knowledge.

That is annoying for maintainers, confusing for users, and expensive for coding agents. Today, basic questions like these often require heuristics or LLM interpretation:
- What is this repo?
- Who owns it?
- How do I build and test it?
- Where are the real docs?
- What policies or constraints apply?

A structured `.repo` record does not replace code or good documentation. It provides a stable layer of essential facts that humans can maintain and machines can query directly.

## Core principles

- **Protocol first**: dotrepo is a shared metadata protocol, not just a CLI.
- **Trust matters**: all records should communicate provenance and trust level clearly.
- **Respect the source**: overlays must distinguish declared facts, imported facts, and inferred facts.
- **Useful before adoption**: the index and overlay model make dotrepo valuable even for repos that do not use it natively.
- **Practical, not doctrinaire**: dotrepo should work with existing files and conventions, not demand an all-or-nothing migration.
- **Machine-readable, human-legible**: the protocol should help agents and tools without making projects feel sterile.

## Current protocol decisions

- **Canonical in-repo v0.1 form**: a single root `.repo` file in TOML format
- **Bundle mode**: reserved for a future version
- **Overlay records**: separate TOML records in the index, with explicit provenance and trust metadata
- **Query support**: first-class CLI support for querying structured fields
- **Mode-aware validation**: native records and overlays validate differently
- **Generated outputs**: supported, but not the sole editing surface
- **Extension namespace**: `x.*` is reserved for non-core extensions
- **Future workspace support**: relations are reserved now so repos do not become permanent islands

## What the repo includes today

- a Rust workspace with `dotrepo-schema`, `dotrepo-core`, `dotrepo-cli`, `dotrepo-mcp`, `dotrepo-lsp`, and the shared internal `dotrepo-transport`
- a thin VS Code extension shell under [`editors/vscode/`](editors/vscode/)
- a thin import path for bootstrapping records from `README.md`, `CODEOWNERS`, and `SECURITY.md`
- a thin stdio MCP server exposing trust-aware validate/query/trust/generate-check/import tools
- updated RFCs that reflect the protocol + toolchain + index model
- example native and overlay records
- a seeded `index/` tree with real overlay layout and validation rules
- GitHub Actions workflows for workspace CI, operator-gate claim checks,
  release-gate packaging, and Pages deployment
- public-facing docs with a balanced tone around ambition, safety, and practicality

## What dotrepo does not claim yet

This repo ships the current dotrepo protocol and reference toolchain surface.
The crates implement import, validation, querying, generated-surface checks,
index validation, claims, public export, and an MCP server.

What remains intentionally out of scope for the current release is broader
post-`1.0` product surface such as search and ranking UX, mutation APIs, bundle
mode, first-class workspace and relations support, richer editor automation,
and arbitrary prose round-tripping.

## First docs to read

- [`PLAN.md`](PLAN.md)
- [`docs/install.md`](docs/install.md)
- [`docs/maintainer-happy-path.md`](docs/maintainer-happy-path.md)
- [`docs/current-status.md`](docs/current-status.md)
- [`docs/v1-go-no-go.md`](docs/v1-go-no-go.md)
- [`docs/vision.md`](docs/vision.md)
- [`docs/public-messaging.md`](docs/public-messaging.md)
- [`docs/trust-model.md`](docs/trust-model.md)
- [`docs/sync-boundaries.md`](docs/sync-boundaries.md)
- [`docs/public-export-workflow.md`](docs/public-export-workflow.md)
- [`docs/public-api-compatibility.md`](docs/public-api-compatibility.md)
- [`docs/public-release-note.md`](docs/public-release-note.md)
- [`docs/public-surface.md`](docs/public-surface.md)
- [`docs/public-export-examples.md`](docs/public-export-examples.md)
- [`docs/authority-handoff-examples.md`](docs/authority-handoff-examples.md)
- [`docs/conflict-surfacing-examples.md`](docs/conflict-surfacing-examples.md)
- [`docs/maintainer-claim-review-workflow.md`](docs/maintainer-claim-review-workflow.md)
- [`index/README.md`](index/README.md)
- [`rfcs/0001-protocol-and-ecosystem.md`](rfcs/0001-protocol-and-ecosystem.md)
- [`rfcs/0004-index-and-trust-model.md`](rfcs/0004-index-and-trust-model.md)
- [`rfcs/0003-cli-and-query-contract.md`](rfcs/0003-cli-and-query-contract.md)
- [`rfcs/0006-mcp-server-contract.md`](rfcs/0006-mcp-server-contract.md)
- [`rfcs/0007-lsp-and-vscode-scope.md`](rfcs/0007-lsp-and-vscode-scope.md)
- [`rfcs/0016-public-index-site-and-query-api.md`](rfcs/0016-public-index-site-and-query-api.md)
- [`rfcs/0017-public-repository-summary-response.md`](rfcs/0017-public-repository-summary-response.md)
- [`rfcs/0018-static-public-serving-and-freshness.md`](rfcs/0018-static-public-serving-and-freshness.md)
- [`rfcs/0019-public-trust-and-query-wrappers.md`](rfcs/0019-public-trust-and-query-wrappers.md)
- [`editors/vscode/README.md`](editors/vscode/README.md)
