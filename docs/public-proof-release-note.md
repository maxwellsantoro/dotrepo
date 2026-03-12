# Public JSON-tree proof release

This note is the current release-style summary for dotrepo's public JSON tree.

It is intentionally modest. The project can now produce, package, and publish a
read-only public export artifact, but that is still different from claiming a
hosted public product surface.

## What exists now

The current proof release includes:
- a static `public/v0/` JSON tree
- snapshot metadata in `meta.json`
- a bundle-level repository inventory in `repos/index.json`
- per-repository summary and trust documents
- a CI artifact for the loose tree
- a CI artifact for a versioned review bundle

## Why this matters

This is the first outward-facing proof that dotrepo can:
- turn the checked-in index into one inspectable public artifact
- keep public responses identity-first and trust-aware
- surface claim-aware visibility without creating a second semantic layer
- support both human review and agent consumption from the same exported tree

## What to inspect first

Start with:
- `public/v0/meta.json`
- `public/v0/repos/index.json`
- one repository `public/v0/repos/<host>/<owner>/<repo>/index.json`
- the matching `trust.json`

If you want the current operator loop, see
[`docs/public-export-workflow.md`](./public-export-workflow.md).

If you want the reasoning behind the proof-surface choice, see
[`docs/public-proof-surface.md`](./public-proof-surface.md).

## What this does not promise yet

This proof release does not yet promise:
- permanent public hosting
- search or browse UX beyond the exported bundle
- live mutation or submission APIs
- production-grade reliability claims

## Current artifact names

CI currently publishes:
- `public-export-v0` for the loose exported tree
- `public-export-v0-bundle` for the packaged review bundle

Those names are enough to make the current proof surface inspectable without
choosing a larger runtime stack first.
