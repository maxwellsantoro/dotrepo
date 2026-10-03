# External consumer integration

Template for landing a non-operator integration that resolves repository facts
through dotrepo instead of scraping. Use this when onboarding an agent
framework, research crawler, IDE extension, or internal tool.

## Prefer hosted lookup before clone

```text
1. Resolve repository identity (host/owner/repo)
2. Prefer GET https://dotrepo.org/v0/repos/{host}/{owner}/{repo}/profile.json
   (agent fields + trust). index.json is the lighter identity/selection surface.
3. On 200: check repository identity, record age, conflicts, and task-required fields
4. On stale/unknown age, conflict, or missing required fields: fall back to upstream
5. On 404: treat as miss (do not invent); fall back to clone/scrape if needed
6. Record the miss identity for coverage demand (operators aggregate DOTREPO_LOOKUP_MISS)
```

### Example: field query via hosted Worker

```bash
curl -sS "https://dotrepo.org/v0/repos/github.com/BurntSushi/ripgrep/query?path=repo.build"
```

### Example: MCP (stdio)

```json
{
  "mcpServers": {
    "dotrepo": {
      "command": "dotrepo-mcp",
      "args": []
    }
  }
}
```

Tool call:

```json
{
  "name": "dotrepo.lookup",
  "arguments": {
    "repositoryUrl": "https://github.com/BurntSushi/ripgrep",
    "path": "repo.description"
  }
}
```

Install the **stable** `dotrepo-mcp` binary from the latest `1.0.x` release
bundle or `cargo install dotrepo-mcp --version 1.0.1`. See
[`docs/install.md`](./install.md).

## Integration acceptance criteria

Template-complete in-repo reference client
([`examples/external-consumer/`](../examples/external-consumer/)) meets these
bullets in fixture tests. Live hosts may serve older profiles, which require fallback. Third-party adoption is still
the distribution success signal.

- [x] Default path hits dotrepo (hosted API or MCP) before cloning for known hosts
- [x] Trust / status / freshness fields are surfaced or logged, not dropped
- [x] Missing fields trigger honest fallback, not hallucinated commands
- [x] 404 / repository-not-found is countable (client metrics or operator logs)
- [ ] An independent consumer has deployed the integration and supplied outcome telemetry

## Reference clients in this repository

- **`examples/external-consumer/`** — lookup-before-scrape template client
  (`lookup_before_scrape.py`); emits Worker-compatible `DOTREPO_LOOKUP_MISS`
  lines for aggregation
- `dotrepo-mcp` — agent tool surface
- `dotrepo-cli public …` — batch/search/compare/relations
- Cloudflare `cloudflare/hosted-query` — production query runtime
- Benchmarks under `benchmarks/head-to-head/` — scrape-versus-dotrepo evidence

When a **third-party** integration lands, link it from
[`docs/distribution.md`](./distribution.md) and note non-operator traffic in the
next ROADMAP snapshot. Live non-operator traffic remains an ops follow-up.

## Task policy and measurements

```bash
uv run python examples/external-consumer/lookup_before_scrape.py \
  github.com/BurntSushi/ripgrep --require repo.build --require repo.test \
  --max-record-age-days 30 --output-json /tmp/consumer-results.json
```

`hit` means an HTTP document was found. `usable` means its identity, record age,
conflicts, and required fields passed the consumer policy. `fallback_reasons`
explains rejection. Age is recalculated at request time from `record.generatedAt`;
neither a newly exported snapshot nor `verified` status resets it. Missing and
future timestamps fail closed. Field assessments are retained where available;
`inferred` means inferred even if the record-wide confidence is high.

The example never executes returned commands. It reports fallback requirements;
the application decides how to inspect its upstream sources. Its request bytes
and elapsed time are real client measurements. They exclude subsequent fallback
and index maintenance and must not be advertised as total task savings.

## Positive command acceptance

The reference consumer accepts a requested primary build/test command only when
it is a nonempty string with an explicit `present`, `extracted`, high-confidence
field assessment, a nonempty source, and a check timestamp matching the record.
Missing, invalidated, malformed, unspecified, inferred, or weaker assessments
require upstream fallback. Record-wide confidence and maintainer status do not
substitute for this contract; no maintainer-authority exemption is implemented.
Unsupported response versions and non-string requested values also require
fallback. Acceptance is metadata suitability, not permission to execute a command.
The benchmark leaves field confidence unknown when absent.

Policy coverage is published on the efficiency page and in its linked JSON.
It distinguishes value presence, policy acceptance, independently established
correctness, and completed tasks. The last two remain unmeasured in the coverage
report; they require the existing benchmark and independent pilot evidence.
