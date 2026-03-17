# Public export workflow

This doc covers the operator and reviewer loop for the read-only public JSON
tree and its hosted deployment.

## What exists now

The public surface is a static JSON tree hosted through GitHub Pages, rooted at:

```text
public/
  v0/
    meta.json
    repos/
      index.json
      <host>/
        <owner>/
          <repo>/
            index.json
            trust.json
```

This surface provides:
- identity-first, trust-aware repository inspection via the hosted deployment
- a bundle-level repository inventory for navigation
- repository summary and trust responses reusing the same local selection,
  conflict, and claim-visibility semantics
- a live accepted maintainer claim in the checked-in index for
  `github.com/maxwellsantoro/ries-rs`, linked to the published upstream `.repo`
  and surfaced with `superseded` handoff state
- local review and CI artifacts sharing the same exported tree

Not yet in scope:
- a public search surface
- live mutation or submission APIs

## Local review loop

### 1. Fixture and golden-output regression gate

The smallest review surface lives under:

- `crates/dotrepo-core/tests/fixtures/public-export/fixture-index/`
- `crates/dotrepo-core/tests/fixtures/public-export/expected/public/v0/`
- `crates/dotrepo-core/tests/public_export_fixture_pack.rs`

Run:

```bash
cargo test -p dotrepo-core --test public_export_fixture_pack -- --nocapture
```

That test fixes `generatedAt` and `staleAfter`, recomputes `snapshotDigest` from
the checked-in fixture index, and compares the exported `meta.json`,
bundle-level `repos/index.json`, and per-repository `index.json` / `trust.json`
files byte-for-byte against the checked-in golden tree.

Use this when reviewing response-shape changes, claim-visibility changes, link
changes, or artifact-path changes.

For the additive-only `v0` compatibility contract around required keys, links,
and error codes, see [`docs/public-api-compatibility.md`](./public-api-compatibility.md).
RFCs 0016 through 0019 serve as the accepted `v0` launch docs for that surface.
For the canonical freshness definitions used by exports and individual
records, see [`docs/public-freshness.md`](./public-freshness.md).

### 2. Deterministic local export from the real seed index

For review artifacts outside the fixture pack, use fixed timestamps so repeated
runs on the same input stay byte-stable:

```bash
cargo run -p dotrepo-cli -- public export \
  --index-root index \
  --out-dir public \
  --generated-at 2026-03-10T18:30:00Z \
  --stale-after 2026-03-11T18:30:00Z
```

Important details:
- `snapshotDigest` is recomputed from the exported `index/` tree
- deterministic mode changes freshness timestamps, not response semantics
- ordinary export runs emit real timestamps
- public `generatedAt` means export time for the snapshot, not proof that an
  upstream repository changed at that exact moment

### 3. Ordinary local export

For a normal non-deterministic export:

```bash
cargo run -p dotrepo-cli -- public export --index-root index --out-dir public
```

You may also add `--stale-after-hours <hours>` for an advisory staleness window.
When deploying behind a subpath such as a GitHub Pages project site, add
`--base-path /<repo-name>` so public links resolve correctly from the hosted
root and point at the exported `index.json` / `trust.json` files.

## CI artifacts

The canonical release review entrypoint is `scripts/check_release_gate.py`. The
main CI workflow runs that script, which builds the public tree from the seed
`index/`, packages the release-style install assets, smoke tests the release
binaries, and uploads the resulting artifacts.

Current behavior:
- the artifact is generated from the real `index/` tree
- CI exercises the hosted `--base-path /dotrepo` path, not just root-relative links
- CI uses fixed review timestamps for inspectable, stable output
- CI also packages a versioned review bundle from the exported tree
- CI also packages a Linux install bundle and a tagged-style VSIX as release-gate artifacts
- CI smoke tests the release binaries from the extracted tarball
- artifact retention is 14 days
- export generation failures fail CI directly

Separate from the release-surface artifacts, the `operator-gate` CI job uploads:
- `operator-gate-claim-reports`
- `operator-gate-live-seed-handoff-public`

Those artifacts demonstrate the overlay-to-claim handoff path exported through
the same public JSON contracts with canonical links. The live checked-in index
already demonstrates the corrected accepted-claim path through
`github.com/maxwellsantoro/ries-rs`, with `superseded` handoff linked to the
upstream native `.repo`.

## Hosted static deployment

`.github/workflows/public-pages.yml`:

- validates the index
- exports the public tree with a hosted-aware `--base-path`
- renders a root landing page with `scripts/render_public_pages_landing.py`
- uploads and deploys to GitHub Pages

The export tree is the source of truth. The hosted surface deploys the same
`public/` output.

## What should stay stable vs variable

Stable for the same input tree and fixed review timestamps:
- file layout under `public/v0/`
- bundle-level repository inventory
- field names and response envelopes
- selection/conflict and claim-visibility semantics
- link structure and artifact locators
- `snapshotDigest`

Intentionally variable in ordinary export runs:
- `generatedAt`
- `staleAfter`

`generatedAt`, `snapshotDigest`, `staleAfter`, and `record.generated_at` are
defined in [`docs/public-freshness.md`](./public-freshness.md).

## How to reason about changes

When the public export changes, ask:

1. Did the source index change?
2. Did the response contract change?
3. Did claim visibility or selection behavior change?
4. Did only review-time freshness metadata change?

The fixture pack is best for contract review. The CI artifact is best for
inspecting the current seed index output as a whole.

The compatibility manifest/test is best for catching accidental key renames,
link-key drift, or error-code drift inside the same `apiVersion`.

For release review, start with `scripts/check_release_gate.py`; use the
individual commands above only when you are isolating one specific part of the
public/export flow.

For a release summary, see
[`docs/public-release-note.md`](./public-release-note.md).
For concrete usage snippets, see
[`docs/public-export-examples.md`](./public-export-examples.md).
For a cut/review checklist, see
[`docs/public-release-checklist.md`](./public-release-checklist.md).

## Related docs

- [`rfcs/0016-public-index-site-and-query-api.md`](../rfcs/0016-public-index-site-and-query-api.md)
- [`rfcs/0017-public-repository-summary-response.md`](../rfcs/0017-public-repository-summary-response.md)
- [`rfcs/0018-static-public-serving-and-freshness.md`](../rfcs/0018-static-public-serving-and-freshness.md)
- [`rfcs/0019-public-trust-and-query-wrappers.md`](../rfcs/0019-public-trust-and-query-wrappers.md)
- [`docs/current-status.md`](./current-status.md)
