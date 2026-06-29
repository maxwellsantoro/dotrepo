# dotrepo-crawler

Internal autonomous index orchestration for dotrepo. This crate is **not
published**; it powers scheduled discovery, factual crawl, verification,
escalation, writeback, and refresh planning for overlay records in `index/`.

## Role in the system

```text
discover / schedule
  -> GitHub fetch + materialize bounded evidence
  -> dotrepo-core import + verification + scoring
  -> optional model adjudication
  -> gate-passed writeback to index/repos/<host>/<owner>/<repo>/
```

All business logic for validation, import, trust, and promotion lives in
`dotrepo-core`. The crawler wires that logic to GitHub APIs, temporary
materialized trees, telemetry, and index writeback.

## Crate layout

| Module | Responsibility |
|--------|----------------|
| `discover.rs` | Candidate discovery and target selection |
| `github.rs` | GitHub API client and repository snapshots |
| `materialize.rs` | Bounded file materialization into temp roots |
| `pipeline.rs` | End-to-end crawl orchestration |
| `adjudication.rs` | Env-driven model provider wiring |
| `synth.rs` | Optional bounded synthesis sidecar |
| `writeback.rs` | Atomic overlay persistence |
| `schedule.rs` | Head-aware refresh planning |
| `state.rs` | Crawl state persistence |

## Local development

```bash
# Offline pipeline regression (no network)
cargo test -p dotrepo-crawler --test pipeline_offline

# Full crawler crate tests
cargo test -p dotrepo-crawler

# Explicit local batch (opt-in; see scripts/run_autonomous_index_batch.py)
uv run python scripts/run_autonomous_index_batch.py \
  --skip-automation-enabled-check \
  --output-dir /tmp/dotrepo-autonomous-batch
```

## Related documentation

- [`docs/factual-crawl-automation.md`](../../docs/factual-crawl-automation.md) — pipeline design and gates
- [`index/README.md`](../../index/README.md) — overlay layout and autonomous rules
- [`ROADMAP.md`](../../ROADMAP.md) — Milestone 1 factory and Milestone 4 scale gates