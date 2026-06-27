# Public lookup efficiency benchmark

dotrepo's public index is meant to be a reusable semantic cache: agents should
look up compact repository facts before cloning, scraping, or asking a model to
re-interpret the same source material.

The deterministic benchmark harness measures that lookup path against a JSON
workload of known-repository questions:

```bash
python3 scripts/measure_public_lookup_efficiency.py \
  --public-root crates/dotrepo-core/tests/fixtures/public-export/expected/public \
  --index-root crates/dotrepo-core/tests/fixtures/public-export/fixture-index \
  --workload scripts/fixtures/public_lookup_workload.json \
  --output-json /tmp/dotrepo-lookup-efficiency.json \
  --output-md /tmp/dotrepo-lookup-efficiency.md
```

The report includes:

- task hit rate: every requested field for a repository was present
- field hit rate: individual requested fields that resolved to non-empty values
- compact dotrepo payload bytes: unique `profile.json` plus `query-input/`
  files needed by the workload
- scrape proxy bytes: checked-in `record.toml` plus `evidence.md` bytes for the
  same repositories
- per-task missing inputs and missing fields

`scrapeProxyBytes` is intentionally named as a proxy. It is deterministic and
reviewable in CI, but it is not a live measurement of GitHub HTML/API traffic,
repository archives, README fetches, dependency manifests, or model context.

## Current fixture result

Against the checked-in public export fixture and workload, the harness reports:

| Metric | Value |
| --- | ---: |
| Tasks answered | 1 / 2 |
| Task hit rate | 0.5 |
| Fields answered | 7 / 11 |
| Field hit rate | 0.6364 |
| dotrepo bytes | 7839 |
| scrape proxy bytes | 1302 |
| dotrepo to scrape proxy ratio | 6.0207 |

The fixture is small enough that the public JSON payload is larger than the
local record/evidence proxy. That is useful signal, not a failure: fixture
records are already normalized and tiny, while real agent scraping usually pays
for source files, host responses, documentation pages, and interpretation
context. The next benchmark step is to run the same report shape against a
larger production workload and publish the resulting hit rate and byte
comparison from the hosted snapshot.

