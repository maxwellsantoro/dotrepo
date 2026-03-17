# Current status

As of March 16, 2026, dotrepo is a working implementation of the protocol,
reference toolchain, and seed index, with a hosted read-only public surface.

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
- Git-backed maintainer-claim artifacts, read-only claim inspection, and a
  reviewer workflow over append-only claim events
- A first live accepted maintainer claim in the checked-in seed index for the
  released public repository `github.com/maxwellsantoro/ries-rs`, exported
  through the normal public JSON path
- Binary-level CLI contract coverage for accepted handoff, corrected claim
  history, and invalid claim-history rejection
- An explicit operator-gate script and CI job for claim inspection, handoff, and
  invalid-history regression coverage, including a staged seed-overlay handoff
  exported through the normal public JSON path
- A hosted-static public surface deployed through GitHub Pages
- Release-artifact packaging for the CLI, LSP, and MCP binaries, with CI smoke
  tests that extract and run the shipped binaries from the packaged tarball
- An explicit release-gate script and CI job that package the hosted public
  tree, install bundles, and VS Code release asset from one reproducible flow
- A checked-in public API compatibility manifest and test for the current `v0`
  summary, trust, query, inventory, and error-wrapper contracts
- Accepted public-serving RFCs 0016 through 0019 as the `v0` launch-doc set

## What dotrepo does not yet include

- A full maintainer claim workflow product surface
- A broader public site UX or live public query API
- Bundle mode or first-class workspace/relations support
- Arbitrary prose round-tripping or automatic conversion of unmanaged files into
  managed-region files
- Editor assistance for placing managed-region markers or semantic autofix flows
- Full TOML language-server parity beyond the current schema-shaped manifest surface

## Live maintainer-claim status

- The checked-in seed index now includes a live accepted maintainer-owned claim
  for `github.com/maxwellsantoro/ries-rs`.
- That claim remains `pending_canonical`, so the selected public record is still
  the reviewed overlay until `ries-rs` publishes a native `.repo`.
- The upstream repository now has a public `v1.0.1` release, so the live claim
  is anchored to a shipped public repo rather than a pre-release draft.
- The operator gate still stages a copied seed entry through accepted handoff
  with canonical links so the superseded-handoff path remains exercised in CI.
- A second independently reviewed example is still desirable soon after launch,
  but the live-index claim gap is no longer a blocker.

See [`docs/v1-go-no-go.md`](./v1-go-no-go.md) for the current release bar.

## What is true about the current editor and sync layers

- The editor layer is intentionally thin. The LSP and VS Code extension reuse core
  validation and trust semantics rather than inventing a second truth model.
- Managed sync is intentionally narrow. dotrepo preserves user-authored prose
  outside supported managed regions, and malformed or unsupported layouts fail
  explicitly instead of being guessed through.
- The current sync contract is limited to supported Markdown surfaces. `CODEOWNERS`
  can be generated, but it is not part of the managed-region contract.

## Where to go next

For the concrete v1.0 launch scope, exit criteria, and deferrals, see
[`PLAN.md`](../PLAN.md).
For the release decision bar, see
[`docs/v1-go-no-go.md`](./v1-go-no-go.md).

For the operator/reviewer loop over the exported public JSON tree, see
[`docs/public-export-workflow.md`](./public-export-workflow.md).
For the public surface architecture, see
[`docs/public-surface.md`](./public-surface.md).
For the release note and usage examples, see
[`docs/public-release-note.md`](./public-release-note.md) and
[`docs/public-export-examples.md`](./public-export-examples.md).
