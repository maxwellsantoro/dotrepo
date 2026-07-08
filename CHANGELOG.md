# Changelog

## Unreleased (`2.0.0-alpha.0` development line)

The post-1.0 tree includes public Rust API changes, including the new
`FieldConfidence::Suspect` variant. Development therefore continues on a 2.0
prerelease line so the source at `main` cannot be confused with the immutable
`v1.0.1` release and crates.io packages. Production installs should stay on
stable `1.0.x` — see [`docs/install.md`](./docs/install.md).

Post-1.0 growth, hardening, and operational-proof work toward the roadmap
milestones. Direction and gates live in [`ROADMAP.md`](./ROADMAP.md); the counts
below are a 2026-06-29 snapshot and refresh with each run from the generated
growth, coverage, promotion, and telemetry artifacts.

### Operator quality and distribution tooling

- Intent-level quality scorecard with soft error budgets
  (`scripts/render_intent_quality_scorecard.py`) covering overview, execution,
  documentation, security, ownership, and discovery intents by language family
- Coverage-gap report for build/test/security recrawl prioritization
  (`scripts/render_coverage_gaps.py`)
- Shared `scripts/language_family.py` classifier (deduplicated across growth,
  audit, factual-accuracy, and scorecard scripts)
- Process-level CPU and peak-RSS sampling on autonomous crawl subprocesses
  (`scripts/process_resources.py`) wired into unit-cost reports
- Hosted lookup-miss demand telemetry: Worker emits `DOTREPO_LOOKUP_MISS` log
  lines; `scripts/aggregate_lookup_misses.py` builds top-miss reports
- Distribution and external-consumer docs
  (`docs/distribution.md`, `docs/external-consumer-integration.md`)
- Milestone 1 escalation canary procedure (`docs/m1-escalation-canary.md`)
- Public repositories catalog: paginated “Show more”, URL `?q=` search restore
- Documented split plans for `import/escalation.rs` and `crawler/pipeline.rs`
- Install docs clarify stable `1.0.x` vs `2.0.0-alpha` development line
- `ROADMAP.md` rewritten for scannable active execution order, current index
  snapshot, and aligned M1/distribution/demand status

### Index hardening batch (2026-07-08)

- Drained promotion headroom: **+18 verified** overlays (572→590), including
  django, langchain, ruff, next.js, imgui, rust-analyzer, react, zstd, and others
- Targeted recrawls of non-verified / quality-queue repositories with live
  GitHub + adjudication sidecar (several `local_primary` resolutions)
- Security URL scoring: treat `security.html` path stems, Meta
  `facebook.com/whitehat`, and `nodesecurity.io` as actionable reporting surfaces
- **M1 second-opinion live canary passed**
  (`second_opinion_live_ladder_from_low_confidence_primary`; record in
  `index/telemetry/m1-second-opinion-canary-20260708.md`)
- Risk-weighted audit sample archived at
  `index/telemetry/audit-sample-20260708.md`
- Security import: reject non-actionable SECURITY.md URLs (Discord, bare repo
  homepage, issue forms, personal sites) so they become honest `unknown` /
  absence instead of medium-confidence promotion blockers; treat gRPC-style
  `*-cve-process.md` docs as actionable
- Quality pass: normalize 18 non-actionable index contacts + scheme-less
  homepages (clap, moment); **+21 verified** via gate-passed promotion
  (590→611; 2 remaining imported with honest build/test conflicts)
- Audit disposition: `index/telemetry/audit-sample-20260708-disposition.md`
- Distribution: `scripts/fixtures/lookup_miss_sample.log` + aggregator E2E;
  template-complete `examples/external-consumer/` lookup-before-scrape client

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

## 1.0.1 - 2026-07-02

- **Fixed MCP stdio framing.** `dotrepo-mcp` only spoke LSP-style
  `Content-Length` framing, so spec-compliant MCP clients (Claude Code, Claude
  Desktop, the SDKs) could not talk to it. The transport now auto-detects
  newline-delimited JSON (the MCP stdio transport) versus `Content-Length`
  framing per message and responds in kind; the CI smoke test drives the
  spec-compliant framing. The LSP server is unchanged.
- The public export emits a pagedigest v1 RC manifest at
  `/.well-known/pagedigest.json`: monotonic per-URL revisions keyed to content
  (freshness churn excluded) with auditable full-byte digests over the
  `/v0/repos/` tree; `public export --pagedigest-previous` carries revision
  state across fresh export directories
- The public site publishes the lookup-efficiency benchmark at `/efficiency/`
  with the compact report at `/benchmarks/lookup-efficiency.json`, re-measured
  on every deploy
- Tagged releases attach a deterministic `dotrepo-mcp-<version>.mcpb` bundle
  and publish `io.github.maxwellsantoro/dotrepo` to the official MCP registry
  via GitHub OIDC (`scripts/package_mcpb_bundle.py`,
  `docs/mcp-registry-publishing.md`)

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
