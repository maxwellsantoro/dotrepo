# Milestone 1: escalation ladder canary

This guide separates a dated live ladder proof from current provider integration.
Use [crawl operations](factual-crawl-automation.md#model-integration-and-budgets)
for active configuration, attempt budgets, and publication gates.

## Retained ladder proof (July 2026)

| Tier | Proof status |
|------|----------------|
| Deterministic only | Proven in production refresh (most repos) |
| Primary model tier | Proven with engineered conflicting-workflow canary |
| Second-opinion tier | **Proven live** (2026-07-08 canary; forced low-confidence primary + HTTP second opinion) |
| Strong remote | Wired; optional third step when second opinion remains low-confidence |
| Confident abstention | Proven on genuine polyglot ties (correct termination) |

These proof statuses describe the retained July run, not current provider
configuration or a complete strong-remote live proof. A hosted primary provider
does not establish local-model execution. The second-opinion live proof is
recorded in [the retained canary](../index/telemetry/m1-second-opinion-canary-20260708.md)
and automated as
`second_opinion_live_ladder_from_low_confidence_primary` in
`crates/dotrepo-crawler/tests/openrouter_env_escalation.rs`.

## Current provider integration (October 4, 2026)

The active local sample selects Luna primary, Qwen3.8 Flash second opinion, and
GLM5.3 Flash tail. Hosted scheduled tiers still require explicit repository
variables and credentials; sample configuration does not enable them.

The [retained integration requests](../benchmarks/model-adjudication/2026-10-04/requests.json)
cover three synthetic candidate-selection cases. Luna passed all three initial
cases. GLM initially chose a broader command without primacy evidence, then passed
all three after the abstention rule was clarified. Qwen initially abstained on
normal CI versus release; its [bounded-reasoning follow-up](../benchmarks/model-adjudication/2026-10-04/qwen-second-opinion-reasoning-canary.json)
passed all three. The [initial Qwen result](../benchmarks/model-adjudication/2026-10-04/qwen-second-opinion-canary.json)
remains retained. Muse was rejected before inference by the account's paid-model
training restriction and is excluded from active configuration.

These checks establish provider/request compatibility on the retained cases.
They do not establish a live three-tier crawler run, independent factual accuracy,
or complete-task savings. A coordinator can run offline policy tests alongside
parser work; live canaries need one owner and a bounded shared spend budget.

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
   revision, run time, actual model/provider IDs, request policy, token/cost usage,
   tier list, and whether the final value was resolved vs honest abstention.
   Preserve failures and unavailable usage; do not infer a tier from configuration.

## Automated canary (preferred)

With the adjudication sidecar running and `.env` loaded
(`DOTREPO_ADJUDICATION_SECOND_OPINION_URL` required):

```bash
cargo test -p dotrepo-crawler --test openrouter_env_escalation \
  second_opinion_live_ladder_from_low_confidence_primary -- --nocapture
```

This stubs only the primary tier to a low-confidence `Absent` (because real
repos almost never produce that shape), then requires a live HTTP second-opinion
provider. Pass criteria: `model_calls >= 2` and
`LocalSecondOpinion` (or `ApiEscalation`) in `adjudication_tiers_used`.

## Offline regression

Escalation policy (including low-confidence Absent continuation) is covered by
unit tests in [`import/escalation/`](../crates/dotrepo-core/src/import/escalation/).

## Related

- `docs/factual-crawl-automation.md` — pipeline and budgets
- `scripts/run_autonomous_index_batch.py` — retained multi-run telemetry
- `scripts/check_autonomous_telemetry_gate.py` — strict proof gate
