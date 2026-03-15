# RFC 0016: Public index site and query API

## Status
Accepted for `v0` public serving

This RFC is now part of the accepted `v0` public launch contract.

Compatibility rule:
- breaking changes to public semantics or endpoint meaning require a new public
  `apiVersion`
- additive fields and implementation details may still evolve within `v0` as
  long as they preserve the accepted response semantics

For the exact checked-in `v0` wire-compatibility surface, see
[`docs/public-api-compatibility.md`](../docs/public-api-compatibility.md).

## Summary

This RFC defines the intended direction for the first public index site and
query API for dotrepo.

The central rule is:
- the public site and API should distribute and explain index data
- they should not become a second protocol with different trust or authority
  semantics

The first public surface should be identity-first, read-only, and explicit about
trust, provenance, and conflict context.

## Why

The index is already a core part of dotrepo's ecosystem story:
- it makes repositories mechanically visible before native adoption
- it gives users and agents a shared place to inspect overlays, canonical
  mirrors, evidence, and later claim history

What does not exist yet is the public serving layer that makes that index easier
to browse and query without cloning the repository or running local tooling.

That public layer should come after the core contract is stable, but before the
project pretends the Git repo itself is the final UX.

## Non-goals

This RFC does not define:
- the final hosting stack
- production moderation tooling
- mutation or submission APIs
- search ranking algorithms
- real-time collaboration features
- claim workflow product UX

## Design principles

### Site and API are downstream of the protocol

The public site and API should reuse the existing protocol semantics:
- record status and trust vocabulary
- `selection` / `conflicts` reasoning
- claim and supersede visibility rules when those surfaces exist

They should not invent a softer or simplified public truth model that conflicts
with the local CLI, MCP, or index contracts.

### Identity-first before discovery-first

The first public surface should optimize for answering:
- what does dotrepo know about this repository identity
- which record is preferred
- what trust context and competing claims exist

It should not start by promising sophisticated search, ranking, or discovery
before the repository-detail surface is trustworthy.

### Read-only first

The first public API should be a read-only inspection surface over the index.

Submission, moderation, and maintainer workflow should stay separate.

## Likely consumers

The first public surface should serve at least these consumers:
- humans who want to inspect one repository and its trust context quickly
- agents and tools that want identity lookup or dot-path query without cloning
  the index
- the future public site itself, which should ideally consume the same
  machine-facing data shape

## Minimum useful site goals

The first public site should support:

### 1. Repository detail pages

A repository page should make it easy to inspect:
- the preferred record
- `record.mode`, `record.status`, `record.source`, and trust context
- evidence links when the preferred or competing record is an overlay
- competing or superseded records when they exist
- links to canonical mirrors or claim artifacts when relevant

### 2. Public trust explanation

The site should explain:
- what canonical, reviewed, verified, imported, inferred, and draft mean
- why one record was selected over another
- why a superseded overlay is still visible

This explanation should be explicit rather than hidden behind tooltips or jargon.

### 3. Claim-aware visibility later

When maintainer-claim workflow exists, the site should be able to show:
- claim existence
- current claim state
- superseded or parallel overlay outcomes
- links to audit artifacts or claim history

That should build on the claim visibility rules rather than re-litigate them in
site-only language.

## First query API surface

The first public API should stay narrow and identity-first.

The most useful day-one endpoints are:

### `GET /v0/repos/{host}/{owner}/{repo}`

Returns a repository summary with:
- preferred record summary
- selection reason
- competing records when present
- stable locators to evidence, claims, or canonical mirrors when relevant

### `GET /v0/repos/{host}/{owner}/{repo}/trust`

Returns the trust-focused view using the same conflict-aware structure as the
local `trust` contract.

### `GET /v0/repos/{host}/{owner}/{repo}/query?path=...`

Returns a dot-path query result using the same `selection` / `conflicts` model
as the local query contract.

Search, filtering, and browse endpoints should remain deferred until these
identity-first surfaces are stable.

## API compatibility rule

The public API should preserve compatibility with existing local semantics.

That means:
- use the same stable `selection.reason` vocabulary where applicable
- use the same `conflicts[].relationship` vocabulary
- keep trust metadata visible in record summaries
- preserve superseded and parallel records instead of flattening them away

The public API may wrap these responses with public-facing metadata, but it
should not reinterpret their semantics.

## Site and API distinction from local tooling

The public site and API are distribution surfaces.

They are not:
- the authoring surface
- the validation surface of record
- the place where protocol semantics are defined

The CLI, MCP, and core library remain the reference for authoring and local
inspection. The public site and API should mirror those semantics as faithfully
as possible.

## Operational and moderation questions

Even as a design note, the public index surface should acknowledge a few
operational realities:

### Freshness and staleness

The public surface should make it clear what index snapshot or update time a
response reflects.

### Abuse and moderation

Later public serving will need a way to handle:
- low-quality overlays
- disputed claims
- misleading evidence or spammy submissions
- abusive query traffic

This RFC does not solve those problems, but it makes them first-class design
inputs.

### Caching and static generation

The first public surface may be statically generated, cache-heavy, or backed by
precomputed JSON. The design should stay compatible with those operationally
simple delivery models.

## Recommended deferrals

The first public index release should defer:
- free-form global search ranking
- authenticated mutation APIs
- public maintainer claim submission
- personalized views or saved collections
- graph visualization for workspaces or relations
- bundle download flows as a first-class public feature

## Worked serving examples

### 1. Repository detail with no conflicts

The site or API should be able to show:
- one preferred record
- its trust metadata
- a simple explanation that no competing records exist

### 2. Canonical record superseding an overlay

The site or API should be able to show:
- the canonical record as preferred
- the older overlay as visible historical context
- why the canonical record won
- where the overlay evidence still lives

### 3. Overlay disagreement with no canonical record

The site or API should be able to show:
- that no canonical authority exists yet
- that competing overlays remain parallel claims
- why the result should not be flattened into one synthetic answer

## Relationship to claims

Public claim surfaces should arrive after the claim-workflow artifacts and
visibility rules are stable enough to serve.

That means the public site and API should not assume:
- claim-product maturity
- final moderation workflow
- final claim submission UX

They should be able to expose claim history later, but they should not force the
claim workflow to be productized prematurely.

## Relationship to future work

This RFC defines the direction for public read-only serving of index data.

Follow-on work should refine:
- first repository-summary response shape (see RFC 0017)
- first trust/query API response wrappers (see RFC 0019)
- static-vs-dynamic serving strategy (see RFC 0018)
- how claim-aware visibility appears in public responses once claim workflow
  lands
