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

### `files.json`

`v0/files.json` is a deterministic manifest for the exported public tree. It
lists each exported payload file, excluding `files.json` itself, with:

- relative `path`
- byte length
- SHA-256 of the emitted file contents

Consumers that already have a snapshot can fetch only `meta.json` and
`files.json`, compare per-file digests, and then refetch only changed JSON
payloads.

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
