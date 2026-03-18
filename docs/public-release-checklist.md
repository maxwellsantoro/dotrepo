# Public release checklist

Use this checklist when cutting or reviewing a public release from the exported
JSON tree.

## Local generation

- `python3 scripts/check_release_gate.py --output-root release-gate`
- `cargo run -p dotrepo-cli -- validate-index`
- `cargo test -p dotrepo-core --test public_export_fixture_pack -- --nocapture`
- `cargo test -p dotrepo-core --test public_contract_compatibility`
- `cargo run -p dotrepo-cli -- public export --index-root index --out-dir public --base-path /dotrepo --generated-at 2026-03-10T18:30:00Z --stale-after 2026-03-11T18:30:00Z`
- `python3 scripts/render_public_pages_landing.py --input public`
- `python3 scripts/sync_cloudflare_public_snapshot.py --input public --output cloudflare/hosted-query/public-snapshot`
- `python3 scripts/package_public_export.py --input public --output-dir dist`

The script is the canonical operator release review entrypoint. The individual
commands are still useful when reviewing only one part of the public/export
flow or when isolating a failure already identified by the gate.
For the canonical freshness semantics used by these outputs, see
[`docs/public-freshness.md`](./public-freshness.md).

## Artifact inspection

- `public/v0/meta.json` exists and has the expected `apiVersion`
- the required `v0` response/link/error keys still match `docs/public-api-compatibility.md`
- `public/v0/repos/index.json` exists and `repositoryCount` matches the bundle
- inventory links honor the hosted `--base-path`
- `public/index.html` and `.nojekyll` exist for the hosted static entry
- representative repository `index.json` and `trust.json` files open cleanly
- representative `query-input/<host>/<owner>/<repo>.json` files exist for the
  same repositories
- the packaged bundle extracts to one self-describing root directory
- the release binary bundle contains `dotrepo`, `dotrepo-public-query`, `dotrepo-lsp`, and `dotrepo-mcp`
- the release binary smoke test passes (binaries execute from extracted bundle)
- the release gate proves a shipped `dotrepo-public-query` binary can serve the
  exported public tree and resolve a real emitted `queryTemplate` on one origin
- the release gate proves the Cloudflare Worker route resolves that same
  emitted `queryTemplate` from the staged export snapshot
- the VS Code release asset installs from a tagged `.vsix`

## Review questions

- Did the source index change, or only the exported surface?
- Did response shape drift intentionally?
- Did claim visibility or trust selection change intentionally?
- Did only review-time freshness metadata change?

## CI and release surface

- CI runs `scripts/check_release_gate.py` and uploads:
  - `public-export-v0`
  - `public-export-v0-bundle`
  - `release-gate-install-bundles`
  - `release-gate-vscode-vsix`
- the same script is the local and CI release review gate
- the release gate smoke tests the extracted release binaries
- the release gate smoke tests same-origin hosted query resolution against the
  exported public tree
- the release gate smoke tests the Cloudflare Worker route against that same
  exported public tree
- the current GitHub Pages workflow deploys the same static tree without
  editing links by hand
- the opt-in Cloudflare deploy workflow builds a Worker-backed hosted surface
  from the reviewed export snapshot when enabled with repository vars/secrets
- the `release-artifacts` workflow publishes tagged `dotrepo`,
  `dotrepo-public-query`, `dotrepo-lsp`, and `dotrepo-mcp` binary bundles plus
  a VSIX
- the release note is current
- the usage examples still match the exported tree

## Non-goals check

- no search/browse UX promise was added implicitly
