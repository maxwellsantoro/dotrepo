# Public export workflow

This doc covers the operator and reviewer loop for the read-only public JSON
tree and its hosted deployment.

## What exists now

The current deployed public surface is a Cloudflare Worker-hosted JSON tree on
`https://dotrepo.org/`, rooted at:

```text
public/
  index.html
  docs/
  repositories/
  writing/
  query-input/
    <host>/
      <owner>/
        <repo>.json
  v0/
    meta.json
    files.json
    repos/
      index.json
      search.json
      <host>/
        <owner>/
          <repo>/
            index.json
            profile.json
            trust.json
    stats.json
    snapshots/
      log.json
      <snapshotId>/
        files.json
        repos/
        query-input/
```

This surface provides:
- identity-first, trust-aware repository inspection via the hosted deployment
- a bundle-level repository inventory for navigation
- repository summary, profile, and trust responses reusing the same local
  selection, conflict, and claim-visibility semantics
- a local and release-reviewed same-origin query runtime using the same set of
  exported files
- a live accepted maintainer claim in the checked-in index for
  `github.com/maxwellsantoro/ries-rs`, linked to the published upstream `.repo`
  and surfaced with `superseded` handoff state
- local review and CI artifacts sharing the same exported tree
- repo-scoped `query-input/` artifacts for Worker-backed hosted query serving

The root `public/` and `release-gate/` directories are generated outputs and
are intentionally gitignored. They can be regenerated from the checked-in
`index/`, scripts, and fixture contracts; CI uploads bounded review artifacts,
and deployed immutable snapshots are archived separately.

Not yet in scope:
- production-scale ranking calibration (search and factual comparison routes
  already exist; see [public examples](public-export-examples.md))
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
`files.json`, bundle-level `repos/index.json`, per-repository `index.json` /
`profile.json` / `trust.json`,
and repo-scoped `query-input/*.json` files byte-for-byte against the checked-in
golden tree.

Use this when reviewing response-shape changes, claim-visibility changes, link
changes, or artifact-path changes.

For the additive-only `v0` compatibility contract around required keys, links,
and error codes, see [`docs/public-api-compatibility.md`](./public-api-compatibility.md).
RFCs 0016 through 0019 serve as the accepted `v0` launch docs for that surface.
For the canonical freshness definitions used by exports and individual
records, see [`docs/public-freshness.md`](./public-freshness.md).

### 2. Deterministic local export from the real index

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
- `snapshotDigest` is recomputed from the checked-in `index/` inputs; ignored
  local crawler state does not perturb it
- `meta.json` is the sole mutable pointer and names the immutable snapshot paths
- `meta.json` publishes the retention contract: current+previous at the static
  edge, all published snapshots through archive, and append-only snapshot log
- the canonical `files.json` lists only immutable snapshot payloads with byte
  sizes and SHA-256 digests
- `v0/snapshots/log.json` records each published snapshot digest,
  `generatedAt`, repository count, and payload count
- `v0/stats.json` derives latest/history/delta instrumentation from that log
  and includes PageDigest economics for the current manifest: records covered,
  records needing fetch, records skipped, bytes covered, bytes avoided, and a
  coarse token-avoidance estimate
- mutable `v0/repos/` and `v0/files.json` copies remain compatibility surfaces;
  the Worker resolves them through the pointer with revalidation required
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
When deploying behind a subpath such as a project-site-style static host, add
`--base-path /<repo-name>` so public links resolve correctly from the hosted
root and point at the exported `index.json` / `profile.json` / `trust.json`
files. The current Cloudflare custom-domain deployment on `dotrepo.org` uses
`--base-path /`.

## CI artifacts

The canonical release review entrypoint is `scripts/check_release_gate.py`. The
main CI workflow runs that script, which builds the public tree from the
`index/`, packages the release-style install assets, smoke tests the release
binaries, smoke tests same-origin hosted-query resolution from the shipped
`dotrepo-public-query` binary against the exported tree, stages that same
validated export into the Cloudflare Worker, smoke tests `queryTemplate`
resolution through `wrangler dev`, and uploads the resulting artifacts.

Current behavior:
- the artifact is generated from the real `index/` tree
- CI exercises both the canonical root-path Cloudflare deployment and the
  release-gate `/dotrepo` hosted-path review surface
- CI records generation timestamps in review artifacts; explicit fixed timestamps
  are available for deterministic contract review
- CI also packages a versioned review bundle from the exported tree
- CI also packages a Linux install bundle and a tagged-style VSIX as release-gate artifacts
- CI smoke tests the release binaries from the extracted tarball
- CI smoke tests that an emitted `queryTemplate` can resolve against the
  shipped hosted-query runtime on the same origin
- CI also smoke tests that the same emitted `queryTemplate` resolves through
  the Cloudflare Worker route backed by the staged export snapshot
- CI also smoke tests hosted search, compare, and relation traversal through
  the Cloudflare Worker route backed by the staged export snapshot
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

## Deployment and runtime

[Cloudflare setup](cloudflare-deploy.md) owns authentication, opt-in workflow
variables, restoration of deployed/archived history, publication serialization,
exact-source checks, and post-deploy smoke verification. Deploy the Worker and
its regenerated export together. A separate scheduled edge canary checks live
coherence; its artifacts establish actual run outcomes.

The static edge retains the current and previous immutable snapshots; historical
payloads belong in the configured archive. Private `query-input/` files serve
the runtime and are not restored from the public origin.

`dotrepo-public-query` serves local static files and dynamic routes from one
process. Hosted search reads the pointer plus the compact `repos/search.json`
export for both text and filtered matching, scanning that document in memory.
It does not fan out to every repository profile. A missing search document fails
rather than switching to unbounded reads. See [architecture](public-surface.md).

## What should stay stable vs variable

Stable for the same input tree and fixed review timestamps:
- file layout under `public/v0/`
- bundle-level repository inventory
- field names and response envelopes
- selection/conflict and claim-visibility semantics
- link structure and artifact locators
- `snapshotDigest`
- `validators`
- file paths, byte sizes, and digests in `v0/files.json`

Intentionally variable in ordinary export runs:
- `generatedAt`
- `staleAfter`

`generatedAt`, `snapshotDigest`, `staleAfter`, validators, `files.json`, and
`record.generated_at` are defined in
[`docs/public-freshness.md`](./public-freshness.md).

## How to reason about changes

When the public export changes, ask:

1. Did the source index change?
2. Did the response contract change?
3. Did claim visibility or selection behavior change?
4. Did only review-time freshness metadata change?

The fixture pack is best for contract review. The CI artifact is best for
inspecting the current index output as a whole.

The compatibility manifest/test is best for catching accidental key renames,
link-key drift, or error-code drift inside the same `apiVersion`.

For release review, start with `scripts/check_release_gate.py`; use the
individual commands above only when you are isolating one specific part of the
public/export flow.

For concrete usage snippets, see
[`docs/public-export-examples.md`](./public-export-examples.md).
For a cut/review checklist, see
[`docs/public-release-checklist.md`](./public-release-checklist.md).

## Related docs

- [`rfcs/0016-public-index-site-and-query-api.md`](../rfcs/0016-public-index-site-and-query-api.md)
- [`rfcs/0017-public-repository-summary-response.md`](../rfcs/0017-public-repository-summary-response.md)
- [`rfcs/0018-static-public-serving-and-freshness.md`](../rfcs/0018-static-public-serving-and-freshness.md)
- [`rfcs/0019-public-trust-and-query-wrappers.md`](../rfcs/0019-public-trust-and-query-wrappers.md)
- [`README.md`](../README.md)
