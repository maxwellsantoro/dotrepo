# Public search quality benchmark

The deterministic search-quality harness measures whether exported public
profiles can answer discovery-style queries without scraping repository pages.
It replays a JSON workload against `v0/repos/**/profile.json`, applies the same
text and filter semantics as public profile search, and reports rank-based
quality metrics.

```bash
uv run python scripts/measure_public_search_quality.py \
  --public-root public \
  --workload scripts/fixtures/public_search_workload.json \
  --min-success-rate 0.8 \
  --min-mean-reciprocal-rank 0.6 \
  --max-average-first-rank 3 \
  --output-json /tmp/dotrepo-search-quality.json \
  --output-md /tmp/dotrepo-search-quality.md
```

The report includes:

- task success rate: all expected repositories appear within each task limit
- mean reciprocal rank and average first expected rank
- candidate profile count and searched profile bytes
- inventory-only versus profile-fanout task counts and rates, mirroring the
  hosted Worker's cheaper text-query path
- inventory bytes and profile bytes per fanout task
- snapshot freshness summary from the evaluated profiles
- optional pass/fail gates for success rate, MRR, and first-rank ceiling

Ranking is intentionally separate from trust. The benchmark score uses only
matched public fields and factual completeness signals. Trust status and
confidence can still be used as filters, but they do not make a result more
relevant.

Cost reporting is intentionally local and deterministic. Text-only tasks are
classified as inventory-only eligible; tasks that use language, topic, trust, or
completeness filters are classified as profile fan-out because they need richer
profile fields.

The checked-in fixture workload is small and exists to pin report shape. For a
production gate, derive or curate a larger workload that reflects real
technology, capability, ecosystem, and relation-discovery tasks.
