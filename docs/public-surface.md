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

The hosted and local public surface gives agents read-only, identity-first,
trust-aware access to the indexed understanding: repository summary, compact
research profiles, trust/conflict context, batch profile and field lookup,
structured profile search, factual profile comparison, and relationship
traversal (including semantic reverse edges such as `depended_on_by` and
`forked_by`) — all through both the reference CLI/core contract and matching
hosted GET routes. Optional profile `synthesis` sections (from validated
`synthesis.toml` sidecars) stay separate from factual fields. A live accepted
maintainer-claim example (`github.com/maxwellsantoro/ries-rs`) demonstrates
claim-aware visibility end to end.

Snapshot-level mechanics for agents and mirrors:
- `meta.json` is the one mutable pointer to a content-addressed tree under
  `/v0/snapshots/<snapshotId>/`; its canonical `files.json`
  (per-file SHA-256 and byte size) support cheap revalidation and selective
  refetch; `scripts/diff_public_export_files.py` turns two `files.json`
  manifests into a delta report
- `/.well-known/pagedigest.json` publishes the same change-detection signal
  through the standard pagedigest protocol (v1 RC): monotonic per-URL
  revisions and auditable SHA-256 digests covering the `/v0/repos/` tree, so
  generic pagedigest consumers can skip unchanged records with one manifest
  request. Revisions track material content change (the volatile `freshness`
  block is excluded), so a re-export with an unchanged index does not churn
  revisions; each entry's `content_digest` extension field carries that state
  forward between exports. The checked-in
  `public/.well-known/pagedigest.json` is the durable revision baseline; the
  deploy workflow passes it to `public export --pagedigest-previous` so
  revisions stay monotonic across fresh export directories
- `scripts/check_public_profile_coverage.py` reports profile-count and
  high-signal coverage gates
- deterministic lookup-efficiency and search-quality benchmark harnesses
  measure hit rate, rank quality, and payload bytes against representative
  workloads
- a stable `queryTemplate` contract resolves same-origin on `dotrepo.org`

For the exact command and route shape of every capability above, see
[`docs/public-export-examples.md`](./public-export-examples.md). For the
operator/CI loop that produces and reviews this surface, see
[`docs/public-export-workflow.md`](./public-export-workflow.md).

## What the public surface provides

The hosted public surface is read-only and downstream of the exported JSON
tree: it does not add a second semantic layer beyond what's described above.
One deployable snapshot serves local review, CI artifacts, and the deployed
Worker route alike, backed by repo-scoped `query-input/` artifacts validated
against that same snapshot.

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
