# Public lookup efficiency benchmark

dotrepo's public index is meant to be a reusable semantic cache: agents should
look up compact repository facts before cloning, scraping, or asking a model to
re-interpret the same source material.

The deterministic benchmark harness measures that lookup path against a JSON
workload of known-repository questions:

```bash
uv run python scripts/build_public_lookup_workload.py \
  --public-root public \
  --limit 500 \
  --output /tmp/dotrepo-public-lookup-workload.json

uv run python scripts/measure_public_lookup_efficiency.py \
  --public-root public \
  --index-root index \
  --workload /tmp/dotrepo-public-lookup-workload.json \
  --min-task-hit-rate 0.8 \
  --min-field-hit-rate 0.9 \
  --output-json /tmp/dotrepo-lookup-efficiency.json \
  --output-md /tmp/dotrepo-lookup-efficiency.md
```

`build_public_lookup_workload.py` derives tasks from the exported inventory and
profile completeness signals. Every task includes common identity-orientation
fields such as `repo.description` and `repo.homepage`; build, test,
documentation, security, ownership, license, language, and topic fields are
included when the profile says those facts are present.

The report includes:

- task hit rate: every requested field for a repository was present
- field hit rate: individual requested fields that resolved to non-empty values
- compact dotrepo payload bytes: unique `profile.json` plus `query-input/`
  files needed by the workload
- scrape proxy bytes: checked-in `record.toml` plus `evidence.md` bytes for the
  same repositories
- per-task missing inputs and missing fields
- optional pass/fail gates for task hit rate, field hit rate, and
  dotrepo-to-scrape-proxy byte ratio

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
| dotrepo bytes | 8762 |
| scrape proxy bytes | 1356 |
| dotrepo to scrape proxy ratio | 6.4617 |

The fixture is small enough that the public JSON payload is larger than the
local record/evidence proxy. That is useful signal, not a failure: fixture
records are already normalized and tiny, while real agent scraping usually pays
for source files, host responses, documentation pages, and interpretation
context. The next benchmark step is to run the same report shape against a
larger production workload and publish the resulting hit rate and byte
comparison from the hosted snapshot.
