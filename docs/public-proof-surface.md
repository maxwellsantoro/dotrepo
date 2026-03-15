# Public proof surface

## Decision

The public proof surface is still anchored on the exported JSON tree, with a
thin hosted-static deployment path layered on top.

That proof surface is:
- the exported `public/v0/` JSON tree
- the CI artifact `public-export-v0`
- the GitHub Pages deployment workflow in `.github/workflows/public-pages.yml`
- the docs that explain how to generate, inspect, and reason about that tree

Adjacent proof artifact:
- the `operator-gate-live-seed-handoff-public` CI artifact, which stages one
  copied seed entry through accepted claim handoff and exports the result

## Why this choice

The exported artifact is still the right center of gravity because it:
- stays fully downstream of the exported JSON tree
- gives humans and agents one inspectable artifact immediately
- keeps the hosted deployment path downstream of the same files and contracts
- avoids inventing a second runtime-specific truth model

## What ships in this first proof surface

### For humans

- the CI artifact `public-export-v0`
- the CI artifact `public-export-v0-bundle`
- the GitHub Pages deployment workflow
- the operator loop in [`docs/public-export-workflow.md`](./public-export-workflow.md)
- the release-style note in [`docs/public-proof-release-note.md`](./public-proof-release-note.md)
- the current public response contracts in RFCs 0017, 0018, and 0019

### For agents

- stable `meta.json`
- stable repository `index.json`
- stable repository `trust.json`
- the same claim-aware selection and conflict semantics already used by local
  query/trust flows

## What this proves

This proof surface demonstrates that dotrepo can:
- render the seed index into a real read-only public artifact
- keep public responses identity-first and trust-aware
- expose claim-aware visibility without inventing a second semantic layer
- publish one reviewable snapshot and deploy the same tree without a second
  runtime

The separate operator-gate artifact demonstrates one thing the checked-in seed
index still does not: a staged overlay-to-claim handoff exported through the
same public JSON path. That boundary is deliberate so the live proof surface
does not pretend a real repository already has a published reviewed maintainer
handoff.

## What this does not prove yet

It does not yet prove:
- public search or browse UX
- runtime caching strategy beyond static hosting
- production-grade operations or public SLA expectations

## How to use it now

1. Review the deterministic fixture pack if the contract changed.
2. Review the CI artifact if the current seed index output changed.
3. Regenerate the tree locally when you need a fresh export from `index/`.

Start with:
- [`docs/public-export-workflow.md`](./public-export-workflow.md)
- [`rfcs/0017-public-repository-summary-response.md`](../rfcs/0017-public-repository-summary-response.md)
- [`rfcs/0018-static-public-serving-and-freshness.md`](../rfcs/0018-static-public-serving-and-freshness.md)
- [`rfcs/0019-public-trust-and-query-wrappers.md`](../rfcs/0019-public-trust-and-query-wrappers.md)

## Upgrade path

The next step is not a second proof surface. It is hardening the hosted-static
deployment path and, later, adding a thin query wrapper over the same response
contracts.
