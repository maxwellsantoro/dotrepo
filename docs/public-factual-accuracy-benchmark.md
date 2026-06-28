# Public factual accuracy benchmark

Presence and hit-rate metrics do not prove that returned values are correct.
The release gate therefore compares a curated cross-ecosystem sample against
exact expected values checked from primary upstream repository sources.

```bash
uv run python scripts/measure_public_factual_accuracy.py \
  --public-root public \
  --workload scripts/fixtures/public_factual_accuracy_workload.json \
  --min-assertions 20 \
  --min-repositories 3 \
  --min-accuracy-rate 1.0 \
  --max-missing-rate 0.0 \
  --max-mismatch-rate 0.0 \
  --output-json /tmp/dotrepo-factual-accuracy.json \
  --output-md /tmp/dotrepo-factual-accuracy.md
```

Every assertion names a repository and dot path, pins an exact expected value,
and records a primary-source URL, locator, and check date. Missing values and
wrong values are reported separately with rates and independent ceilings.
Workload volume and repository count are gated so accuracy cannot be preserved
by silently shrinking the sample.

The initial workload contains 20 assertions across FastAPI, Tokio, and Gin. It
covers names, descriptions, homepages, licenses, build/test commands,
documentation, and a security contact. It caught and drove deterministic fixes
for a logo-derived name, promotional announcement descriptions, and a badge
asset misclassified as documentation.

The current release baseline requires 20/20 exact matches, zero missing sampled
facts, and zero mismatched sampled facts. This is sampled accuracy evidence, not
a universal claim about every field in every profile. The workload should grow
across repositories, ecosystems, and field classes as coverage expands toward
500 profiles.
