# Distribution workstream

Index quality creates value; distribution captures it. This checklist tracks the
concrete surfaces that make agents and tools check dotrepo before scraping.
It follows the current source branch; consult
[release compatibility](release-compatibility.md) for stable binary behavior.

## Shipped surfaces

| Surface | Status | Notes |
|---------|--------|-------|
| Hosted public API (`https://dotrepo.org/v0/...`) | Live | Static export + Cloudflare hosted-query Worker |
| MCP server (`dotrepo-mcp`) | Shipped | Stdio; NDJSON framing (1.0.1); registry package path documented |
| crates.io (`dotrepo-cli`, `dotrepo-mcp`, `dotrepo-lsp`, …) | Stable package path | Pin `1.0.1` for consumers; `main` is unreleased `2.0.0-alpha.0`; the separate `dotrepo` alias was added after the stable tag |
| Lookup-efficiency benchmark page | Live | `/efficiency/` on the public site |
| pagedigest publisher | Live | `/.well-known/pagedigest.json` |

## Operator checklist (recurring)

1. **MCP registry listing** — keep `server.json` / mcpb bundle and
   [`docs/mcp-registry-publishing.md`](./mcp-registry-publishing.md) aligned
   with the latest stable release; re-publish on each stable tag.
2. **Efficiency pitch** — regenerate the public efficiency page on deploy
   (`scripts/render_public_efficiency_page.py` via the release/public gate).
   Label presence and policy acceptance separately; request reduction is modeled.
   Use complete consumer measurements before claiming token, latency, or net
   cost savings ([methodology](public-lookup-efficiency-benchmark.md)).
3. **Lookup-miss demand (fixed cadence)** — weekly scheduled workflow
   `.github/workflows/lookup-miss-demand.yml` (Mondays 07:30 UTC) or manual
   `workflow_dispatch`. Offline by default (fixture proof); attach a live log
   artifact and set `log_artifact_name` for real Worker demand.

   The hosted Worker emits `DOTREPO_LOOKUP_MISS` on **static** repository-surface
   404s for published leaves
   (`/v0/repos/{host}/{owner}/{repo}/{index,profile,trust,relations}.json`) and
   on dynamic not-found paths (query/batch/compare/relations). Summary content
   is `index.json` (not a bare `/summary` path). Verify the deployed Worker
   version before treating exported demand as complete.

   Local path:

   ```bash
   # Capture live lines (Cloudflare Logpush, dashboard, or):
   #   cd cloudflare/hosted-query && npx wrangler tail --format pretty
   # Then standardize outputs under index/telemetry/:
   uv run python scripts/export_lookup_miss_demand.py \
     --input /tmp/lookup-misses.log

   # Offline proof (fixture):
   uv run python scripts/export_lookup_miss_demand.py
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
framework adopts the reference pattern. The in-repo client is a reference implementation, not an independent consumer.

## Success signal

Sustained hosted-API or MCP traffic from **non-operator** consumers, plus a
growing lookup-miss list that is not empty only because logs were never
exported. Distribution outranks maintainer-adoption polish until that signal
exists.

## Evidence handoff

Use [the pilot plan](consumer-pilot.md) for preparation packages, outcome telemetry,
and adoption/savings acceptance. Use
[the integration contract](external-consumer-integration.md) for lookup suitability.
The reference client reports usable answers, fallback requirements, and lookup
bytes/latency; the end-to-end harness includes upstream fallback. Neither an
operator run nor the reference client's lookup-only timings establishes
independent adoption or total task savings.
