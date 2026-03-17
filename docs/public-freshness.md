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
