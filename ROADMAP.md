# dotrepo Roadmap

This document defines both the long-range direction and the active execution
order for dotrepo. Shipped capabilities live in [`README.md`](./README.md);
release history lives in [`CHANGELOG.md`](./CHANGELOG.md).

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

## Operating strategy

The roadmap advances through parallel workstreams. Maintainer adoption improves
authority, but autonomous scale, utility, and reliability proceed whether or not
adoption occurs.

| Workstream | Immediate objective | Success criterion or scale gate |
| --- | --- | --- |
| Reliability | Prove repeated autonomous refresh and safe partial failure | Strict telemetry SLOs pass for consecutive scheduled runs |
| Accuracy | Improve factual precision and honest abstention by intent and ecosystem | No intent or ecosystem cohort regresses beyond its error budget |
| Efficiency | Avoid unchanged work and route unresolved fields to the cheapest sufficient method | No-op, changed-record, and improved-record unit costs are measured and within budget |
| Throughput | Increase repositories processed per unit of wall time and compute | Cohort completes within latency, memory, rate-limit, and failure-isolation budgets |
| Utility | Answer representative lookup, execution, documentation, security, and discovery tasks | Intent-level hit-rate and exact-value gates pass |
| Authority and adoption | Make native ownership and canonical handoff easy | Conversion and retention improve; this workstream does not block overlay coverage |
| Maintainability | Keep the reference implementation safe to change | Structural gates and focused tests remain healthy |

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
findings — the fixture/fix/calibration/policy conversion loop is still future
work once this tool has actually run and produced findings.

### Status discipline

`ROADMAP.md` owns stable direction, gates, and execution order. Date-stamped
counts are snapshots sourced from the repository's growth, coverage, promotion,
accuracy, and telemetry reports. Operational dashboards and generated artifacts
own live values so changing counts do not silently redefine strategy.

## Product milestones

Milestones are capability and quality gates, not release dates.

**v0.1 implementation status: complete.** The protocol and native/overlay record
contracts, Rust CLI/MCP/LSP reference toolchain, autonomous index factory,
public lookup/search/compare/relations surfaces, growth tooling, and M1–M3 gate
implementations are shipped. Milestone 1's strict multi-run operational proof is
still pending; Milestones 2 and 3 have passed their shipped-surface and coverage
gates. Remaining roadmap work is production proof, operational scale, continuous
quality calibration, and maintainer uptake.

**Checked-in index snapshot (2026-06-29):** 613 overlay records, 516 high-signal
public profiles (103.2% of the Milestone 2 target), 514 `verified` records, and 1
accepted maintainer claim. The 500-profile Milestone 2 coverage gate is
complete. *High-signal* here is profile-level coverage (a quality-signal
aggregate over each exported `profile.json`), distinct from the 514 record-level
`verified` statuses; a few profiles are high-signal before their record reaches
`verified`. The next priority is quality hardening across the larger index, not
raw record growth. Live counts come from the generated growth, coverage,
promotion, and telemetry artifacts and refresh with each run; this snapshot fixes
direction, not numbers.

### Active execution order

This is the operative ordering across milestones. Detailed milestone sections
describe the destination; this section decides what runs now.

**Now — prove, measure, and harden the autonomous factory (Milestone 1).**

1. **Done.** `check_autonomous_telemetry_gate.py` passes without `--warn-only`
   at three consecutive scheduled-run checkpoints. This required two fixes
   surfaced by running real scheduled batches: the worst-run rate window is
   now bounded to the last `WORST_RUN_WINDOW_SIZE` (10) runs
   (`scripts/run_autonomous_index_batch.py`) so a single historic failure
   cannot pin the gate red forever while still failing the gate for the next
   10 runs after any real bad run; and the crawler no longer silently
   downgrades an already-`verified` record on routine refresh
   (`guard_against_unjustified_downgrade` in
   `crates/dotrepo-core/src/promotion.rs`, wired into
   `crates/dotrepo-crawler/src/pipeline.rs`) — previously a refresh that only
   gained a new, imperfectly-scored field (not a real regression) could drop
   `verified`/`high` back to `inferred`/`medium`.
2. **Partially done.** A first bounded canary confirmed the deterministic-to-
   model escalation path fires correctly end to end: real GitHub repositories
   almost never contain genuinely conflicting build/test candidates (of
   ~145 repositories refreshed while proving the strict telemetry gate,
   zero triggered model escalation), so a throwaway public GitHub repository
   was deliberately engineered with two same-tier conflicting build-command
   workflows, crawled with `dotrepo-crawler crawl` against the live GitHub
   API and the local OpenRouter adjudication sidecar
   (`scripts/adjudication_openrouter_sidecar.py`), and produced exactly the
   expected result: `deterministicRequests: 1`, `modelCalls: 1`,
   `modelResolved: 1`, `tokensUsed: 300`, resolving `repo.build` to the
   manifest-tier candidate with the conflict honestly recorded in
   `evidence.md`. This proves the primary-tier escalation path, not merely
   that it exists unused. The second-opinion and strong-remote-escalation
   tiers remain unexercised by a live model call; a broader challenge cohort
   covering those tiers is still open work.
