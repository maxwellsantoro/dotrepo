# dotrepo

**dotrepo** is an open metadata protocol for software repositories, with a reference toolchain and a public index.

It is designed to help three sides at once:
- **maintainers** get a cleaner, more reliable way to describe and maintain repository metadata
- **users** get better discovery and a more consistent understanding of projects
- **agents and tools** get a structured way to query repository information instead of inferring it from scattered conventions and prose

The goal is not to replace the character of projects or flatten their documentation into machine sludge. The goal is to create a shared, trustworthy metadata layer that makes repositories easier to understand and work with, while respecting the source materials they come from.

## What dotrepo is

At day one, dotrepo has three inseparable parts:

1. **A protocol**
   A versioned `.repo` schema for essential repository metadata, provenance, trust, and synchronization hints.
2. **A reference toolchain**
   A Rust CLI and related integrations for validating, querying, syncing, and generating compatible repository surfaces.
3. **An index**
   A public, Git-backed collection of canonical records and overlays that makes public repositories mechanically visible whether or not maintainers have adopted dotrepo yet.

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

## Day-one decisions in this scaffold

- **Canonical in-repo v0.1 form**: a single root `.repo` file in TOML format
- **Bundle mode**: reserved for a future version
- **Overlay records**: separate TOML records in the index, with explicit provenance and trust metadata
- **Query support**: first-class CLI support for querying structured fields
- **Mode-aware validation**: native records and overlays validate differently
- **Generated outputs**: supported, but not the sole editing surface
- **Extension namespace**: `x.*` is reserved for non-core extensions
- **Future workspace support**: relations are reserved now so repos do not become permanent islands

## What this scaffold includes

- a Rust workspace with `dotrepo-schema`, `dotrepo-core`, and `dotrepo-cli`
- updated RFCs that reflect the protocol + toolchain + index model
- example native and overlay records
- a seeded `index/` tree with real overlay layout and validation rules
- starter GitHub Actions templates
- public-facing docs with a balanced tone around ambition, safety, and practicality

## What this scaffold does not claim yet

This scaffold is a planning and architecture package. It is not a production implementation. The Rust crates contain meaningful structure and APIs, but this repo is still a starting point for real development.

## First docs to read

- [`docs/vision.md`](docs/vision.md)
- [`docs/public-messaging.md`](docs/public-messaging.md)
- [`docs/trust-model.md`](docs/trust-model.md)
- [`index/README.md`](index/README.md)
- [`rfcs/0001-protocol-and-ecosystem.md`](rfcs/0001-protocol-and-ecosystem.md)
- [`rfcs/0004-index-and-trust-model.md`](rfcs/0004-index-and-trust-model.md)
- [`rfcs/0003-cli-and-query-contract.md`](rfcs/0003-cli-and-query-contract.md)
