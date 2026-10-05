# Documentation

Start with the task you need to complete. Relative guides describe this source
branch; installed binaries need [version-matched documentation](release-compatibility.md).
The hosted export can advance independently of client releases.

## Start here

| Task | Guide |
| --- | --- |
| Understand dotrepo and try a lookup | [Project README](../README.md) |
| Install a stable tool or extension | [Installation](install.md), [release compatibility](release-compatibility.md) |
| Integrate an agent or tool | [Consumer integration](external-consumer-integration.md), [reference client](../examples/external-consumer/README.md) |
| Adopt a native `.repo` | [Maintainer path](maintainer-happy-path.md), [sync boundaries](sync-boundaries.md) |
| Interpret authority, evidence, or age | [Trust model](trust-model.md), [freshness](public-freshness.md) |
| Use HTTP/CLI public routes | [Public examples](public-export-examples.md), [architecture](public-surface.md) |
| Contribute code or records | [Contributing](../CONTRIBUTING.md), [index guide](../index/README.md) |
| Find active work and gates | [Roadmap](../ROADMAP.md#active-execution-order) |
| Coordinate concurrent implementation | [Agent execution](agent-execution.md), [project coordination skill](../.agents/skills/roadmap-coordination/SKILL.md) |

## Develop and operate

| Area | Reference |
| --- | --- |
| Tool surfaces and version owners | [Toolchain reference](reference-overview.md) |
| Structure and split plans | [Maintainability](toolchain-maintainability.md), [crawler crate](../crates/dotrepo-crawler/README.md) |
| Import regressions | [Fixture rationale](import-baseline-audit.md) |
| Autonomous refresh, landing, telemetry, recovery | [Crawl automation](factual-crawl-automation.md) |
| Escalation live proof | [Canary procedure](m1-escalation-canary.md) |
| Export generation and local runtime | [Export workflow](public-export-workflow.md) |
| Release checks and publication | [Release checklist](public-release-checklist.md), [MCP registry](mcp-registry-publishing.md) |
| Hosting and snapshot restoration/archive | [Cloudflare setup](cloudflare-deploy.md) |
| Maintainer authority review | [Claim workflow](maintainer-claim-review-workflow.md), [handoff examples](authority-handoff-examples.md), [conflict examples](conflict-surfacing-examples.md) |
| Distribution and demand collection | [Distribution](distribution.md) |
| Script inventory | [Scripts guide](../scripts/README.md) |

## Evaluate the product

Presence, policy acceptance, independently checked correctness, completed tasks,
and independent adoption are separate evidence levels.

- [Lookup-efficiency methodology](public-lookup-efficiency-benchmark.md): field
  presence, local payload proxy, modeled requests, and consumer-policy coverage
- [Factual-accuracy suites](public-factual-accuracy-benchmark.md): cited exact
  assertions, missing facts, incorrect assertions, and correct abstentions
- [Search-quality harness](public-search-quality-benchmark.md): discovery/rank
  metrics and limitations of legacy cost estimates
- [Head-to-head benchmark](../benchmarks/head-to-head/README.md): independent
  gold, upstream fallback, frozen inputs, and retained wins and losses
- [Own-project study and later pilot](consumer-pilot.md): operator task outcomes
  now; independent external use and complete cost accounting at a later stage

## Contracts and history

- [Public API compatibility](public-api-compatibility.md): executable wire contract
- [RFC index](../rfcs/README.md): design records and deferred proposals;
  RFC acceptance and implementation completion are separate
- [Changelog](../CHANGELOG.md): release and completed implementation history
- [Archived reviews](archive/README.md), [AI interviews](ai-tool-interviews.md),
  [edge canary history](public-edge-canary-history.md): historical evidence with
  their original scope and dates

Code and tested contracts outrank prose. Keep active sequencing in the roadmap,
current measurements in generated reports, and historical evidence immutable.
Routine generated overlays use machine gates; the manual contribution checklist
and claim review are distinct workflows.

Use one owner for each instruction: roadmap packets/dependencies in the roadmap,
team dispatch/handoffs in the execution guide, invariant rules in `AGENTS.md`,
and commands in the relevant workflow guide. Update the owner and link to it;
do not copy its model choices, version constants, status tables, or gate output
into additional docs. Draft RFCs and archived implementation sequences are design
context rather than another ready-work queue.
