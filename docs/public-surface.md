# Public surface

## What it is

The dotrepo public surface is a human-readable website backed by a hosted,
read-only JSON tree and thin query contract. It provides repository identity,
trust context, and claim-aware selection without requiring local tooling or
index access.

The public surface consists of:
- the deployed `v0/` JSON tree and same-origin query route at
  `https://dotrepo.org/`
- the homepage, documentation, writing, and searchable repository catalog
- the local and release-reviewed same-origin hosted-query runtime
  `dotrepo-public-query`
- export-time `query-input/` artifacts that capture repo-scoped hosted-query
  snapshot inputs without runtime TOML traversal
- an in-repo Cloudflare Worker project that serves the same `v0` query route
  from those snapshot inputs during local review, release-gate smoke, and the
  deployed `dotrepo.org` public origin
- the CI-generated `public-export-v0` and `public-export-v0-bundle` artifacts
- the Cloudflare deployment workflow in `.github/workflows/public-cloudflare.yml`
- the `v0` public contracts defined in RFCs 0016 through 0019

## Why this architecture

The export-first hosted surface is the right default because it:
- stays fully downstream of the exported JSON tree
- gives humans and agents one inspectable surface immediately
- keeps deployed hosting, local runtime review, and CI artifacts sharing the
  same files and contracts
- avoids inventing a second runtime-specific truth model

## What ships

### For humans

- a searchable repository catalog at `https://dotrepo.org/repositories/`
- product, protocol, and trust documentation on the same origin
- hosted repository summary, compact profile, and trust responses at stable
  URLs
- a deployed same-origin query runtime on the public origin
- the CI artifact `public-export-v0` for offline inspection
- the CI artifact `public-export-v0-bundle` for versioned review snapshots
- the operator loop in [`docs/public-export-workflow.md`](./public-export-workflow.md),
  with `scripts/check_release_gate.py` as the canonical release review entrypoint
- the accepted `v0` public contracts in RFCs 0016 through 0019
- the `v0` compatibility note in
  [`docs/public-api-compatibility.md`](./public-api-compatibility.md)
- the canonical freshness reference in
  [`docs/public-freshness.md`](./public-freshness.md)

### For agents

- stable `meta.json` with snapshot digest and freshness metadata
- stable `files.json` with per-file SHA-256 and byte-size metadata for
  delta-friendly consumers
- deterministic `files.json` delta reports through
  `scripts/diff_public_export_files.py` for mirrors and agent caches
- deterministic profile coverage reports through
  `scripts/check_public_profile_coverage.py` for profile-count and
  high-signal gates, plus per-signal minimum gates for completeness growth
- stable repository `index.json` with inventory and navigation links
- stable per-repository `profile.json` with compact research fields,
  completeness signals, record freshness, evidence path, and trust context
- optional profile `synthesis` sections loaded from validated `synthesis.toml`
  sidecars, kept separate from factual profile fields
- stable per-repository `trust.json` with selection, conflict, and claim context
- local and CLI batch profile/query responses for repeated known-repository
  access
- hosted GET batch routes at `/v0/batch/profiles?repo=...` and
  `/v0/batch/query?repo=...&path=...`
- local and hosted structured profile search through `dotrepo public search`
  and `/v0/search`, covering text, language, topic, trust, and completeness
  filters with relevance ranking metadata kept separate from trust
- local and hosted factual profile comparison through `dotrepo public compare`
  and `/v0/compare`, returning side-by-side trust, completeness, shared
  language/topic, and profile signals
- local and hosted relationship traversal through `dotrepo public relations`
  and `/v0/repos/<host>/<owner>/<repo>/relations`, resolving declared outgoing
  legacy references plus trust-bearing `reference`, `alternative`, `dependency`,
  `predecessor`, `fork`, and `related` assertions. Incoming traversal reports
  semantic inverses such as `depended_on_by`, `successor`, and `forked_by` when
  the related repository exists in the same index
- a deterministic lookup-efficiency benchmark harness for measuring task hit
  rate, field hit rate, and compact payload bytes against representative
  workloads
- a deterministic search-quality benchmark harness for measuring discovery
  success rate, rank quality, searched profile bytes, and freshness against
  representative workloads
- the same claim-aware selection and conflict semantics used by local
  query/trust flows
- a stable `queryTemplate` contract in public responses, with deployed,
  same-origin resolution on `dotrepo.org`

## What the public surface provides

The hosted public surface provides:
- read-only repository summary, profile, and trust responses
- compact per-repository research profiles for known repository identities
- batch profile and batch field lookup through the reference CLI/core contract
  and hosted GET routes
- structured profile search, factual profile comparison, and reference/
  referenced-by traversal through the reference CLI/core contract and hosted GET
  routes
- optional bounded synthesis in profile responses when a valid synthesis sidecar
  is present for the selected record
- identity-first, trust-aware public responses
- snapshot validators and a file manifest for cheap revalidation and selective
  refetch
- claim-aware visibility without a second semantic layer
- a live accepted maintainer-claim example from the checked-in index, currently
  `github.com/maxwellsantoro/ries-rs` with `superseded` handoff state linked to
  its upstream `.repo`
- one deployable snapshot from the same export used for local review
- one same-origin runtime shape that can serve the exported tree and query
  responses from the same snapshot family during deployment, local review, and
  release smoke checks
- one repo-scoped query-input artifact family that backs the live Worker route
  from the same validated snapshot
- one Worker route implementation that preserves the current error-vocabulary
  semantics on the live public origin

Freshness on the hosted JSON is snapshot-first:
- `freshness.generatedAt`, `freshness.snapshotDigest`, and `freshness.staleAfter`
  follow the public freshness reference in
  [`docs/public-freshness.md`](./public-freshness.md)
- per-record crawl freshness remains a record concern via `record.generated_at`,
  not a separate public truth model

The operator-gate CI artifact separately demonstrates the overlay-to-claim
handoff path with canonical links exported through the same public JSON
contracts.

## What is not yet in scope

The public surface does not yet include:
- production synthesis generation or richer semantic relationship classes beyond
  reference/referenced-by traversal
- live mutation or submission APIs
- public SLA expectations

## How to use it

The primary deployed consumption path is now `https://dotrepo.org/`. For local
review or CI inspection, start with the canonical release gate:

```bash
uv run python scripts/check_release_gate.py --output-root release-gate
```

Then, if needed:

1. Review the deterministic fixture pack if the contract changed.
2. Review the CI artifact if the current index output changed.
3. Regenerate the tree locally when you need a fresh export from `index/`.

Start with:
- [`docs/public-export-workflow.md`](./public-export-workflow.md)
- [`rfcs/0017-public-repository-summary-response.md`](../rfcs/0017-public-repository-summary-response.md)
- [`rfcs/0018-static-public-serving-and-freshness.md`](../rfcs/0018-static-public-serving-and-freshness.md)
- [`rfcs/0019-public-trust-and-query-wrappers.md`](../rfcs/0019-public-trust-and-query-wrappers.md)

## Next steps

The next public-surface work is hardening freshness and caching, scaling profile
coverage through planned crawl tranches, running the lookup-efficiency benchmark
on a larger representative workload, and eventually building discovery and
comparison on top of the trusted index. See
[`ROADMAP.md`](../ROADMAP.md) for the active sequence. For the freshness
definitions that apply to responses, see
[`docs/public-freshness.md`](./public-freshness.md). For deployment operations,
see [`docs/cloudflare-deploy.md`](./cloudflare-deploy.md).
