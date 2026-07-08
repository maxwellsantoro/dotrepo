# External consumer reference client

Template-complete client for the distribution workstream. It hits the hosted
dotrepo public API **before** any scrape/clone fallback and surfaces
trust / status / freshness.

See [`docs/external-consumer-integration.md`](../../docs/external-consumer-integration.md)
for the acceptance checklist this example implements.

## Quick start

```bash
# Live hosted lookup (optional network)
uv run python examples/external-consumer/lookup_before_scrape.py \
  https://github.com/BurntSushi/ripgrep \
  github.com/acme/does-not-exist-dotrepo-probe \
  --miss-log /tmp/lookup-misses.log \
  --output-json /tmp/consumer-results.json

# Aggregate client-recorded misses the same way as Worker logs
uv run python scripts/aggregate_lookup_misses.py \
  --input /tmp/lookup-misses.log \
  --output-md /tmp/lookup-miss-report.md
```

## Acceptance mapping

| Criterion | How this client meets it |
| --- | --- |
| Hosted lookup before clone | `fetch_profile` only calls `/v0/repos/.../index.json` |
| Trust / freshness surfaced | Printed and included in JSON output |
| Honest missing fields | `missing_fields` list; no invented build/test commands |
| Countable 404 | `miss=true` + optional `DOTREPO_LOOKUP_MISS` log lines |
| Non-operator style | Example path under `examples/`; not wired into operator CI smoke |

Live non-operator production traffic remains an operations follow-up once a
third-party framework adopts this pattern.
