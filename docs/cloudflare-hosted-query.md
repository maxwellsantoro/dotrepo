# Cloudflare Hosted Query Plan

This note selects the first real hosted-query deployment target for dotrepo.

It does **not** change the public contract.

The `v0` summary, trust, query, inventory, and freshness semantics remain the
same. This note only changes the planned serving layer.

## Decision

Use **one Cloudflare Worker with Static Assets** as the first deployed hosted
query surface.

The Worker should:

- serve the exported `public/` tree on the same origin
- handle the live `/<base>/v0/repos/.../query?path=...` route
- keep `queryTemplate` same-origin and base-path-correct
- remain GET-only and snapshot-based

This replaces "GitHub Pages plus a future query runtime" with "one same-origin
runtime that serves both the static public tree and query responses."

## What stays unchanged

Do not rewrite:

- the `v0` public wire contract
- the current machine-readable error vocabulary
- the current freshness block semantics
- the current `queryTemplate` behavior
- the current no-search / no-discovery / no-mutation boundary

Summary, trust, inventory, and `meta.json` remain export-first artifacts. The
edge runtime exists to serve them and to answer live query requests from the
same immutable snapshot family.

## Rewrite boundary

Do **not** port the current Rust TCP server 1:1.

Instead:

- keep the product contract and snapshot model unchanged
- replace the filesystem-bound serving layer with a Worker-oriented runtime
- add an export-time query input artifact that the Worker can load cheaply

The current Rust runtime remains useful for:

- local same-origin review
- contract and parity tests
- release-bundle smoke checks

It is not the final deployed serving implementation.

## Deployment shape

### Public origin

Use one Worker as the primary public origin.

- Static Assets serves the exported `public/` tree
- the Worker handles `/query`
- non-query requests fall through to the static asset layer

That keeps the existing relative links and `queryTemplate` contract intact.

### Data shape

Add a query-oriented snapshot artifact at export time, for example:

- `query-input/<host>/<owner>/<repo>.json`

This artifact should contain only what is needed to reproduce the current query
wrapper semantics:

- repository identity
- selected values
- selection reason
- visible conflicts
- links/base-path inputs
- freshness block inputs

The Worker should not parse TOML or walk the checked-in index tree per request.

### Storage tiers

Start with:

- Worker Static Assets for the exported `public/` tree
- the same asset bundle for query-input artifacts if the snapshot remains small

Scale to:

- Static Assets for the public tree
- R2 for query-input snapshot backing

This keeps the public contract stable while leaving room to grow beyond one
asset bundle.

## Cache model

The cache model stays the same:

- static files are cacheable as ordinary static assets
- query responses are cacheable by full request URL plus snapshot identity
- cache invalidation happens by snapshot replacement, not by record mutation

The Worker should not invent a second freshness system.

## Implementation slices

### E2-06 Select Cloudflare as the hosted query runtime

Freeze:

- Worker + Static Assets as the first deployment target
- same-origin serving as a hard requirement
- R2 as the scale fallback, not a day-one dependency

### E2-07 Add export-time query input artifacts

Acceptance:

- one repo-level query-input artifact per exported repository
- enough data to reproduce current query semantics without runtime TOML parsing
- parity tests against the existing local query wrapper

### E2-08 Refactor query serving into a pure snapshot function

Acceptance:

- one function takes identity, dot path, loaded query-input data, freshness, and
  base path
- one function returns the current query response or the current public error
  shape

### E2-09 Implement the Worker

Acceptance:

- query route matches the current `v0` wrapper contract
- non-query requests serve static assets
- same error vocabulary and base-path behavior remain intact

### E2-10 Add Wrangler project and deploy workflow

Acceptance:

- one deployable Worker project exists in-repo
- CI can build the deploy artifact from the same reviewed export snapshot
- deployment stops depending on GitHub Pages as the primary hosted surface

### E2-11 Extend the release gate for Worker smoke

Acceptance:

- release review proves the Worker route resolves a real emitted `queryTemplate`
- same-origin hosted query remains part of the canonical release gate

## Explicit non-goals

Do not use this rewrite to add:

- search or browse UX
- repository discovery
- live mutation APIs
- claim-history endpoints
- per-user state
- real-time freshness promises beyond snapshot replacement

## Current status

As of now:

- local same-origin runtime exists in `dotrepo-public-query`
- export now emits repo-scoped `query-input/<host>/<owner>/<repo>.json`
  artifacts from the reviewed snapshot
- core now has a pure snapshot query function that can answer the current `v0`
  query wrapper from those artifacts
- release bundles and the release gate already cover that runtime locally
- deployed hosting is still static GitHub Pages

So the remaining gap is the Worker route and deployment workflow, not public
query semantics or snapshot data shape.
