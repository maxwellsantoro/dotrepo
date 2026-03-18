# Hosted Query Serving

This doc freezes the first serving direction for hosted public query responses.

It is intentionally narrower than the public RFCs:

- RFCs 0016 through 0019 define the public contract
- this doc defines the first runtime shape for serving that contract beyond the
  current GitHub Pages static tree

## Current state

What already exists:

- the public query wrapper contract is defined and accepted in
  [`RFC 0019`](../rfcs/0019-public-trust-and-query-wrappers.md)
- the core wrapper implementation already exists in `dotrepo-core` via
  `public_repository_query_or_error_with_base`
- the CLI already exposes the same wrapper locally through `dotrepo public query`
- a thin HTTP runtime binary already exists locally as `dotrepo-public-query`
- that runtime can now also serve an exported `public/` tree on the same origin
  through `--public-root`, so local same-origin review does not require a
  separate static host
- public summary and trust responses are exported as a static tree and deployed
  through GitHub Pages
- public responses already emit a stable `queryTemplate`

What does not exist yet:

- release packaging and deployment for the hosted query runtime
- a deployed route behind the same public contract family as summary and trust

## Decision

The first hosted query target should be a small Rust HTTP service that serves
only the public query route against a read-only exported snapshot.

It should not:

- read from a mutable live index checkout
- invent a second response model
- add search, browse, ranking, or submission behavior
- become the new source of truth for summary or trust responses

The static export remains primary for summary and trust. The query service is a
thin runtime wrapper over the same `v0` public contract family.

## Recommended runtime shape

Use one small HTTP service with:

- a single read-only snapshot root on local disk
- one configured `base_path`
- one query endpoint family under that base path
- no write routes
- no authenticated behavior in the first slice

Recommended route split:

- static hosting continues to serve:
  - `/index.html`
  - `/v0/meta.json`
  - `/v0/repos/index.json`
  - `/v0/repos/.../index.json`
  - `/v0/repos/.../trust.json`
- the query runtime serves:
  - `/v0/repos/{host}/{owner}/{repo}/query?path=...`

The current local runtime can already collapse those into one origin by serving
the exported `public/` tree and the query route from the same process. The
remaining hosted gap is deployment, not route semantics.

## Source of truth

The query runtime should load from the same exported snapshot semantics as the
static public tree.

That means:

- `snapshotDigest` comes from the snapshot the service was started against
- `generatedAt` and `staleAfter` must stay aligned with that snapshot
- the runtime should not synthesize freshness independently per request
- public query responses should match the same snapshot identity as summary,
  trust, inventory, and `meta.json`

The first runtime should prefer reading a read-only copy of the exported index
input or equivalent snapshot directory on disk, not the checked-in repo in a
mutable working tree.

## Request routing and base path

The first implementation should preserve the existing `base_path` model already
used by public export links.

Rules:

- the configured base path is authoritative
- the service should mount query routes under `/<base>/v0/...`
- it should not guess or rewrite around malformed prefixes
- `queryTemplate` should resolve exactly against that configured base path

Example with `base_path = /dotrepo`:

- summary: `/dotrepo/v0/repos/github.com/acme/widget/index.json`
- trust: `/dotrepo/v0/repos/github.com/acme/widget/trust.json`
- query: `/dotrepo/v0/repos/github.com/acme/widget/query?path=repo.description`

## Cache boundaries

The cache model should stay simple:

- static summary and trust files remain cacheable as ordinary static assets
- query responses are cacheable per full request URL plus snapshot identity
- cache invalidation happens by snapshot replacement, not by record-level
  mutation

The first runtime should treat the snapshot as immutable for the life of the
process or deployment revision.

That avoids:

- mixed-snapshot responses
- per-request freshness recomputation
- cache keys that silently drift away from `snapshotDigest`

## Error handling

The first hosted query runtime should preserve the existing machine-readable
error vocabulary:

- `invalid_repository_identity`
- `query_path_not_found`
- `repository_not_found`

Malformed or unsupported requests should fail early and explicitly:

- malformed identity segments should produce `invalid_repository_identity`
- missing `path` should be treated as invalid query input rather than guessed
- unknown repositories should produce `repository_not_found`
- unknown query paths should produce `query_path_not_found`

The runtime should not coerce missing fields into empty strings and should not
flatten equal-authority conflicts.

## Operational constraints

The first hosted query deployment should make these constraints explicit:

- GET-only request surface
- request timeout small enough for cache-heavy public use
- path-length and query-length limits to avoid abuse
- no free-form discovery endpoints
- no dynamic mutation, uploads, or claim actions
- no promise of real-time freshness beyond snapshot replacement

If rate limiting is added, it should live at the HTTP edge or deployment layer,
not in a second application-specific query vocabulary.

## Recommended first implementation slice

Build the first slice in this order:

1. Keep the small Rust HTTP binary that wraps
   `public_repository_query_or_error_with_base` thin and release-packaged.
2. Load one read-only snapshot root and one `base_path` from configuration.
3. Serve only the public query route and a small health check.
4. Reuse the existing public freshness block from the loaded snapshot.
5. Keep parity tests that compare hosted HTTP responses with the existing local
   public query fixtures.

That slice is enough to prove:

- hosted query uses the same contract as local query
- `queryTemplate` can resolve to a real runtime
- freshness stays aligned with the exported snapshot

It is not enough to justify search, browse, or broader public-site expansion.

## Explicit non-goals for the first slice

Do not add:

- search or repository discovery
- aggregate browse endpoints
- public mutation or submission APIs
- claim-history endpoints
- per-user state
- live writes against the checked-in index
- a second public truth model separate from the static export and core wrapper
