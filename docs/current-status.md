# Current status

As of March 14, 2026, dotrepo is a coherent early implementation of the protocol,
reference toolchain, and seed index. It is still not production-hardened, but it
is no longer just an architecture sketch.

## What exists now

- A canonical root `.repo` format plus overlay records for index use
- Shared Rust core semantics for validation, query, trust, import, generate-check,
  and authority/conflict reporting
- A thin CLI, stdio MCP server, stdio LSP server, and thin VS Code extension shell
- Managed sync for supported Markdown surfaces through explicit managed regions
- Richer import heuristics for `README.md`, `CODEOWNERS`, and `SECURITY.md`, backed
  by a checked-in fixture pack and regression gate
- A seed `index/` tree with evidence rules, showcase overlays, and validation checks
- Contract-level claim, supersede, and conflict surfacing semantics
- Git-backed maintainer-claim artifacts, read-only claim inspection, and a first
  reviewer workflow over append-only claim events
- Binary-level CLI contract coverage for accepted handoff, corrected claim
  history, and invalid claim-history rejection
- An explicit operator-gate script and CI job for claim inspection, handoff, and
  invalid-history regression coverage, including a staged seed-overlay handoff
  exported through the normal public JSON path
- A hosted-static deployment path for the exported public JSON tree through
  GitHub Pages workflow automation
- A release-artifact workflow for packaging the CLI, LSP, and MCP binaries
- An explicit release-gate script and CI job that package the hosted public
  tree, install bundles, and VS Code release asset from one reproducible flow
- A checked-in public API compatibility manifest and test for the current `v0`
  summary, trust, query, inventory, and error-wrapper contracts
- Accepted public-serving RFCs 0016 through 0019 as the `v0` launch-doc set

## What dotrepo does not promise yet

- Production hardening, broad ecosystem adoption, or long-tail operational polish
- A full maintainer claim workflow product surface
- A broader public site UX or live public query API
- Bundle mode or first-class workspace/relations support
- Arbitrary prose round-tripping or automatic conversion of unmanaged files into
  managed-region files
- Editor assistance for placing managed-region markers or semantic autofix flows
- Full TOML language-server parity beyond the current schema-shaped manifest surface

## What is still deliberately proof-only

- The checked-in seed index remains overlay-only. dotrepo does not yet publish a
  reviewed accepted maintainer claim for a live repository from `index/`.
- The operator gate stages one copied seed entry through accepted handoff and
  `public export` as a proof artifact, then uploads that output separately in CI.
- That split is intentional: it proves the claim-aware public path without
  asserting a real maintainer-reviewed handoff in the live public seed tree.

## What is true about the current editor and sync layers

- The editor layer is intentionally thin. The LSP and VS Code extension reuse core
  validation and trust semantics rather than inventing a second truth model.
- Managed sync is intentionally narrow. dotrepo preserves user-authored prose
  outside supported managed regions, and malformed or unsupported layouts fail
  explicitly instead of being guessed through.
- The current sync contract is limited to supported Markdown surfaces. `CODEOWNERS`
  can be generated, but it is not part of the managed-region contract.

## What the next strategic constraint is

The next meaningful constraint is no longer import quality, initial editor
ergonomics, or basic maintainer-claim workflow. It is public, read-only index
serving: how dotrepo exposes repository identity, preferred-record summary,
trust context, and competing claims without inventing a second public truth
model.

That is why the next strategic track should focus on the identity-first public
index site and query API described in RFC 0016 and its follow-on response-shape
work, not on widening the editor surface or expanding bundle/workspace semantics
first.

For the concrete v1.0 launch scope, exit criteria, and deferrals, see
[`PLAN.md`](../PLAN.md).

For the current operator/reviewer loop over the exported public JSON tree, see
[`docs/public-export-workflow.md`](./public-export-workflow.md).
For the current outward-facing proof vehicle built on that export tree, see
[`docs/public-proof-surface.md`](./public-proof-surface.md).
For the current release-style note and usage examples around that proof surface,
see [`docs/public-proof-release-note.md`](./public-proof-release-note.md) and
[`docs/public-export-examples.md`](./public-export-examples.md).
