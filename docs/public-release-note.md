# Public JSON-tree release

This note is the current release summary for dotrepo's public JSON tree.

## What exists now

The current release includes:
- a static `public/v0/` JSON tree hosted through GitHub Pages
- snapshot metadata in `meta.json` with digest and freshness
- a bundle-level repository inventory in `repos/index.json`
- per-repository summary and trust documents
- live accepted maintainer-claim context for
  `github.com/maxwellsantoro/ries-rs`, linked to a published canonical `.repo`
- a CI artifact for the loose tree
- a CI artifact for a versioned review bundle
- a GitHub Pages deployment workflow with root landing page

## What this provides

The hosted public surface provides:
- read-only repository identity and trust inspection without cloning the index
- identity-first, trust-aware responses for both human and agent consumption
- claim-aware visibility surfacing maintainer handoff context in public responses
- one deployable snapshot from the same export tree used for local review and CI

## What to inspect first

Start with the hosted deployment URL, then:
- `v0/meta.json` for snapshot metadata
- `v0/repos/index.json` for the repository inventory
- one repository `v0/repos/<host>/<owner>/<repo>/index.json` for a summary
- the matching `trust.json` for trust and selection context

For the current operator and review loop, see
[`docs/public-export-workflow.md`](./public-export-workflow.md).

For the public surface architecture, see
[`docs/public-surface.md`](./public-surface.md).

## What is not yet in scope

This release does not yet include:
- search or browse UX beyond the exported tree
- live mutation or submission APIs

## Current artifact names

CI publishes:
- `public-export-v0` for the loose exported tree
- `public-export-v0-bundle` for the packaged review bundle
