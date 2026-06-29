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

Automation may promote eligible records to `verified`. It does not mint
maintainer authority, `reviewed`, or `canonical` status.

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
complete. Five bounded discovery waves expanded the corpus across
non-overlapping GitHub star bands; the next priority is quality hardening across
the larger index rather than raw record growth.

### Active execution order

This is the operative ordering across milestones. Detailed milestone sections
describe the destination; this section decides what runs now.

**Now — prove and harden the autonomous factory (Milestone 1).**

1. Pass `check_autonomous_telemetry_gate.py` without `--warn-only`. In the
   2026-06-29 snapshot, retained history has 7 runs and 75 processed
   repositories, but still fails the worst-run failure-rate and recent
   failure-drift checks.
2. Work the snapshot's 501-record quality queue through bounded batches and
   deterministic fixes. Ratchet its missing-signal ceilings of 285 build, 290
   test, and 408 security downward without regressing the factual-accuracy gates.
3. Process the current promotion headroom through the normal validation path.
   `promotion-report` currently reports 61 promotion candidates, while the
   narrower growth-status heuristic reports 19 high-signal lift candidates.
4. Preserve at least 613 valid public profiles, 516 high-signal profiles, zero
   malformed profiles, and the current factual-accuracy floors during hardening.

**Next — begin the first ecosystem-scale and adoption checkpoints (Milestones 4
and 5).**

1. Grow to 1,000 incrementally maintained profiles while keeping stale or
   missing `generated_at` records at or below 10% and maximum refresh overdue
   latency at or below 7 days, using the existing 30-day stale threshold.
2. Publish a versioned baseline for refresh work, network/model cost, and cost
   per maintained profile before claiming that incremental refresh becomes
   cheaper at scale.
3. Publish adoption telemetry, then reach an initial checkpoint of 10
   maintainer-owned native records and 5 accepted overlay-to-native handoffs.

**Later — broaden scale, adoption, and interoperability.** Expand from 1,000 to
10,000 profiles only after the first scale gates hold, deepen the maintainer
flywheel, and begin Milestone 6 compatibility work once independent producers or
consumers are ready to test against the protocol.

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

**Implementation status: complete; operational proof status: pending.** Scheduled
planning, bounded adjudication, gate-passed writeback, retained telemetry, proof
gates, and deploy coherence are implemented. The retained multi-run proof gate
must pass in strict mode before the milestone itself is complete.

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
- stable autonomous writeback and refresh over repeated runs
- deterministic resolution for the large majority of repositories
- model adjudication required for less than 25% of processed repositories
- strong remote escalation required only for a small tail
- no measurable quality regression as throughput increases

Implemented operational controls:

- scheduled operation now has budgeted primary, second-opinion, and stronger
  remote adjudication sidecar paths, but repeated runs still need to prove the
  tier mix stays within the intended cheap-primary/rare-tail shape
- retained multi-run telemetry and a proof gate now exist, including worst-run
  quality checks plus recent-window quality, tier-mix, adjudication-budget, and
  token-cost drift checks; repeated scheduled runs still need to satisfy that
  gate to demonstrate stable cost, resolution, promotion, and regression rates
- automatic deploy coherence checks now compare the live Worker against the
  reviewed export's core contract files and a deterministic public
  `v0/files.json` hash sample before post-deploy smoke checks pass
- Cloudflare packaging and smoke paths run on Node.js 22 in CI, matching the
  supported Wrangler runtime used by the deployment gate
- scheduled failures now retain telemetry and valid partial writebacks before
  restoring the failed workflow result, so early proof-gate failures and live
  repository defects no longer prevent the multi-run history from accumulating
- head-aware planning now bounds network inspection to the configured limit and
  rotates oldest crawls first; quality reprocessing also rotates by generation
  time so repeatedly partial records cannot monopolize scheduled batch slots
- autonomous refresh now reprocesses lower-confidence checked-in records and
  newly discovered repositories through the same gate-passed writeback conveyor
- recurring failures are grouped into operational defect classes, classified by
  ecosystem, and tagged with fixture eligibility; eligible stubs can now be
  captured into checked-in, offline-runnable regression fixtures that replay the
  overlay import path in `cargo test` (see
  `docs/factual-crawl-automation.md`). The checked-in baseline now covers every
  named ecosystem emitted by the classifier, recurring stubs retain implicated
  repository identities, and `--stub` can drive capture without retyping
  provenance; converting live recurring failures into failure-derived fixtures
  and deterministic fixes remains open work.
