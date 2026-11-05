# Distribution operations

This guide maintains the existing discovery and installation surfaces. It is
not a separate growth or outreach queue; the [roadmap](../ROADMAP.md) selects
new consumer, publisher and independent-use work.
It follows the current source branch; consult
[release compatibility](release-compatibility.md) for stable binary behavior.

<!-- dotrepo:release-status:start -->
Stable installs use `1.0.4`; current source is `2.0.0-rc.2` (release candidate).
Use the matching tagged documentation for installed binaries.
<!-- dotrepo:release-status:end -->

## Shipped surfaces

| Surface | Status | Notes |
|---------|--------|-------|
| Hosted public API (`https://dotrepo.org/v0/...`) | Live | Static export + Cloudflare hosted-query Worker |
| MCP server (`dotrepo-mcp`) | Shipped | Stdio; NDJSON framing (1.0.1); registry package path documented |
| crates.io (`dotrepo-cli`, `dotrepo-mcp`, `dotrepo-lsp`, …) | Stable package path | Use the stable version in [install guidance](install.md); source follows the release status above; the separate `dotrepo` alias is absent from the stable release |
| Lookup-efficiency benchmark page | Live | `/efficiency/` on the public site |
| pagedigest publisher | Live | `/.well-known/pagedigest.json` |

## Operator checklist (recurring)

1. **MCP registry listing** — keep `server.json` / mcpb bundle and
   [`docs/mcp-registry-publishing.md`](./mcp-registry-publishing.md) aligned
   with the source release being packaged; publish the matching bundle on each
   tag. The registry's latest view can prefer a higher prerelease: link the
   explicit stable version from installation guidance and label preview builds.
2. **Efficiency pitch** — regenerate the public efficiency page on deploy
   (`scripts/render_public_efficiency_page.py` via the release/public gate).
   Label presence and policy acceptance separately; request reduction is modeled.
   Use complete consumer measurements before claiming token, latency, or net
   cost savings ([methodology](public-lookup-efficiency-benchmark.md)).
3. **Lookup-miss review** — process actual exported logs locally using the
   command below. `.github/workflows/lookup-miss-demand.yml` is a manual
   `workflow_dispatch` fixture proof; it collects no live logs and does not run
   on a schedule. Its artifact is labeled as fixture evidence.

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
   # Replace TASK with a unique task/run name and retain the source logs:
   uv run python scripts/export_lookup_miss_demand.py \
     --input /tmp/lookup-misses.log \
     --output-dir /tmp/dotrepo-TASK/lookup-miss-review

   # Offline proof (fixture):
   uv run python scripts/export_lookup_miss_demand.py \
     --input scripts/fixtures/lookup_miss_sample.log \
     --output-dir /tmp/dotrepo-TASK/lookup-miss-fixture
   ```

   Use repeated misses to identify a bounded workflow gap. General cohort
   growth still requires the roadmap's usefulness, independent-use and cost
   evidence; `scripts/plan_index_growth_tranche.py` is an operator tool, not
   automatic permission to expand.
4. **External consumer** — when D5 is selected and authorized, use a bounded
   non-operator integration (agent framework, research crawler, or IDE) with
   stated outcomes and costs. Preparing its guide does not authorize outreach.
   Template and in-repo reference client: [`docs/external-consumer-integration.md`](./external-consumer-integration.md)
   and [`examples/external-consumer/`](../examples/external-consumer/).
5. **Version clarity** — public install docs must send production users to
   the current stable release; prerelease installation is an explicit opt-in
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

Sustained hosted-API or MCP use by **non-operator** consumers with dated task
outcomes and a declared observation window. Report whether miss collection was
complete: absent logs mean unknown demand, and zero observed misses do not prove
complete coverage. Traffic alone does not establish useful work or net benefit.
The [roadmap](../ROADMAP.md#active-execution-order) owns sequencing:
improve useful consumer decisions and low-maintenance publisher setup together,
then evaluate both sides' effort. Operator fixtures remain useful local controls
while independent adoption is unestablished.

## Evidence handoff

Use [current workflow evidence](workflow-status.md) for decision/reuse outcomes
and [the separately scoped pilot plan](consumer-pilot.md) for execution-pilot
preparation and independent-use acceptance. Use
[the integration contract](external-consumer-integration.md) for lookup suitability.
The reference client reports usable answers, fallback requirements, and lookup
bytes/latency; the end-to-end harness includes upstream fallback. Neither an
operator run nor the reference client's lookup-only timings establishes
independent adoption or total task savings.
