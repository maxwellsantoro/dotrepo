# dotrepo

[![CI](https://github.com/maxwellsantoro/dotrepo/actions/workflows/ci.yml/badge.svg)](https://github.com/maxwellsantoro/dotrepo/actions/workflows/ci.yml)
[![Latest Release](https://img.shields.io/github/v/release/maxwellsantoro/dotrepo)](https://github.com/maxwellsantoro/dotrepo/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-0f766e.svg)](LICENSE)

**dotrepo** gives software repositories a trustworthy source of truth for
essential metadata.

It packages that into three aligned surfaces:
- **maintainers** get a cleaner, more reliable way to describe and maintain repository metadata
- **users** get better discovery and a more consistent understanding of projects
- **agents and tools** get a structured way to query repository information instead of inferring it from scattered conventions and prose

The goal is not to replace the character of projects or flatten their
documentation into machine sludge. The goal is to create a shared,
trustworthy metadata layer that makes repositories easier to understand and
work with, while respecting the source materials they come from.

Hosted public surface:
[maxwellsantoro.github.io/dotrepo](https://maxwellsantoro.github.io/dotrepo/)

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

1. Install `dotrepo` from the latest GitHub release bundle.
   See [`docs/install.md`](docs/install.md) for platform bundles and the VS Code
   extension package.
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

If you want to contribute to the protocol, toolchain, or seed index, start with
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## What dotrepo is

At day one, dotrepo has three inseparable parts:

1. **A protocol**
   A versioned `.repo` schema for essential repository metadata, provenance, trust, and synchronization hints.
2. **A reference toolchain**
   A Rust CLI, stdio MCP server, and related integrations for importing, validating, querying, syncing, and generating compatible repository surfaces.
3. **An index**
   A public, Git-backed collection of canonical records and overlays that makes public repositories mechanically visible whether or not maintainers have adopted dotrepo yet.

## Why it matters for agents

`dotrepo-mcp` is a thin stdio MCP server that exposes the same trust-aware core
used by the CLI. It gives agent clients structured tools instead of forcing them
to scrape README prose.

Current MCP tools:
- `dotrepo.validate`
- `dotrepo.query`
- `dotrepo.trust`
- `dotrepo.claim_inspect`
- `dotrepo.generate_check`
- `dotrepo.import_preview`
- `dotrepo.import_write`

Example MCP tool call:

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
conflict context. See
[`rfcs/0006-mcp-server-contract.md`](rfcs/0006-mcp-server-contract.md) for the
tool contract.

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

## Versioning note

The project release is `1.0.0`, the canonical in-repo schema is currently
`dotrepo/v0.1`, and the hosted public JSON API is currently `v0`.

Those are separate version lines on purpose:
- the release version tracks the shipped reference toolchain
- the schema version tracks the `.repo` document contract
- the public API version tracks the hosted JSON response surface

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

## Read next

If you are adopting dotrepo in a repository:
- [`docs/install.md`](docs/install.md)
- [`docs/maintainer-happy-path.md`](docs/maintainer-happy-path.md)
- [`docs/sync-boundaries.md`](docs/sync-boundaries.md)

If you are consuming the hosted public surface or building agent tooling:
- [`docs/public-release-note.md`](docs/public-release-note.md)
- [`docs/public-export-examples.md`](docs/public-export-examples.md)
- [`docs/public-surface.md`](docs/public-surface.md)
- [`rfcs/0006-mcp-server-contract.md`](rfcs/0006-mcp-server-contract.md)

If you want the protocol and trust model:
- [`docs/current-status.md`](docs/current-status.md)
- [`docs/trust-model.md`](docs/trust-model.md)
- [`rfcs/0001-protocol-and-ecosystem.md`](rfcs/0001-protocol-and-ecosystem.md)
- [`rfcs/0004-index-and-trust-model.md`](rfcs/0004-index-and-trust-model.md)

If you want to contribute:
- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`index/README.md`](index/README.md)
- [`index/review-checklist.md`](index/review-checklist.md)
