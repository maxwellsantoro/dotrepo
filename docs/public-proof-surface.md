# Public proof surface

## Decision

The first proof surface for the public JSON tree is a release-style artifact
surface, not a hosted demo.

That proof surface is:
- the exported `public/v0/` JSON tree
- the CI artifact `public-export-v0`
- the docs that explain how to generate, inspect, and reason about that tree

## Why this choice

Two options were on the table:

1. a thin hosted demo over the exported JSON tree
2. a release-style “what exists now” surface centered on the exported artifact

The second option is the better first move because it:
- stays fully downstream of the exported JSON tree
- gives humans and agents one inspectable artifact immediately
- avoids prematurely choosing a hosting/runtime stack
- remains easy to replace later with a thin hosted surface if the artifact
  proves useful

## What ships in this first proof surface

### For humans

- the CI artifact `public-export-v0`
- the CI artifact `public-export-v0-bundle`
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
- publish one reviewable snapshot without waiting for a hosted product surface

## What this does not prove yet

It does not yet prove:
- permanent hosting
- public search or browse UX
- runtime caching strategy beyond the current export artifact
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

If this proof surface becomes clearly useful, the next step can be a thin hosted
reader over the same exported JSON tree or the same response contracts.

That future step should remain downstream of the current artifact, not replace
it with a second independent truth model.
