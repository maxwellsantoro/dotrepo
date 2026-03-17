# Changelog

## 1.0.0 - 2026-03-16

First stable release of the dotrepo protocol, reference toolchain, and public index.

### Protocol

- Canonical in-repo `.repo` format with schema `dotrepo/v0.1`, plus overlay records for the public index
- Trust and status ladder across draft, imported, inferred, reviewed, verified, and canonical records
- Provenance-aware conflict surfacing and selection reporting
- Maintainer claim lifecycle with append-only event history and correction support

### Toolchain

- `dotrepo` CLI for init, import, validate, query, generate, doctor, trust, validate-index, public export, claim-init, claim-event, and claim inspection
- `dotrepo-lsp` stdio language server for `.repo` and overlay records
- `dotrepo-mcp` stdio MCP server exposing trust-aware repository tools
- `dotrepo-vscode` thin VS Code extension shell over the CLI and LSP

### Public Surface

- Hosted static `public/v0/` JSON tree with repository summary, trust, and inventory responses
- Freshness metadata with snapshot digest and staleness hints on every response
- Public API version `v0`, intentionally decoupled from the release version
- GitHub Pages deployment from the same exported tree used for local review and CI

### Index

- Seed index with reviewed overlay entries for ripgrep, cli/cli, bat, fd, and ries-rs
- Live accepted maintainer claim for `github.com/maxwellsantoro/ries-rs` with canonical handoff to the upstream native `.repo`
- Evidence and review documentation for all checked-in index entries
- Operator workflow for claim review, correction, and public export

### Release Discipline

- Release gate that packages the hosted public tree, install bundles, and VS Code asset from one reproducible flow
- Smoke-tested release bundles for `dotrepo`, `dotrepo-lsp`, and `dotrepo-mcp`
- Claim-aware operator-gate artifacts and public export regression coverage
