# Growth And Automation Plan

As of April 18, 2026, the live public surface at
[`https://dotrepo.org/`](https://dotrepo.org/) is coherent across the homepage,
[`/v0/meta.json`](https://dotrepo.org/v0/meta.json), and
[`/v0/repos/index.json`](https://dotrepo.org/v0/repos/index.json):

- the current reviewed export publishes 15 repositories
- the live snapshot was generated at `2026-04-18T03:02:00.573009786Z`
- the homepage, summary, trust, and query surfaces are all coming from one
  reviewed snapshot family

That is enough product surface to prove the thesis. It is not yet enough
coverage or automation to make dotrepo a likely first check for arbitrary
public repositories.

This doc turns the existing post-v1 direction into an execution plan for the
next phase: grow the reviewed index deliberately, automate the review and
refresh loop around it, and keep the public surface narrow while the lookup and
coverage story gets strong.

## Current Read

What is already working:

- The public surface is live, coherent, and same-origin on `dotrepo.org`.
- The first suggested 10 overlays from
  [`index/tranche-one-targets.md`](../index/tranche-one-targets.md) are already
  present in the checked-in index.
- The crawler can discover, materialize, write back, and schedule factual
  refreshes through `dotrepo-crawler`.
- The Cloudflare deploy path, Worker smoke, and release-gate export path are in
  place.

What remains weak:

- 15 repositories is still below the threshold where users or agents should
  expect a likely hit for common public repos.
- Growth is still mostly a manual operator loop instead of a predictable review
  conveyor.
- Refresh and drift handling exist as primitives, but not yet as an always-on
  operating loop.
- Hosted lookup now exists in MCP and on the homepage, but the value of that
  path still depends on much broader reviewed coverage.
- The homepage now makes growth visible, but the public product should stay
  narrow until the review conveyor is materially stronger.

## Goals

### Goal 1

Reach the first tranche of 50 reviewed repositories across Rust,
TypeScript/JavaScript, Python, and Go without lowering the review bar described
in [`index/review-checklist.md`](../index/review-checklist.md).

### Goal 2

Turn index growth from an ad hoc maintainer task into a repeatable weekly
system:

- candidate discovery is scheduled
- reviewable batches are emitted automatically
- factual refreshes are scheduled automatically
- deploy coherence is checked automatically

### Goal 3

Ship one remote-lookup product path that makes the hosted public surface useful
to coding agents without requiring a clone:

- `dotrepo.lookup` in MCP
- a matching public lookup affordance on the homepage

## Guardrails

- Do not weaken overlay evidence standards to chase repo count.
- Do not let search, ranking, mutation APIs, or broader editor work outrun
  index coverage and hosted lookup.
- Keep synthesis subordinate to factual crawl output and review.
- Keep the public surface export-first and contract-stable.
- Prefer small, reviewable automation batches over fully autonomous merging.

## Workstreams

### Workstream A: Public Surface Integrity

The deploy path should prove semantic coherence, not just reachability.

Planned work:

- Extend deployed smoke to fetch `/`, `/v0/meta.json`, `/v0/repos/index.json`,
  and sampled repository summary or trust endpoints, then assert the same
  `generatedAt`, `snapshotDigest`, and `staleAfter` values across the response
  family.
- Assert that homepage snapshot counters match the live inventory count.
- Keep `scripts/check_release_gate.py` as the canonical local review entrypoint,
  but add explicit coherence checks that would catch a stale landing page or a
  staged-snapshot mismatch before deployment.
- Treat cache behavior as a hardening concern only after these semantic checks
  exist.

Acceptance criteria:

- A deploy cannot succeed if the homepage and live `v0` JSON disagree on
  freshness or repository count.
- The same snapshot digest is mechanically verified across homepage, `meta`,
  inventory, summary, trust, and query responses.

### Workstream B: Deliberate Index Growth

The index needs throughput, but it also needs curation discipline.

Execution model:

- Use [`index/tranche-one-targets.txt`](../index/tranche-one-targets.txt) as
  the canonical seed queue.
- Work in batches of 3 to 5 repositories at a time.
- Keep the language mix visible in every short batch instead of allowing
  prolonged Rust-only or infra-only runs.
- Prefer 2 to 3 moderate-complexity wins before each giant monorepo.

Operating target:

- move from 15 reviewed repositories to 25 with the first automation loop in
  place
- move from 25 to 50 with review cadence and refresh cadence both stable

Acceptance criteria:

- the checked-in index reaches 50 reviewed repositories
- every merged overlay still ships `record.toml` plus `evidence.md`
- review artifacts remain readable and grounded in source-specific evidence

### Workstream C: Candidate And Refresh Automation

Automation should reduce operator overhead without removing human review.

### Candidate seeding loop

Add a scheduled GitHub Actions workflow that:

- runs `dotrepo-crawler seed --targets-file index/tranche-one-targets.txt`
- emits JSON output plus `--review-report-md`
- groups candidate overlays into small review batches
- uploads artifacts for inspection
- optionally opens or updates a draft PR for a batch, but never auto-merges

The first implementation of that loop now lives in
[`index-seed-review.yml`](../.github/workflows/index-seed-review.yml)
and is intentionally artifact-first but now batch-aware:

- weekly scheduled dry-run execution over the tranche list
- machine-readable `seed-report.json`
- reviewer-facing `seed-review.md`
- machine-readable `seed-batches.json` grouping review work into small batches
- reviewer-facing `seed-batches.md` with suggested PR titles and per-batch repo
  details
- GitHub step summary via
  [`scripts/render_seed_review_summary.py`](../scripts/render_seed_review_summary.py)

Manual draft-PR creation now exists as a separate workflow in
[`index-seed-batch-pr.yml`](../.github/workflows/index-seed-batch-pr.yml),
which regenerates one selected batch, applies it, validates the index, and
opens a draft PR. The review workflow can now also optionally open one draft PR
for the first eligible batch when explicitly enabled by dispatch input or a
repository variable. Broad scheduled PR opening remains follow-on work.

### Refresh loop

Add a second scheduled workflow that:

- reads the tracked crawler state
- fetches current GitHub heads for tracked repositories
- uses scheduler reasons from the crawler refresh planner
- proposes factual refresh batches when a repo is missing factual crawl data or
  its head SHA changed
- keeps synthesis optional and off the critical path

The first implementation of that loop now lives in
[`index-refresh-review.yml`](../.github/workflows/index-refresh-review.yml)
and is head-aware rather than discovery-only:

- it reads [`index/.crawler-state.toml`](../index/.crawler-state.toml)
- it fetches current GitHub default-branch heads for tracked repositories via
  `dotrepo-crawler refresh-plan`
- it emits `refresh-plan.json` plus a reviewer-facing
  `refresh-plan.md`
- it emits `refresh-batches.json` plus a reviewer-facing
  `refresh-batches.md` so scheduled work is already grouped into small execution
  units
- it publishes a GitHub step summary via
  [`scripts/render_refresh_plan_summary.py`](../scripts/render_refresh_plan_summary.py)

Manual refresh execution now exists as a separate workflow in
[`index-refresh-batch-pr.yml`](../.github/workflows/index-refresh-batch-pr.yml),
which regenerates one selected refresh batch, applies factual crawl writeback
for those repositories, validates the index, and opens a draft PR. The review
workflow can now also optionally open one top-batch draft PR when explicitly
enabled. Broad scheduled refresh execution remains follow-on work.

### State and reporting

Automation should produce one simple weekly readout:

- current reviewed repository count
- count by language family
- queued candidate count
- queued refresh count
- maintainer-claim example count
- last successful deployed snapshot timestamp

Acceptance criteria:

- reviewers can pull one artifact or draft PR and see a small, coherent batch
- refresh work is reason-coded as `MissingFactualCrawl`, `HeadChanged`,
  `MissingSynthesis`, `PreviousSynthesisFailed`, or
  `SynthesisModelChanged`
- the automation loop reduces manual repo triage, but humans still control
  merge decisions

### Workstream D: Hosted Lookup And Public Product Surface

The thin lookup layer is now in place on both the agent and human paths.

Delivered work:

- `dotrepo.lookup` now ships in MCP
- it accepts either a repository URL or `(host, owner, repo)` identity
- it returns hosted repository summary, trust entrypoints, snapshot links, and
  an optional immediate hosted query result without requiring a local checkout
- the homepage now includes a simple repo lookup input that resolves against
  the live hosted public surface
- the homepage now exposes visible progress counters for `reviewed repos`,
  `tranche progress`, `language mix`, and `maintainer-claim examples`

Acceptance criteria:

- an agent can resolve a repository against `https://dotrepo.org/` from MCP
- a human can paste a GitHub repository URL into the homepage and reach the
  matching hosted summary or trust surface
- the homepage exposes progress without introducing search or ranking

## Milestones

### Milestone 1: Stabilize The Operating Surface

Target outcome:

- deploy coherence smoke exists
- docs point to one canonical execution plan
- candidate and refresh workflows are specified and scaffolded

Exit bar:

- homepage and live JSON coherence checks are in CI or deploy smoke
- this plan is linked from roadmap and current-status docs

### Milestone 2: Make Growth Routine

Target outcome:

- scheduled candidate seeding is live
- scheduled refresh planning is live
- reviewed index reaches at least 25 repositories

Exit bar:

- reviewers receive predictable small batches
- language mix remains visible
- refresh reasons are surfaced in automation output

### Milestone 3: Make Lookup Real

Target outcome:

- `dotrepo.lookup` is shipped
- homepage lookup exists
- reviewed index reaches the 50-repository tranche target

Exit bar:

- remote lookup works without cloning
- the public surface remains narrow and contract-stable
- the project can credibly claim both hosted utility and growing coverage

## Immediate Next Actions

1. Exercise the new seed-batch and refresh-batch draft-PR workflows on GitHub,
   including the guarded auto-PR mode, and tighten any rough edges in their
   branch, commit, or PR defaults.
2. Decide whether the current guarded top-batch auto-PR mode is sufficient or
   whether broader scheduled PR opening is actually desirable, still keeping
   merge control human.
3. Use those execution paths to move from the current 15 reviewed repositories
   toward the 25-repository milestone without losing language mix discipline.
4. Add at least one more independently reviewed accepted maintainer-claim
   example to reduce the current single-example gap.
5. Keep deploy coherence smoke and homepage lookup stable as contract surfaces
   while the index-growth loop scales.

## Non-Goals For This Phase

- public search or ranking UX
- public mutation or submission APIs
- schema expansion beyond current post-v1 blockers
- synthesis-led repository onboarding
- broader editor or managed-surface product work not required for index growth
  or remote lookup

## Related Docs

- [`docs/current-status.md`](./current-status.md)
- [`docs/roadmap.md`](./roadmap.md)
- [`docs/post-v1-backlog.md`](./post-v1-backlog.md)
- [`index/tranche-one-targets.md`](../index/tranche-one-targets.md)
- [`index/review-checklist.md`](../index/review-checklist.md)
- [`docs/public-export-workflow.md`](./public-export-workflow.md)