3. Add versioned unit-cost reports for unchanged, changed, and usefully improved
   records — network, CPU, memory, wall time, model calls, tokens, and provider
   cost — with cache hits and avoided work as first-class outcomes. Wall time,
   network request/byte counting, and unchanged/changed/improved
   classification are implemented (`crates/dotrepo-crawler/src/github.rs`,
   `scripts/run_autonomous_index_batch.py`,
   `scripts/render_unit_cost_report.py`); process-level CPU time and peak
   memory remain a documented gap (no `libc`/`getrusage` dependency has been
   added yet).
4. Establish intent- and ecosystem-level quality scorecards with explicit error
   budgets for incorrect facts, missing facts, and correct abstention.
5. **In progress; one deterministic fix landed.** Investigating individual
   missing-signal records (rather than blindly re-crawling) found that
   routine refresh alone never moves the missing-build/test/security
   ceilings, because `SUPPLEMENTAL_ROOT_FILES`
   (`crates/dotrepo-crawler/src/github.rs`) only ever fetched
   `Cargo.toml`/`package.json`/`pyproject.toml`/`go.mod` from GitHub, even
   though `dotrepo-core`'s import parser has had working support for Maven,
   Gradle, Composer, Mix, Rebar, CMake presets, Makefile, justfile,
   Rakefile, and setup.py/setup.cfg all along — those parsers were simply
   never fed a file to parse. Fixed by fetching every ecosystem file the
   parser already supports (plus a new root `.csproj` directory listing
   for arbitrarily-named .NET project files). Re-crawling the 23 known
   non-verified records missing build/test after the fix moved
   verified 575→580, missing build 278→275, missing test 285→279, with
   zero status/confidence regressions. `owners.security_contact` (408
   missing) is largely honest absence (most flagged repos genuinely lack a
   `SECURITY.md`) rather than a parser gap, and remains open for further
   sampling.
6. Process the current promotion headroom through the normal validation path;
   consult `promotion-report` and the growth-status renderer for live candidate
   counts.
7. Begin randomized and risk-weighted system audits and convert every actionable
   result into a fixture, deterministic fix, calibration change, or policy update.
   `scripts/audit_index_sample.py` now produces the read-only, risk-weighted
   sample (see "Audit strategy" above); actually running it repeatedly and
   converting its findings into fixtures, fixes, calibration changes, or policy
   updates remains open.
8. Preserve the gated profile floors (valid profiles, high-signal ratio, zero
   malformed) and the current factual-accuracy floors during hardening; the
   release-gate baseline owns the pinned thresholds.

**Next — begin the first ecosystem-scale cohorts (Milestone 4).**

1. Expand in gated 50–100 repository cohorts until the index reaches 1,000
   incrementally maintained profiles.
2. Keep stale or missing `generated_at` records at or below 10% and maximum
   refresh overdue latency at or below 7 days, using the existing 30-day stale
   threshold.
3. Require each cohort to remain inside accuracy, abstention, throughput,
   resource, model-tier, and unit-cost budgets before increasing batch size.
4. Select coverage from demand signals and ecosystem gaps, not raw count alone.

**In parallel — improve maintainer authority and adoption (Milestone 5).**
Publish adoption-funnel telemetry and reach an initial checkpoint of 10
maintainer-owned native records and 5 accepted overlay-to-native handoffs. These
outcomes improve authority and durability, but neither target gates autonomous
index growth or the usefulness of unclaimed overlay records.

**Later — broaden scale, adoption, and interoperability.** Expand from 1,000 to
10,000 profiles only after the first scale gates hold, then advance toward all
publicly processable repositories through successively larger gated cohorts.
Deepen the maintainer flywheel in parallel. Begin a minimal Milestone 6
conformance suite and independent-consumer test before full ecosystem-scale
completion so the protocol does not overfit the reference implementation.

### Reference toolchain maintainability

**Goal:** keep the shipped CLI/MCP/LSP/core codebase navigable as the index and
surfaces grow past v0.1.

**Status:** in progress. The first structural splits, contributor docs, and
rustdoc examples for the three high-traffic repository APIs are landed. LSP/MCP
extraction and documented dispositions for the remaining oversized source files
remain open.

