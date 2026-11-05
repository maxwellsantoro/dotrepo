# Documentation

Use the owning guide for the task, then follow supporting links only as needed.
These guides describe this source checkout; [release compatibility](release-compatibility.md)
owns installed versions. The hosted export, source workflows and packages can
advance independently.

## Start here

| Task | Owning guide |
| --- | --- |
| Understand the product or try a lookup | [Project README](../README.md) |
| Install or integrate a released tool | [Installation](install.md), [consumer integration](external-consumer-integration.md) |
| Complete an experimental repository decision | [Selection flow](experimental-decision-selection.md), then [requirement assessments](experimental-decision-requirements.md) for setup/meaning |
| Retain or inspect source evidence | [Source cache](experimental-decision-source-cache.md) |
| Derive publisher context and check updates | [Maintainer path](maintainer-happy-path.md) |
| Select a dependency-ready work packet | [Roadmap](../ROADMAP.md#active-execution-order) |
| Coordinate a team | [Agent execution](agent-execution.md), [coordination skill](../.agents/skills/roadmap-coordination/SKILL.md) |
| Choose checks or understand delivery | [CONTRIBUTING](../CONTRIBUTING.md#local-checks), [CI execution](ci.md) |

## Reading paths (owner first, supporting only as needed)

| Area | Owner | Open supporting material for |
| --- | --- | --- |
| Capability and evidence | [Workflow status](workflow-status.md) | Public/source/released distinctions, shared source-status vocabulary and original negative studies; [discovery](experimental-decision-discovery.md) and its [comparison](experimental-decision-discovery-comparison.md) for that interface |
| Public surface | [Architecture](public-surface.md) | [Examples](public-export-examples.md) for routes/CLI equivalents; [API compatibility](public-api-compatibility.md) for wire fixtures; [freshness](public-freshness.md) for record versus export age |
| Maintainer and claims | [Maintainer path](maintainer-happy-path.md) | [Sync boundaries](sync-boundaries.md) for generation ownership; [claim review](maintainer-claim-review-workflow.md) for operator steps; [handoff](authority-handoff-examples.md) and [conflict](conflict-surfacing-examples.md) examples for illustrations |
| Authority and assurance | [Trust model](trust-model.md) | [Consumer acceptance](external-consumer-integration.md#positive-command-acceptance) for task-specific command use; source provenance alone is not correctness or permission |
| Tool implementation | [Reference overview](reference-overview.md) | [Maintainability](toolchain-maintainability.md) for module boundaries, [crawler](../crates/dotrepo-crawler/README.md) for orchestration and [import fixtures](import-baseline-audit.md) for regression rationale |

## Develop and operate

| Work | Guide |
| --- | --- |
| Local contributors and script inventory | [CONTRIBUTING](../CONTRIBUTING.md), [scripts](../scripts/README.md) |
| Index review, refresh, recovery and telemetry | [Index guide](../index/README.md), [crawl operations](factual-crawl-automation.md); use [escalation canary](m1-escalation-canary.md) only for a selected live escalation check |
| Generate and review public output | [Export workflow](public-export-workflow.md) |
| Host, restore or archive snapshots | [Cloudflare deployment](cloudflare-deploy.md) |
| Package or publish an authorized release | [Release checklist](public-release-checklist.md), [MCP registry](mcp-registry-publishing.md) |
| Maintain distribution surfaces | [Distribution](distribution.md); roadmap gates still select growth or independent-use work |

## Evaluate the product

[Workflow status](workflow-status.md#latest-evidence) is the compact evidence
entrypoint. It retains unsuccessful decisions, the source-cache comparison,
Discovery-100 and coding outcomes. Local correctness fixes do not replace those
observations or prove productivity.

| Question | Method or scoped evidence |
| --- | --- |
| Field presence, modeled requests and consumer-policy coverage | [Lookup efficiency](public-lookup-efficiency-benchmark.md) |
| Correct/incorrect assertions, missing facts and abstentions | [Factual accuracy](public-factual-accuracy-benchmark.md) |
| Discovery and ranking quality | [Search quality](public-search-quality-benchmark.md) |
| Paired task outcomes and frozen inputs | [Head-to-head benchmark](../benchmarks/head-to-head/README.md) |
| A separately selected execution or external-use study | [Consumer evaluation](consumer-pilot.md); its historical F-05/E1 protocols are not the active roadmap |

Keep task authoring, implementation and independent acceptance separate. Count
unfinished attempts, fallback and maintenance at equal quality/freshness. Presence,
policy acceptance, correctness, completed tasks and independent adoption are
different evidence levels.

## Contracts and history

The [RFC index](../rfcs/README.md) routes contract-specific design records and
labels deferred proposals. Code and executable fixtures outrank illustrative RFC
payloads; RFC acceptance does not imply a release. Preserve contract paths when
updating semantics intentionally.

[CHANGELOG](../CHANGELOG.md) owns completed implementation and releases;
[the archive](archive/README.md) owns dated reviews and earlier plans. Captured
sources, fixtures, telemetry and frozen experiment reports remain evidence.
`AGENTS.md` or `CLAUDE.md` inside those captures is upstream data, not repository
instructions. Do not rewrite it while maintaining this project's guidance.

Keep one authority per instruction: roadmap for dependencies, execution guide for
dispatch/handoffs, AGENTS for repository constraints, CONTRIBUTING/CI for checks,
and task guides for operational commands. Update the owner and link to it rather
than copying status tables, version constants, gate output or a second task list.