- writeback and auto-publish now use distinct gates: `autonomous_writeback_eligible`
  (verification passed) may persist honestly partial overlays, while promotion to
  `verified` still requires `eligible_for_auto_publish`; the distinction is
  documented in `docs/factual-crawl-automation.md` and `index/README.md`, with
  crawler and core regression tests guarding the looser writeback path
- `public-surface-gate` now runs lightweight CLI, MCP, LSP, and crawler contract
  tests in addition to core import and public-export checks, reducing the chance
  that index-only changes skip surface regressions

Current Milestone 1 work queue (subordinate to the cross-milestone execution
order above):

1. Work down the quality hardening queue through bounded autonomous batches and
   targeted re-crawls. The 2026-06-29 renderer snapshot reports 501 records in
   the broader queue, including 285 missing build, 290 missing test, and 408
   missing security signals; it has no stale or overdue records.
2. Convert the discovery-wave failure corpus into deterministic parser fixes and
   checked-in regression fixtures, beginning with noisy README relation targets
   that fail repository-identity validation.
3. Improve lookup completeness on the 613-repository workload, especially the
   measured security and execution intents, without weakening honest abstention.
4. Continue bounded autonomous discovery only to preserve ecosystem balance or
   replace records lost to staleness, archive state, or validation failures.

Milestone 1 is complete when autonomous runs are repeatable, bounded, directly
publish gate-passed records, improve quality without a human queue, and expose
enough retained telemetry to support cost and regression claims.

### Milestone 2: Useful shared semantic cache

**Goal:** make dotrepo a rational first lookup for common public repositories.

**Status: complete.** Profile, batch, query, cache, freshness, accuracy, and
efficiency contracts and their release gates are shipped. The corpus has 516
high-signal profiles, exceeding the 500-profile quantitative coverage gate.

Deliver:

- at least 500 high-signal repository profiles
- a compact public research-profile response
- build, test, license, languages, topics, docs, ownership, relations, trust,
  evidence, and record freshness in one predictable shape
- batch profile and batch field lookup
- cache validators and snapshot/delta-friendly consumption
- measured hit rate for representative agent research workloads
- published scrape-versus-dotrepo efficiency benchmark

Current status:

- compact per-repository `profile.json` responses are generated in the static
  public export and available through `dotrepo public profile`
- local/core batch profile and batch field lookup are available through
  `dotrepo public batch-profiles` and `dotrepo public batch-query`
- hosted batch profile and batch field lookup are available as cacheable GET
  routes on the same public surface and in the local `dotrepo-public-query`
  runtime
- batch profile and batch query requests now enforce shared cardinality limits in
  core, the hosted Worker, and the reference HTTP server (50 repositories, 25
  paths, 500 query results); `dotrepo-public-query` is documented as a local and
  review-only surface
- static exports include `meta.validators` and `v0/files.json` for
  snapshot-level revalidation and selective refetch
- `scripts/diff_public_export_files.py` now turns two `v0/files.json`
  manifests into an exact added/changed/removed/refetch report for mirrors and
  agent caches
- `scripts/check_public_profile_coverage.py` now measures exported profile
  count, high-signal profile count and ratio, missing quality signals, and
  conflict-bearing profile rate, plus optional Milestone 2 count, ratio,
  conflict-rate, per-signal minimum, and per-signal ceiling gates against the
  public tree
- profile coverage now validates the accepted response shape and path identity,
  excludes malformed files from every coverage claim, and is enforced by the
  canonical release gate through a versioned 613-profile/516-high-signal
  baseline with ratcheted build, test, docs, ownership, security, and license
  floors
- `scripts/build_public_lookup_workload.py` now emits a fixed four-intent
  research workload for every exported profile without preselecting known-present
  fields, so production lookup-efficiency reports do not depend on a
  hand-maintained tiny fixture or self-fulfilling completeness filters
- `scripts/measure_public_lookup_efficiency.py` now produces deterministic
  aggregate and per-intent task/field hit-rate, workload-volume, payload-byte,
  request-reduction, and pass/fail gate reports for known-repository workloads;
  the canonical release gate publishes the current 613-repository, 2,452-task
  benchmark against a versioned baseline
- the canonical release gate also checks a cited exact-value accuracy sample:
  20 assertions across FastAPI, Tokio, and Gin currently pass, with workload
  volume and repository count guarded against silent shrinkage; this sample
  exposed and fixed live logo-title, announcement-description, and badge-link
  parser failures now preserved as offline regression fixtures
- `scripts/plan_index_growth_tranche.py` now turns grouped candidate catalogs
  into balanced, crawler-ready growth target files in candidate-file group
  order while excluding repositories already present in
  `index/repos/**/record.toml`; the checked-in
  `index/tranche-two-targets.txt` file supplied the completed 106-target crawl
  wave toward the 500-profile expansion; all seven language-family groups are
  now exhausted, and the seed-review workflows retain the catalog as the
  reproducible record of that tranche
