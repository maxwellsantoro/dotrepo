# Public proof release checklist

Use this checklist when cutting or reviewing a public proof release from the
exported JSON tree.

## Local generation

- `python3 scripts/check_release_gate.py --output-root release-gate`
- `cargo run -p dotrepo-cli -- validate-index`
- `cargo test -p dotrepo-core --test public_export_fixture_pack -- --nocapture`
- `cargo run -p dotrepo-cli -- public export --index-root index --out-dir public --base-path /dotrepo --generated-at 2026-03-10T18:30:00Z --stale-after 2026-03-11T18:30:00Z`
- `python3 scripts/render_public_pages_landing.py --input public`
- `python3 scripts/package_public_export.py --input public --output-dir dist`

The script is the intended release-surface gate. The individual commands are
still useful when reviewing only one part of the public/export flow.

## Artifact inspection

- `public/v0/meta.json` exists and has the expected `apiVersion`
- `public/v0/repos/index.json` exists and `repositoryCount` matches the bundle
- inventory links honor the hosted `--base-path`
- `public/index.html` and `.nojekyll` exist for hosted static entry
- representative repository `index.json` and `trust.json` files open cleanly
- the packaged bundle extracts to one self-describing root directory
- the release binary bundle contains `dotrepo`, `dotrepo-lsp`, and `dotrepo-mcp`
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
- the GitHub Pages workflow can deploy the same tree without editing links by hand
- the `release-artifacts` workflow publishes tagged CLI/LSP/MCP bundles and a VSIX
- the release-style note is current
- the usage examples still match the exported tree

## Non-goals check

- no search/browse UX promise was added implicitly
- no production-hardening claim was added implicitly
