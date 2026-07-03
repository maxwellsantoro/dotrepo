# Public Freshness

This is the canonical reference for freshness metadata on dotrepo's public
read-only surface.

The public surface uses two separate freshness concepts:

- snapshot freshness for the exported public tree
- record freshness for individual crawled or imported records

## Snapshot freshness

Snapshot freshness describes when a public export was produced and which export
input tree it represents.

### `generatedAt`

`generatedAt` is the timestamp when dotrepo produced the public export or
response.

It answers: "When was this JSON generated?"

It does not imply that the underlying repository changed at that exact moment.
For example, a fresh export can still contain older factual records.

### `snapshotDigest`

`snapshotDigest` is the digest of the exported index snapshot used to produce
the public tree.

It answers: "Which exported snapshot did this response come from?"

It should be stable across every response emitted from the same export run and
change when the exported input tree changes.

### `staleAfter`

`staleAfter` is an optional advisory timestamp for when a consumer should
consider the response stale enough to revalidate or refetch.

It answers: "When should I stop trusting this snapshot without rechecking?"

It is an operational hint, not a guarantee that the underlying repository data
became invalid at that time.

### `validators`

`meta.json` also carries cache validators derived from `snapshotDigest`:

- `validators.snapshot` is the digest in explicit `sha256:<digest>` form
- `validators.etag` is the recommended strong ETag value for the exported
  snapshot family

Consumers can compare either validator with a previously seen value before
refetching profile, trust, query-input, or inventory files.

### Content-addressed paths

`/v0/meta.json` is the primary mutable snapshot pointer. Its `snapshotId` is
the first 12 hexadecimal characters of `snapshotDigest`, and its `paths` object
names the immutable snapshot root, inventory, file manifest, stats document,
snapshot log, and internal query-input root.

Canonical snapshot responses are served with a one-year `immutable` cache
policy. Compatibility paths such as `/v0/repos/index.json` remain available,
but the Worker resolves them through the current pointer and marks them
`no-cache`. Every JSON record still carries the full digest and generation
time in `freshness`, so a consumer can reject an accidentally mixed response.

### Retention contract

Snapshot retention is part of the public trust surface:

- current and previous snapshots are guaranteed on the static edge path for
  fast reads, instant rollback, and deploy-race tolerance
- every published snapshot is expected to remain retrievable from the archive
  path, backed by the Worker `SNAPSHOT_ARCHIVE` R2 binding when configured
- `/v0/snapshots/log.json` is append-only and never pruned; it lists every
  published digest with `generatedAt`, `repositoryCount`, and `fileCount`

The static asset bundle is intentionally not the historical archive. Workers
static asset deployments replace the deployed asset manifest, so retaining every
historical digest in the bundle would eventually fail on file-count limits even
though the raw storage cost is small. Consumers should use the current pointer
for hot reads, immutable snapshot URLs for exact references, and the log for
audit history.

### `stats.json`

`/v0/stats.json` is a mutable instrumentation document derived from the
append-only snapshot log. It exposes the latest snapshot, the retained history,
and count deltas between adjacent snapshots. Phase 2 dashboard and essay work
should build from this document rather than scraping individual payload paths.

### `files.json`

`paths.files` (with `/v0/files.json` retained as a convenience path) is a
deterministic manifest for the immutable exported snapshot. It
lists each exported payload file, excluding `files.json` itself, with:

- relative `path`
- byte length
- SHA-256 of the emitted file contents

Consumers fetch `meta.json`, follow `paths.files`, and need no further work if
the snapshot digest is unchanged. When it changes, the file manifest provides
the exact immutable payload set and hashes.

The deployed export currently promises a seven-day `staleAfter` window. That
matches the cadence the project can sustain without pretending a push-driven
deployment is a daily refresh service. The scheduled public-edge canary must
stay green for seven consecutive days before Phase 0 is declared
operationally complete.

For local review, mirrors, or agent caches, use the deterministic delta helper:

```bash
uv run python scripts/diff_public_export_files.py \
  --old-files old-public/v0/files.json \
  --new-files public/v0/files.json \
  --output-json /tmp/dotrepo-public-file-delta.json \
  --output-md /tmp/dotrepo-public-file-delta.md
```

The report lists added, changed, removed, and unchanged files, plus the exact
refetch set and refetch byte ratio for the new snapshot.

## Record freshness

### `record.generated_at`

`record.generated_at` is the factual timestamp attached to an imported or
crawled record.

It answers: "When was this record itself generated or refreshed?"

It is independent from snapshot freshness:

- a record can be older than the public export that currently surfaces it
- a newer export can still point to an older record if that record remains the
  selected one
- record freshness should not be promoted into a separate public trust model

## Practical rule

Use snapshot freshness to understand the public export and record freshness to
understand the underlying factual data. Do not conflate the two when reviewing
trust, conflicts, or stale metadata.