- the canonical release gate publishes the growth plan and crawler-ready target
  file from a versioned tranche baseline; with tranche two exhausted, the
  baseline now requires zero selected targets while preserving completed
  coverage evidence and preventing planned targets from being counted as
  completed profiles
- the operational growth-status renderer now reports record-level high-signal
  progress, active-tranche high-signal capacity upper bounds, and remaining
  Milestone 2 gap in scheduled seed-review artifacts, so day-to-day review
  batches expose the same scale path as the release gate; it also separates
  advisory high-signal lift candidates from the broader quality-hardening queue
- `dotrepo promotion-report --json` separates total eligible records from
  promotion candidates, exposing deterministic auto-promotion headroom in the
  checked-in index. Recent quality and promotion waves promoted 48 eligible
  overlays to `verified` through expanded actionable-security URL scoring, primary-CI
  workflow preference during intra-tier command conflicts, targeted re-crawls,
  and bounded autonomous batches. As of 2026-06-29, the report identifies 61
  promotion candidates; the separate growth-status heuristic identifies 19
  high-signal lift candidates. The current public export has 516 high-signal
  profiles out of 613 total
- `is_actionable_security_url()` now recognizes GitHub security surfaces,
  coordinated-disclosure platforms, and first-party policy URLs while rejecting
  issue trackers and non-reporting channels; workflow command resolution now
  prefers `ci.yml` / `main.yml` over platform-specific workflows when multiple
  workflow sources conflict at the same tier, without weakening manifest-tier
  conflict honesty
- tranche-two writeback is complete at 106/106 targets across .NET, C/C++, Go,
  JVM, Python, Rust, and TypeScript/JavaScript; quality hardening and promotion
  waves followed by five bounded discovery waves brought the checked-in coverage
  baseline to 613 profiles and 516 high-signal profiles
- the 500 high-signal profile gate is complete at 516 profiles

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

Current status:

- `dotrepo public search` provides the first structured profile-search response
  over the public index, with text, language, topic, trust, and completeness
  filters grounded in generated `profile.json` semantics plus explicit
  relevance ranking metadata that remains separate from factual trust
- `scripts/measure_public_search_quality.py` now reports discovery success,
  rank quality, inventory-only versus profile-fanout task rates, searched
  profile bytes, freshness, and optional pass/fail gates for public-profile
  search workloads
- `scripts/measure_public_factual_accuracy.py` now reports exact cited
  assertion accuracy with separate missing and mismatch rates, and the release
  gate applies versioned ceilings for both so sampled abstention and wrong facts
  cannot hide behind aggregate accuracy
- `dotrepo public compare` provides the first factual comparison response for
  selected profiles, preserving trust, completeness, shared language/topic, and
  side-by-side signal values without ranking or synthesis
- public `profile.json` can now expose validated optional `synthesis.toml`
  guidance in a separate `synthesis` section, preserving factual fields as the
  authority and failing export on invalid or fact-conflicting synthesis
- crawler synthesis now runs through an opt-in bounded HTTP sidecar using the
  freshly validated in-memory manifest and capped source excerpts; factual
  build/test commands are injected by the crawler, model output is schema-
  checked before atomic writeback, failures remain nonblocking, and autonomous
  telemetry retains synthesis success and failure classes
- `dotrepo public relations` provides the first relationship traversal response
  over legacy references and explicit trust-bearing links for alternatives,
  dependencies, predecessors, forks, related projects, and references; reverse
  traversal emits semantic inverses and resolves profiles present in the index
- public export precomputes each repository's traversal response as
  `relations.json`; the hosted Worker serves cacheable GET search, compare, and
  relations routes from the staged public snapshot, loading this static artifact
  instead of performing request-time index-wide traversal and profile fanout
- hosted search now uses inventory-only matching for text-only queries, loading
  full `profile.json` snapshots only when completeness or trust filters require
  them; this keeps inventory-scale discovery cheaper on the Worker
- deterministic relation discovery now derives grounded repository links from
  GitHub snapshot facts, carries them through import and public export, and
  covers the behavior with offline and facade regression tests
- production-scale ranking calibration and sustained production synthesis runs
  with measured quality/cost remain ongoing operational work

### Milestone 4: Index at ecosystem scale

**Goal:** grow from a useful service into broadly reusable infrastructure.

Deliver:

