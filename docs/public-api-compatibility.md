# Public API Compatibility

This doc is the current compatibility note for the public read-only dotrepo
surface.

It covers the `v0` contracts for:

- repository summary
- compact research profile
- structured profile search
- factual profile comparison
- typed relationship traversal with semantic inverse edges
- batch profile and batch field lookup
- trust wrapper
- query wrapper
- machine-readable public errors
- static inventory under `public/v0/repos/index.json`
- static file manifest under `public/v0/files.json`

## Current rule

Within `apiVersion = "v0"`:

- existing field names are treated as stable
- existing link-key names are treated as stable
- existing machine-readable error codes are treated as stable
- additive fields are allowed only when they do not rename, remove, or change
  the meaning of current fields
- optional advisory fields such as profile `synthesis` must remain separate
  from factual fields and must not change their precedence semantics
- typed relation items may add optional relation-local `trust` and `notes`;
  legacy reference items retain the original required item keys
- profile execution may add optional `buildContext`/`testContext` and candidate
  `context`; [RFC 0021](../rfcs/0021-value-bound-execution-context.md) defines
  their value binding, scope, directory, prerequisites, and source. Missing
  context remains unassessed and does not receive inferred defaults.

That means `v0` may still grow, but it should not silently reshuffle existing
JSON contracts.

## Intentional value change: `verified` is now `checked` (2026-11-03)

The record status and trust provenance value `verified` is renamed `checked`.
It never meant human review or correctness, only that every field passed the
automated pipeline checks, and the old word needed a disclaimer wherever it
appeared. Field names, links and error codes are unchanged; only this value
changes, in `recordStatus`, `selectedStatus`, `record.status` and
`trust.provenance`.

- Exports generated from this change onward emit `checked`.
- Archived snapshots keep the value they were published with, so a consumer
  reading history sees both. Treat `verified` and `checked` as the same status.
- `.repo` files and index records that say `verified` still parse and validate;
  tools read them as `checked` and write `checked`.
- The released `dotrepo-mcp` passes hosted JSON through without interpreting
  this value, so existing installs keep working.

## Source of truth

The executable compatibility source of truth lives in:

- `crates/dotrepo-core/tests/fixtures/public-contract/compatibility.json`
- `crates/dotrepo-core/tests/public_contract_compatibility.rs`

The checked-in manifest freezes:

- required top-level keys for metadata, file manifest, summary, profile, search,
  compare, relations, batch profile, batch query, trust, query, inventory, and
  error responses
- required nested keys for freshness, selection, record summaries, artifact
  locators, and claim context
- stable link-key names for summary, profile, trust, query, and inventory entries
- batch item success/error envelope keys
- metadata validator keys and file-manifest entry keys
- the current machine-readable public error codes:
  - `invalid_repository_identity`
  - `query_path_not_found`
  - `repository_not_found`

For the canonical definitions of `generatedAt`, `snapshotDigest`,
`staleAfter`, and `record.generated_at`, see
[`docs/public-freshness.md`](./public-freshness.md).

## Relationship to RFCs

RFCs 0016 through 0019 are now the accepted `v0` public launch docs. This doc
and the compatibility test are narrower: they define the exact checked-in
wire-level keys, links, and error codes that those RFCs must not drift from
within `apiVersion = "v0"`.

If the public contract changes intentionally, update:

1. the RFC or docs that explain the change
2. the fixture packs or public export expectations
3. `compatibility.json`
4. the release note and checklist if the change is externally visible
