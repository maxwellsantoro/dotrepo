# Active Plan: Autonomous Index Growth

This doc is the **current execution plan** for dotrepo after the `v1.0` launch.

For shipped launch scope and rationale, see [v1.0 launch record](#v10-launch-record) below.
For day-to-day status, see [`docs/current-status.md`](./docs/current-status.md).

## Objective

Grow and maintain the public overlay index through a **fully autonomous conveyor**
that:

- spends tokens only when deterministic work cannot honestly resolve a field
- lands gate-passed index updates without human per-record review
- keeps the hosted public surface contract-stable while coverage improves

The operator may pause, revert, or change policy at any time. The loop does not
wait for human approval.

## Current baseline

As of June 2026:

- 55 checked-in overlay records; tranche-one target list (50 repos) is fully seeded
- record mix: 28 `verified`, 19 `imported`, 7 `inferred`, 1 `reviewed`
- 44 records still carry quality-hardening signals (missing build/test/security,
  lower-confidence provenance)
- automation primitives exist: crawler factual writeback, field scoring,
  adjudication post-checks, auto-promotion, refresh planning, public export CI

The next phase is not "seed more repos first." It is **make the autonomous loop
the default way the index improves**.

## Operating model

```text
scheduled trigger (or manual dispatch)
  → plan refresh batch (head-changed / missing factual crawl)
  → for each repository:
       materialize → import → verify → score
       → escalation ladder (deterministic → optional model tiers)
       → re-verify → re-score → auto-promote when eligible
       → gate check
       → writeback when gate passes
  → validate-index
  → commit + push main
  → export + deploy (existing release/deploy path)
  → publish batch telemetry
```

Human role: **circuit breaker only** — not reviewer.

## Escalation ladder

Each repository stops as soon as its fields are honestly resolved.

| Tier | Cost | Action |
|------|------|--------|
| 0 | 0 tokens | Import heuristics, cleaners, `verify_import_plan`, `score_import_fields` |
| 1 | 0 tokens | Deterministic command-tier walk for unresolved `repo.build` / `repo.test` |
| 2 | Cheap local model | Narrow adjudication on remaining unresolved fields (candidates + snippets only) |
| 3 | Cheap local second opinion | Disagreement resolver when tier 2 is low-confidence |
| 4 | API escalation | Rare tail; capped per batch/week |
| 5 | Partial publish | Stay `imported` / `inferred`; writeback only if structural gates pass |

Design rules (from [`docs/factual-crawl-automation.md`](./docs/factual-crawl-automation.md)):

- never spend tokens on filesystem/API-answerable questions
- treat high-confidence absent as success, not failure
- synthesis and whole-repo model analysis stay out of scope

## Autonomous gates (replace human review)

A repository is written back only when:

1. `validate_manifest` passes
2. `verify_import_plan` passes (no verification failures)
3. `validate-index` passes on the resulting tree (batch-level)

Promotion to `verified` requires `eligible_for_auto_publish` after escalation.
Partial overlays may still write back at `imported` / `inferred` when structural
gates pass.

Machine checks replace [`index/review-checklist.md`](./index/review-checklist.md)
for automation:

- identity invariants (`record.source`, path, homepage)
- imported sources exist in materialized tree
- evidence bullets are template-generated from provenance (not free-form LLM prose)
- auto-promotion never mints `reviewed` or `canonical`
- existing regression packs stay green (`import_quality_gate`, public export fixtures)

## Circuit breakers

| Control | Purpose |
|---------|---------|
| `INDEX_AUTOMATION_ENABLED` repo variable | Pause scheduled autonomous runs |
| `INDEX_MAX_BATCH_SIZE` | Cap repositories per run |
| `INDEX_MAX_ADJUDICATION_CALLS` | Cap model spend per batch |
| Workflow `concurrency` + cancel | Stop in-flight batch when paused |
| Batch telemetry artifact | `promoted`, `skipped`, `gate_failures`, `tokens_used` |
| Git revert on `index/` commits | Operator recovery path |

## Implementation sequence

### Phase 1 — Close the crawler loop (complete)

- [x] Document autonomous plan (this file)
- [x] Wire deterministic escalation into `dotrepo-crawler` pipeline
- [x] Add `autonomous_writeback_eligible` gate before `--write`
- [x] Add `scripts/run_autonomous_index_batch.py`
- [x] Add scheduled `.github/workflows/index-autonomous-refresh.yml`

### Phase 2 — Model tiers (complete)

- [x] Pluggable adjudication provider (local sidecar / API) behind tier 2–4 caps
- [x] Batch telemetry for adjudication rate and token spend
- [x] Deterministic deepen for security/owners absent scoring (tier 1 expansion)

### Phase 3 — Scale

- [ ] Tranche-two queue once conveyor metrics are stable
- [ ] Auto-deploy coherence smoke on landed batches
- [ ] Deprecate artifact-only / draft-PR review workflows

## Success metrics

Optimize these, not raw merge count:

- `verified_per_batch`
- `autonomous_writeback_rate` (gate-passed / crawled)
- `adjudication_rate` (target: <25% of repos)
- `tokens_per_improved_record`
- `gate_failure_rate` (should be low; spikes mean gate or importer bugs)
- hosted lookup hit rate on high-traffic repositories

## Guardrails

- Do not weaken evidence or provenance standards to increase throughput.
- Do not mint `reviewed` from automation; machine path promotes to `verified` or
  leaves lower statuses explicit.
- Do not enable synthesis-led onboarding.
- Do not expand public search, mutation APIs, or editor scope ahead of conveyor
  stability.
- Keep public API `v0` contract-stable.

## Related docs

- [`docs/factual-crawl-automation.md`](./docs/factual-crawl-automation.md) — pipeline design
- [`docs/growth-and-automation-plan.md`](./docs/growth-and-automation-plan.md) — workstreams (being superseded by this plan for operations)
- [`index/tranche-one-targets.md`](./index/tranche-one-targets.md) — seeded queue
- [`docs/public-export-workflow.md`](./docs/public-export-workflow.md) — export/deploy path

---

## v1.0 Launch Record

The `v1.0` launch track is **complete**. This section is historical reference only.

### What v1.0 meant

dotrepo was ready for v1.0 when all of the following were true:

1. Maintainers could install the CLI, LSP, and MCP surfaces without building from source.
2. A repository could adopt the documented native flow and keep CI green with
   `validate`, `query`, `trust`, `doctor`, and `generate --check`.
3. Index operators could validate the index and cut deterministic public exports
   from repeatable documented steps.
4. Public consumers could inspect repository identity and trust through a stable,
   read-only hosted surface with freshness metadata.
5. Public promises, CI gates, and release process matched each other.

### Shipped launch outcomes

- Public read-only contract frozen (RFCs 0016–0019) with compatibility tests
- Hosted surface live at [`https://dotrepo.org/`](https://dotrepo.org/)
- Installable release artifacts for CLI, MCP, LSP, and VS Code shell
- Explicit release gate in CI; `v1.0.0` tagged
- One live accepted maintainer-claim example in the seed index

Release decision record: [`docs/v1-go-no-go.md`](./docs/v1-go-no-go.md)

### Deferred past v1.0 (still deferred)

- Discovery-first search, ranking, and browse UX
- Public mutation or self-serve submission APIs
- Bundle mode and first-class workspace/relations
- Richer editor authoring and managed-marker UX
- Arbitrary prose round-tripping beyond managed-surface boundaries