# Toolchain and protocol reference

This is the detailed inventory for the current source branch. For installed
stable binaries, use [release compatibility](release-compatibility.md) and its
version-matched documentation links. The [README](../README.md) contains the
short getting-started path.

## Three parts

1. **Protocol:** a versioned TOML `.repo` manifest for repository metadata,
   ownership, provenance, trust, and synchronization hints
2. **Reference tools:** the Rust CLI, stdio MCP server, language server, and
   editor integration share validation and selection logic in `dotrepo-core`
3. **Public index:** Git-backed overlay records make source-linked repository
   facts available before maintainers adopt a native `.repo`

The index is refreshed automatically. Parsers and evidence checks run first;
bounded model adjudication can resolve uncertainty from grounded candidates.
Routine generated records do not require human review. Humans set policy,
improve checks, monitor results, and handle maintainer authority claims. See
[crawl automation](factual-crawl-automation.md), [index layout](../index/README.md),
and the [manual contribution and audit checklist](../index/review-checklist.md).

## MCP tools

`dotrepo-mcp` exposes:

- `dotrepo.validate`
- `dotrepo.query`
- `dotrepo.trust`
- `dotrepo.adoption_status`
- `dotrepo.lookup`
- `dotrepo.claim_inspect`
- `dotrepo.generate_check`
- `dotrepo.import_preview`
- `dotrepo.import_write`

Local example:

```json
{
  "name": "dotrepo.query",
  "arguments": {
    "root": "examples/native-minimal",
    "path": "repo.build"
  }
}
```

The response contains the selected value, record status, provenance, and conflict
context. `dotrepo.lookup` accesses the hosted index without a local clone; see the
[consumer integration guide](external-consumer-integration.md) for configuration
and fallback. Response fields and network safeguards differ by release; see
[release compatibility](release-compatibility.md#mcp-network-policy).

Tool execution errors use MCP tool results with `isError: true` and
machine-readable `structuredContent`. Protocol mistakes, including unknown tool
names, use JSON-RPC errors. The [MCP contract](../rfcs/0006-mcp-server-contract.md)
defines the current interface.

## Validation and generated files

`dotrepo validate` checks only the root `.repo` or root `record.toml` for the
selected repository. Use `dotrepo validate-index` for descendant
`index/repos/**/record.toml` overlays. `query` and `trust` can load matching
descendant candidates when resolving conflict-aware answers.

Supported generated Markdown regions include README, SECURITY, and CONTRIBUTING.
CODEOWNERS can be fully generated but is not partially managed. See
[sync boundaries](sync-boundaries.md) and the
[maintainer guide](maintainer-happy-path.md) before adopting an existing file.

## Hosted queries

The public API provides exact lookup, batch profiles and fields, structured
search, factual comparison, and relationship traversal. For example:

```bash
curl -sS "https://dotrepo.org/v0/batch/profiles?repo=github.com/sharkdp/fd"
```

[Public examples](public-export-examples.md) document routes and CLI equivalents.
[Public architecture](public-surface.md) explains the exported JSON and the query
runtime. Optional research synthesis stays separate from factual fields.
[Freshness](public-freshness.md) distinguishes export time from record age.

## Protocol decisions and versions

The canonical native form is a single root `.repo` TOML file. Overlay records
live separately in the index and carry their own provenance and trust metadata.
Validation is mode-aware. Generated files complement the manifest rather than
replacing all existing editing workflows. `x.*` is reserved for extensions;
repository relations are explicit directed links with their own trust context.

Read exact schema and protocol versions from their owners instead of assuming
they match the tool version:

- release version: [GitHub releases](https://github.com/maxwellsantoro/dotrepo/releases)
- manifest schema: the manifest's version and [validation implementation](../crates/dotrepo-core/src/validation.rs)
- claim schema: [claim implementation](../crates/dotrepo-core/src/claims.rs)
- MCP negotiation: [MCP implementation](../crates/dotrepo-mcp/src/dispatch.rs)
- hosted API: the deployed [meta.json](https://dotrepo.org/v0/meta.json) and [compatibility contract](public-api-compatibility.md)

Bundle mode, first-class workspace semantics, public mutation APIs, broad editor
automation, arbitrary prose round-tripping, and production-scale ranking
calibration remain deferred. See [the roadmap](../ROADMAP.md).

## Source inventory

- Rust workspace: `dotrepo-schema`, `dotrepo-core`, `dotrepo-cli`, `dotrepo-mcp`,
  `dotrepo-lsp`, `dotrepo-crawler`, and shared internal `dotrepo-transport`
- Current development alias package: [`crates/dotrepo/`](../crates/dotrepo/)
- [VS Code extension](../editors/vscode/) and [native/overlay examples](../examples/)
- [Crawler](../crates/dotrepo-crawler/README.md) for discovery, verification,
  adjudication, optional synthesis, refresh, and writeback
- [Public index](../index/), [CI/release workflows](../.github/workflows/), and
  [Cloudflare deployment](cloudflare-deploy.md)

## Principles and evidence

Keep the protocol open, source-linked, useful before adoption, and readable by
both people and tools. Imported, declared, and inferred facts must remain
distinguishable. Deterministic parsing comes first; uncertainty must remain
visible when checks cannot resolve it. See the [trust model](trust-model.md) and
[protocol RFC](../rfcs/0001-protocol-and-ecosystem.md).

The [head-to-head benchmark](../benchmarks/head-to-head/) measures accuracy,
abstention, confidently wrong answers, latency, and transferred bytes against a
GitHub API + README baseline. It is allowed to show losses.
[AI interviews](ai-tool-interviews.md) are dated product research, and the
[consumer pilot](consumer-pilot.md) defines evidence needed before claiming
independent adoption or end-to-end savings.
