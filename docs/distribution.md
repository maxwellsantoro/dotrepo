# Distribution workstream

Index quality creates value; distribution captures it. This checklist tracks the
concrete surfaces that make agents and tools check dotrepo before scraping.

## Shipped surfaces

| Surface | Status | Notes |
|---------|--------|-------|
| Hosted public API (`https://dotrepo.org/v0/...`) | Live | Static export + Cloudflare hosted-query Worker |
| MCP server (`dotrepo-mcp`) | Shipped | Stdio; NDJSON framing (1.0.1); registry package path documented |
| crates.io (`dotrepo`, `dotrepo-cli`, `dotrepo-mcp`, `dotrepo-lsp`, …) | Shipped | Prefer stable `1.0.x` for consumers; `main` is `2.0.0-alpha` |
| Lookup-efficiency benchmark page | Live | `/efficiency/` on the public site |
| pagedigest publisher | Live | `/.well-known/pagedigest.json` |

## Operator checklist (recurring)

1. **MCP registry listing** — keep `server.json` / mcpb bundle and
   [`docs/mcp-registry-publishing.md`](./mcp-registry-publishing.md) aligned
   with the latest stable release; re-publish on each stable tag.
2. **Efficiency pitch** — regenerate the public efficiency page on deploy
   (`scripts/render_public_efficiency_page.py` via the release/public gate).
   Share measured tokens/bytes/requests saved, not coverage vanity metrics.
3. **Lookup-miss demand** — after deploys, sample Worker logs for
   `DOTREPO_LOOKUP_MISS` lines and aggregate:

   ```bash
   wrangler tail # or Logpush export
   # save matching lines to /tmp/lookup-misses.log
   uv run python scripts/aggregate_lookup_misses.py \
     --input /tmp/lookup-misses.log \
     --output-json /tmp/lookup-miss-report.json \
     --output-md /tmp/lookup-miss-report.md
   ```

   Feed repeated misses into Milestone 4 cohort selection after ecosystem
   balancing (`scripts/plan_index_growth_tranche.py`).
4. **External consumer** — land or renew at least one non-operator integration
   (agent framework, research crawler, or IDE). Template and in-repo reference
   client: [`docs/external-consumer-integration.md`](./external-consumer-integration.md)
   and [`examples/external-consumer/`](../examples/external-consumer/).
5. **Version clarity** — public install docs must send production users to
   stable `1.0.x`, not the `2.0.0-alpha` development line on `main`
   ([`docs/install.md`](./install.md)).

## Fixture and reference path (offline-proof)

```bash
# Capturable Worker-style sample (checked in)
uv run python scripts/aggregate_lookup_misses.py \
  --input scripts/fixtures/lookup_miss_sample.log \
  --output-json /tmp/lookup-miss-report.json \
  --output-md /tmp/lookup-miss-report.md

# Template-complete consumer (lookup before scrape; countable 404s)
uv run python examples/external-consumer/lookup_before_scrape.py \
  https://github.com/BurntSushi/ripgrep \
  github.com/acme/does-not-exist-dotrepo-probe \
  --miss-log /tmp/lookup-misses.log \
  --output-json /tmp/consumer-results.json
```

Live non-operator production traffic remains an ops follow-up after a third-party
framework adopts the reference pattern. The in-repo client is not operator CI
smoke; it is the integration template.

## Success signal

Sustained hosted-API or MCP traffic from **non-operator** consumers, plus a
growing lookup-miss list that is not empty only because logs were never
exported. Distribution outranks maintainer-adoption polish until that signal
exists.
