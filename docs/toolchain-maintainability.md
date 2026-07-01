# Reference Toolchain Maintainability

This document tracks structural health of the shipped v0.1 reference
toolchain. Product sequencing lives in [`ROADMAP.md`](../ROADMAP.md).

## Architecture rule

CLI, MCP, and LSP must remain thin transports over `dotrepo-core`. When
adding behavior, extend core first and delegate from the surface crate.

## Current layout

| Area | Status |
|------|--------|
| `dotrepo-core` business logic | Focused modules under `src/`; public API re-exported from `lib.rs` |
| `dotrepo-core` facade tests | Split into `src/facade_tests/` by domain (selection, public, claims, import, surfaces, validation, relations) |
| `dotrepo-mcp` | `lookup.rs` extracted for remote lookup policy and SSRF protections; remaining `main.rs` holds JSON-RPC dispatch and tools |
| `dotrepo-lsp` | Split into `protocol.rs` (JSON-RPC/LSP message and type definitions), `state.rs` (server state, open-document tracking, and the `DocumentIndex` byte/UTF-16 offset mapping), `diagnostics.rs` (parse/validation/adoption-status diagnostics), `completions.rs` (completion and hover support over the schema catalog), `code_actions.rs` (adoption-status quick fixes), and `dispatch.rs` (JSON-RPC request/notification routing); `main.rs` retains only the stdio read/write loop and module wiring |
| `dotrepo-crawler` | Documented in [`crates/dotrepo-crawler/README.md`](../crates/dotrepo-crawler/README.md) |

## Oversized-file dispositions

The roadmap requires a split plan or explicit retain rationale for every
reference-toolchain Rust source file above roughly 1,500 lines. Line counts are
directional and should be refreshed when this table is used to schedule work.

| File | Current disposition |
|------|---------------------|
| `dotrepo-mcp/src/main.rs` | Active after the LSP pattern lands: extract tool schemas and handlers; retain transport startup in `main.rs`. |
| `dotrepo-core/src/public.rs` | Next: split export construction, search/compare/relations responses, and static-file emission into focused modules behind unchanged facade exports. |
| `dotrepo-core/src/import/mod.rs` | Next: reduce to import orchestration and re-exports by moving remaining evidence assembly and field-resolution helpers into focused import modules. |
| `dotrepo-core/src/import/parsing.rs` | Next: split ecosystem-specific parsers from shared candidate normalization and reconciliation. |
| `dotrepo-core/src/import/commands.rs` | Next: separate workflow extraction from command safety and command-ranking policy. |
| `dotrepo-crawler/src/main.rs` | Done: `main.rs` now holds only clap argument/subcommand definitions, `main()`, and top-level dispatch; command execution moved to `src/commands.rs` and report/output rendering moved to `src/report.rs`. |
| `dotrepo-cli/src/tests.rs` | Retain temporarily: this is test-only code with no production navigation cost; split by CLI command domain when the next test family is added. |
| `dotrepo-core/src/facade_tests/import_repository.rs` | Split on next import-fixture expansion into parsing, evidence, escalation, and manifest-assembly test modules. |

New files that cross the threshold must be added here before the maintainability
exit criterion can pass.

## Targeted refactors

1. **MCP tools module** — move remaining tool handlers out of `main.rs` now that the LSP split establishes the pattern.
2. **Core public/import splits** — execute the module boundaries in the table while preserving `dotrepo-core` facade exports.
3. **Crawler command split** — keep orchestration behavior stable while reducing the entrypoint to startup and dispatch.
4. **Facade test domains** — keep one concern per file; run a single domain with `cargo test -p dotrepo-core --lib tests::<domain>`.

## Public API documentation

High-traffic entrypoints (`validate_repository`, `query_repository`,
`trust_repository`) carry rustdoc examples. Expand coverage to batch/public
helpers as those surfaces stabilize.

## Index scale operations

At 613+ overlay records, maintainability includes operational observability:

- `scripts/render_index_growth_status.py` — growth, quality queue, stale freshness
- release-gate baselines — ratcheted profile counts and high-signal floors
- Milestone 4 metrics — refresh latency, stale-record rate, cost per maintained profile

See **Metrics that matter** in [`ROADMAP.md`](../ROADMAP.md) for the full
operational scorecard.
