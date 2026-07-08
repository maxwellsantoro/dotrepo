# Milestone 1: escalation ladder canary

## Status

| Tier | Proof status |
|------|----------------|
| Deterministic only | Proven in production refresh (most repos) |
| Local primary model | Proven with engineered conflicting-workflow canary |
| Local second opinion | **Wired; awaits live low-confidence primary** |
| Strong remote | **Wired; awaits live low-confidence primary** |
| Confident abstention | Proven on genuine polyglot ties (correct termination) |

Primary-tier proof and the Absent low-confidence continuation fix are described
in `ROADMAP.md` (active execution order, Milestone 1). This page is the
operator procedure for closing the remaining second-opinion / strong-remote
live-call gap without weakening honesty gates.

## Why confident abstention is not enough

A confident model `Absent` (no single honest command) must **stop** escalation.
Only a **low-confidence** primary `Absent` or `Rejected` should climb the ladder.
Hard polyglot repos that abstain confidently are success for correctness, not
proof that tier-3/4 ran.

## Canary procedure (operator)

1. **Environment** — run against a throwaway public repository or a private
   fixture repo you control. Enable adjudication sidecars:

   ```bash
   export INDEX_AUTOMATION_ENABLED=true
   # primary + second-opinion + remote providers per crawler/adjudication env
   # see scripts/adjudication_openrouter_sidecar.py and crawler README
   ```

2. **Force low-confidence primary** — prefer a repository whose same-tier
   candidates are incomplete or weakly evidenced (not a clean three-way tie the
   primary can confidently refuse). If the primary returns high-confidence
   Absent, the canary did not exercise tier-3; adjust evidence, not the ladder.

3. **Crawl with JSON**:

   ```bash
   cargo run -p dotrepo-crawler -- crawl \
     --host github.com --owner <owner> --repo <repo> \
     --write --json
   ```

4. **Pass criteria** — escalation report includes:
   - `modelCalls >= 2` (primary + at least one higher tier), or
   - `adjudicationTiersUsed` containing a second-opinion / API tier after a
     low-confidence primary outcome
   - final field still passes post-checks (candidate set, validation)
   - telemetry retained in the batch NDJSON with non-zero tokens for those tiers

5. **Record** — append a short note under
   `index/telemetry/` (or the batch output dir) with repository identity,
   tier list, and whether the final value was resolved vs honest abstention.

## Offline regression

Escalation policy (including low-confidence Absent continuation) is covered by
unit tests in `crates/dotrepo-core/src/import/escalation.rs`. Offline tests do
not replace the live multi-tier canary above.

## Related

- `docs/factual-crawl-automation.md` — pipeline and budgets
- `scripts/run_autonomous_index_batch.py` — retained multi-run telemetry
- `scripts/check_autonomous_telemetry_gate.py` — strict proof gate
