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
  --min-tasks 628 \
  --min-repositories 157 \
  --min-task-hit-rate 0.64 \
  --min-field-hit-rate 0.82 \
  --min-intent-hit-rate overview=0.90 \
  --min-intent-hit-rate execution=0.70 \
  --min-intent-hit-rate documentation=0.32 \
  --min-intent-hit-rate security=0.65 \
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
- per-task missing inputs and missing fields
- per-intent task and field hit rates
- optional pass/fail gates for workload volume, repository coverage, aggregate
  and per-intent hit rates, and dotrepo-to-scrape-proxy byte ratio

`scrapeProxyBytes` is intentionally named as a proxy. It is deterministic and
reviewable in CI, but it is not a live measurement of GitHub HTML/API traffic,
repository archives, README fetches, dependency manifests, or model context.

## Current production-export result

The canonical release gate builds the research workload from all 157 current
profiles and applies the versioned baseline in
`scripts/fixtures/public_lookup_efficiency_baseline.json`. Its current result is:

| Metric | Value |
| --- | ---: |
| Repositories | 157 |
| Tasks answered | 410 / 628 |
| Task hit rate | 0.6529 |
| Fields answered | 1168 / 1413 |
| Field hit rate | 0.8266 |
| Abstention rate | 0.1734 |
| Overview task hit rate | 0.9045 |
| Execution task hit rate | 0.7134 |
| Documentation task hit rate | 0.3312 |
| Security task hit rate | 0.6624 |
| dotrepo bytes | 917209 |
| scrape proxy bytes | 398648 |
| dotrepo to scrape proxy ratio | 2.3008 |

The documentation slice is the clearest current bottleneck. The byte ratio is
also reported without dressing it up: profile plus query-input JSON is larger
than the already-normalized local record/evidence proxy. That proxy is not live
GitHub or documentation scraping, so the report does not claim a 2.302x live
network penalty or savings.

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

The fixture remains a deterministic unit-scale contract. Production thresholds
come from the full generated export above, not from these two repositories.
