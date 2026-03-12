# Public proof release checklist

Use this checklist when cutting or reviewing a public proof release from the
exported JSON tree.

## Local generation

- `cargo run -p dotrepo-cli -- validate-index`
- `cargo test -p dotrepo-core --test public_export_fixture_pack -- --nocapture`
- `cargo run -p dotrepo-cli -- public export --index-root index --out-dir public --generated-at 2026-03-10T18:30:00Z --stale-after 2026-03-11T18:30:00Z`
- `python3 scripts/package_public_export.py --input public --output-dir dist`

## Artifact inspection

- `public/v0/meta.json` exists and has the expected `apiVersion`
- `public/v0/repos/index.json` exists and `repositoryCount` matches the bundle
- representative repository `index.json` and `trust.json` files open cleanly
- the packaged bundle extracts to one self-describing root directory

## Review questions

- Did the source index change, or only the exported surface?
- Did response shape drift intentionally?
- Did claim visibility or trust selection change intentionally?
- Did only review-time freshness metadata change?

## CI and release surface

- CI uploads both `public-export-v0` and `public-export-v0-bundle`
- the release-style note is current
- the usage examples still match the exported tree

## Non-goals check

- no hosted-runtime claim was added implicitly
- no search/browse UX promise was added implicitly
- no production-hardening claim was added implicitly
