# Changelog

## Unreleased

Post-1.0 growth, hardening, and operational-proof work toward the roadmap
milestones. Direction and gates live in [`ROADMAP.md`](./ROADMAP.md); the counts
below are a 2026-06-29 snapshot and refresh with each run from the generated
growth, coverage, promotion, and telemetry artifacts.

### Index growth

- Five bounded discovery waves across non-overlapping GitHub star bands brought
  the checked-in corpus to 613 overlay records and 516 high-signal public
  profiles, completing the 500-profile Milestone 2 coverage gate (103.2%)
- Tranche-two writeback complete at 106/106 targets across .NET, C/C++, Go, JVM,
  Python, Rust, and TypeScript/JavaScript; all seven language-family groups are
  exhausted
- 514 records at `verified` and 1 accepted maintainer claim

### Quality and promotion

- Quality and promotion waves promoted 48 eligible overlays to `verified`
  through expanded `is_actionable_security_url()` scoring, primary-CI workflow
  preference during intra-tier command conflicts, targeted re-crawls, and bounded
  autonomous batches
- As of 2026-06-29: 61 promotion candidates (`promotion-report`), 19 high-signal
  lift candidates (growth-status heuristic), and a 501-record quality-hardening
  queue (285 missing build, 290 missing test, 408 missing security)

### Operational controls

- Retained multi-run autonomous telemetry with a strict proof gate covering
  worst-run and recent-window quality, tier-mix, adjudication-budget, and
  token-cost drift; as of 2026-06-29 the gate is not yet passing in strict mode
  (7 retained runs, 75 processed repositories), failing worst-run failure rate
  and recent failure drift
- Scheduled-failure partial-progress safety: failed runs retain telemetry and
  valid writebacks before restoring the failed result
- Head-aware planning bounds network inspection and rotates oldest and
  most-partial records first
- Recurring-failure regression-fixture capture (`--stub`) with checked-in
  coverage across every named ecosystem the classifier emits
- `public-surface-gate` extended to run lightweight CLI, MCP, LSP, and crawler
  contract tests alongside core import and public-export checks
- Automatic deploy-coherence checks against the reviewed export's contract files
  and a deterministic `v0/files.json` hash sample; Cloudflare packaging on
  Node.js 22

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
