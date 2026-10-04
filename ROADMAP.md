# dotrepo Roadmap

Make repository understanding reusable infrastructure: extract a compact set of
facts once, preserve their evidence and age, and reuse them across agents,
developers, and tools.

This file owns direction, execution order, and milestone gates. [README](README.md)
owns shipped behavior, [CHANGELOG](CHANGELOG.md) owns release history, and
[the documentation map](docs/README.md) routes implementation and operator work.
Code and tested contracts outrank prose. Installed binaries follow their
[version-matched documentation](docs/release-compatibility.md).

## Active execution order

The September 16 product review and October 3 semantic review establish this
sequence. Implementation completion does not establish factual accuracy,
sustained operations, consumer adoption, or net savings.

| Priority | Work | Required evidence |
| --- | --- | --- |
| 1 | Sustain factual freshness and correct uncertain fields | Real source checks; record-age gate; independent exact-value and abstention results across ecosystems |
| 2 | Populate and evaluate useful execution metadata | Source-grounded contexts under the value-bound command/directory/scope/prerequisite contract; consumer results before restoring nested commands |
| 3 | Enforce CI and prepare a stable release | Required checks compatible with scoped jobs; dependencies and compatibility validated against the immutable stable tag; published artifacts before changing install defaults |
| 4 | Measure complete consumer tasks | Independently selected upstream answers, fallback work, actual model usage, cache state, and allocated index maintenance costs |
| 5 | Establish independent use | One consenting external consumer with a deployed integration, repeated usage, and reproducible task outcomes |
| 6 | Open larger growth cohorts | Quality, freshness, reliability, throughput, and unit-cost budgets hold before increasing coverage |

### Now

- Work the coverage and audit queues where source evidence can improve answers.
  Preserve honest absence and conflicts; do not fill fields merely to meet counts.
- Keep nested, component-scoped, incomplete, and prerequisite-dependent commands
  withheld as scalar repository defaults. Extraction confidence does not establish
  usefulness. Candidate commands also require review of their scope.
  Use [the execution-context contract](rfcs/0021-value-bound-execution-context.md)
  to preserve explicit facts; extraction must establish the complete context
  before populating it, and absent context remains unassessed.
- Require fresh crawler inspection for new verification. Standalone
  `promotion-report --apply` is disabled on this branch; retained assessments and
  status labels cannot establish a new upstream check. Stable behavior differs.
- Confirm repository settings enforce the relevant CI result at merge time.
  Account for intentionally skipped jobs in the change-scope classifier.
- Prepare and validate a stable-line backport/release. Keep generated maintainer
  CI pinned to an existing stable artifact until its replacement ships.
- Run a fresh end-to-end evaluation, then complete the
  [independent consumer pilot](docs/consumer-pilot.md). Preserve unfavorable results
  and distinguish regressions on known cases from independent proof.

### In parallel

- Maintain the [distribution and demand path](docs/distribution.md): registry
  listings, version-matched installs, exported lookup misses, and external
  integration support. Report the efficiency page's presence and modeled-request
  metrics according to their measurement limits.
