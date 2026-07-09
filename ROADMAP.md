# dotrepo Roadmap

This document defines both the long-range direction and the active execution
order for dotrepo. Shipped capabilities live in [`README.md`](./README.md);
release history lives in [`CHANGELOG.md`](./CHANGELOG.md).

**How to use this document**

| Need | Read |
| --- | --- |
| What to do next | [Active execution order](#active-execution-order) |
| Why the system exists | [Mission](#mission), [Core thesis](#core-thesis), [Non-negotiable principles](#non-negotiable-principles) |
| Capability gates | [Product milestones](#product-milestones) |
| Safety / ops integrity (closed) | [Platform integrity](#platform-integrity) — keep green; not the active work queue |
| Live numbers | Generated artifacts (`scripts/render_index_growth_status.py`, intent scorecard, unit-cost report) — not this file |
| Operator procedures | [`docs/factual-crawl-automation.md`](./docs/factual-crawl-automation.md), [`docs/distribution.md`](./docs/distribution.md), [`docs/m1-escalation-canary.md`](./docs/m1-escalation-canary.md) |
| Toolchain structure debt | [`docs/toolchain-maintainability.md`](./docs/toolchain-maintainability.md) |

Date-stamped counts below are **snapshots**. They fix direction and compare
progress; they do not redefine strategy when the index moves. Prefer growth,
coverage, promotion, telemetry, and scorecard outputs for live values.

Stable installs track the **`1.0.x`** release line. Development on `main` is
**`2.0.0-alpha.x`** (public Rust API breaks). See [`docs/install.md`](./docs/install.md).

## Mission

Make repository understanding reusable infrastructure.

Today, agents repeatedly discover repositories, fetch large amounts of loosely
structured material, infer the shape of each project, extract a small set of
facts, and then discard most of that work. Repeating this process across users,
agents, and research sessions wastes network, compute, tokens, time, and
attention while producing inconsistent answers.

dotrepo exists to replace that repeated interpretation with a shared,
refreshable, trust-aware semantic layer for software repositories.

The intended loop is:

```text
maintainer-authored repository truth
  -> normalized .repo record
  -> generated conventional repository surfaces
  -> public indexed profile
  -> cheap lookup, discovery, comparison, and agent use
  -> incremental refresh or maintainer correction
```

Repositories that have not adopted dotrepo enter the same system through an
autonomously generated overlay. Maintainers can later publish a native `.repo`
and replace that overlay as the authoritative source.

## Core thesis

Repository structure is necessary infrastructure, but repeatedly reasoning
about its accidental complexity is not valuable software-development work.

dotrepo attacks that problem from both directions:

1. **Authoring:** give maintainers one structured source of truth that can
   project standard repository documentation and compatibility surfaces without
   drift.
2. **Consumption:** give humans and agents a stable shape for repository facts,
   trust, freshness, evidence, and relationships without scraping the project
   from scratch.
3. **Indexing:** make the same normalized shape available for repositories that
   have not adopted dotrepo yet, using an autonomous and cost-disciplined
   extraction system.

The public index is not a manually curated directory. It is a continuously
maintained semantic cache for repository understanding.

## Non-negotiable principles

### Parse once, reuse many times

The cost of understanding a repository should be paid when the repository
changes, not every time somebody asks a question about it.

### Deterministic work comes first

Filesystem structure, manifests, machine-readable configuration, workflow
files, package metadata, and known conventions should be handled by parsers and
rules. LLMs should not spend tokens rediscovering facts that deterministic code
can establish.

### Intelligence escalates progressively

Model use is narrow, evidence-bounded, and confidence-driven. The system starts
with no-token methods, then uses the cheapest suitable model, then a second
opinion or stronger remote model only when unresolved value justifies it.

### Routine index generation has no human review step

The generated overlay index must scale without per-record human approval.
Humans define policy, improve the system, handle protocol disputes, and process
maintainer authority claims. They are not a normal tier in the factual overlay
pipeline.

Uncertainty is handled through deterministic gates, additional evidence,
progressive model escalation, explicit lower-confidence publication, or
abstention. It is not silently converted into a human review queue.

### Evidence outranks fluency

Generated prose is never accepted because it sounds plausible. Every published
fact must be grounded in repository material, source APIs, or maintainer-owned
metadata, with provenance preserved.

### Honest absence is a valid result

The system must distinguish missing, unresolved, conflicting, and confidently
absent fields. It should never fabricate completeness to improve coverage
metrics.

### Refresh is incremental

Unchanged repositories should be served from the existing semantic cache.
Refresh cost should scale with changed repository heads and stale records, not
with the total size of the index.

### Autonomous usefulness does not depend on adoption

The public overlay index must remain accurate, fresh, and useful for repositories
whose maintainers never adopt dotrepo or claim their records. Native adoption is
an authority and maintenance upgrade, not a prerequisite for coverage and not a
scaling strategy for the index.

### Marginal cost is a product constraint

The long-range target is coverage of all publicly processable repositories. At
that scale, unnecessary network reads, parsing passes, model calls, tokens, and
high-cost model selections become system-level defects. The default refresh path
for an unchanged repository should approach the cost of an identity and head
check. Every more expensive tier must justify its incremental expected value.

### Scale advances through measured cohorts

The index grows through bounded cohorts that preserve ecosystem diversity and
pass quality, freshness, reliability, throughput, and unit-cost gates. A larger
corpus is not progress if each record becomes more expensive, less fresh, or
less trustworthy.

### Native records win

Generated overlays bootstrap usefulness. Maintainer-owned native records are
the preferred long-term authority and must be able to supersede overlays without
erasing their provenance or history.

### The core schema stays small

The canonical factual shape should answer a compact set of high-value questions
reliably. Research synthesis, ranking, and ecosystem-specific extensions should
remain separable from the factual substrate.

## The system we are building

### 1. Author plane

The author plane makes repository maintenance simpler:

- bootstrap `.repo` from existing project materials
- validate one canonical repository record
- generate or manage supported README, security, contribution, ownership, and
  pull-request surfaces
- detect drift in CI
- expose stable local query and trust semantics to tools
- publish a native record that can become canonical in the public index

The author experience should converge on one short path:

```text
inspect existing overlay
  -> initialize or import .repo
  -> preview generated changes
  -> add managed surfaces and CI
  -> publish
  -> claim canonical authority
```

### 2. Autonomous index plane

The index plane discovers, extracts, verifies, scores, publishes, refreshes, and
promotes overlay records with almost no marginal human labor.

Its normal pipeline is:

```text
discover or schedule
  -> materialize bounded repository evidence
  -> deterministic parse and import
  -> verify and score every field
  -> escalate only unresolved fields
  -> re-verify model output against candidates and evidence
  -> publish, partially publish, or abstain
  -> validate the resulting index
  -> export and deploy
  -> record cost and quality telemetry
```

### 3. Research and consumption plane

The consumption plane lets humans and agents reuse the indexed understanding:

- exact repository lookup
- compact research profiles
- topic and capability discovery
- batch retrieval
- project comparison
- relationship traversal
- trust-aware field queries
- freshness and change inspection
- evidence inspection
- MCP, HTTP, CLI, and future SDK access

The website is the human-readable inspection and adoption surface for this
plane. The API and MCP tools are the primary agent surfaces.

## Autonomous intelligence ladder

Every repository and field should stop at the cheapest tier that can resolve it
honestly.

| Tier | Method | Expected use |
| --- | --- | --- |
| -1 | Cached identity, head, and evidence digests | Skip unchanged repositories and repeated work |
| 0 | Structured parsers, host APIs, manifests, known files | Most repository facts |
| 1 | Deterministic inference and cross-source reconciliation | Conventional build, test, docs, owners, and absence decisions |
| 2 | Cheap local model with narrow candidates and snippets | Ambiguous extraction that requires semantic judgment |
| 3 | Independent local second opinion | Low-confidence output or model disagreement |
| 4 | Strong remote model with strict budget and bounded context | Rare difficult tail |
| 5 | Partial publication or abstention | Evidence remains insufficient or contradictory |

There is no human adjudication tier for routine generated records.

Model responses must be post-checked against allowed candidates, evidence,
field constraints, and repository identity. A stronger model can improve a
decision; it cannot bypass validation.

Escalation is field-scoped and stops as soon as the remaining uncertainty is not
worth the additional cost. Provider routing should choose the least expensive
model that meets a calibrated quality target for the task class. Evidence,
candidate sets, negative results, and adjudication outcomes should be cached by
content digest so retries and related queries do not repay the same cost.

Work avoidance precedes escalation. In order: check repository identity and heads
before materializing source; prefer event-driven refresh signals with adaptive
polling keyed to churn, demand, staleness risk, and prior failures; cache
evidence and parser results by content digest; process changed files as deltas
rather than full re-imports; and batch, deduplicate, and coalesce host-API
conditional requests.

Model-decision cache keys must include the evidence digest, field, prompt and
policy versions, and model identity so reuse never hides a semantic change.
Archived, unavailable, and repeatedly failing repositories use explicit negative
caching with bounded backoff rather than consuming hot-loop capacity. Provider
and tier policies are benchmarked periodically because model price, latency, and
quality drift; a more expensive model is justified only by measured net
improvement after post-checks, not by capability claims. Local models are not
presumed free: accelerator time, energy, queueing, maintenance, and opportunity
cost belong in the same comparison as hosted-model pricing.

## Quality model

The index becomes trustworthy through systems, not optimism.

Required protections include:

- repository identity and path invariants
- structured parsing before prose interpretation
- field-level confidence and provenance
- explicit conflict and absence states
- evidence pointers for imported and inferred facts
- candidate-constrained model output
- independent checks for low-confidence adjudication
- command safety checks for build and test fields
- fixture packs and golden regression outputs
- canary repositories covering difficult ecosystems and layouts
- automatic quarantine or abstention on gate failures
- promotion only when all required fields are honestly resolved
- immutable telemetry for model tier, cost, tokens, and outcome
- randomized and risk-weighted audits that test the system without creating a
  per-record approval queue

Automation may promote eligible records to `verified`. It does not mint
maintainer authority, `reviewed`, or `canonical` status.

Additional platform protections required as the public surface and scheduled
writeback path carry real traffic:

- remote MCP lookup stays on allowlisted origins; snapshot path pointers cannot
  retarget host via protocol-relative or absolute URLs
- custom lookup bases keep an explicit private-IP / metadata denylist (including
  CGNAT and common cloud-metadata hosts), with no redirects and DNS pinning
- multi-file index writeback is multi-artifact durable (stage then swap, or
  roll back) so a failed evidence write cannot leave a new `record.toml` without
  its sibling artifacts
- hosted search and relations stay inside default request budgets so inventory
  growth cannot become unbounded Worker cost
- autonomous automation is **fail-closed**: unset enablement means no scheduled
  writeback; scheduled jobs honor the gate rather than skipping it

## Operating strategy

The roadmap advances through parallel workstreams. Maintainer adoption improves
authority, but autonomous scale, utility, and reliability proceed whether or not
adoption occurs.

| Workstream | Immediate objective | Success criterion or scale gate |
| --- | --- | --- |
| Platform integrity | Fail-closed automation, origin-bound remote fetches, multi-file writeback durability, Worker cost bounds | Scheduled index writeback cannot land without explicit enablement; remote clients cannot leave allowlisted origin via snapshot pointers; partial writeback cannot strand half-updated records; search/relations stay inside request budgets |
| Reliability | Keep repeated autonomous refresh and safe partial failure green | Strict telemetry SLOs pass for consecutive scheduled runs (fail the run, not warn-only, once baselines are stable) |
| Accuracy | Improve factual precision and honest abstention by intent and ecosystem | No intent or ecosystem cohort regresses beyond its error budget |
| Efficiency | Avoid unchanged work and route unresolved fields to the cheapest sufficient method | No-op, changed-record, and improved-record unit costs are measured and within budget |
| Throughput | Increase repositories processed per unit of wall time and compute | Cohort completes within latency, memory, rate-limit, and failure-isolation budgets |
| Utility | Answer representative lookup, execution, documentation, security, and discovery tasks | Intent-level hit-rate and exact-value gates pass |
| Authority and adoption | Make native ownership and canonical handoff easy | Conversion and retention improve; this workstream does not block overlay coverage |
| Distribution | Put the lookup surface in the default toolchains agents already use | Hosted and MCP traffic from non-operator consumers exists and grows; at least one external integration ships |
| Maintainability | Keep the reference implementation safe to change | Structural gates and focused tests remain healthy; oversized orchestration modules split before large features |

### Cohort-based expansion

After the current proof gate passes, growth proceeds in cohorts of roughly
50–100 repositories before moving to larger batches. Each cohort must report:

- exact-value accuracy, incorrect-assertion rate, and correct-abstention rate
- intent-level task success for overview, execution, documentation, security,
  ownership, comparison, and discovery
- parser and validation failures by ecosystem
- cache hit rate and unchanged-repository skip rate
- network bytes, files materialized, CPU and accelerator time, peak memory,
  storage/cache growth, export/serving work, and wall-clock time
- model calls, tokens, and cost by tier, provider, task class, and outcome
- cost for an unchanged repository, a changed repository, and a repository with
  at least one useful field improvement
- refresh latency, stale-record rate, quarantine rate, and promotion outcome

A cohort may advance, pause for deterministic fixes, or be excluded with an
explicit reason. Expansion never weakens validation or converts uncertainty into
unsupported facts.

### Demand and coverage strategy

Coverage selection combines ecosystem balance with demonstrated utility:

- exact-lookup misses and repeated scrape fallbacks
- repositories frequently encountered by agents or downstream consumers
- ecosystem, language, and repository-layout gaps
- dependency and relationship centrality
- benchmark and canary coverage needs
- maintainer interest, without making interest a prerequisite

Star bands and curated catalogs remain useful sampling tools, but they are not
the sole definition of demand.

**Demand signal stack (preferred order once volume exists):**

1. Hosted lookup misses — Worker emits `DOTREPO_LOOKUP_MISS` log lines on
   repository-not-found; aggregate with
   `scripts/aggregate_lookup_misses.py` (see
   [`docs/distribution.md`](./docs/distribution.md)).
2. Repeated scrape-fallback or agent-client telemetry from non-operator consumers
   (when an external integration reports it).
3. Package-registry download rankings (npm, PyPI, crates.io, Go module proxy) as
   the best *proxy* until miss volume is meaningful — still the primary cohort
   selector for early Milestone 4 growth.
4. Ecosystem/layout gaps, relationship centrality, benchmark/canary needs, then
   maintainer interest (never a prerequisite).

### Distribution strategy

Index quality creates the value; distribution captures it. Agents check dotrepo
first only when dotrepo is present in toolchains they already use, so
distribution is a workstream with its own gates, not a hoped-for side effect of
coverage. Operator checklist:
[`docs/distribution.md`](./docs/distribution.md); integration template:
[`docs/external-consumer-integration.md`](./docs/external-consumer-integration.md).

| Lever | Status | Next step |
| --- | --- | --- |
| Hosted public API + Worker | Live | Keep canaries green; search/relations cost bounds closed; refresh public snapshot with index for M4 growth |
| MCP server + registry packaging | Shipped (`1.0.x` stable; NDJSON framing in 1.0.1) | Keep listings current on each stable tag; origin-bind snapshot path fetches |
| crates.io toolchain | Shipped (seven packages; auto-publish on tag) | Point production consumers at stable `1.0.x` only |
| Efficiency benchmark page | Live (`/efficiency/`) | Refresh on deploy; use as the external pitch |
| pagedigest publisher | Live | Consume manifests in the crawler when non-GitHub sources appear |
| Lookup-miss telemetry | **Live emission deployed** (static published leaves + dynamic not-found) | Export on cadence (`lookup-miss-demand.yml` or `wrangler tail` → `export_lookup_miss_demand.py`); feed M4 selection |
| External non-operator consumer | In-repo reference landed | Sustained third-party traffic still open; see `examples/external-consumer/` |

### Shared direction with pagedigest

dotrepo and [pagedigest](https://pagedigest.org) (sibling protocol, pre-release)
are two layers of one goal: a cooperation layer that lets automated consumers
stop re-deriving what a publisher — or a trustworthy overlay — can declare once.

- **pagedigest** answers *"what changed?"* for any published URL set via a
  one-request `/.well-known/pagedigest.json` of monotonic revisions and optional
  digests.
- **dotrepo** answers *"what is this and how do I use it?"* for software
  repositories with a trust-aware semantic record.

pagedigest is the general-web form of dotrepo's tier −1 (skip unchanged work via
cached identity and digests); dotrepo is the deep-semantics form of what
pagedigest makes cheap to detect.

The projects stay independent, but point the same direction through three
concrete commitments:

1. **dotrepo publishes pagedigest.** Shipped: the static public export emits
   `/.well-known/pagedigest.json` alongside `v0/files.json`, the hosted site
   serves it live, and each deploy fetches the currently deployed manifest as
   a fail-closed baseline so per-URL revisions and `site_rev` advance
   monotonically. dotrepo is pagedigest's first production publisher, and each
   project gives the other a live proof.
2. **dotrepo consumes pagedigest.** Where non-GitHub evidence sources publish a
   manifest, the crawler's work-avoidance ladder should honor it before
   materializing anything, exactly as it honors cached heads today.
3. **One narrative, one audience.** Both projects pitch measured waste
   reduction to the same people — agent-framework authors and crawler
   operators — so positioning, benchmark publication, and directory listings
   are coordinated rather than duplicated.

Neither project gates the other's milestones; the shared direction is about
compounding distribution and proof, not coupling release trains.

### Audit strategy

There is no routine human approval tier. Instead, randomized and risk-weighted
audits examine samples by ecosystem, confidence, parser family, model tier,
promotion threshold, and surprising cost or completeness. Audit findings become
deterministic fixes, fixtures, calibration changes, or policy changes.

`scripts/audit_index_sample.py` now exists as the first, honest slice of this:
a read-only, local-only sampler that computes a heuristic risk weight per
record (confidence, missing build/test/security, promotion-threshold
proximity, surprising completeness vs. language-family peers) and draws a
seedable, risk-weighted random sample for a human or future automated pass to
inspect against `index/review-checklist.md`. It does not call any model or
adjudication provider, does not touch the network, and does not act on
findings. Cadence and conversion expectations are documented in
`docs/factual-crawl-automation.md` (Audit cadence). Lookup-miss demand from
the hosted Worker (`DOTREPO_LOOKUP_MISS` log lines +
`scripts/aggregate_lookup_misses.py`) feeds Milestone 4 cohort selection once
logs are exported.

### Platform integrity

M1 proved that autonomous generation can run without a human queue. Scale and
distribution still require the factory to be **safe by default** under token
compromise, hostile snapshot metadata, partial disk failure, and Worker load.

| Control | Status | Notes |
| --- | --- | --- |
| Scheduled autonomous enablement | **Closed** | Workflow requires `vars.INDEX_AUTOMATION_ENABLED == 'true'`; no env default to enabled; scheduled job honors enablement (no `--skip-automation-enabled-check`); script/env defaults fail closed; `.env.example` is `false` |
| Multi-file writeback | **Closed** | Crawler stages all `*.tmp` artifacts then renames; missing evidence cannot leave a lone new `record.toml` |
| MCP snapshot path binding | **Closed** | `resolve_same_origin_path_url` rejects `//`, schemes, and `..`; join result must keep base origin; unit tests cover host escape |
| Custom-base SSRF denylist | **Closed** | CGNAT `100.64.0.0/10`, documentation ranges, multicast/broadcast, IPv6 docs, cloud-metadata hostnames |
| Worker cost bounds | **Closed** | Search default limit 50 / max 200; reverse relations inventory scan only when ≤64 peers (prefer `relations.json`) |
| Writeback path (PR vs direct push) | **Closed** | Autonomous refresh opens a **draft PR** via `peter-evans/create-pull-request` (no direct `git push` to default branch); requires telemetry + validate-index |
| Telemetry SLO on schedule | **Closed** | Telemetry gate is **strict** (no `--warn-only`); failed gate fails the job and blocks draft PR open |
| CI / supply chain hygiene | **Closed** | `ci.yml` least-privilege `contents: read`; Dependabot for actions/cargo/npm; `mcp-publisher` **v1.7.9** pinned with SHA-256 verify in release + registry workflows |
| Dual CLI entrypoint | **Closed** | Shared `dotrepo_cli::run` / `dotrepo_cli::main`; workspace and install alias binaries are thin wrappers |

Platform integrity closed 2026-07-09 (including mcp-publisher pin and escalation module split).

Primary surfaces: `.github/workflows/index-autonomous-refresh.yml`,
`scripts/run_autonomous_index_batch.py`, `crates/dotrepo-mcp/src/{handlers,lookup}.rs`,
`crates/dotrepo-crawler/src/writeback.rs`, `cloudflare/hosted-query/`,
`.github/workflows/ci.yml`, `crates/dotrepo/src/main.rs`.

### Status discipline

`ROADMAP.md` owns stable direction, gates, and **execution order**. It is not a
changelog of every investigation: long-form operator narratives belong in
`CHANGELOG.md`, commit history, or `docs/*` procedures. Whole-project reviews
feed this file only as **gates, workstream rows, and Now/Next bullets** — not as
unstructured audit dumps.

Date-stamped counts are snapshots sourced from growth, coverage, promotion,
accuracy, and telemetry reports. Regenerated dashboards and artifacts own live
values so moving numbers do not silently redefine strategy. When a snapshot and
a script disagree, **trust the script**, then update the snapshot.

## Product milestones

Milestones are capability and quality gates, not release dates.

| Milestone | Goal | Status |
| --- | --- | --- |
| **M0** Working protocol and proof surface | Protocol + toolchain + public origin | **Complete** |
| **M1** Autonomous index factory | Generation/refresh without human queue | **Complete** (ops proof closed 2026-07-08) |
| **M2** Useful shared semantic cache | ≥500 high-signal profiles + lookup contracts | **Complete** |
| **M3** Research substrate | Search, compare, relations, optional synthesis | **Complete** (calibration ongoing) |
| **M4** Index at ecosystem scale | 1k→10k+ with cost/freshness gates | **Next scale phase** (after quality + demand volume) |
| **M5** Maintainer adoption flywheel | Native ownership without blocking overlays | **In parallel** (does not gate M4) |
| **M6** Open metadata standard | Independent producers/consumers | **Later** |

**v0.1 surfaces and M1–M3 capability gates are shipped. Platform integrity is
closed (2026-07-09).** Active work is **quality hardening** at current corpus
size, **distribution / demand capture** (miss emission live; non-operator
traffic still open), then gated cohort growth (M4). M5 stays parallel and lower
priority.

**Checked-in index snapshot (2026-07-09, post unit-test preference batch)** —
refresh with `scripts/render_index_growth_status.py` and
`dotrepo promotion-report`:

| Metric | Value |
| --- | ---: |
| Overlay records | 613 |
| `verified` / high confidence | 613 / 613 |
| `imported` / `inferred` | 0 / 0 |
| Record-level high-signal vs M2 target (500) | 613 (123%) |
| Promotion-eligible (re-score) | 613 / 613 |
| Verified-but-ineligible residual | 0 |
| Missing build / test / security | 221 / 226 / 420 |
| Quality-hardening queue | ~460 (refresh via scripts) |
| Intent scorecard within soft budgets | yes (execution missing 36.4% / budget 50%) |
| Stale or missing `generated_at` | 0 (0%) |
| Max refresh overdue | 0 days |
| Accepted maintainer claims | 1 |

*High-signal* here is the growth-status record-level aggregate (status ×
confidence), not a separate profile-export count. Milestone 2’s 500-profile
coverage gate is already complete; until M4 cohorts open, prioritize
**quality and utility hardening** and **demand capture**, not raw record growth.

### Active execution order

This section decides what runs **now**. Milestone sections below describe
destination gates; do not treat their “current status” lists as the work queue.

Priority when workstreams conflict:

```text
quality hardening (honest fields)
  -> distribution / demand capture
  -> M4 cohorts
  -> M5 adoption polish
```

Keep [platform integrity](#platform-integrity) green as a standing constraint
(not a gate that reopens before each feature).

#### Status at a glance

| Workstream | State | Blocker or next proof |
| --- | --- | --- |
| M1 factory + ops proof | **Done** (2026-07-08) | Keep green; do not reopen as a gate |
| Platform integrity | **Closed** (2026-07-09) | Standing keep-green only ([table](#platform-integrity)) |
| Intent/ecosystem scorecards | **Tooling shipped** | Soft budgets; harden only after stable |
| Execution-field completeness | **Hardening** | Missing build/test still `221`/`226` (many honest absences); recent batch improved command *quality* (Makefile `unit-test` preference) rather than vanity fills |
| Distribution / demand capture | **Emission + export path live** | Production Worker miss logs + `export_lookup_miss_demand.py` proven; **sustained non-operator traffic** still open |
| M4 first 1k profiles | **Ready when demand volume is useful** | 50–100 repo cohorts; prefer exported live misses (or registry proxies) + soft scorecards green |
| Maintainability hotspots | **Mostly closed** | Remaining: `crawler/github.rs` on next materialization feature; CLI test / facade import tests on next expansion |
| M5 adoption checkpoint (10 native / 5 handoffs) | **Parallel, lower priority** | Does not block overlays or M4 |

#### Now — quality + distribution (integrity closed)

Milestone 1 and platform integrity are **closed**. The factory is safe-by-default;
the remaining product risk is **honest field density** and **whether agents
check the public surface before scraping**.

0. **Platform integrity** — **closed** 2026-07-09 (see [Platform integrity](#platform-integrity)).
   No new integrity gate before quality/distribution work; regressions fail CI
   and scheduled automation as before.
1. **Work the quality-hardening queue** without inventing completeness.
   - Prioritize: `scripts/render_coverage_gaps.py` and growth-status “Next
     Quality Targets”.
   - Score: `scripts/render_intent_quality_scorecard.py` (soft budgets).
   - Expectation: many security gaps are honest absence; multi-ecosystem ties
     keep `build_candidates` / `test_candidates` (RFC 0020).
   - Residual missing build/test ~**221/226**. Prefer coverage-gap recrawl only
     where evidence can improve fields (guides, awesome-lists, and polyglot
     monorepos often stay honestly partial). Do not invent commands for empty
     `package.json` scripts or host-package CI noise.
   - **2026-07-09 quality batch:** prefer Makefile/justfile `unit-test` over
     composite `test`; prefer Makefile over justfile on dual task-script
     conflict; reject specialized Go CI coverdir/`-args` as `repo.test`.
     Recrawl: `jesseduffield/lazygit` → `go test ./... -short` (was CI
     coverdir / conflict-unresolved). Other gap candidates re-confirmed honest
     absence (no invent).
2. **Drain any new promotion headroom** after recrawls
   (`dotrepo promotion-report --apply`) — never bypass gates. Corpus is
   **613/613 verified** and **613/613 re-score eligible** (0 verified-but-
   ineligible residual).
3. **Keep audit conversion running.** Weekly sample
   (`scripts/audit_index_sample.py`); findings → fixture/parser/policy.
   Latest closed sample: `index/telemetry/audit-sample-20260708.md` +
   `audit-sample-20260708-disposition.md`.
4. **Hold release floors** during hardening (profile/high-signal + factual
   accuracy baselines). Prefer pinned stable **`1.0.x`** for production
   consumers; keep `main` on `2.0.0-alpha` without marketing alpha as drop-in stable.
5. **Distribution (parallel, outranks M5):** miss **emission and operator export
   path are live** (production Worker + `export_lookup_miss_demand.py` / weekly
   workflow). Remaining open: cadence with non-operator volume, one external
   consumer — see
   [In parallel — distribution](#in-parallel--distribution-outranks-m5-polish).

#### Standing maintainability (when touching hotspots)

Do not expand these modules without executing the documented splits first
([`docs/toolchain-maintainability.md`](./docs/toolchain-maintainability.md)):

| Hotspot | Plan |
| --- | --- |
| `dotrepo-crawler/src/github.rs` | Split on next materialization/API feature (client/HTTP, discovery, monorepo path selection) |
| `dotrepo-cli/src/tests.rs` | Split by command domain on next test-family expansion |
| `facade_tests/import_repository.rs` | Split on next import-fixture expansion |

#### Done recently (do not re-litigate)

Summaries only; detail lives in Git history and [`CHANGELOG.md`](./CHANGELOG.md).

- M1 closed; platform integrity closed (fail-closed automation, draft-PR landing,
  strict telemetry, MCP origin bind / SSRF denylist, multi-file writeback, Worker
  cost bounds, CI least-privilege, Dependabot, shared CLI entry, pinned
  `mcp-publisher`, `import/escalation/` + crawler `pipeline/` splits).
- Index quality: monorepo command inference waves (.NET / JS-TS / Python tox /
  Rust nested Cargo / workflow preference); corpus **613/613 verified** and
  promotion re-score eligible; ray re-promotion; pyenv host-package
  `build-essential` false-conflict fix; Makefile `unit-test` preference +
  Makefile-over-justfile resolution + Go CI coverdir rejection (lazygit).
- Distribution demand path: Worker emits `DOTREPO_LOOKUP_MISS` on published
  static leaves and dynamic not-found; **deployed to production** (restrict
  unknown leaves so bare `/summary` typos are not demand); weekly
  `lookup-miss-demand.yml` + `export_lookup_miss_demand.py`; live tail → export
  proof works (all four published leaves); external-consumer template landed;
  third-party traffic still open.
- Operator tooling: intent scorecard, coverage-gap, unit-cost, audit sample
  disposition, language-family classifier.

#### Next — Milestone 4 cohorts (after Now quality + distribution are healthy)

Platform integrity is closed. Prefer opening M4 cohorts only once lookup-miss
demand is **exported on cadence with non-trivial volume** (or package-registry
proxies stand in) and soft intent scorecards are not in regression.

1. Expand in gated **50–100** repository cohorts toward **1,000** maintained
   profiles.
2. Freshness: stale/missing `generated_at` ≤ **10%**; max refresh overdue ≤
   **7 days** (30-day stale threshold).
3. Each cohort must stay inside accuracy, abstention, throughput, resource,
   model-tier, and unit-cost budgets before batch size increases.
4. Select coverage from the [demand signal stack](#demand-and-coverage-strategy)
   and ecosystem gaps — not raw count alone.

#### In parallel — distribution (outranks M5 polish)

Checkpoint: **sustained hosted or MCP traffic from non-operator consumers**,
plus exported lookup-miss volume that can steer M4 selection.

**Shipped for demand capture:** production Worker miss emission on published
static leaves (`index.json` summary, `profile.json`, `trust.json`,
`relations.json`) and dynamic query/batch/compare/relations not-found paths;
operator export path (`docs/distribution.md`).

Still open:

1. Keep MCP registry listings and stable `1.0.x` install paths current (pin
   versions in docs and scaffolds; never treat crates.io alpha as production default).
2. Keep the efficiency page as the external pitch (tokens/bytes/requests saved).
3. **Cadence with live volume:** scheduled
   `.github/workflows/lookup-miss-demand.yml` (or
   `wrangler tail` / Logpush → `scripts/export_lookup_miss_demand.py`). Fixture
   path remains offline proof only.
4. Land **one** external consumer integration beyond the in-repo reference
   ([template](./docs/external-consumer-integration.md);
   [`examples/external-consumer/`](./examples/external-consumer/)).
   Live third-party non-operator traffic remains the open success signal.

Adoption follows consumers, not the reverse.

#### In parallel — Milestone 5 (authority, not coverage)

Target checkpoint: **10** maintainer-owned native records and **5** accepted
overlay-to-native handoffs, with adoption-funnel telemetry. Neither target gates
overlay usefulness or M4 growth.

#### Later

1k → 10k only after M4 gates hold; then broader public coverage through larger
cohorts. Start a minimal M6 conformance suite and independent-consumer test
before full ecosystem-scale completion so the protocol does not overfit the
reference implementation. Adjudication sidecars should refuse non-loopback bind
without an explicit opt-in before multi-tenant or shared-runner use expands.

### Reference toolchain maintainability

**Goal:** keep the shipped CLI/MCP/LSP/core codebase navigable as the index and
surfaces grow past v0.1.

**Status:** structural baseline delivered; standing gate with **open hotspot
work** listed under [Active execution order](#active-execution-order). Core
`import/`, `public/`, and `surfaces/` extraction, MCP tool/handler/dispatch
extraction, LSP protocol/state/diagnostics extraction, crawler command split,
contributor docs, and rustdoc on the three high-traffic repository APIs are
landed. Every file above the size threshold has a disposition in
[`docs/toolchain-maintainability.md`](./docs/toolchain-maintainability.md).

Delivered:

- domain-scoped facade integration tests under `dotrepo-core/src/facade_tests/`
- extracted MCP remote-lookup policy in `dotrepo-mcp/src/lookup.rs` (SSRF
  allowlist, no redirects, DNS pin — further origin-binding is platform integrity)
- contributor onboarding for the internal crawler crate
- rustdoc examples on high-traffic public APIs (`validate_repository`,
  `query_repository`, `trust_repository`)
- LSP and MCP handler module extraction without transport behavior changes
- documented split plans for remaining oversized orchestration modules

Open (on next expansion in these areas):

- `dotrepo-cli/src/tests.rs` — split by command domain when the next test family lands
- `facade_tests/import_repository.rs` — split on next import-fixture expansion

Done recently (maintainability hygiene):

- dual CLI entrypoints collapsed onto `dotrepo_cli::run` / `dotrepo_cli::main`
- Dependabot expanded to cargo + npm (`cloudflare/hosted-query`, `editors/vscode`)
- `import/escalation/` and `crawler/pipeline/` oversized-module splits executed

Exit criteria:

- no reference-toolchain source file exceeds ~1,500 lines without a documented
  split plan or retain rationale in
  [`docs/toolchain-maintainability.md`](./docs/toolchain-maintainability.md)
- facade tests can be exercised by domain without loading a multi-thousand-line
  test module
- new contributors can orient to crawler and server crates without reading entire
  `main.rs` entrypoints
- install-alias and workspace CLI cannot silently diverge on new subcommands
  (**met** via shared `dotrepo_cli::main`)

### Milestone 0: Working protocol and proof surface

**Status: complete.**

- versioned native and overlay schema
- CLI, MCP, LSP, and editor shell
- validation, query, trust, import, and managed generation
- public export, hosted query, freshness, and conflict contracts
- crawler, scoring, promotion, refresh planning, and escalation primitives
- live public origin and first maintainer handoff

The architectural thesis is proven. The remaining work is scale, quality,
utility, and adoption.

### Milestone 1: Autonomous index factory

**Goal:** make autonomous generation and refresh the default operating model.

**Implementation: complete. Operational proof: complete (2026-07-08).** Scheduled
planning, bounded adjudication, gate-passed writeback, retained telemetry,
strict multi-run proof gates, deploy coherence, unit-cost reporting (including
CPU/RSS), primary-tier live canary, and second-opinion live ladder canary are
in place. Strong-remote remains an optional third step when second opinion is
still low-confidence; it is wired and covered by the same env-driven provider
path. Day-to-day quality hardening is listed under
[Active execution order](#active-execution-order).

Deliver:

- scheduled discovery and head-aware refresh
- end-to-end autonomous writeback for gate-passed records
- production local and remote adjudication providers
- progressive escalation budgets and circuit breakers
- partial publication and abstention semantics
- per-field and per-tier telemetry
- automatic deploy coherence checks
- removal of routine draft-PR and per-record review dependencies

Exit criteria:

- zero routine human reviews per generated overlay
- strict autonomous telemetry gates pass for at least three consecutive
  scheduled runs
- stable autonomous writeback and refresh over repeated runs, including safe
  retention of valid partial progress when individual repositories fail
- deterministic resolution for at least 75% of processed repositories
- model adjudication required for less than 25% of processed repositories
- strong remote escalation required for no more than 5% of processed repositories
- a bounded adjudication canary or challenge cohort has exercised the
  cheap-model, second-opinion, and strong-model paths, so the escalation system
  is proven rather than merely untriggered
- no measurable quality regression as throughput increases
- unchanged, changed, and improved-record unit costs are separately observable

Implemented operational controls:

- scheduled discovery and head-aware refresh with budgeted primary,
  second-opinion, and stronger-remote adjudication sidecar paths
- retained multi-run telemetry and a strict proof gate covering worst-run quality
  and recent-window quality, tier-mix, adjudication-budget, and token-cost drift
- partial-progress safety: scheduled failures retain telemetry and valid
  writebacks before restoring the failed result, so early failures and live
  defects do not block history from accumulating
- head-aware planning bounds network inspection to a configured limit and rotates
  oldest and most-partial records first so they cannot monopolize batch slots
- autonomous refresh reprocesses lower-confidence checked-in records and newly
  discovered repositories through the same gate-passed writeback conveyor
- distinct writeback and promotion gates: `autonomous_writeback_eligible` may
  persist honestly partial overlays, while promotion to `verified` still requires
  `eligible_for_auto_publish` (see `docs/factual-crawl-automation.md`,
  `index/README.md`)
- recurring failures are classified into operational defect classes by ecosystem
  and tagged for fixture eligibility; eligible stubs are captured as offline
  `cargo test` regression fixtures that replay the overlay import path, with the
  checked-in baseline covering every named ecosystem the classifier emits
- automatic deploy-coherence checks compare the live Worker against the reviewed
  export's core contract files and a deterministic `v0/files.json` hash sample
  before post-deploy smoke checks; Cloudflare packaging runs on Node.js 22,
  matching the deployment gate's Wrangler runtime
- `public-surface-gate` runs lightweight CLI, MCP, LSP, and crawler contract
  tests alongside core import and public-export checks
- per-crawl wall time (`wallTimeMs`/`totalWallTimeMs`) and GitHub network
  request/byte counters (`HttpGitHubClient::network_usage`) are captured by
  `dotrepo-crawler crawl --json`; the autonomous batch orchestrator tags every
  outcome as `unchanged` (scheduler-skipped, zero cost by construction),
  `changed` (re-crawled, no status-ladder gain), or `improved` (re-crawled with
  a status-ladder gain), samples child CPU/RSS via
  `scripts/process_resources.py`, and
  `scripts/render_unit_cost_report.py` renders versioned per-category unit-cost
  summaries from the retained NDJSON history
- intent-level soft scorecards and coverage-gap prioritization
  (`scripts/render_intent_quality_scorecard.py`,
  `scripts/render_coverage_gaps.py`)
- risk-weighted audit sampling with documented conversion cadence
  (`scripts/audit_index_sample.py`,
  [`docs/factual-crawl-automation.md`](./docs/factual-crawl-automation.md))

**M1 exit criteria are met.** The factory is proven. Platform-integrity residual
work is **closed** (see [Platform integrity](#platform-integrity)) and does
**not** reopen M1. Open M4 cohorts only when demand signals are exported with
useful volume and soft scorecards are healthy — see
[Active execution order](#active-execution-order).

### Milestone 2: Useful shared semantic cache

**Goal:** make dotrepo a rational first lookup for common public repositories.

**Status: complete.** Profile, batch, query, cache, freshness, accuracy, and
efficiency contracts and their release gates are shipped. The corpus exceeds the
500-profile quantitative coverage gate (see the snapshot above).

Deliver:

- at least 500 high-signal repository profiles
- a compact public research-profile response
- build, test, license, languages, topics, docs, ownership, relations, trust,
  evidence, and record freshness in one predictable shape
- batch profile and batch field lookup
- cache validators and snapshot/delta-friendly consumption
- measured hit rate for representative agent research workloads
- published scrape-versus-dotrepo efficiency benchmark

Current status (shipped capabilities; release history in [`CHANGELOG.md`](./CHANGELOG.md)):

- compact per-repository `profile.json` responses in the static public export and
  via `dotrepo public profile`
- local/core and hosted batch profile and batch field lookup (`public
  batch-profiles`, `public batch-query`, and cacheable hosted GET routes), with
  shared cardinality limits enforced in core, the hosted Worker, and the
  reference HTTP server (50 repositories, 25 paths, 500 query results)
- static exports include `meta.validators` and `v0/files.json` for
  snapshot-level revalidation and selective refetch;
  `scripts/diff_public_export_files.py` turns two `v0/files.json` manifests into
  an added/changed/removed/refetch report for mirrors and agent caches
- `scripts/check_public_profile_coverage.py` measures profile count, high-signal
  count and ratio, missing quality signals, and conflict rate, with optional
  Milestone 2 gates; coverage validates response shape and path identity and
  excludes malformed files, enforced by the release gate through a versioned
  baseline with ratcheted build/test/docs/ownership/security/license floors
- `scripts/build_public_lookup_workload.py` emits a fixed four-intent research
  workload for every exported profile — 613 repositories × {overview, execution,
  documentation, security} = 2,452 tasks — without preselecting known-present
  fields, so efficiency reports do not depend on a hand-maintained fixture
- `scripts/measure_public_lookup_efficiency.py` produces deterministic aggregate
  and per-intent task/field hit-rate, payload-byte, request-reduction, and
  pass/fail gate reports; the release gate publishes the benchmark against a
  versioned baseline
- a cited exact-value accuracy sample (20 assertions across FastAPI, Tokio, and
  Gin) with versioned missing- and mismatch-rate ceilings; live parser failures
  it exposed are preserved as offline regression fixtures
- `scripts/plan_index_growth_tranche.py` turns grouped candidate catalogs into
  balanced, crawler-ready target files; the completed tranche-two expansion
  supplied the path to the 500-profile gate, and the seed-review workflows retain
  the catalog as the reproducible record
- `dotrepo promotion-report` separates total eligible records from promotion
  candidates, exposing deterministic auto-promotion headroom; the growth-status
  renderer separates advisory high-signal lift candidates from the broader
  quality-hardening queue
- `is_actionable_security_url()` recognizes GitHub security surfaces,
  coordinated-disclosure platforms, and first-party policy URLs while rejecting
  trackers and non-reporting channels; workflow command resolution prefers
  `ci.yml`/`main.yml` over platform-specific workflows at the same tier without
  weakening manifest-tier conflict honesty

Exit criteria:

- agents can answer known-repository questions without cloning or scraping in a
  large majority of benchmark cases
- repeated lookups reuse previously extracted understanding
- factual accuracy and abstention rates are measured, not anecdotal

Incremental refresh-cost proof is intentionally a Milestone 4 scale gate rather
than a condition of the completed lookup and coverage milestone.

### Milestone 3: Research substrate

**Goal:** support finding and comparing projects, not only looking up known
identities.

**Implementation status: complete.** Structured search, factual comparison,
static relationship traversal, optional bounded synthesis, hosted routes, and
their observable quality gates are shipped. Further ranking and synthesis work
is production calibration rather than a missing v0.1 surface.

Deliver:

- structured search over topics, capabilities, ecosystems, languages, and
  relations
- relevance ranking that remains separate from factual trust
- comparison responses for multiple repositories
- relationship traversal for alternatives, dependencies, predecessors, forks,
  and related projects
- optional bounded synthesis for architecture, entry points, key concepts, and
  agent guidance
- URL-addressable human research and comparison views

Exit criteria:

- an agent can move from a technology question to a candidate set and compact
  comparable profiles without scraping repository pages
- synthesis remains optional and cannot overwrite factual fields
- search quality, coverage, freshness, and cost are observable

Current status (shipped capabilities; production calibration is ongoing):

- `dotrepo public search`: structured profile search with text, language, topic,
  trust, and completeness filters grounded in `profile.json` semantics, with
  relevance ranking kept separate from factual trust
- `dotrepo public compare`: factual comparison preserving trust, completeness,
  shared language/topic, and side-by-side signal values without ranking or
  synthesis
- `dotrepo public relations`: relationship traversal for alternatives,
  dependencies, predecessors, forks, related projects, and references; reverse
  traversal emits semantic inverses and resolves profiles present in the index
- public export precomputes each repository's traversal as `relations.json`; the
  hosted Worker serves cacheable GET search, compare, and relations routes from
  the staged snapshot rather than performing request-time fanout. Text-only
  hosted search uses inventory-only matching and loads full `profile.json`
  snapshots only when completeness or trust filters require them
- `profile.json` can expose validated optional `synthesis.toml` guidance in a
  separate `synthesis` section, preserving factual fields as authority and
  failing export on invalid or fact-conflicting synthesis; crawler synthesis runs
  through an opt-in bounded HTTP sidecar over the validated in-memory manifest
  and capped excerpts, with factual build/test commands injected, schema-checked
  atomic writeback, and nonblocking failures
- deterministic relation discovery derives grounded repository links from GitHub
  snapshot facts and carries them through import and public export, covered by
  offline and facade regression tests
- quality instrumentation: `scripts/measure_public_search_quality.py` (discovery
  success, rank quality, inventory-only vs fanout task rates, freshness, gates)
  and `scripts/measure_public_factual_accuracy.py` (exact cited assertion
  accuracy with separate missing and mismatch rates under versioned ceilings,
  plus a per-ecosystem breakdown via the shared
  `scripts/language_family.py` classifier and explicit correct-abstention
  counts alongside incorrect- and missing-fact counts)
- intent soft scorecards
  (`scripts/render_intent_quality_scorecard.py`) complement release-gate
  accuracy samples for continuous calibration
- production-scale ranking calibration and sustained synthesis runs with measured
  quality and cost remain ongoing operational work

### Milestone 4: Index at ecosystem scale

**Goal:** grow from a useful service into broadly reusable infrastructure.

Deliver:

- thousands, then tens of thousands, of incrementally maintained profiles
- bounded cohort expansion with automatic quality, reliability, freshness,
  throughput, and cost gates
- head-aware and content-digest-aware work avoidance for unchanged repositories
- cached parser, evidence, candidate, and adjudication results with explicit
  invalidation semantics
- delta processing that limits materialization and parsing to relevant changes
- adaptive refresh scheduling based on observed churn, demand, freshness risk,
  and bounded backoff for unavailable repositories
- partitioned export and serving paths where needed
- bounded scheduling, concurrency, retries, backpressure, and failure isolation
- batched and conditional host-API access with request deduplication and
  coalescing
- calibrated model-provider routing based on task class, expected quality,
  latency, and cost
- explicit budgets for model calls, tokens, network, CPU, memory, and wall time
- capacity and cost forecasts that extrapolate measured cohort behavior to
  1,000, 10,000, and broader repository populations
- demand-driven discovery informed by lookup misses, scrape fallbacks,
  relationship centrality, and ecosystem gaps
- automated regression sampling across ecosystems
- randomized and risk-weighted system audits
- public operational status and coverage telemetry

Current status (pre-scale scaffolding; growth batches not yet opened at M4 size):

- checked-in corpus **613** overlays, all `verified` / high confidence; M2
  coverage gate already exceeded
- `scripts/render_index_growth_status.py` reports growth, tranche coverage,
  quality queues, language-family mix, freshness and overdue latency
- unit-cost and intent scorecards exist for cohort entry/exit reporting
  (`render_unit_cost_report.py`, `render_intent_quality_scorecard.py`,
  `render_coverage_gaps.py`)
- lookup-miss **emission is live on production Worker** (published static leaves
  + dynamic not-found); miss *volume* becomes a selection input only after logs
  are exported and aggregated (`export_lookup_miss_demand.py` /
  `aggregate_lookup_misses.py`); cadence workflow exists; non-operator traffic
  still open
- refresh cost and stale-record rate are first-class metrics from generated
  artifacts, not inferred from profile count alone
- release-gate baselines ratchet profile volume and high-signal floors so growth
  does not silently regress lookup completeness or factual accuracy
- first quantitative scale checkpoint: **1,000** maintained profiles, stale or
  missing `generated_at` ≤ **10%**, max refresh overdue ≤ **7 days**, published
  refresh-cost baseline
- path to 1,000: gated **50–100** repository cohorts; larger batches unlock only
  by passing cohort gates, not by calendar time
- **entry preconditions:** platform integrity **closed**; regularly exported
  lookup-miss demand with useful volume (or interim package-registry proxies);
  soft intent scorecards not in regression

Exit criteria:

- common repository lookups have a high hit rate across major ecosystems
- intent- and ecosystem-level error budgets remain satisfied as coverage grows
- refresh latency and stale-record rates meet published targets
- measured refresh work tracks changed or stale repositories rather than total
  index coverage
- unchanged repositories normally stop after cached identity/head validation,
  without source materialization or model calls
- model tiers and providers are selected by calibrated task-level quality and
  expected value, with strong remote models remaining a rare tail
- throughput rises while per-record network, CPU, memory, model, and wall-time
  budgets remain bounded
- cost per maintained record declines as coverage grows
- measured cohort costs support a credible total-resource forecast for the next
  scale step before that step begins
- throughput can increase without adding proportional human labor
- these scale gates hold independently of maintainer adoption or claim volume

### Milestone 5: Maintainer adoption flywheel

**Goal:** make maintainer-owned truth easy to adopt without making autonomous
coverage depend on adoption.

Deliver:

- clear "inspect my record" and "adopt dotrepo" paths
- one-command bootstrap from an existing overlay or repository
- excellent preview, managed-surface, and CI onboarding
- low-friction claim and canonical handoff
- visible native-record benefits for maintainers and downstream tools
- integrations that make `.repo` useful even before public indexing
- adoption-funnel telemetry from record inspection through durable native
  maintenance

Current status:

- `dotrepo adopt-overlay <record.toml>` bootstraps a native draft `.repo` from a
  public overlay record while clearing overlay authority fields and requiring
  maintainer review before canonical claims
- `dotrepo claim-from-native --index-root <index>` scaffolds the corresponding
  draft maintainer claim from a reviewed native `.repo`, deriving target
  identity and canonical URL from `repo.homepage`
- `dotrepo claim-submit-native --index-root <index> --claim-id <id>` appends
  the submitted event using the native record identity instead of a hand-typed
  claim path
- `dotrepo claim-accept-native --index-root <index> --claim-id <id>` appends
  the accepted handoff event with claim, canonical `.repo`, and mirror paths
  derived from the native record
- `dotrepo adoption-status [--json]` summarizes native-record readiness for
  validation, claim identity, CI onboarding, and managed-surface drift
- MCP exposes the same readiness contract as `dotrepo.adoption_status`, sharing
  the core report used by the CLI; RFC 0006 now documents `dotrepo.adoption_status`
  and `dotrepo.lookup`, and MCP root resolution accepts not-yet-created repository
  directories for validate/import flows through `resolve_workspace_repository_root`
- LSP diagnostics surface native adoption hints for claim-ready `repo.homepage`
  and the starter CI workflow while maintainers edit `.repo`, including quick
  fixes for adding the homepage placeholder and creating the workflow; adoption
  CI readiness now comes from `adoption_status_repository`, and
  `validate_repository` diagnostics for other root manifests (for example
  coexisting `record.toml`) are surfaced while editing `.repo`
- the first adoption checkpoint is 10 maintainer-owned native records and 5
  accepted overlay-to-native handoffs, backed by published adoption telemetry

Exit criteria:

- native adoption grows without manual operator outreach for every repository
- claims and handoffs are routine, safe, and auditable
- maintainers correct the public substrate by maintaining their own source of
  truth
- downstream consumers prefer native records when available
- unclaimed repositories remain independently useful, fresh, and honestly
  represented by autonomous overlays

### Milestone 6: Open repository metadata standard

**Goal:** make repository metadata portable infrastructure rather than a single
implementation's feature.

Deliver:

- stable specification and compatibility suites
- an early minimal conformance suite exercised outside the reference CLI
- independent producers and consumers
- SDKs and integrations for major agent and development platforms
- governance for schema evolution and trust vocabulary
- interoperable indexes and mirrors

Exit criteria:

- tools can consume `.repo` without depending on the reference implementation
- multiple systems produce compatible native records and projections
- the protocol survives implementation and hosting diversity
- at least one independent consumer validates compatibility before the reference
  implementation reaches full ecosystem scale

## Research profile direction

The current manifest should remain the factual source. The public research
profile should be a compact, derived response optimized for repeated discovery
and comparison.

It should include:

- canonical identity and project purpose
- language and ecosystem signals
- license, visibility, and project status
- exact build and test guidance where established
- documentation and architecture entry points
- maintainers and security channels
- topics and repository relationships
- factual completeness indicators
- selected record, authority, confidence, and provenance
- record and snapshot freshness
- conflicts, evidence, and explicit unknowns
- optional bounded synthesis in a clearly separate section

Agents should not need to know a collection of dot paths before retrieving the
normal research shape. Dot-path query remains useful for narrow access after
profile retrieval.

## Website direction

The public site should demonstrate and inspect the shared substrate rather than
becoming a generic project directory.

Its primary tasks should be:

1. Look up a repository.
2. Research a technology or capability.
3. Compare projects.
4. Inspect trust, freshness, evidence, and conflicts.
5. Adopt dotrepo for a repository.
6. Integrate dotrepo into an agent or tool.

Human pages should render the same public contracts used by agents. Raw JSON
remains canonical and directly accessible.

## Metrics that matter

### Index quality

- field-level precision and abstention rate
- incorrect-assertion, missing-fact, and correct-abstention rates by user intent
  and ecosystem (factual-accuracy workload +
  `render_intent_quality_scorecard.py`)
- verified / high-signal counts and ratios (`render_index_growth_status.py`)
- missing build/test/security and honest execution abstentions
  (`render_coverage_gaps.py`)
- unresolved and conflicting field rates
- stale-record rate and refresh latency
- regression failures by parser, ecosystem, and model tier
- audit findings by risk class and resulting fixture or policy action

### Reliability

- strict-gate pass streak and worst-run regression
- batch success, partial-writeback, quarantine, and retry rates
- stale backlog, maximum overdue latency, and backlog drain time
- provider, host-API, and infrastructure failure rates
- recovery time without loss of valid completed work
- autonomous enablement fail-closed (scheduled run skipped when unset/disabled)
- multi-file writeback failure rate and half-updated record detections
  (`validate-index` post-batch must stay green without manual repair)
- Worker request budgets: default search limit hits; relations served from
  precomputed snapshots vs inventory fanout rate

### Efficiency

- deterministic resolution rate
- unchanged-repository skip rate and cache hit rate
- adjudication rate by tier
- strong-model escalation rate
- avoided model calls and avoided source materialization
- tokens and model cost per improved record
- network bytes, files materialized, CPU time, peak memory, and wall time per
  unchanged, changed, and improved record
- accelerator time, cache/storage growth, and export/serving cost
- repositories processed per wall-clock hour and per compute unit
- compute cost per maintained profile per month
- marginal cost as cohort and corpus size increase
- total operating cost and projected cost at the next scale checkpoint

### Utility

- exact-lookup hit rate
- research-discovery success rate
- task success by overview, execution, documentation, security, ownership,
  comparison, and discovery intent
- batch requests served
- lookup misses and scrape fallbacks that become future coverage demand
- agent tasks completed without repository scraping
- bytes, tokens, requests, latency, and error reduction versus scrape-from-scratch
- non-operator hosted/MCP traffic share (distribution checkpoint)

### Platform integrity

- MCP remote fetch origin violations (should stay zero; cover `//` and absolute
  snapshot path cases in regression tests)
- custom-base SSRF denylist coverage for CGNAT and cloud-metadata hosts
- scheduled automation skips when enablement is unset (expected) vs unexpected runs
- dual-CLI dispatch drift (subcommand parity check in release-version or CI gate)

### Adoption

- native `.repo` repositories
- successful overlay-to-native handoffs
- conversion from record view to adoption start, native record, CI enablement,
  claim, canonical handoff, and 90-day retention
- active MCP, API, CLI, and SDK consumers
- independent protocol producers and consumers

Raw repository count is a capacity metric, not the primary success metric.
Adoption is an authority metric, not a prerequisite for overlay utility. Scale is
successful only when accuracy, honest abstention, freshness, reliability,
throughput, and marginal cost remain inside their budgets.

## Explicit non-goals

- manually reviewing every generated index record
- using LLMs for facts deterministic parsers can establish
- hiding uncertainty to make the index look complete
- allowing synthesis to overwrite factual metadata
- becoming a general code-search engine or package registry
- adding public mutation before provenance and authority remain enforceable
- expanding the core schema for every research or ecosystem-specific need
- optimizing raw repository count at the expense of accuracy or refreshability
- treating maintainer adoption as a prerequisite for public-index usefulness
- spending model or compute budget merely to avoid publishing an honest unknown
- scaling cohort size while platform-integrity controls remain fail-open
- treating crates.io / `main` prereleases as the production install default

## Strategic test

The roadmap is succeeding when this behavior becomes normal:

```text
agent receives a repository or technology question
  -> checks dotrepo first
  -> receives a small, fresh, trust-aware profile or candidate set
     whether the source is a native record or an autonomous overlay
  -> retrieves only the additional source material the task truly requires
  -> reuses the same maintained understanding on future requests
```

At that point, scraping an entire repository to recover basic project facts is
the fallback, not the default. Index growth can continue toward all publicly
processable repositories without waiting for maintainer participation, while
native adoption independently improves authority and long-term maintenance.

## Related documents

- [`README.md`](./README.md) — shipped capabilities and project entrypoint
- [`CHANGELOG.md`](./CHANGELOG.md) — release history
- [`AGENTS.md`](./AGENTS.md) — agent-facing repo commands and architecture rules
- [`docs/install.md`](./docs/install.md) — stable `1.0.x` vs `2.0.0-alpha` install lines
- [`docs/factual-crawl-automation.md`](./docs/factual-crawl-automation.md) — crawler, telemetry, audit cadence
- [`docs/m1-escalation-canary.md`](./docs/m1-escalation-canary.md) — second-opinion / strong-remote live proof
- [`docs/distribution.md`](./docs/distribution.md) — distribution checklist and demand signals
- [`docs/external-consumer-integration.md`](./docs/external-consumer-integration.md) — non-operator integration template
- [`docs/public-surface.md`](./docs/public-surface.md) — hosted public contract
- [`docs/maintainer-happy-path.md`](./docs/maintainer-happy-path.md) — native adoption workflow
- [`docs/trust-model.md`](./docs/trust-model.md) — authority, provenance, and confidence semantics
- [`docs/toolchain-maintainability.md`](./docs/toolchain-maintainability.md) — structure gates and oversized-file plans
- [`index/README.md`](./index/README.md) — index layout and automation policy
- [`crates/dotrepo-crawler/README.md`](./crates/dotrepo-crawler/README.md) — internal autonomous index crate
- [pagedigest](https://pagedigest.org) — sibling change-detection protocol; see
  [Shared direction with pagedigest](#shared-direction-with-pagedigest)
