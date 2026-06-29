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
| `dotrepo-lsp` | Monolithic `main.rs` (~2.5k lines); module extraction planned |
| `dotrepo-crawler` | Documented in [`crates/dotrepo-crawler/README.md`](../crates/dotrepo-crawler/README.md) |

## Targeted refactors

1. **LSP module split** — extract diagnostics, completions, and document sync into focused modules without changing stdio behavior.
2. **MCP tools module** — move remaining tool handlers out of `main.rs` once LSP split establishes the pattern.
3. **Facade test domains** — keep one concern per file; run a single domain with `cargo test -p dotrepo-core --lib tests::<domain>`.

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