# pagedigest

**Check what changed before fetching it again.**

PageDigest is a JSON change manifest for public websites. Publishers list resource
revisions; recurring crawlers, indexers, and caches compare them with local state
and avoid refetching resources they already have.

Designed for mostly static content and consumers that retain results between runs.
Optional SHA-256 digests support spot checks of published representations. Publisher
claims depend on correct revision history; digest samples do not prove every skip.

**[Publish a manifest](#publish-a-manifest)** · **[Integrate a consumer](#integrate-a-consumer)**

For a warm consumer covering 10,000 pages with 20 changes per cycle, the ideal
request count is one manifest plus 20 page fetches. A 1% audit of skipped pages
adds roughly 100 requests. These estimates assume complete usable local results,
accurate publisher revisions, and no fallback work. Initial synchronization still
fetches the required collection.

```json
{
  "version": 1,
  "generated": "2026-09-16T12:00:00Z",
  "site_rev": 8,
  "coverage": { "mode": "complete" },
  "entries": {
    "/": { "rev": 3 },
    "/docs/start/": { "rev": 5 }
  }
}
```

`site_rev` summarizes the covered set. Per-URL `rev` determines which usable
local results may be reused. Equality never supplies missing bodies, completes a
failed sync, or describes unlisted URLs. Digests are optional hashes of served
identity-encoded bytes. [Wire format and consumer rules](./SPEC.md).

## Status

**v1.0** — the version 1 wire format is final. Implementation maturity and
package releases are separate from protocol status. Discovery uses
`Link: </.well-known/pagedigest.json>; rel="https://pagedigest.org/rel"` pending
a short-form IANA relation. `PageDigest-State` is an optional observation header,
not authentication or evidence that every subsequent fetch is necessary.

**Consumer safety release (September 16, 2026):** generator/launcher 0.3.0 and
Python/Astro 0.2.0 include explicit publisher initialization/recovery,
incomplete-cache handling, and audits across 304 responses. The experimental
Scrapy adapter replays cached responses to preserve traversal. See the
[migration notes and artifact verification](./docs/releases/consumer-safety.md).
Independent recurring-consumer evidence remains an open adoption milestone.

### Version matrix

| Component | Version / tag | Notes |
|-----------|---------------|--------|
| Spec wire field `version` | `1` | Final v1.0 protocol; stays `1` until a breaking protocol change |
| Protocol release tag | `v1.0.0` | Spec/status milestone; independent of package semver |
| `pagedigest-generator` / `npx pagedigest` / crates.io `pagedigest` | `0.3.0` | Publisher CLI; explicit initialization and recovery |
| Python consumer (PyPI `pagedigest`) | `0.2.0` | Validated-manifest conditional requests and per-URL cache checks |
| `@pagedigest/astro` | `0.2.0` | Static HTML subset; explicit initialization and recovery |
| Scrapy middleware | experimental in-tree | Depends on consumer `>=0.1.0`; not on PyPI |

## Publish a manifest

Install the released generator and consumer CLI:

```bash
cargo install pagedigest --version 0.3.0 --locked
python -m pip install pagedigest==0.2.0

# Build your site into ./site-dist first.
# ONE TIME ONLY, for an origin with no prior publication:
pagedigest-generator ./site-dist \
  --state /durable/pagedigest/example.com/state.json --init --with-digest

# Every subsequent build: missing state is an error, never a fresh initialization.
pagedigest-generator ./site-dist \
  --state /durable/pagedigest/example.com/state.json --with-digest
```

The same generator is available as `npx pagedigest@0.3.0` and
[release binaries](https://github.com/maxwellsantoro/pagedigest/releases/tag/generator-v0.3.0).

Replace `/durable/...` with backed-up storage that survives builds. An evictable
CI cache is insufficient. Serialize generation, state persistence, deployment,
and reconciliation. Publish pages before or atomically with the manifest.

When digests are enabled, run the repository reconciliation tool from a checkout
after deployment:

```bash
python tools/reconcile_served_digests.py ./site-dist/.well-known/pagedigest.json \
  --base-url https://example.com --apply
# Redeploy the manifest if reconciliation changed it.
pagedigest verify-live https://example.com --sample-size 25
```

[State initialization, CI persistence, and recovery](./CONTENT_HYGIENE.md#durable-publisher-state)
are part of installation. The reference generators detect **byte changes**, not
semantic significance; disabling digests does not suppress revision churn.

[Generator flags](./implementations/rust-generator/README.md) ·
[Astro setup](./packages/astro/README.md)

## Integrate a consumer

Install the consumer, then run the persistent example from this checkout:

```bash
python -m pip install pagedigest==0.2.0
python implementations/python-consumer/examples/cache_persistence.py \
  https://example.com ./cache/example.json --audit-rate 0.01
```

Run it again with the same state and body directory. The example validates cached
bodies, executes audits even when the manifest returns 304, and commits completed
snapshots only after required fetches succeed. Failed audits retain revision state
and force refresh on the next cycle. Inconclusive audits request a retry. Manifest
anomalies report that ordinary crawling is required and exit nonzero.

The API separates `check_site` planning from `audit` execution. Conditional
requests require the last validated manifest; `not_modified` describes the HTTP
response, not permission to ignore downloads or audits in the returned plan.
[Consumer integration guide](./docs/consumer-integration.md).

The [experimental Scrapy adapter](./integrations/scrapy/) replays cached responses
so spider callbacks can follow links through unchanged parents. It still incurs
parsing work and needs normal discovery outside the manifest's scope.

## Why this format?

| Mechanism | What it provides | PageDigest tradeoff |
|---|---|---|
| Conditional HTTP | Per-resource ETag/Last-Modified validation | Batches publisher change claims to avoid many URL requests |
| Sitemap + accurate `lastmod` | Discovery and incremental refresh information | Explicit revision and coverage semantics; neither mechanism makes incorrect publisher metadata trustworthy |
| ResourceSync | Lists, changes, hashes, discovery, and richer synchronization | Smaller JSON implementation surface, with fewer synchronization capabilities |
| Fingerprint manifest + ETag | Bulk byte comparison and manifest no-change validation | Counters provide ordering and optional semantic/byte separation, but require durable history |
| RSS/Atom, IndexNow, WebSub | Recent-entry feeds or push notifications | A pullable covered-set manifest for stateful consumers |

The savings primarily come from batching metadata. Counters are a design tradeoff,
not the sole source of request reduction. [Comparison and primary references](./SPEC.md#8-relationship-to-existing-mechanisms-non-normative).

## Evidence and limits

- [Controlled consumer benchmark](./docs/benchmarks/README.md): equivalent results,
  conditional sitemap fetching, matched audit policies, and the real persistent
  consumer's disk integrity work. Seven strategies across six local scenarios;
  not independent adoption evidence.
- [dotrepo July 3 case study](./docs/case-studies/dotrepo.md): export-derived estimates
  for 2,453 covered records, including manifest overhead. Not measured model-token savings.
- [pagedigest.org](https://pagedigest.org): dogfood deployment.
  [Release verification](./docs/releases/consumer-safety.md#verification) records
  published-artifact checks and the live digest audit separately.

Version 1 uses one manifest. The reference consumer caps it at 10 MiB. Large
collections must use partial coverage until a sharding extension exists. Dynamic,
personalized, and one-shot workloads are outside the main use case.

## Quality gates and contributing

```bash
./tools/run_checks.sh
```

Checks cover conformance, failed and incomplete syncs, generator state progression,
Astro parity, real Scrapy traversal, clean wheel/tarball installation, and equivalent
benchmark outcomes. Protocol and package versions remain separate.

Next priority: an independently operated recurring consumer measuring equivalent
results and freshness, including audit, discovery, fallback, and processing costs.
See [ROADMAP.md](./ROADMAP.md), [release gates](./RELEASE_CHECKLIST.md), and
[the documentation index](./docs/README.md). Cooperation and optional operational
policies are discussed in [CONTRACT.md](./CONTRACT.md).

MIT licensed.
