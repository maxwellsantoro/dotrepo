# Public surface

The public surface distributes the index as a read-only, export-backed JSON
service and human-readable website. It shares core selection, trust, conflicts,
and claim semantics with local tools. This guide describes source architecture;
[release compatibility](release-compatibility.md) separates client releases from
independently deployed hosted snapshots.

## Components and capabilities

- Static inventory, repository summary, compact profile, trust, and typed
  relations responses under the public export
- Dynamic field queries, batches, search, comparison, and relations routes from
  the same exported snapshot inputs
- Homepage, searchable catalog, documentation, writing, and measurement pages
- `dotrepo-public-query` for local same-origin review and a
  [Cloudflare Worker](../cloudflare/hosted-query/README.md) for hosted serving
- CI-generated public tree and versioned bundle for inspectable release artifacts

[Public examples](public-export-examples.md) give HTTP and CLI routes.
Profiles expose purpose, execution, docs, ownership, trust, conflicts, record age,
and retained field evidence where available. Optional `synthesis.toml` guidance
stays separate from factual fields. Claim context exposes handoff links without
turning acceptance into proof of canonical publication.

The repository website is an inspection/integration surface; raw JSON remains
directly accessible. Metadata supports orientation, while debugging, architecture
research, and suitability decisions still require source inspection.

## Snapshot architecture

`meta.json` points at a content-addressed tree under
`/v0/snapshots/<snapshotId>/`. Its immutable file manifest lists hashes and byte
sizes for selective refetch; compatibility paths resolve through the current
pointer. Snapshot identity includes serialized payloads and freshness metadata,
while source digest identifies index inputs. They are distinct validators.

The static edge retains current and previous snapshots. Older immutable paths
can fall through to a configured R2 archive. The snapshot log is append-only;
`stats.json` derives history/count deltas and PageDigest instrumentation from it.
Archive availability depends on operator provisioning.

`/.well-known/pagedigest.json` publishes per-URL change revisions and digests for
public records. Material-content digests exclude volatile export freshness so
unchanged facts do not churn revisions. Replacement deploys validate and restore
prior manifest/snapshot history instead of resetting it. The instrumentation's
coarse token estimates are not billed usage or measured agent savings.

See [freshness](public-freshness.md) for cache and retention semantics and
[Cloudflare deployment](cloudflare-deploy.md) for restoration/archive setup.

## Runtime bounds

Queries reconstruct core reports from private repo-scoped `query-input/` files
rather than traversing TOML at request time. Batch and comparison limits bound
request work and preserve per-item errors.

Hosted search reads the snapshot pointer and `repos/search.json`, a compact
export with fields needed for both free-text matching and filters. It uses two
asset reads independent of repository count; matching scans the document in
memory. Default/max result limits bound response size, not scan cost. A missing
search document fails rather than fetching all profile files.

Relations prefer precomputed `relations.json`; any legacy reverse traversal
fallback remains bounded. Search ranking is separate from factual trust;
comparison is a factual matrix, not a recommendation.

## Publication and validation

The [export workflow](public-export-workflow.md) owns generation, packaging,
local runtime review, and CI artifacts. The [release checklist](public-release-checklist.md)
owns publication checks. Generated `public/`, `release-gate/`, and `dist/` outputs
are gitignored; `index/` and fixtures are source inputs.

The [wire compatibility manifest/test](public-api-compatibility.md) pins required
keys, links, and errors. Fresh export time does not refresh underlying records;
release gates independently check record age, correctness samples, validity,
conflicts, completeness, quality, and policy acceptance reporting.

## Boundaries and remaining proof

Public mutation/submission APIs, authenticated maintainer submission, public
SLAs, and operational workspace semantics remain deferred. Typed research
relations and search/comparison are implemented; production-scale ranking and
synthesis calibration, maintained freshness, complete task evaluation, and
independent consumer outcomes remain active proof work.

Use [the roadmap](../ROADMAP.md#active-execution-order) for priorities and
[the consumer pilot](consumer-pilot.md) before claiming external adoption or net
savings. Benchmark presence, policy acceptance, correctness, and task completion
remain distinct measurements.
