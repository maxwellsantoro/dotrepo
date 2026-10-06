# Contextual own-project campaign — October 5, 2026

Both arms completed all eight tasks. Lookup-first completed **six tasks directly
from independently selected public profile instructions**, with no source-guide
fetch or fallback for those tasks. It refused the two unassessed RamenOS aggregate
wrappers and completed them through source fallback. No accepted wrong answers,
failed attempts, or setup failures occurred in this packet.

This is a new, known-coverage, operator-controlled campaign on the maintainer's
four public projects. Source inspection and record authoring preceded the frozen
comparison. The generic consumer constructs an instruction from the actual public
profile; the runner then compares it with the frozen task context. These outcomes
establish useful instruction reuse in this prepared workflow. Independent adoption,
population answer precision, autonomous source investigation, and net cost benefit
remain unmeasured.

## Observed outcomes

| Metric | Source-first | Lookup-first |
| --- | ---: | ---: |
| Completed tasks | 8 / 8 | 8 / 8 |
| Direct profile completions | 0 | 6 |
| Accepted wrong answers | 0 | 0 |
| Failed attempts / setup failures | 0 / 0 | 0 / 0 |
| Source fallback attempts | 0 | 2 |
| Explicit HTTP requests | 8 | 10 |
| Decoded HTTP bytes | 46,020 | 49,970 |
| Application response-cache hits | 0 | 0 |
| Sum of measured arm elapsed time | 789.17 s | 797.29 s |

Lookup-first avoided six source-guide requests but still made more total explicit
HTTP requests and received more bytes: it requested a profile for every task and
also fetched a guide for each RamenOS fallback. These totals exclude source cloning,
bootstrap metadata, package-manager traffic and preparation. Existing shared
download caches were warm; checkouts, virtual environments and build outputs were
fresh per arm. The host was unreserved, with other compilation and local checks
overlapping parts of execution. Elapsed times are descriptive, not a causal speed
comparison. Actual model usage and allocated preparation/maintenance costs remain
null; the runner makes no model calls, while operator work is unallocated.

The Atlas build covered all 19 admitted implementations in both arms. Each
correctness arm checked **1,020 vectors per implementation**, with all 19 passing.
Both RamenOS host proofs passed validation, denied-access and receipt-replay checks;
their reports, journals and source/artifact manifests are retained in
`oracle-artifacts/`. This is host evidence, not hardware/kernel enforcement or a
model comparison.

## Frozen inputs and differences from earlier packets

The eight command strings and completion oracles are unchanged. Scope labels now
name physical owning directories; operator/toolchain preparation is separate from
profile instruction metadata. RamenOS task requests name `services` and
`services/store_service` as requested surfaces, while their original root wrappers
span multiple components. No single-component profile context is asserted for
those aggregates. RIES uses `src`; PageDigest uses its two implementation paths.

| Repository | Source pin | Lookup disposition |
| --- | --- | --- |
| RamenOS | `8dc5ff88ddc404528c384aead9ea77f17bf63d40` | Two source fallbacks; merged-main prerequisite fix |
| sha256-benchmark-atlas | `71eda5d6480e0b9e39f914f3641d91f98402e943` | Direct build and correctness; merged full-cohort prerequisite docs |
| ries-rs | `cfa959ed21a5a5e5f3d9538d9d1714c2401611e5` | Direct core/CLI build and tests |
| pagedigest | `f880f813cc0df49603482dbd879ff4ef49b3a519` | Direct Python-consumer and Rust-generator component tests |

The snapshot is
[`75707322809f36bee39edf66ce1011143b2ac62bf0cac158b7f94f8279eab35d`](https://dotrepo.org/v0/snapshots/75707322809f36bee39edf66ce1011143b2ac62bf0cac158b7f94f8279eab35d/repos/index.json).
The successful deployment retained all seven preceding history entries. Bootstrap
metadata/inventory/history bodies and receipt hashes are under `bootstrap/`;
`prior-public/` retains the comparison history. A post-fetch inspection helper
initially used `snapshots` instead of the contract's `entries` key; its corrected
prefix check and disclosure are retained. The deployment's own history smoke had
already passed, and the correction changed no frozen task input.

The runner/consumer/scorer source is from merged dotrepo
`d54d8a5292dcab9e2cf1eba0cbde71cdb6536ed4`. It uses the development contextual
consumer policy `value-bound-contextual-instruction-v1`, separately from stable
installation behavior. `execution-source/` retains every benchmark Python module,
the external consumer, `pyproject.toml` and `uv.lock`, with workload-bound hashes.
The frozen runtimes are Python **3.12.13** and uv **0.11.8**. Java **21.0.12.1**,
Zig **0.14.0** and the composite SDK inputs are declared in the preparation
contract. SDK selection is private to the Zig child. Atlas alone receives
`DOTREPO_STUDY_ZIG_SDK` through `preparationEnvironment`; every profile instruction's
environment and parameters are empty.

`preregistration.json` records source selection before record authoring. Coverage
was already known from earlier work, so the workload explicitly declares
`selectionBeforeCoverageInspection: false`, `knownCoverage: true`, and
`selectionFrozenBeforeExecution: true`. The source-derived records remain imported
overlays with exact candidate value/check-time bindings. `source-inspection/`
retains source files, hashes, prior RIES evidence and the ownership reinspection;
`indexed-records/` retains exactly the authored records. Preparation and authoring
costs have not been allocated. This is not held-out selection.

After the freeze, a separate Rake parser follow-up addressed a quoted `#` hiding a
later conditional modifier. It affects import recognition; no frozen benchmark
dependency, record, command, source pin, snapshot or oracle changed. The unchanged
execution dependency hashes were rechecked after the run.

## Replay and inspection

`workload.json` binds source pins, task contexts, setup, runtimes and execution
sources. `observations.json` binds that workload's bytes and every attempt log.
`attempts/` retains command output/exit status; `http/` retains all 18 live response
bodies and URL/status/hash receipts. `verification.json` records score replay,
retained profile reselection at the frozen clock, HTTP counts/bytes/hash checks,
unchanged execution dependencies, and full Atlas vector checks.

From `benchmarks/head-to-head`:

```bash
uv run python -m bench.tasks \
  --workload results/own-projects-contextual-2026-10-05/workload.json \
  --observations results/own-projects-contextual-2026-10-05/observations.json \
  --out /tmp/dotrepo-contextual-replay
```

See [report.md](report.md) and [results.json](results.json) for the scorer output.
Hashes establish consistency with supplied logs, not independent observation.
The October 4, readiness-repeat, failed broad-SDK and successful scoped-SDK packets
are unchanged. This eight-task campaign is scored separately and does not rewrite
their revisions, denominators or unfavorable outcomes.
