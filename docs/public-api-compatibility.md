# Public API Compatibility

This doc is the current compatibility note for the public read-only dotrepo
surface.

It covers the `v0` contracts for:

- repository summary
- trust wrapper
- query wrapper
- machine-readable public errors
- static inventory under `public/v0/repos/index.json`

## Current rule

Within `apiVersion = "v0"`:

- existing field names are treated as stable
- existing link-key names are treated as stable
- existing machine-readable error codes are treated as stable
- additive fields are allowed only when they do not rename, remove, or change
  the meaning of current fields

That means `v0` may still grow, but it should not silently reshuffle existing
JSON contracts.

## Source of truth

The executable compatibility source of truth lives in:

- `crates/dotrepo-core/tests/fixtures/public-contract/compatibility.json`
- `crates/dotrepo-core/tests/public_contract_compatibility.rs`

The checked-in manifest freezes:

- required top-level keys for summary, trust, query, inventory, and error
  responses
- required nested keys for freshness, selection, record summaries, artifact
  locators, and claim context
- stable link-key names for summary, trust, query, and inventory entries
- the current machine-readable public error codes:
  - `invalid_repository_identity`
  - `query_path_not_found`
  - `repository_not_found`

## Relationship to RFCs

RFCs 0016 through 0019 still describe the design direction and public-serving
intent. This doc and the compatibility test are narrower: they define what the
repo currently treats as the frozen `v0` wire contract.

If the public contract changes intentionally, update:

1. the RFC or docs that explain the change
2. the fixture packs or public export expectations
3. `compatibility.json`
4. the release note and checklist if the change is externally visible
