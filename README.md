# dotrepo

[![CI](https://github.com/maxwellsantoro/dotrepo/actions/workflows/ci.yml/badge.svg)](https://github.com/maxwellsantoro/dotrepo/actions/workflows/ci.yml)
[![Latest Release](https://img.shields.io/github/v/release/maxwellsantoro/dotrepo)](https://github.com/maxwellsantoro/dotrepo/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-0f766e.svg)](LICENSE)

**dotrepo** is an open metadata protocol and shared semantic cache for software
repositories. It makes repository understanding reusable instead of forcing
every human and agent to fetch, parse, and infer the same basic facts again.

It packages that into three aligned surfaces:
- **maintainers** get one structured source of truth and tools that keep supported repository surfaces from drifting
- **users** get consistent, evidence-linked project orientation and an increasingly useful research index
- **agents and tools** get compact, trust-aware repository facts before resorting to cloning or scraping

Repositories that have not adopted dotrepo can still receive autonomously
generated overlays. The pipeline uses deterministic parsers first, escalates
only unresolved fields through progressively stronger model tiers, validates
all output against evidence, and publishes uncertainty instead of inventing
certainty. Maintainers can later publish a native `.repo` and become the
canonical authority.

The goal is not to replace project documentation or character. It is to pay the
cost of basic repository understanding when a project changes, then reuse that
understanding across future tools, users, and research tasks.

Project site and hosted public surface:
[dotrepo.org](https://dotrepo.org/)

## See it in 60 seconds

This repository now ships its own native [`.repo`](.repo). A minimal slice of
that record looks like:

```toml
schema = "dotrepo/v0.1"

[record]
mode = "native"
status = "canonical"

[record.trust]
confidence = "high"
provenance = ["declared", "verified"]
notes = "Maintainer-controlled source of truth."

[repo]
name = "dotrepo"
description = "Open metadata protocol for software repositories"
build = "cargo build --workspace"
test = "cargo test --workspace"

[repo.toolchain]
min = "1.90.0"
ecosystem = "Rust"
```

What the CLI gives you once `dotrepo` is on your `PATH`:

```bash
dotrepo --root examples/native-minimal validate
dotrepo --root examples/native-minimal query repo.build --raw
dotrepo --root examples/native-minimal trust
```

```text
manifest valid
cargo build
selected: .repo (Native, Canonical)
selection reason: only matching record
source: none
confidence: high
provenance: declared, verified
notes: Maintainer-controlled source of truth.
```

That is the wedge: dotrepo does not just answer a repository question, it tells
you why that answer should be trusted.

## Quick start

1. Install `dotrepo` from the latest **stable** GitHub release bundle (`1.0.x`),
   or with `cargo install dotrepo-cli` (pin a `1.0.x` version for production).
   The `main` branch tracks a `2.0.0-alpha` development line with public API
   changes. See [`docs/install.md`](docs/install.md) for platform bundles and
   the VS Code extension package.
2. Start a record in your repository:

```bash
dotrepo --root <repo> init
# or bootstrap from existing README.md / CODEOWNERS / SECURITY.md:
dotrepo --root <repo> import
```

3. Run the canonical maintainer loop:

```bash
dotrepo --root <repo> validate
dotrepo --root <repo> query repo.build --raw
dotrepo --root <repo> trust
dotrepo --root <repo> generate --check
```

For the full maintainer flow, see
[`docs/maintainer-happy-path.md`](docs/maintainer-happy-path.md).

If you want to contribute to the protocol, toolchain, or public index, start with
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## What dotrepo is

dotrepo has three inseparable parts:

1. **A protocol**
   A versioned `.repo` schema for essential repository metadata, provenance, trust, and synchronization hints.
2. **A reference toolchain**
   A Rust CLI, stdio MCP server, and related integrations for importing, validating, querying, syncing, and generating compatible repository surfaces.
3. **An index**
   A public, Git-backed collection of evidence-backed overlays, trust context,
   and maintainer handoffs that makes repositories mechanically visible before
   native adoption.

The current index is generated and refreshed through an autonomous conveyor.
Routine generated records do not require per-record human review. Humans set
policy, improve gates and parsers, monitor aggregate health, and handle
maintainer authority claims.

## Why it matters for agents

`dotrepo-mcp` is a thin stdio MCP server that exposes the same trust-aware core
used by the CLI. It gives agent clients structured tools instead of forcing them
to scrape README prose.

Current MCP tools:
- `dotrepo.validate`
- `dotrepo.query`
- `dotrepo.trust`
- `dotrepo.adoption_status`
- `dotrepo.lookup`
- `dotrepo.claim_inspect`
- `dotrepo.generate_check`
- `dotrepo.import_preview`
- `dotrepo.import_write`

Tool execution errors are returned as MCP tool results with
`isError: true` and machine-readable `structuredContent`. Protocol-level
mistakes, such as calling an unknown tool name, still use normal JSON-RPC
errors.

Example local MCP tool call:

```json
{
  "name": "dotrepo.query",
  "arguments": {
    "root": "examples/native-minimal",
    "path": "repo.build"
  }
}
```

That returns the selected value together with record status, provenance, and
conflict context.

`dotrepo validate` intentionally checks only the root `.repo` or root
`record.toml` for the selected repository. Use `dotrepo validate-index` for
descendant `index/repos/**/record.toml` overlays; `query` and `trust` still
load matching descendant candidates when resolving conflict-aware answers.

Example hosted lookup call:

```json
{
  "name": "dotrepo.lookup",
  "arguments": {
    "repositoryUrl": "https://github.com/BurntSushi/ripgrep",
    "path": "repo.description"
  }
}
```

That resolves the repository against `https://dotrepo.org/`, returns the hosted
summary, profile, trust, and query entrypoints, and optionally includes the live
query result for the requested dot-path. See
[`rfcs/0006-mcp-server-contract.md`](rfcs/0006-mcp-server-contract.md) for the
tool contract.

For repeated known-repository access, the reference CLI and hosted public
surface also expose batch profile/field lookup, structured profile search,
factual profile comparison, and relationship traversal as cacheable GET
routes:

```bash
cargo run -p dotrepo-cli -- public batch-profiles --repo github.com/sharkdp/fd
curl -s "https://dotrepo.org/v0/batch/profiles?repo=github.com/sharkdp/fd"
```

See [`docs/public-export-examples.md`](docs/public-export-examples.md) for the
full set of batch, search, compare, relations, lookup-efficiency, and coverage
examples, and for the operator-facing measurement scripts.

The repository also includes a falsifiable
[head-to-head benchmark harness](benchmarks/head-to-head/) that compares
dotrepo lookups against a GitHub API + README baseline on accuracy, abstention,
confidently-wrong answers, latency, and bytes over the wire. It is intentionally
allowed to make dotrepo lose; that is the measurement point.

## Why now

Repository metadata is fragmented. Some facts live in README files. Some live in `CODEOWNERS`, `SECURITY.md`, CI config, or platform settings. Some are nowhere except tribal knowledge.

That is annoying for maintainers, confusing for users, and expensive for coding agents. Today, basic questions like these often require heuristics or LLM interpretation:
- What is this repo?
- Who owns it?
- How do I build and test it?
- Where are the real docs?
- What policies or constraints apply?

A structured `.repo` record does not replace code or good documentation. It
provides a stable layer of essential facts that humans can maintain and machines
can query directly. The public index extends that stable shape to repositories
that have not adopted the protocol yet.

## Core principles

- **Protocol first**: dotrepo is a shared metadata protocol, not just a CLI.
- **Trust matters**: all records should communicate provenance and trust level clearly.
- **Respect the source**: overlays must distinguish declared facts, imported facts, and inferred facts.
- **Useful before adoption**: the index and overlay model make dotrepo valuable even for repos that do not use it natively.
- **Deterministic first**: parsers and evidence checks do the common work; model intelligence escalates only when needed.
- **Honest automation**: generated overlays publish confidence, provenance, conflicts, and explicit unknowns without a routine human review queue.
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
- **Repository relations**: explicit directed links carry their own trust;
  workspace-specific relation kinds remain reserved for future work

## Versioning note

The project release, manifest schema, claim schema, MCP protocol, and hosted API
have independent version lines. Read tool versions from GitHub releases,
manifest versions from the manifest itself, and the hosted API version from
[`meta.json`](https://dotrepo.org/v0/meta.json) instead of copying them into
additional status documents.

Those are separate version lines on purpose:
- the release version tracks the shipped reference toolchain
- the schema version tracks the `.repo` document contract
- the public API version tracks the hosted JSON response surface

## What the repo includes today

- a Rust workspace with `dotrepo-schema`, `dotrepo-core`, `dotrepo-cli`, `dotrepo-mcp`, `dotrepo-lsp`, and the shared internal `dotrepo-transport`
- a thin VS Code extension shell under [`editors/vscode/`](editors/vscode/)
- a thin import path for bootstrapping records from `README.md`, `CODEOWNERS`, and `SECURITY.md`
- a thin stdio MCP server exposing trust-aware validate/query/trust/generate-check/import tools
- an autonomous crawler with deterministic verification, field scoring,
  progressive adjudication providers, optional bounded synthesis sidecars,
  promotion, refresh planning, and batch telemetry
- updated RFCs that reflect the protocol + toolchain + index model
- example native and overlay records
- a seeded `index/` tree with real overlay layout and validation rules
- GitHub Actions workflows for workspace CI, operator-gate claim checks,
  release-gate packaging, and Cloudflare deployment
- public-facing docs with a balanced tone around ambition, safety, and practicality

## What dotrepo does not claim yet

This repo ships the current dotrepo protocol and reference toolchain surface.
The crates implement import, validation, querying, generated-surface checks,
index validation, claims, public export, and an MCP server.

The current public site includes exact lookup, ranked repository search,
factual profile comparison, relationship lookup, and optional bounded research
synthesis. What remains intentionally deferred is production-scale ranking
calibration, public mutation APIs, bundle mode, first-class workspace semantics,
broad editor automation, and arbitrary prose round-tripping.

## Read next

For strategy and active execution:
- [`ROADMAP.md`](ROADMAP.md)
- [`docs/README.md`](docs/README.md)

If you are adopting dotrepo in a repository:
- [`docs/install.md`](docs/install.md)
- [`docs/maintainer-happy-path.md`](docs/maintainer-happy-path.md)
- [`docs/sync-boundaries.md`](docs/sync-boundaries.md)

If you are consuming the hosted public surface or building agent tooling:
- [`docs/public-export-examples.md`](docs/public-export-examples.md)
- [`docs/public-surface.md`](docs/public-surface.md)
- [`docs/ai-tool-interviews.md`](docs/ai-tool-interviews.md)
- [`rfcs/0006-mcp-server-contract.md`](rfcs/0006-mcp-server-contract.md)

If you want the protocol and trust model:
- [`docs/trust-model.md`](docs/trust-model.md)
- [`rfcs/0001-protocol-and-ecosystem.md`](rfcs/0001-protocol-and-ecosystem.md)
- [`rfcs/0004-index-and-trust-model.md`](rfcs/0004-index-and-trust-model.md)

If you want to contribute:
- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`index/README.md`](index/README.md)
- [`index/review-checklist.md`](index/review-checklist.md)

Repository Python tooling is managed exclusively with `uv`: run `uv venv`,
`uv sync --dev --locked`, then invoke scripts and tests through `uv run`.
