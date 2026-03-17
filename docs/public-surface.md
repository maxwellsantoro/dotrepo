# Public surface

## What it is

The dotrepo public surface is a hosted read-only JSON tree deployed through
GitHub Pages. It provides repository identity, trust context, and claim-aware
selection to humans and agents without requiring local tooling or index access.

The public surface consists of:
- the hosted `v0/` JSON tree at the GitHub Pages deployment URL
- the CI-generated `public-export-v0` and `public-export-v0-bundle` artifacts
- the GitHub Pages deployment workflow in `.github/workflows/public-pages.yml`
- the `v0` public contracts defined in RFCs 0016 through 0019

## Why this architecture

The static hosted surface is the right default because it:
- stays fully downstream of the exported JSON tree
- gives humans and agents one inspectable surface immediately
- keeps the hosted deployment and CI artifacts sharing the same files and contracts
- avoids inventing a second runtime-specific truth model

## What ships

### For humans

- hosted repository summary and trust responses at stable URLs
- the CI artifact `public-export-v0` for offline inspection
- the CI artifact `public-export-v0-bundle` for versioned review snapshots
- the operator loop in [`docs/public-export-workflow.md`](./public-export-workflow.md),
  with `scripts/check_release_gate.py` as the canonical release review entrypoint
- the release note in [`docs/public-release-note.md`](./public-release-note.md)
- the accepted `v0` public contracts in RFCs 0016 through 0019
- the `v0` compatibility note in
  [`docs/public-api-compatibility.md`](./public-api-compatibility.md)
- the canonical freshness reference in
  [`docs/public-freshness.md`](./public-freshness.md)

### For agents

- stable `meta.json` with snapshot digest and freshness metadata
- stable repository `index.json` with inventory and navigation links
- stable per-repository `trust.json` with selection, conflict, and claim context
- the same claim-aware selection and conflict semantics used by local
  query/trust flows
- a stable `queryTemplate` contract in public responses, even though the hosted
  static tree does not precompute arbitrary query-path outputs yet

## What the public surface provides

The hosted public surface provides:
- read-only repository summary and trust responses
- identity-first, trust-aware public responses
- claim-aware visibility without a second semantic layer
- a live accepted maintainer-claim example from the checked-in index, currently
  `github.com/maxwellsantoro/ries-rs` with `superseded` handoff state linked to
  its upstream `.repo`
- one deployable snapshot from the same export used for local review

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
- search or browse UX
- runtime caching beyond static hosting
- public SLA expectations

## How to use it

The primary consumption path is the hosted GitHub Pages deployment. For local
review or CI inspection, start with the canonical release gate:

```bash
python3 scripts/check_release_gate.py --output-root release-gate
```

Then, if needed:

1. Review the deterministic fixture pack if the contract changed.
2. Review the CI artifact if the current seed index output changed.
3. Regenerate the tree locally when you need a fresh export from `index/`.

Start with:
- [`docs/public-export-workflow.md`](./public-export-workflow.md)
- [`rfcs/0017-public-repository-summary-response.md`](../rfcs/0017-public-repository-summary-response.md)
- [`rfcs/0018-static-public-serving-and-freshness.md`](../rfcs/0018-static-public-serving-and-freshness.md)
- [`rfcs/0019-public-trust-and-query-wrappers.md`](../rfcs/0019-public-trust-and-query-wrappers.md)

## Next steps

The next evolution is adding a thin query wrapper over the same response
contracts and hardening freshness and caching for the hosted deployment. For
the freshness definitions that apply to those responses, see
[`docs/public-freshness.md`](./public-freshness.md).