Deliver:

- domain-scoped facade integration tests under `dotrepo-core/src/facade_tests/`
- extracted MCP remote-lookup policy in `dotrepo-mcp/src/lookup.rs`
- contributor onboarding for the internal crawler crate
- rustdoc examples on high-traffic public APIs (`validate_repository`,
  `query_repository`, `trust_repository`)
- LSP and remaining MCP handler module extraction without transport behavior
  changes
- a documented split plan or explicit retain rationale for every
  reference-toolchain source file above the size threshold

Exit criteria:

- no reference-toolchain source file exceeds ~1,500 lines without a documented
  split plan or retain rationale in
  [`docs/toolchain-maintainability.md`](./docs/toolchain-maintainability.md)
- facade tests can be exercised by domain without loading the full 5k-line module
- new contributors can orient to crawler and server crates without reading entire
  `main.rs` entrypoints

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

**Core implementation status: complete; operational proof status: partially
demonstrated.** Scheduled planning, bounded adjudication, gate-passed
writeback, retained telemetry, proof gates, and deploy coherence are
implemented. The retained multi-run proof gate now passes in strict mode
(three consecutive scheduled-run checkpoints, see the active execution order
above) and versioned unit-cost reports are in place for wall time, network,
tokens, and model calls (CPU/memory remain a documented gap). A first bounded
adjudication canary exercised and proved the primary-tier (cheap-model)
escalation path with a real live model call (see the active execution order
above); the second-opinion and strong-remote-escalation tiers remain
unexercised by a live model call, so the milestone is not yet complete.

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
  a status-ladder gain), and `scripts/render_unit_cost_report.py` renders
  versioned per-category unit-cost summaries from the retained NDJSON history

Current Milestone 1 work queue (subordinate to the cross-milestone execution
order above):

1. Work down the quality-hardening queue through bounded autonomous batches and
   targeted re-crawls; ratchet its missing build/test/security ceilings (reported
   by the growth-status renderer) downward. The index currently has no stale or
   overdue records.
2. Convert the discovery-wave failure corpus into deterministic parser fixes and
   checked-in regression fixtures, beginning with noisy README relation targets
   that fail repository-identity validation.
3. Improve lookup completeness, especially the security and execution intents,
   without weakening honest abstention (workload volume comes from the generated
   lookup workload).
4. Continue bounded autonomous discovery only to preserve ecosystem balance or
   replace records lost to staleness, archive state, or validation failures.

Milestone 1 is complete when autonomous runs are repeatable, bounded, directly
publish gate-passed records, improve quality without a human queue, and expose
enough retained telemetry to support cost and regression claims.

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
  plus a per-ecosystem breakdown reusing the growth-status renderer's language
  family classifier and an explicit correct-abstention count/rate alongside
  incorrect- and missing-fact counts)
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

Current status:

- `scripts/render_index_growth_status.py` reports record growth, tranche
  coverage, quality queues, language-family coverage, stale-or-missing
  `generated_at` rate, maximum record age, overdue refresh latency, and optional
  operational gates for tranche coverage, missing targets, lower-confidence
  backlog, stale freshness backlog, and maximum refresh overdue days.
- refresh cost and stale-record rate are tracked as first-class Milestone 4
  metrics from the generated status and coverage artifacts rather than inferred
  from profile count alone
- release-gate baselines ratchet profile volume and high-signal floors so index
  growth does not silently regress lookup completeness or factual accuracy
- the first quantitative scale checkpoint is 1,000 maintained profiles with a
  stale-or-missing record rate at or below 10%, maximum refresh overdue latency
  at or below 7 days, and a published refresh-cost baseline
- the 1,000-profile checkpoint will be reached through 50–100 repository cohorts;
  larger batch sizes are unlocked by passing cohort gates rather than by elapsed
  time or operator preference

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
  and ecosystem
- verified profile count and percentage
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

- [`README.md`](./README.md) - shipped capabilities and project entrypoint
- [`CHANGELOG.md`](./CHANGELOG.md) - release history
- [`docs/factual-crawl-automation.md`](./docs/factual-crawl-automation.md) - crawler and escalation design
- [`docs/public-surface.md`](./docs/public-surface.md) - hosted public contract
- [`docs/maintainer-happy-path.md`](./docs/maintainer-happy-path.md) - native adoption workflow
- [`docs/trust-model.md`](./docs/trust-model.md) - authority, provenance, and confidence semantics
- [`docs/toolchain-maintainability.md`](./docs/toolchain-maintainability.md) - reference toolchain structure and refactor gates
- [`crates/dotrepo-crawler/README.md`](./crates/dotrepo-crawler/README.md) - internal autonomous index crate orientation
