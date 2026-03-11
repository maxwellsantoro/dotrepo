# RFC 0018: Static public serving and freshness metadata

## Status
Draft

## Summary

This RFC chooses the first delivery strategy for dotrepo public index serving.

The day-one choice is:
- static-first, identity-first JSON export for repository summary and trust
  surfaces
- on-demand query wrapping kept compatible with the same public response model
- explicit freshness metadata carried on every public response

This is intentionally operationally simple. The first public release should
distribute index semantics, not prove a dynamic hosting stack.

## Why

RFC 0016 explicitly deferred the serving stack. That was the right choice while
the protocol, trust model, and claim workflow were still in motion.

Now that the public-serving tranche has started, the project still needs one
concrete answer to:
- what is precomputed
- what is served dynamically later
- how public consumers know what snapshot they are looking at

The current repo shape strongly favors a static-first approach:
- the index is Git-backed and read-only for public consumers
- repository detail responses are identity-first, not search-first
- selection, conflict, and claim-aware visibility already exist as deterministic
  local semantics

## Chosen strategy

### Day-one strategy: static summary and trust, query wrapper ready for later

The first public-serving implementation should:
- precompute repository summary responses
- precompute repository trust responses
- expose the public query wrapper as a stable response contract and local export
  helper, without requiring the first public release to precompute arbitrary
  query-path outputs

This is a staged combination, but it is still static-first in the only places
that matter for the initial public UX:
- repository detail pages
- trust explanation pages

### Why not full dynamic first

A dynamic-first serving stack would force decisions about:
- hosting runtime
- request routing
- caching
- abuse handling
- operational monitoring

before the project has even proven the simplest public read-only flow.

That is the wrong inversion of risk.

### Why not fully static query precomputation

The query endpoint accepts arbitrary dot-paths. Precomputing every possible path
would either:
- explode the output surface, or
- force a prematurely curated query allowlist

Neither is necessary for the first public release.

## Delivery model

The recommended first delivery model is:

1. generate a static JSON tree from the checked-in index snapshot
2. host that tree behind ordinary static hosting or cache-heavy object storage
3. allow a later lightweight query wrapper to read from the same snapshot and
   preserve the same public response semantics

The static tree should be compatible with either:
- a later CDN-only site
- a later cache-heavy API
- a later thin dynamic wrapper for the query endpoint

## Recommended export layout

```text
public/
  v0/
    meta.json
    repos/
      github.com/
        acme/
          widget/
            index.json
            trust.json
```

Recommended meanings:
- `index.json` -> repository summary response for `GET /v0/repos/{host}/{owner}/{repo}`
- `trust.json` -> trust response for `GET /v0/repos/{host}/{owner}/{repo}/trust`
- `meta.json` -> snapshot-wide export metadata

The public query wrapper should reuse the same response envelope, but does not
need a precomputed static file for every possible path.

## Freshness metadata

Every public response should include a `freshness` block.

Recommended day-one shape:

```json
{
  "freshness": {
    "generatedAt": "2026-03-10T18:30:00Z",
    "snapshotDigest": "3c29d77b5b1f...",
    "staleAfter": "2026-03-11T18:30:00Z"
  }
}
```

Required fields:
- `generatedAt`
- `snapshotDigest`

Optional field:
- `staleAfter`

### `generatedAt`

Timestamp for when the public response or static export was produced.

This is not a promise that the underlying repository changed at that moment. It
only tells the consumer when dotrepo produced the response they are reading.

### `snapshotDigest`

Digest for the exported index snapshot.

This should be stable across all responses produced from the same export run and
change whenever the underlying exported index content changes.

It lets:
- site pages verify they are rendering one consistent snapshot
- API clients detect whether cached responses came from the same export
- later dynamic wrappers stay aligned with a static snapshot contract

### `staleAfter`

Optional advisory timestamp for when a client should consider the response
stale enough to revalidate or refetch.

This is an operational hint, not a real-time guarantee.

## Deterministic export review mode

The reference CLI may offer a deterministic export mode for fixture generation,
golden-output review, and CI.

That mode may fix `generatedAt` and `staleAfter` explicitly while still
recomputing `snapshotDigest` from the index snapshot being exported.

This is a tooling affordance, not a second public contract:
- ordinary export runs should still emit real generation timestamps
- deterministic runs should preserve the exact same response shapes and
  selection/trust semantics
- `snapshotDigest` should continue to reflect the exported input tree rather
  than an injected placeholder value

## Snapshot-wide metadata

The static export should also produce one snapshot-wide metadata document such
as:

```json
{
  "apiVersion": "v0",
  "generatedAt": "2026-03-10T18:30:00Z",
  "snapshotDigest": "3c29d77b5b1f...",
  "staleAfter": "2026-03-11T18:30:00Z",
  "strategy": "static_summary_and_trust"
}
```

This file is useful for:
- static site build verification
- external mirrors
- future cache invalidation and roll-forward logic

## Compatibility rules

The strategy must preserve these constraints:
- repository summary and trust responses stay downstream of existing local
  semantics
- query wrapper semantics remain compatible with the same public response model
- freshness metadata does not imply real-time guarantees
- claim-aware visibility remains compatible with RFC 0012 and later public claim
  surfaces

## Explicit deferrals

This RFC does not define:
- final HTTP runtime or vendor choice
- global search indexing
- live mutation or submission APIs
- authenticated public claim actions
- real-time invalidation or push updates
- per-user caching behavior

## Relationship to other RFCs

- RFC 0016 defines the overall public-serving direction.
- RFC 0017 defines the repository summary response.
- Later trust and query wrapper work should use this RFC's freshness block and
  static-first delivery assumptions.