- Convert weekly risk-weighted [audits](docs/factual-crawl-automation.md#audit-cadence)
  into fixtures, parser fixes, or explicit policy dispositions.
- Execute [maintainability split plans](docs/toolchain-maintainability.md) when
  touching their hotspots; keep transports thin and facade imports compatible.
- Improve native authoring and claim handoffs without making maintainer adoption
  a prerequisite for overlay usefulness.

### Next and later

After consumer and operating proof, expand in 50–100 repository cohorts toward
1,000 maintained profiles. Move toward 10,000 and broader public coverage only
when measured resource forecasts support the next step. Start an independent
conformance test before full ecosystem scale so the protocol does not overfit
its reference implementation.

## Mission

Agents repeatedly fetch loosely structured repository material to recover the
same purpose, commands, docs, and ownership facts. dotrepo provides a shared,
refreshable semantic layer with evidence, authority, conflicts, and age attached.
Repository orientation is the immediate use; architecture research, debugging,
suitability decisions, and code changes still need source inspection.

The intended loop is:

```text
repository sources or maintainer-authored .repo
  -> normalized facts with evidence and uncertainty
  -> public profile and compatible repository surfaces
  -> lookup, discovery, comparison, and agent use
  -> incremental refresh or maintainer correction
```

Autonomous overlays provide coverage before adoption. A maintainer-controlled
canonical record can supersede an overlay for the same identity while preserving
its history. Native mode alone does not grant canonical precedence.

## Core thesis

The three parts reinforce each other:

1. **Authoring:** one structured source for maintainer metadata and supported
   generated documentation, with drift detection.
2. **Consumption:** predictable facts, trust, age, and relationships through
   local tools, JSON, and MCP.
3. **Indexing:** evidence-backed overlays for repositories whose maintainers
   have not adopted the protocol.

The API and MCP are the primary agent surfaces. The website lets people look up
records, inspect evidence and limits, and start adoption or integration.

## Non-negotiable principles

- **Parse once, reuse:** deterministic parsers and host metadata precede models;
  avoid unchanged work before escalating uncertainty.
- **Evidence bounds intelligence:** models choose grounded candidates and pass
  deterministic post-checks. Synthesis remains optional and separate from facts.
- **Absence is valid:** missing, unresolved, conflicting, and not-found answers
  remain distinguishable. Pipeline confidence is not a calibrated probability.
- **No routine human approval tier:** machine gates publish generated overlays;
  humans define policy, audit systems, and review maintainer authority claims.
  Automation never mints `reviewed` or `canonical`.
- **Authority stays explicit:** canonical native records take precedence;
  selection preserves conflicts and does not silently blend fields.
- **Refresh and cost constrain growth:** changed or stale records drive work;
  cohort budgets cover network, CPU, memory, accelerator use, storage, tokens,
  and wall time. Local models also have operating costs.
- **Adoption is independent of coverage:** unclaimed repositories must remain
  useful and honestly represented.
- **Keep the schema small:** factual metadata stays compact; synthesis, ranking,
  and ecosystem extensions remain separable.

## Autonomous intelligence ladder

Every field should stop at the cheapest method that resolves it honestly.

| Tier | Method | Purpose |
| --- | --- | --- |
| -1 | Cached identity, head, and evidence digests | Avoid unchanged work |
| 0 | Parsers, host APIs, manifests, known files | Establish explicit facts |
| 1 | Deterministic inference and reconciliation | Resolve conventions, conflicts, and inspected absence |
| 2 | Bounded primary adjudicator | Choose among grounded candidates |
| 3 | Independent second opinion | Resolve low confidence or disagreement |
| 4 | Stronger remote model within strict budgets | Address the difficult tail |
| 5 | Partial publication or abstention | Preserve insufficient evidence |

There is no routine human adjudication tier. Budget exhaustion must preserve
partial progress without bypassing validation. Model/provider routing should be
calibrated against task-level quality, latency, and cost; a stronger model must
justify its incremental value.

Further work avoidance includes content-digest caches for evidence and parser
results, delta processing, conditional/batched host requests, adaptive scheduling,
and bounded negative caching for unavailable repositories. Model cache keys must
include evidence digest, field, prompt/policy versions, and model identity.
These are scale objectives, not claims that every optimization is implemented.

## Quality model

Quality requires identity/path invariants, source-linked field assessments,
explicit conflicts and absence, safe command screening, grounded model output,
fixtures and golden contracts, ecosystem canaries, and risk-weighted audits.

Writeback and verification are separate: a structurally sound partial overlay
may publish, while `verified` requires every scored field to be honestly resolved
at high confidence. Labels never guarantee correctness, completeness, recent
inspection, or human approval. Release policy gates factual accuracy, record age,
validity, conflicts, and completeness; status counts are reported without a
minimum verified-count incentive.

See [trust semantics](docs/trust-model.md),
[crawler gates](docs/factual-crawl-automation.md), and
[consumer acceptance](docs/external-consumer-integration.md#positive-command-acceptance).

## Platform integrity

Keep these implemented controls green; historical closure is not evidence that
current deployments or repository settings are configured correctly.

| Control | Contract and implementation |
| --- | --- |
| Explicit automation enablement | Scheduled refresh requires `INDEX_AUTOMATION_ENABLED=true`; unset disables writeback |
| Tested automatic landing | Same-repository index-only PR; exact head/base checks; explicitly dispatched CI; non-forced fast-forward; deployment dispatch and smoke verification |
| Multi-artifact writeback | Per-record lock, staging and backups, rollback on I/O failure; crash recovery remains an operator responsibility |
| MCP remote lookup | Allowlisted origins, same-origin snapshot paths, private-address checks, no redirects, resolved-address pinning; opt-in overrides relax policy |
| Hosted cost bounds | Search reads pointer plus compact search data; limit bounds response size, while matching scans that document; relations prefer precomputed snapshots |
| Telemetry and release gates | Strict scheduled telemetry, index validation, and public gates before landing; retain partial-progress and failure evidence |
| Supply chain and CLI parity | SHA-pinned actions, checked publisher downloads, locked dependencies, shared CLI dispatch |

Sources: [refresh workflow](.github/workflows/index-autonomous-refresh.yml),
[landing helper](scripts/land_autonomous_index.py),
[MCP policy](crates/dotrepo-mcp/src/lookup.rs),
[writeback](crates/dotrepo-crawler/src/writeback.rs),
[Worker](cloudflare/hosted-query/src/worker.mjs), and [CI](.github/workflows/ci.yml).
Safeguards on this branch do not retroactively change stable binaries.

## Product milestones

Milestones are capability and outcome gates, not release dates. Historical
implementation proof is recorded in the changelog and retained reports.

| Milestone | Implementation position | Remaining outcome or scale proof |
| --- | --- | --- |
| M0: Working protocol and proof surface | Native/overlay schema, CLI/MCP/LSP, generation, trust, hosted export implemented | Keep contracts and version boundaries coherent |
| M1: Autonomous index factory | Crawl, refresh, bounded escalation, telemetry, and automatic landing implemented; July operational proof retained | Sustain current cadence, partial-failure recovery, freshness, and costs |
| M2: Useful shared semantic cache | Profile, batch/query, cache/freshness contracts and historical 500-profile gate delivered | Independent accuracy and complete consumer task results |
| M3: Research substrate | Search, comparison, typed relations, optional synthesis implemented | Representative ranking/synthesis calibration and costs |
| M4: Ecosystem scale | Scheduling and reporting scaffolding implemented | Consumer proof and measured cohorts before larger growth |
| M5: Maintainer adoption | Bootstrap, readiness, CI, claim helpers, and audit trail implemented | Durable independent native use and handoffs |
| M6: Open metadata standard | Design direction | External conformance, independent producers/consumers, interoperable indexes |

### Milestone 4: Index at ecosystem scale

Entry requires sustained factual freshness, independent evaluation, a consenting
external consumer's repeated use, and healthy operating budgets. Demand comes
from exported lookup misses and repeated consumer fallbacks; package-registry
rankings can serve as interim proxies. Balance ecosystems, layouts, relationship
centrality, and canary needs; maintainer interest is optional.

The first scale checkpoint is 1,000 maintained profiles. Each 50–100 record
cohort must report:

- exact-value accuracy, incorrect assertions, missing answers, and correct
  abstentions by intent and ecosystem
- parser/validation failures, quarantine, retry outcomes, and partial-progress safety
- record freshness: at most 10% stale or unknown under the 30-day policy, with
  maximum refresh overdue no more than seven days
- unchanged-work avoidance and cache hits, with real planning costs included
- network requests/bytes, files materialized, CPU/accelerator use, peak memory,
  storage/export/serving cost, and wall time
- model calls, tokens, cost, and outcomes by tier/provider/task class
- separate unchanged, changed, improved-record, and monthly maintenance costs

Raise cohort size only while these budgets hold. Refresh work should follow
changed/stale records, throughput should improve without proportional human
labor, and measured costs must support a resource forecast before the next
scale step. Field improvement must be measured separately from status promotion.

### Milestone 5: Maintainer adoption flywheel

Make record inspection, native bootstrap, preview, managed surfaces, CI, and
claim handoff easy. The first adoption checkpoint remains ten maintainer-owned
native records and five accepted overlay-to-native handoffs, with conversion and
retention telemetry. Acceptance alone is not canonical publication. M5 does not
gate autonomous coverage; current consumer proof outranks adoption polish.

### Milestone 6: Open repository metadata standard

Deliver a stable specification and compatibility suite exercised by an
independent consumer, then support independent producers, SDKs, mirrors, and
schema/trust governance. Tools must be able to consume the protocol without the
reference implementation. Bundle mode and workspace semantics stay deferred
until justified by usage.

## Metrics that matter

| Dimension | Evidence | Interpretation |
| --- | --- | --- |
| Quality | Exact-value suites, head-to-head answers, intent/ecosystem scorecards, audit dispositions | Presence, policy acceptance, correctness, and completed tasks are distinct |
| Freshness/reliability | Record-age gate, overdue backlog, scheduled pass streaks, failure/recovery outcomes | Export time does not reset factual age; an implemented schedule is not successful operation |
| Efficiency | Unit-cost reports plus complete consumer transport/model/maintenance measurements | Modeled requests and payload estimates do not establish billed token or net task savings |
| Utility/distribution | Frozen workloads, fallback reasons, non-operator repeated usage, exported lookup misses | Reference clients and operator traffic do not establish independent adoption |
| Authority/adoption | Native records, accepted handoffs, canonical publication, 90-day retention | Claims and authority upgrades remain separate from overlay coverage |
| Capacity | Maintained profile count, throughput, resource forecasts | Raw count and verified ratio are not success metrics by themselves |

Generate current values from growth, coverage, freshness, accuracy, policy,
telemetry, and unit-cost artifacts. Keep dated results in
[historical reports](docs/archive/README.md) and [benchmark results](benchmarks/head-to-head/README.md).
Do not copy live dashboards or completed implementation inventories into this file.

## Shared direction with pagedigest

[pagedigest](https://pagedigest.org) provides change signals for published URLs;
dotrepo provides repository facts and their authority/evidence context. The
public export publishes a PageDigest manifest to support avoiding unchanged
fetches. That complement is useful infrastructure, while measured consumer
outcomes remain dotrepo's product proof.

## Explicit non-goals

- routine human review of every generated overlay
- model calls for facts parsers can establish, or budget spent to hide unknowns
- synthesis overwriting factual metadata
- silent field merging or authority inflation
- a general code-search engine or package registry
- public mutation without enforceable provenance and authority
- arbitrary prose round-tripping or operational workspace orchestration
- growth that weakens accuracy, freshness, safety, or resource budgets
- treating prereleases as production install defaults

## Strategic test

Success means an agent checks dotrepo, receives suitable facts with source and
age context, inspects the additional upstream material its task needs, and reuses
that maintained understanding later. Independent outcomes must demonstrate that
this improves useful work after fallback and maintenance costs are included.
