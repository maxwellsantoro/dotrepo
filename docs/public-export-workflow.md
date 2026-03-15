# Public export workflow

This doc covers the current operator and reviewer loop for the read-only public
JSON tree.

It is intentionally narrow. dotrepo can now export a static public surface,
publish it as a CI artifact, and deploy the same tree through the GitHub Pages
workflow in `.github/workflows/public-pages.yml`. That still does not imply a
live public query API or production-hardened serving.

## What exists now

The current public export surface is a static JSON tree rooted at:

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

Today this surface proves:
- the seed index can be rendered into a stable, identity-first public artifact
- the exported tree includes one bundle-level repository inventory for inspection
- repository summary and trust responses reuse the same local selection,
  conflict, and claim-visibility semantics
- operators and reviewers can inspect one concrete exported tree without
  rebuilding higher-level serving infrastructure first

It does not yet promise:
- a public search surface
- live mutation or submission APIs
- production-hardened freshness or runtime guarantees

Important boundary:
- the checked-in `index/` tree is still overlay-only today
- the operator gate stages one copied seed entry through accepted claim handoff
  and `public export` so claim-aware public responses are exercised without
  publishing a fake accepted claim for a live repository

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
- `snapshotDigest` is still recomputed from the exported `index/` tree
- deterministic mode changes freshness timestamps, not response semantics
- ordinary export runs still emit real timestamps

### 3. Ordinary local export

For a normal non-deterministic export:

```bash
cargo run -p dotrepo-cli -- public export --index-root index --out-dir public
```

You may also add `--stale-after-hours <hours>` for an advisory staleness window.
When deploying behind a subpath such as a GitHub Pages project site, add
`--base-path /<repo-name>` so public links resolve correctly from the hosted
root.

## CI artifact

The main CI workflow now runs `scripts/check_release_gate.py`, which builds the
public tree from the seed `index/`, packages the release-style install assets,
and uploads the resulting public artifacts as `public-export-v0` and
`public-export-v0-bundle`.

Current behavior:
- the artifact is generated from the real `index/` tree
- CI exercises the hosted `--base-path /dotrepo` path, not just root-relative links
- CI uses fixed review timestamps for inspectable, stable output
- CI also packages a versioned review bundle from the exported tree
- CI also packages a Linux install bundle and a tagged-style VSIX as release-gate artifacts
- artifact retention is 14 days
- export generation failures fail CI directly rather than being downgraded to
  warnings

This gives reviewers a fetchable snapshot of the public JSON tree without
rebuilding locally.

Separate from that release-surface artifact, the `operator-gate` CI job uploads:
- `operator-gate-claim-reports`
- `operator-gate-live-seed-handoff-public`

Those artifacts are proof-only operator outputs. They demonstrate the live
overlay-to-claim-to-public-export path on a staged copy of `index/repos/github.com/cli/cli/`.
They are not the checked-in public seed index.

## Hosted static deployment

The repo now also includes `.github/workflows/public-pages.yml`, which:

- validates the index
- exports the public tree with a hosted-aware `--base-path`
- renders a small root landing page with `scripts/render_public_pages_landing.py`
- uploads the result to GitHub Pages

The export tree remains the source of truth. The hosted surface is just a thin
deployment layer over the same `public/` output.

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

## How to reason about changes

When the public export changes, ask:

1. Did the source index change?
2. Did the response contract change?
3. Did claim visibility or selection behavior change?
4. Did only review-time freshness metadata change?

The fixture pack is best for contract review. The CI artifact is best for
inspecting the current seed index output as a whole.

For a release-style summary of the current proof surface, see
[`docs/public-proof-release-note.md`](./public-proof-release-note.md).
For concrete usage snippets, see
[`docs/public-export-examples.md`](./public-export-examples.md).
For a cut/review checklist, see
[`docs/public-proof-release-checklist.md`](./public-proof-release-checklist.md).

## Related docs

- [`rfcs/0016-public-index-site-and-query-api.md`](../rfcs/0016-public-index-site-and-query-api.md)
- [`rfcs/0017-public-repository-summary-response.md`](../rfcs/0017-public-repository-summary-response.md)
- [`rfcs/0018-static-public-serving-and-freshness.md`](../rfcs/0018-static-public-serving-and-freshness.md)
- [`rfcs/0019-public-trust-and-query-wrappers.md`](../rfcs/0019-public-trust-and-query-wrappers.md)
- [`docs/current-status.md`](./current-status.md)
