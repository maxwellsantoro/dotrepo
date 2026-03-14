# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

dotrepo is an open metadata protocol for software repositories. It has three interlinked deliverables:

1. **A `.repo` schema** — versioned TOML manifests that encode provenance, trust, owners, docs, and build/test metadata
2. **A reference toolchain** — Rust CLI, stdio MCP server, and LSP for importing, validating, querying, syncing, and generating compatible surfaces
3. **A public index** — a Git-backed collection of canonical records at `index/repos/<host>/<owner>/<repo>/record.toml` that makes public repos mechanically visible whether or not maintainers have adopted dotrepo natively

## Commands

```bash
cargo fmt --all -- --check          # Format check (CI enforced)
cargo test --workspace              # Run all tests
cargo build -p <crate-name>        # Build specific crate

# CLI
cargo run -p dotrepo-cli -- --root <path> validate
cargo run -p dotrepo-cli -- --root <path> query repo.name
cargo run -p dotrepo-cli -- --root <path> import --mode native
cargo run -p dotrepo-cli -- --root <path> generate --check
cargo run -p dotrepo-cli -- --root <path> trust
cargo run -p dotrepo-cli -- --root <path> doctor
cargo run -p dotrepo-cli -- validate-index
cargo run -p dotrepo-cli -- public export --index-root index --out-dir public --generated-at <time> --stale-after <time>

# MCP server (stdio JSON-RPC)
cargo run -p dotrepo-mcp

# LSP server (stdio JSON-RPC)
cargo run -p dotrepo-lsp

# Public export packaging
python3 scripts/package_public_export.py --input public --output-dir dist
```

Run a single test file: `cargo test -p dotrepo-core --test import_fixture_pack`

Run a single test function: `cargo test -p dotrepo-core --test import_quality_gate -- test_name`

## Crate Architecture

```
dotrepo-schema   → types only (Manifest, Record, Repo, Trust, etc.), TOML parsing, no logic
dotrepo-core     → all validation, query, trust analysis, import heuristics, public export
dotrepo-transport → JSON-RPC transport helpers shared by MCP and LSP
dotrepo-cli      → clap-based CLI, delegates to core
dotrepo-mcp      → stdio MCP 2025-11-25 server, delegates to core
dotrepo-lsp      → stdio LSP server with diagnostics/hover/completion, delegates to core
```

**Key rule**: No validation or trust logic is duplicated across CLI/MCP/LSP. All business logic lives in `dotrepo-core`.

`dotrepo-core` is a single large `lib.rs` (~3800 lines). All public API entry points, report types, and internal helpers live in that one file. When adding new functionality, add it to the appropriate section of `lib.rs` rather than creating new modules.

## Core Concepts

**Record modes**: `native` (`.repo` at repo root, maintainer-owned) vs `overlay` (index records, community-contributed)

**Trust / status ladder**: `draft` → `imported` → `inferred` → `reviewed` → `verified` → `canonical`. Confidence levels: `low` / `medium` / `high`. Provenance arrays like `["declared"]`, `["declared", "verified"]`, `["inferred"]`.

**Conflict resolution**: native beats overlay; higher status wins; explicit selection overrides. The `query` and `trust` commands surface conflicts.

**Managed regions**: TOML-delimited blocks in Markdown surfaces (`README.md`, `SECURITY.md`, `CODEOWNERS`) that `generate` syncs from the manifest.

**Claim workflow**: Maintainers submit a claim directory to upgrade an overlay record to native/canonical. Claim lifecycle is append-only event log with state machine enforcement (Draft → Submitted → InReview → Accepted/Rejected/Withdrawn/Disputed). A `corrected` event type allows recovering from terminal states.

**Public export**: Static JSON tree at `public/v0/` summarizing all index records, trust context, and conflicts for AI-readable access. Every response carries a `freshness` block with `generatedAt`, `snapshotDigest` (SHA-256 of the index tree), and optional `staleAfter`. Built in CI and served statically.

## Key Report Types

CLI, MCP, and LSP all consume the same core report structs. The main ones:

- `ValidateReport` — diagnostics list + per-record results from `validate_repository()`
- `QueryReport` — resolved value + selection report + conflicts from `query_repository()`
- `TrustReport` — selected record + selection reason + conflicts from `trust_repository()`
- `GenerateCheckReport` — per-file drift detection from `generate_check_repository()`
- `ImportPlan` — manifest text + evidence text + imported sources + inferred fields from `import_repository()`
- `ClaimInspectionReport` — claim state + event history + validation from `inspect_claim_directory()`
- `PublicRepositorySummaryResponse`, `PublicTrustResponse`, `PublicQueryResponse` — public export wrappers with freshness metadata

## Index Conventions

Overlay records live at `index/repos/<host>/<owner>/<repo>/record.toml` with an accompanying `evidence.md`. See `index/README.md` and `index/review-checklist.md` for submission rules.

## Testing

Tests are **fixture-based with golden outputs** and live in `crates/dotrepo-core/tests/`. Key test files:

- `import_fixture_pack.rs` — import heuristic accuracy across all fixtures
- `import_quality_gate.rs` — regression gate: loads `expectations.json` and asserts exact field values (repo name, description, status, sources, trust provenance, evidence substrings) for every import fixture
- `claim_fixture_pack.rs` — claim lifecycle with scenario fixtures and golden-path workflow tests
- `public_export_fixture_pack.rs` — runs `export_public_index_static()` and asserts the generated JSON tree matches golden expected output exactly

**Testing pattern**: Each fixture directory under `tests/fixtures/` contains input files (README.md, CODEOWNERS, etc.). An `expectations.json` file drives the quality gate, defining exact expected outputs per fixture. When adding a new fixture, create the fixture directory and add its expectations to `expectations.json`.

MCP and LSP have inline tests in their respective `main.rs` files that verify parity with core functions using temp directories.

## CI Pipeline

`.github/workflows/ci.yml` runs in a single job:
1. `cargo fmt --all -- --check` — formatting
2. `cargo test --workspace` — all tests
3. CLI smoke: validate + generate-check on `examples/native-minimal`, validate-index on `index/`
4. `cargo publish --dry-run` for all 6 crates in dependency order
5. Public export build + Python packaging script
6. MCP stdio smoke test (initialize handshake → tools/list → validate → query)

## Schema Constants

Current schema version: `dotrepo/v0.1`. Claim schema: `dotrepo-claim/v0`. MCP protocol: `2025-11-25`. Public API: `v0`. These are defined as constants at the top of `dotrepo-core/src/lib.rs`.