- thousands, then tens of thousands, of incrementally maintained profiles
- partitioned export and serving paths where needed
- bounded scheduling, retries, and failure isolation
- model-provider routing based on task class, quality, latency, and cost
- automated regression sampling across ecosystems
- public operational status and coverage telemetry

Current status:

- `scripts/render_index_growth_status.py` reports record growth, tranche
  coverage, quality queues, language-family coverage, stale-or-missing
  `generated_at` rate, maximum record age, overdue refresh latency, and optional
  operational gates for tranche coverage, missing targets, lower-confidence
  backlog, stale freshness backlog, and maximum refresh overdue days.
- the checked-in corpus is 613 overlay records; refresh cost and stale-record
  rate must be tracked as first-class Milestone 4 metrics rather than inferred
  from profile count alone
- release-gate baselines ratchet profile volume and high-signal floors so index
  growth does not silently regress lookup completeness or factual accuracy
- the first quantitative scale checkpoint is 1,000 maintained profiles with a
  stale-or-missing record rate at or below 10%, maximum refresh overdue latency
  at or below 7 days, and a published refresh-cost baseline

Exit criteria:

- common repository lookups have a high hit rate across major ecosystems
- refresh latency and stale-record rates meet published targets
- measured refresh work tracks changed or stale repositories rather than total
  index coverage
- cost per maintained record declines as coverage grows
- throughput can increase without adding proportional human labor

### Milestone 5: Maintainer adoption flywheel

**Goal:** convert generated coverage into maintainer-owned durable truth.

Deliver:

- clear "inspect my record" and "adopt dotrepo" paths
- one-command bootstrap from an existing overlay or repository
- excellent preview, managed-surface, and CI onboarding
- low-friction claim and canonical handoff
- visible native-record benefits for maintainers and downstream tools
- integrations that make `.repo` useful even before public indexing

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

### Milestone 6: Open repository metadata standard

**Goal:** make repository metadata portable infrastructure rather than a single
implementation's feature.

Deliver:

- stable specification and compatibility suites
- independent producers and consumers
- SDKs and integrations for major agent and development platforms
- governance for schema evolution and trust vocabulary
- interoperable indexes and mirrors

Exit criteria:

- tools can consume `.repo` without depending on the reference implementation
- multiple systems produce compatible native records and projections
- the protocol survives implementation and hosting diversity

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
- verified profile count and percentage
- unresolved and conflicting field rates
- stale-record rate and refresh latency
- regression failures by parser, ecosystem, and model tier

### Efficiency

- deterministic resolution rate
- adjudication rate by tier
- strong-model escalation rate
- tokens and model cost per improved record
- network bytes and files materialized per refresh
- compute cost per maintained profile per month

### Utility

- exact-lookup hit rate
- research-discovery success rate
- batch requests served
- agent tasks completed without repository scraping
- bytes, tokens, requests, latency, and error reduction versus scrape-from-scratch

### Adoption

- native `.repo` repositories
- successful overlay-to-native handoffs
- active MCP, API, CLI, and SDK consumers
- independent protocol producers and consumers

Raw repository count is a capacity metric, not the primary success metric.

## Explicit non-goals

- manually reviewing every generated index record
- using LLMs for facts deterministic parsers can establish
- hiding uncertainty to make the index look complete
- allowing synthesis to overwrite factual metadata
- becoming a general code-search engine or package registry
- adding public mutation before provenance and authority remain enforceable
- expanding the core schema for every research or ecosystem-specific need
- optimizing raw repository count at the expense of accuracy or refreshability

## Strategic test

The roadmap is succeeding when this behavior becomes normal:

```text
agent receives a repository or technology question
  -> checks dotrepo first
  -> receives a small, fresh, trust-aware profile or candidate set
  -> retrieves only the additional source material the task truly requires
  -> reuses the same maintained understanding on future requests
```

At that point, scraping an entire repository to recover basic project facts is
the fallback, not the default.

## Related documents

- [`README.md`](./README.md) - shipped capabilities and project entrypoint
- [`CHANGELOG.md`](./CHANGELOG.md) - release history
- [`docs/factual-crawl-automation.md`](./docs/factual-crawl-automation.md) - crawler and escalation design
- [`docs/public-surface.md`](./docs/public-surface.md) - hosted public contract
- [`docs/maintainer-happy-path.md`](./docs/maintainer-happy-path.md) - native adoption workflow
- [`docs/trust-model.md`](./docs/trust-model.md) - authority, provenance, and confidence semantics
- [`docs/toolchain-maintainability.md`](./docs/toolchain-maintainability.md) - reference toolchain structure and refactor gates
- [`crates/dotrepo-crawler/README.md`](./crates/dotrepo-crawler/README.md) - internal autonomous index crate orientation
