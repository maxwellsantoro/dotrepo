# Public lookup efficiency benchmark

dotrepo's public index is meant to be a reusable semantic cache: agents should
look up compact repository facts before cloning, scraping, or asking a model to
re-interpret the same source material.

The deterministic harness measures field presence and local artifact sizes.
It does not measure the objective above or end-to-end task efficiency. See the
[November 3 measurement review](measurement-review-20261103.md) for the population
mix failure, counterexamples, consumer evidence and the benefit-evaluation rubric.
The following command measures a changing-catalog diagnostic; release floors
apply separately to the frozen regression cohort:

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

Failed thresholds are printed to stderr with the gate name, actual value, and
required bound, including when JSON and Markdown reports are written to files.
The public-surface and complete release CI jobs retain the lookup reports and
generated workload in their gate-timings artifact even when a gate fails. Use
the per-task missing fields to trace a coverage regression back to source
declarations; a missing answer alone is not a reason to lower the baseline.

`scrapeProxyBytes` is intentionally named as a proxy. It is deterministic and
reviewable in CI, but it is not a live measurement of GitHub HTML/API traffic,
repository archives, README fetches, dependency manifests, or model context.
Likewise, `scrapeProxyRequests` is a conservative local proxy, while
`dotrepoBatchQueryRequests` models the public batch-query surface that agents
can cache and reuse.

## Historical production-export snapshot

The canonical release gate reports the research workload from all exported
profiles. It applies the versioned numeric baseline in
`scripts/fixtures/public_lookup_efficiency_baseline.json` to a separate frozen
615-repository cohort from pre-follow-up commit `303ed90a`. The
`public-lookup-reference-*` artifacts retain that regression control, including
missing repositories; `public-lookup-*` retains the whole changing catalog.
No numeric floor was lowered. This post-observation engineering correction is
not held-out evidence of product benefit. The pre-September-refresh result was:

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

In that historical snapshot, security and execution were the clearest bottlenecks: both dropped
substantially as coverage grew from 157 to 613 profiles (execution 0.7134 ->
0.4666, security 0.6624 -> 0.3507), while documentation and overview shifted
(documentation 0.3312 -> 0.5432; overview 0.9045 -> 0.7406). This tracks the
quality-hardening queue reported by `scripts/render_index_growth_status.py`
(285 missing build, 290 missing test, 408 missing security as of this
snapshot). These figures describe presence, not factual correctness or current
consumer acceptance. Regenerate reports before prioritizing the present queue. The byte ratio is also reported without
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

## Release policy after the September review

Authority labels are reported without a minimum verified-count incentive. The
release still gates profile validity, field completeness, conflicts, generic or
duplicated content, and factual accuracy. Independent structured metadata adds
the assertions from the active dated upstream capture; the
[factual-accuracy guide](public-factual-accuracy-benchmark.md) owns its scope and
computed counts. The original September capture remains historical evidence. Factual record age has a
separate hard gate: at most 10% stale or unknown at the gate's current evaluation
time, with maximum refresh overdue of seven days. Export age is reported
separately; see [the freshness contract](public-freshness.md#profile-record-policy).
Lower confidence
is visible in the quality dashboard and is not itself classified as malformed or
incorrect content. This policy allows honest partial publication without
inflating status to retain a coverage badge.

## Consumer-policy coverage

The release gate also runs:

```sh
uv run python scripts/measure_public_policy_coverage.py --public-root public \
  --output-json /tmp/policy-coverage.json --output-md /tmp/policy-coverage.md
```

This applies the shipped reference consumer to each primary profile for
repository-description, documentation, build, test, and combined build/test
requests. Snapshot copies and candidate commands are excluded. It retains the
presence metric and separately reports policy-acceptable counts, denominators,
and per-repository fallback reasons. Evaluation defaults to the export timestamp;
`--evaluated-at` permits a later age check. The efficiency page publishes the same
measurement. No lower bound on acceptance encourages weakening the policy.

Independent correctness and completed-task counts are null, not zero or inferred
from acceptance. The structured assertion suites and head-to-head answer scoring
remain separate evidence; actual consumer task completion belongs to the pilot.
