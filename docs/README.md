# Documentation

dotrepo keeps active project-level facts in three places:

- [`../README.md`](../README.md) - what dotrepo is, what ships, and how to start
- [`../ROADMAP.md`](../ROADMAP.md) - direction, active execution order, and milestone gates
- [`../CHANGELOG.md`](../CHANGELOG.md) - release history

Code and tested contracts outrank prose. Detailed tasks belong in issues or
project tooling rather than additional plan documents.

## Use dotrepo

- [`install.md`](./install.md)
- [`maintainer-happy-path.md`](./maintainer-happy-path.md)
- [`sync-boundaries.md`](./sync-boundaries.md)
- [`trust-model.md`](./trust-model.md)

## Consume the public index

- [`public-surface.md`](./public-surface.md)
- [`public-export-examples.md`](./public-export-examples.md)
- [`public-freshness.md`](./public-freshness.md)
- [`public-api-compatibility.md`](./public-api-compatibility.md)
- [`public-lookup-efficiency-benchmark.md`](./public-lookup-efficiency-benchmark.md)
- [`public-factual-accuracy-benchmark.md`](./public-factual-accuracy-benchmark.md)
- [`public-search-quality-benchmark.md`](./public-search-quality-benchmark.md)
- [`distribution.md`](./distribution.md) - how agents and tools discover and use the public surface
- [`external-consumer-integration.md`](./external-consumer-integration.md) - template for non-operator integrations
- [`../benchmarks/head-to-head/`](../benchmarks/head-to-head/) - falsifiable GitHub-baseline vs dotrepo benchmark harness
- [`../index/README.md`](../index/README.md)

## Develop the reference toolchain

- [`toolchain-maintainability.md`](./toolchain-maintainability.md)
- [`import-baseline-audit.md`](./import-baseline-audit.md) - import fixture rationale and regression barrier
- [`../crates/dotrepo-crawler/README.md`](../crates/dotrepo-crawler/README.md)

## Operate the system

- [`factual-crawl-automation.md`](./factual-crawl-automation.md)
- [`m1-escalation-canary.md`](./m1-escalation-canary.md) - second-opinion / strong-remote live proof procedure
- [`public-export-workflow.md`](./public-export-workflow.md)
- [`public-release-checklist.md`](./public-release-checklist.md)
- [`mcp-registry-publishing.md`](./mcp-registry-publishing.md)
- [`cloudflare-deploy.md`](./cloudflare-deploy.md)
- [`public-edge-canary-history.md`](./public-edge-canary-history.md) - operator log of notable canary runs
- [`maintainer-claim-review-workflow.md`](./maintainer-claim-review-workflow.md)

Generated overlays use machine publication gates. The index review checklist is
for manual contributions and audits, not a routine human approval tier.

## Design records

- [`../rfcs/`](../rfcs/) - protocol and contract decisions
- [`authority-handoff-examples.md`](./authority-handoff-examples.md)
- [`conflict-surfacing-examples.md`](./conflict-surfacing-examples.md)
- [`ai-tool-interviews.md`](./ai-tool-interviews.md) - dated product research
- [`archive/`](./archive/) - explicitly retained historical reviews

Superseded plans and release snapshots are preserved by Git history rather than
kept in the active documentation tree.
