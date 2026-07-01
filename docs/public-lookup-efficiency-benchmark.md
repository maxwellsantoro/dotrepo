# Public lookup efficiency benchmark

dotrepo's public index is meant to be a reusable semantic cache: agents should
look up compact repository facts before cloning, scraping, or asking a model to
re-interpret the same source material.

The deterministic benchmark harness measures that lookup path against a JSON
workload of known-repository questions:

```bash
uv run python scripts/build_public_lookup_workload.py \
  --public-root public \
  --mode research \
  --limit 0 \
  --output /tmp/dotrepo-public-lookup-workload.json

uv run python scripts/measure_public_lookup_efficiency.py \
  --public-root public \
  --index-root index \
  --workload /tmp/dotrepo-public-lookup-workload.json \
  --min-tasks 2452 \
  --min-repositories 613 \
  --min-task-hit-rate 0.525 \
  --min-field-hit-rate 0.734 \
  --min-intent-hit-rate overview=0.74 \
  --min-intent-hit-rate execution=0.466 \
  --min-intent-hit-rate documentation=0.543 \
  --min-intent-hit-rate security=0.35 \
  --output-json /tmp/dotrepo-lookup-efficiency.json \
  --output-md /tmp/dotrepo-lookup-efficiency.md
```

`build_public_lookup_workload.py --mode research` emits four fixed tasks for
every exported repository, independent of profile completeness: overview,
execution, documentation, and security stewardship. This prevents the
benchmark from selecting questions only after observing which answers are
already present. The legacy `observed` mode remains useful for payload and
retrieval-path checks, but it is not the production hit-rate workload.

The report includes:

- task hit rate: every requested field for a repository was present
- field hit rate: individual requested fields that resolved to non-empty values
- abstention rate: requested fields left empty rather than fabricated
- compact dotrepo payload bytes: unique `profile.json` plus `query-input/`
  files needed by the workload
- scrape proxy bytes: checked-in `record.toml` plus `evidence.md` bytes for the
  same repositories
- dotrepo batch-query request count: cacheable public batch-query GETs needed
  for the workload under the documented repository/path/result limits
- scrape proxy request count: unique checked-in `record.toml` and `evidence.md`
  proxy files for the same repositories
- per-task missing inputs and missing fields
- per-intent task and field hit rates
- optional pass/fail gates for workload volume, repository coverage, aggregate
  and per-intent hit rates, and dotrepo-to-scrape-proxy byte ratio

`scrapeProxyBytes` is intentionally named as a proxy. It is deterministic and
reviewable in CI, but it is not a live measurement of GitHub HTML/API traffic,
repository archives, README fetches, dependency manifests, or model context.
Likewise, `scrapeProxyRequests` is a conservative local proxy, while
`dotrepoBatchQueryRequests` models the public batch-query surface that agents
can cache and reuse.

## Current production-export result

The canonical release gate builds the research workload from all 613 current
profiles and applies the versioned baseline in
`scripts/fixtures/public_lookup_efficiency_baseline.json`. Its current result is:

| Metric | Value |
| --- | ---: |
| Repositories | 613 |
| Tasks answered | 1288 / 2452 |
| Task hit rate | 0.5253 |
| Fields answered | 4054 / 5517 |
| Field hit rate | 0.7348 |
| Abstention rate | 0.2652 |
| Overview task hit rate | 0.7406 |
| Execution task hit rate | 0.4666 |
| Documentation task hit rate | 0.5432 |
| Security task hit rate | 0.3507 |
| dotrepo bytes | 3431044 |
| scrape proxy bytes | 1417339 |
| dotrepo to scrape proxy ratio | 2.4208 |
| unique fields requested | 9 |
| dotrepo batch query requests | 13 |
| scrape proxy requests | 1226 |
| request reduction rate | 0.9894 |

Security and execution are the clearest current bottlenecks: both dropped
substantially as coverage grew from 157 to 613 profiles (execution 0.7134 ->
0.4666, security 0.6624 -> 0.3507), while documentation and overview shifted
(documentation 0.3312 -> 0.5432; overview 0.9045 -> 0.7406). This tracks the
quality-hardening queue reported by `scripts/render_index_growth_status.py`
(285 missing build, 290 missing test, 408 missing security as of this
snapshot): growth outpaced quality hardening, and closing that queue is the
direct lever for these intents. The byte ratio is also reported without
dressing it up: profile plus query-input JSON is larger than the
already-normalized local record/evidence proxy. That proxy is not live GitHub
or documentation scraping, so the report does not claim a 2.42x live network
penalty or savings.

## Fixture result

Against the checked-in public export fixture and workload, the harness reports:

| Metric | Value |
| --- | ---: |
| Tasks answered | 1 / 2 |
| Task hit rate | 0.5 |
| Fields answered | 7 / 11 |
| Field hit rate | 0.6364 |
| dotrepo bytes | 8762 |
| scrape proxy bytes | 1356 |
| dotrepo to scrape proxy ratio | 6.4617 |
| unique fields requested | 9 |
| dotrepo batch query requests | 1 |
| scrape proxy requests | 4 |
| request reduction rate | 0.75 |

The fixture remains a deterministic unit-scale contract. Production thresholds
come from the full generated export above, not from these two repositories.
