# Reference Toolchain Maintainability

This document tracks structural health of the shipped v0.1 reference
toolchain. Product sequencing lives in [`ROADMAP.md`](../ROADMAP.md).

## Architecture rule

CLI, MCP, and LSP must remain thin transports over `dotrepo-core`. When
adding behavior, extend core first and delegate from the surface crate.

## Current layout

| Area | Status |
|------|--------|
| `dotrepo-core` business logic | Focused modules under `src/`; public API re-exported from `lib.rs`. `public.rs` is further split into `src/public/{mod,types,profile,search,compare,relations,export,error}.rs` behind unchanged facade exports |
| `dotrepo-core` facade tests | Split into `src/facade_tests/` by domain (selection, public, claims, import, surfaces, validation, relations) |
| `dotrepo-mcp` | `lookup.rs` (remote lookup policy and SSRF protections), `tools.rs` (MCP tool schema declarations), `handlers.rs` (tool handler bodies calling into `dotrepo-core`/`lookup`), `dispatch.rs` (JSON-RPC request/notification routing and MCP lifecycle); `main.rs` reduced to module wiring plus the stdio `main()`/`run()` loop |
| `dotrepo-lsp` | Split into `protocol.rs` (JSON-RPC/LSP message and type definitions), `state.rs` (server state, open-document tracking, and the `DocumentIndex` byte/UTF-16 offset mapping), `diagnostics.rs` (parse/validation/adoption-status diagnostics), `completions.rs` (completion and hover support over the schema catalog), `code_actions.rs` (adoption-status quick fixes), and `dispatch.rs` (JSON-RPC request/notification routing); `main.rs` retains only the stdio read/write loop and module wiring |
| `dotrepo-crawler` | Documented in [`crates/dotrepo-crawler/README.md`](../crates/dotrepo-crawler/README.md) |

## Oversized-file dispositions

The roadmap requires a split plan or explicit retain rationale for every
reference-toolchain Rust source file above roughly 1,500 lines. Line counts are
directional and should be refreshed when this table is used to schedule work.

| File | Current disposition |
|------|---------------------|
| `dotrepo-core/src/import/mod.rs` | Done: reduced to import orchestration and re-exports (~1,030 lines). Data types moved to `import/types.rs` (~300 lines); field scoring/adjudication reconciliation moved to `import/fields.rs` (~500 lines); owners/docs/compat construction, evidence.md rendering, and relation discovery moved to `import/evidence.rs` (~650 lines). |
| `dotrepo-core/src/import/parsing.rs` | Done: split into `import/parsing/` (~2,050 lines total, largest file 754 lines). README title/description/name parsing in `readme.rs`; shared markdown/text normalization and link extraction in `markdown.rs`; URL quality gates in `urls.rs`; CODEOWNERS parsing in `codeowners.rs`; security-contact parsing in `security.rs`; `mod.rs` is a thin re-export hub. |
| `dotrepo-core/src/import/commands.rs` | Done: split into `import/commands/` (~1,590 lines total, largest file 814 lines). Ecosystem-specific candidate *extraction* (Cargo/npm/pyproject/setup.py/go.mod/Maven/Gradle/Composer/.csproj/Mix/Rebar/CMake/Makefile/justfile/Rakefile/CONTRIBUTING/workflows) lives in `extraction.rs`; command sanitization and build/test ranking policy (incl. Node package-runner detection) lives in `policy.rs`; `mod.rs` holds file loading and the `infer_imported_commands` orchestration entrypoint. |
| `dotrepo-crawler/src/main.rs` | Done: `main.rs` now holds only clap argument/subcommand definitions, `main()`, and top-level dispatch; command execution moved to `src/commands.rs` and report/output rendering moved to `src/report.rs`. |
| `dotrepo-cli/src/tests.rs` | Retain temporarily: this is test-only code with no production navigation cost; split by CLI command domain when the next test family is added. |
| `dotrepo-core/src/facade_tests/import_repository.rs` | Split on next import-fixture expansion into parsing, evidence, escalation, and manifest-assembly test modules. |
| `dotrepo-core/src/import/escalation.rs` (~1,473 lines) | **Split plan (next change that touches escalation):** extract (1) deterministic command-tier resolution + confidence mapping into `import/escalation/deterministic.rs`, (2) model-tier loop / Absent-vs-Rejected continuation policy into `import/escalation/model_ladder.rs`, (3) report assembly into `import/escalation/report.rs`, leave `mod.rs` as `run_import_escalation` orchestration. Keep public re-exports stable via `import/mod.rs`. Do not mix this with adjudication provider HTTP code. |
| `dotrepo-crawler/src/pipeline.rs` (~1,462 lines) | **Split plan (next pipeline feature):** extract (1) GitHub snapshot merge + identity guards (`homepage_conflicts_with_identity`, language ordering consumers) into `pipeline/merge.rs`, (2) import/verify/score/escalate sequence into `pipeline/factual.rs`, (3) writeback eligibility + downgrade guard wiring into `pipeline/writeback_gate.rs`. Keep `pipeline.rs` (or `pipeline/mod.rs`) as the single `crawl_repository` entry used by commands. |

New files that cross the threshold must be added here before the maintainability
exit criterion can pass.

## Targeted refactors

1. **Facade test domains** — keep one concern per file; run a single domain with `cargo test -p dotrepo-core --lib tests::<domain>`.

The LSP split, MCP tools module split, `public.rs` split, `import/` splits, and
crawler command split are all complete (see the oversized-file dispositions
table above and the "Current layout" table). Facade test domains are the only
remaining item from this list.

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
