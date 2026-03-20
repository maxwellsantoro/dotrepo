# Current status

As of March 18, 2026, dotrepo is a working implementation of the protocol,
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
  released public repository `github.com/maxwellsantoro/ries-rs`, now linked to
  its published native `.repo` and exported through the normal public JSON path
- Binary-level CLI contract coverage for accepted handoff, corrected claim
  history, and invalid claim-history rejection
- An explicit operator-gate script and CI job for claim inspection, handoff, and
  invalid-history regression coverage, including a staged seed-overlay handoff
  exported through the normal public JSON path
- A deployed Cloudflare Worker public surface on `https://dotrepo.org/`,
  built from the reviewed export snapshot and serving the hosted `v0` JSON tree
  and same-origin query route from one origin
- A live Cloudflare Worker staging deployment on `workers.dev`, with post-deploy
  smoke coverage in CI and continued use as the secondary staging origin
- A real public homepage and writing surface on `https://dotrepo.org/`,
  generated from the reviewed export and published through the same Cloudflare
  deployment path as the hosted JSON surface
- Release-artifact packaging for `dotrepo`, `dotrepo-public-query`,
  `dotrepo-lsp`, and `dotrepo-mcp`, with CI smoke tests that extract and run
  the shipped binaries from the packaged tarball
- A local same-origin hosted-query runtime that can serve both the exported
  `public/` tree and query responses from one process
- A working in-repo `dotrepo-crawler` binary that can discover GitHub
  repositories by star band, plan factual overlay crawls, write imported
  overlays into an index root, persist crawler state for later refresh
  scheduling, preserve README variant paths, and derive factual `repo.build`
  and `repo.test` defaults from unambiguous root package manifests or,
  conservatively, from `.github/workflows/` when workflow signals are
  unambiguous and manifest-backed commands are absent, plus a deterministic
  `--targets-file` batch-seeding path for executing the tranche-one review queue
- Export-time per-repository `query-input/` artifacts plus a pure snapshot
  query function in core, so hosted query no longer depends on runtime TOML
  parsing as the only implementation path
- An in-repo Cloudflare Worker project that serves the same `v0` query route
  from exported `query-input/` artifacts and falls through to static assets
- A documented Cloudflare Worker + Static Assets deployment plan now realized on
  `dotrepo.org` without changing the `v0` contract
- An explicit release-gate script and CI job that package the hosted public
  tree, install bundles, smoke test same-origin hosted-query resolution from
  the shipped runtime, and serve as the canonical operator review entrypoint
  for public-surface changes
- Release-gate Worker smoke that stages the reviewed export into the Cloudflare
  project, runs Worker tests, dry-runs Wrangler packaging, and proves an
  emitted `queryTemplate` resolves through the Worker locally
- A checked-in public API compatibility manifest and test for the current `v0`
  summary, trust, query, inventory, and error-wrapper contracts
- Accepted public-serving RFCs 0016 through 0019 as the `v0` launch-doc set

## What dotrepo does not yet include

- A full maintainer claim workflow product surface
- Richer public browse and search UX on top of the now-live hosted public API
  origin
- An MCP remote-lookup tool that resolves repository URLs or identities against
  `https://dotrepo.org/` without a local checkout
- A seed index broad enough across languages to make dotrepo a likely first
  check for arbitrary public repositories
- Bundle mode or first-class workspace/relations support
- Arbitrary prose round-tripping or automatic conversion of unmanaged files into
  managed-region files
- Editor assistance for placing managed-region markers or semantic autofix flows
- Full TOML language-server parity beyond the current schema-shaped manifest surface

## Highest-leverage next steps

- Execute the concrete tranche-one seed-index program in
  [`index/tranche-one-targets.md`](../index/tranche-one-targets.md) until the
  checked-in index reaches a first tranche of 50 reviewed repositories across
  Rust, TypeScript, Python, and Go.
- Add a `dotrepo.lookup`-style MCP tool that wraps the hosted public surface for
  URL-first remote lookup immediately after the first index-growth tranche is
  underway.
- Keep hardening and public-site work tightly scoped to blockers for those two
  leverage points rather than letting them reclaim the roadmap.

See [`docs/ai-tool-interviews.md`](./ai-tool-interviews.md) for the synthesized
interview-backed rationale behind those priorities.

## Live maintainer-claim status

- The checked-in seed index now includes a live accepted maintainer-owned claim
  for `github.com/maxwellsantoro/ries-rs`, linked to the published native
  `.repo` in the upstream repository.
- The derived handoff is `superseded`. The checked-in seed index remains
  overlay-only today, so the public export still shows the reviewed overlay as
  visible seed-index context while surfacing the canonical handoff.
- The upstream repository now has a public `v1.0.1` release and native `.repo`,
  so the live claim is anchored to a shipped canonical public repo rather than
  a pre-release draft.
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

For the historical `v1.0` launch scope, exit criteria, and deferrals, see
[`PLAN.md`](../PLAN.md).
For the release decision bar, see
[`docs/v1-go-no-go.md`](./v1-go-no-go.md).

For the operator/reviewer loop over the exported public JSON tree, see
[`docs/public-export-workflow.md`](./public-export-workflow.md).
For the public surface architecture, see
[`docs/public-surface.md`](./public-surface.md).
For the planned Cloudflare deployment target for hosted query, see
[`docs/cloudflare-hosted-query.md`](./cloudflare-hosted-query.md).
For the local and GitHub setup for the Worker deploy path, see
[`docs/cloudflare-deploy.md`](./cloudflare-deploy.md).
For the release note and usage examples, see
[`docs/public-release-note.md`](./public-release-note.md) and
[`docs/public-export-examples.md`](./public-export-examples.md).
