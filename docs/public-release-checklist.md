# Public release checklist

Use this checklist when cutting or reviewing a public release from the exported
JSON tree.

After a stable release is tagged and published, advance the workspace and
standalone alias package to the next SemVer-honest prerelease line in the next
commit. Never leave post-tag development on the published version: a version
must identify one source tree across GitHub, release artifacts, and crates.io.
When cutting a stable release, also advance `DEFAULT_CI_RELEASE_VERSION` in
`crates/dotrepo-core/src/adoption.rs` and regenerate the checked-in native CI
example so new adopters pin an artifact that actually exists.

## Local generation

- `uv run python scripts/check_release_gate.py --output-root release-gate`
- `cargo run -p dotrepo-cli -- validate-index`
- `cargo test -p dotrepo-core --test public_export_fixture_pack -- --nocapture`
- `cargo test -p dotrepo-core --test public_contract_compatibility`
- `cargo run -p dotrepo-cli -- public export --index-root index --out-dir public --base-path / --generated-at 2026-03-10T18:30:00Z --stale-after 2026-03-11T18:30:00Z`
- `uv run python scripts/render_public_pages_landing.py --input public`
- `uv run python scripts/sync_cloudflare_public_snapshot.py --input public --output cloudflare/hosted-query/public-snapshot`
- `uv run python scripts/package_public_export.py --input public --output-dir dist`

The script is the canonical operator release review entrypoint. The individual
commands are still useful when reviewing only one part of the public/export
flow or when isolating a failure already identified by the gate.
The root `public/`, `release-gate/`, and `dist/` outputs are gitignored and
must be regenerated for each review; do not commit them.
For the canonical freshness semantics used by these outputs, see
[`docs/public-freshness.md`](./public-freshness.md).

## Artifact inspection

- `public/v0/meta.json` exists and has the expected `apiVersion`
- `public/v0/meta.json` includes `validators.snapshot` and `validators.etag`
- `public/v0/files.json` exists and lists emitted JSON payloads with SHA-256
  digests
- the required `v0` response/link/error keys still match `docs/public-api-compatibility.md`
- `public/v0/repos/index.json` exists and `repositoryCount` matches the bundle
- inventory links honor the hosted `--base-path`
- `public/index.html` and `.nojekyll` exist for the hosted static entry
- `public/repositories/index.html` exposes the generated catalog
- `public/docs/` and `public/writing/` contain their expected entry pages
- representative repository `index.json`, `profile.json`, and `trust.json`
  files open cleanly
- `public-profile-coverage.json` and `.md` pass the versioned valid-profile,
  high-signal, conflict-rate, malformed-profile, and completeness-signal
  baseline
- `index-growth-plan.json`, `.md`, and `index-growth-targets.txt` pass the
  versioned active-tranche baseline, exclude already-indexed repositories, and
  report planned Milestone 2 capacity without counting it as completed coverage
- `public-lookup-workload.json` covers the release inventory, and
  `public-lookup-efficiency.json` and `.md` pass aggregate and per-intent volume,
  hit-rate, and payload-ratio baselines
- `public-factual-accuracy.json` and `.md` pass every cited exact-value
  assertion, missing-rate ceiling, and mismatch-rate ceiling in the versioned
  cross-ecosystem accuracy sample
- representative `query-input/<host>/<owner>/<repo>.json` files exist for the
  same repositories
- the packaged bundle extracts to one self-describing root directory
- the release binary bundle contains `dotrepo`, `dotrepo-public-query`, `dotrepo-lsp`, and `dotrepo-mcp`
- the release binary smoke test passes (binaries execute from extracted bundle)
- the `publish-crates` release job published all seven crates for the tag,
  including the standalone `dotrepo` alias package (its version and
  `dotrepo-cli` dependency must both match the tag)
- the release gate's hosted-query and Cloudflare Worker smoke checks pass (see
  "What the workflow does after deploy" in
  [`docs/cloudflare-deploy.md`](./cloudflare-deploy.md) for what those checks
  cover)
- the VS Code release asset installs from a tagged `.vsix`

## Review questions

- Did the source index change, or only the exported surface?
- Did response shape drift intentionally?
- Did claim visibility or trust selection change intentionally?
- Did only review-time freshness metadata change?

## CI and release surface

- CI runs `scripts/check_release_gate.py` (the same script as local generation
  above) and uploads `public-export-v0`, `public-export-v0-bundle`,
  `index-growth-plan.json`/`index-growth-targets.txt`,
  `release-gate-install-bundles`, and `release-gate-vscode-vsix`
- the `release-artifacts` workflow publishes tagged binary bundles and a VSIX
- the usage examples still match the exported tree

For what each CI job and smoke check actually does, see "CI artifacts" in
[`docs/public-export-workflow.md`](./public-export-workflow.md) and "What the
workflow does after deploy" in
[`docs/cloudflare-deploy.md`](./cloudflare-deploy.md).

## Non-goals check

- no discovery, ranking, mutation, or SLA contract was added implicitly
