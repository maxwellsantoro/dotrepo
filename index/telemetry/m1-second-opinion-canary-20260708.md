# M1 second-opinion live canary — 2026-07-08

## Result

**Pass.** Live ladder exercised primary (forced low-confidence `Absent`) →
HTTP second-opinion provider.

## How

```bash
# sidecar listening on DOTREPO_ADJUDICATION_* URLs from .env
cargo test -p dotrepo-crawler --test openrouter_env_escalation \
  second_opinion_live_ladder_from_low_confidence_primary -- --nocapture
```

## Report

```text
ImportEscalationReport {
  deterministic_requests: 1,
  deterministic_resolved: 0,
  model_calls: 2,
  model_resolved: 1,
  tokens_used: 326,
  remaining_unresolved: 0,
  adjudication_tiers_used: [Deterministic, LocalPrimary, LocalSecondOpinion]
}
```

## Design note

Real public repositories almost never emit a *low-confidence* primary response
(they resolve deterministically or abstain confidently). The canary therefore
stubs the primary tier to a low-confidence `Absent` and requires a live HTTP
second-opinion provider from the environment — proving the ladder continuation
path without weakening honesty gates on confident abstention.

Procedure: `docs/m1-escalation-canary.md`.
Test: `crates/dotrepo-crawler/tests/openrouter_env_escalation.rs`
`second_opinion_live_ladder_from_low_confidence_primary`.
