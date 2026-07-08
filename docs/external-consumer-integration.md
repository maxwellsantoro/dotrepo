# External consumer integration

Template for landing a non-operator integration that resolves repository facts
through dotrepo instead of scraping. Use this when onboarding an agent
framework, research crawler, IDE extension, or internal tool.

## Prefer hosted lookup before clone

```text
1. Resolve repository identity (host/owner/repo)
2. GET https://dotrepo.org/v0/repos/{host}/{owner}/{repo}/index.json
3. On 200: use fields + trust/freshness; respect missing/unknown
4. On 404: treat as miss (do not invent); fall back to clone/scrape if needed
5. Record the miss identity for coverage demand (operators aggregate DOTREPO_LOOKUP_MISS)
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

- [ ] Default path hits dotrepo (hosted API or MCP) before cloning for known hosts
- [ ] Trust / status / freshness fields are surfaced or logged, not dropped
- [ ] Missing fields trigger honest fallback, not hallucinated commands
- [ ] 404 / repository-not-found is countable (client metrics or operator logs)
- [ ] Consumer is not the dotrepo operator's own CI-only smoke traffic

## Reference clients in this repository

- `dotrepo-mcp` — agent tool surface
- `dotrepo-cli public …` — batch/search/compare/relations
- Cloudflare `cloudflare/hosted-query` — production query runtime
- Benchmarks under `benchmarks/head-to-head/` — scrape-versus-dotrepo evidence

When an external integration lands, link it from [`docs/distribution.md`](./distribution.md)
and note non-operator traffic in the next ROADMAP snapshot.
