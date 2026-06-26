# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## What This Is

dotrepo is an open metadata protocol for software repositories. It has three interlinked deliverables:

1. **A `.repo` schema** — versioned TOML manifests that encode provenance, trust, owners, docs, and build/test metadata
2. **A reference toolchain** — Rust CLI, stdio MCP server, and LSP for importing, validating, querying, syncing, and generating compatible surfaces
3. **A public index** — a Git-backed collection of evidence-backed overlays and maintainer authority context at `index/repos/<host>/<owner>/<repo>/` that makes public repos mechanically visible whether or not maintainers have adopted dotrepo natively

The public overlay index is generated and refreshed through an autonomous,
evidence-constrained conveyor. Deterministic parsers run first; unresolved fields
may escalate through progressively stronger model tiers; routine generated
records do not wait for human review.

## Documentation Authority

- `README.md` — project overview and shipped capabilities
- `ROADMAP.md` — strategy, active execution order, and milestone gates
- `CHANGELOG.md` — release history
- `docs/README.md` — documentation map
- RFCs — design records and accepted contracts, not live task lists

When documentation conflicts, prefer current code and contracts, then
`README.md` for shipped behavior and `ROADMAP.md` for direction.

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

# Autonomous index batch (local, explicit opt-in)
python3 scripts/run_autonomous_index_batch.py --skip-automation-enabled-check --output-dir /tmp/dotrepo-autonomous-batch

# Canonical public release gate
python3 scripts/check_release_gate.py --output-root /tmp/dotrepo-release-gate --skip-vsix
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
dotrepo-crawler  → discovery, factual crawl, verification, scoring, escalation, promotion, refresh planning, and autonomous writeback
```

**Key rule**: No validation or trust logic is duplicated across CLI/MCP/LSP. All business logic lives in `dotrepo-core`.

`dotrepo-core` is split across focused modules under `src/` (`claims.rs`, `import/` with `commands.rs` and `parsing.rs`, `surfaces.rs`, `public.rs`, `selection.rs`, `promotion.rs`, `validation.rs`, `query.rs`, `synthesis.rs`, `util.rs`) plus a thin `lib.rs` facade that re-exports the complete public API. Facade unit tests live in `facade_tests.rs`. When adding new functionality, place it in the most appropriate module (or create a small new focused one if none fits). Keep the public surface in `lib.rs` unchanged so that all existing `use dotrepo_core::...` sites continue to work.

## Core Concepts

**Record modes**: `native` (`.repo` at repo root, maintainer-owned) vs `overlay` (index records, autonomously generated or contributed)

**Trust / status ladder**: `draft` → `imported` → `inferred` → `reviewed` → `verified` → `canonical`. `reviewed` denotes human review. `verified` may be minted by exhaustive machine verification and does not imply human approval. Confidence levels: `low` / `medium` / `high`. Provenance arrays like `["declared"]`, `["declared", "verified"]`, `["inferred"]`.

**Conflict resolution**: native beats overlay; higher status wins; explicit selection overrides. The `query` and `trust` commands surface conflicts.

**Managed regions**: delimited blocks in supported Markdown surfaces (`README.md`, `SECURITY.md`, `CONTRIBUTING.md`) that `generate` syncs from the manifest. `CODEOWNERS` may be fully generated but is not partially managed.

**Autonomous index rule**: Routine generated overlays have no human review tier. Uncertainty ends in deterministic resolution, bounded model escalation, honest partial publication, or abstention. Models may choose only from grounded candidates and never bypass post-checks or validation. Automation may mint `verified`, but never `reviewed` or `canonical`.

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

Overlay records live at `index/repos/<host>/<owner>/<repo>/record.toml` with an accompanying `evidence.md`. See `index/README.md` for layout and autonomous operations. `index/review-checklist.md` is the manual contribution and audit rubric, not a required approval gate for routine generated records.

## Testing

Tests are **fixture-based with golden outputs** and live in `crates/dotrepo-core/tests/`. Key test files:

- `import_fixture_pack.rs` — import heuristic accuracy across all fixtures
- `import_quality_gate.rs` — regression gate: loads `expectations.json` and asserts exact field values (repo name, description, status, sources, trust provenance, evidence substrings) for every import fixture
- `claim_fixture_pack.rs` — claim lifecycle with scenario fixtures and golden-path workflow tests
- `public_export_fixture_pack.rs` — runs `export_public_index_static()` and asserts the generated JSON tree matches golden expected output exactly

**Testing pattern**: Each fixture directory under `tests/fixtures/` contains input files (README.md, CODEOWNERS, etc.). An `expectations.json` file drives the quality gate, defining exact expected outputs per fixture. When adding a new fixture, create the fixture directory and add its expectations to `expectations.json`.

MCP and LSP have inline tests in their respective `main.rs` files that verify parity with core functions using temp directories.

## CI Pipeline

`.github/workflows/ci.yml` classifies changed files in a `change-scope` job, then runs scoped downstream jobs:

1. **`rust-and-index`** — `cargo fmt`, `cargo clippy`, `cargo test`, CLI smoke (validate + generate-check on `examples/native-minimal`, validate-index on `index/`), `cargo publish --dry-run` for all 6 crates, MCP stdio smoke test, LSP stdio smoke test
2. **`operator-gate`** — maintainer-claim inspection and handoff regression (`scripts/check_operator_claim_gate.py`)
3. **`public-surface-gate`** — lightweight public export gate for index/public-surface-only changes (`check_release_gate.py --skip-release-bundle --skip-vsix`)
4. **`release-gate`** — full release packaging, VSIX, and hosted-query Worker smoke

Index-only or other public-surface-only changes route to `public-surface-gate` without paying the full release-bundle path. Rust toolchain, docs, or RFC changes route through `rust-and-index` and `release-gate`.

## Version Constants

Do not copy protocol or schema version constants into new documentation. Read
them from their owning implementations: manifest validation in `validation.rs`,
claims in `claims.rs`, MCP negotiation in `dotrepo-mcp`, and public API wrappers
in `public.rs`.
