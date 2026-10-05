# Maintainer public-project study — October 4, 2026

This is an operator-run reference workflow on all four substantive other public projects. Tasks were frozen before requesting their dotrepo profiles. dotrepo itself and the throwaway adjudication canary were excluded by a roster rule, not by coverage. This workload supersedes the earlier prospective external-participant plan for the current stage; historical rubrics and controlled packets remain unchanged.

The directory date uses America/New_York; machine receipt timestamps use UTC.

## Frozen workload

| Project | Pinned commit | Tasks |
| --- | --- | --- |
| RamenOS | [eba7fb7ce538](https://github.com/maxwellsantoro/RamenOS/tree/eba7fb7ce53807a6b9b5a85bd3caaf9f7749d917) | host-build, host-proof |
| sha256-benchmark-atlas | [866fe1275421](https://github.com/maxwellsantoro/sha256-benchmark-atlas/tree/866fe127542178c35515f51afed30c41616bdd77) | build, correctness |
| ries-rs | [cfa959ed21a5](https://github.com/maxwellsantoro/ries-rs/tree/cfa959ed21a5a5e5f3d9538d9d1714c2401611e5) | core-build, core-test |
| pagedigest | [f880f813cc0d](https://github.com/maxwellsantoro/pagedigest/tree/f880f813cc0df49603482dbd879ff4ef49b3a519) | consumer-test, generator-test |

The eight tasks cover repository-default atlas build/correctness and scoped RamenOS host, RIES Rust-core, and PageDigest consumer/generator work. A component task does not establish a whole-project build or test. Atlas correctness includes its documented build prerequisite; RamenOS host build retains its codegen wrapper. Required tooling is part of the task, not silently installed or removed. Each command has a preregistered 300-second limit.

## Observed outcomes

| Task | Source first | Lookup first | Disposition |
| --- | --- | --- | --- |
| RamenOS host build | Complete | Complete after fallback | Wrapper runs codegen first |
| RamenOS host proof | Failed | Failed after fallback | Clean checkout lacks generated native-runner bindings; documented recipe does not run codegen |
| Atlas build | Failed | Failed after fallback | Java unavailable; installed Zig 0.16 rejects the pinned build script |
| Atlas correctness | Setup failed | Setup failed after fallback | Its required all-candidate build fails; correctness command not reached |
| RIES Rust-core debug build | Complete | Complete after context refusal/fallback | Accepted `npm run build` is WASM scope; unexecuted by study guard |
| RIES Rust-core tests | Complete | Complete after context refusal/fallback | Accepted `npm test` is WASM scope; unexecuted by study guard |
| PageDigest Python-consumer tests | Complete | Complete after fallback | Scoped working directory retained; nonempty unittest run |
| PageDigest Rust-generator tests | Complete | Complete after fallback | Scoped working directory retained; nonempty Cargo test run |

Both arms complete 5/8 tasks. Lookup-first makes 16 explicit source/profile
requests versus 8 source requests, accepts two context-mismatched RIES scalars,
and uses eight source fallbacks. The scorer's five failed lookup-first attempts
include three executed/setup failures and two unexecuted context refusals. Its
`acceptedWrongAnswer` count measures mismatch with this frozen task, not an
observed npm execution failure. Its `correctFallback` counter is three successful
rejected-profile cases; the two accepted-mismatch recoveries are separate.

Source-first totals about 550 seconds, lookup-first about 480 seconds. Shared
download-cache carryover and an unreserved host prevent interpreting that
difference as a latency advantage. There is no demonstrated task, request, model,
or net-cost benefit in this packet. It is a useful first operator checkpoint.

After all paired runs, source inspection at the RIES overlay's retained commit
`0904c3ed17d2f221ea565a7b9e15929d9fe8b419` confirmed root package scripts target
WASM, while the maintainer's `.repo` already declares Rust defaults. The separate
`ries-source-inspection.json` binds those source bytes. The overlay now uses
those exact native defaults, with superseded assessments and verified provenance
removed and status downgraded pending complete verification. Record age, unrelated
assessments, claim events, and the original study are preserved. `record-correction.json` owns
the before/after disposition; this does not demonstrate improved post-correction
outcomes. A later complete verification must be a separate run.

Keep external recruitment deferred. Next practical work is source-preserving
readiness on these same projects: resolve RamenOS's generated-binding prerequisite,
prepare the atlas's declared toolchain versions, and evaluate honest default or
component coverage with a new frozen snapshot. Do not count a repaired record or
operator familiarity as independent use.

## Evidence and measurement boundary

- `workload.json` binds source revisions, SHA-256 source digests, exact instructions, prerequisites, scopes, and completion oracles. Its freeze precedes individual profile requests.
- `coverage-inventory.json` and its receipt retain a supplemental inventory fetch after freeze, outside timed arms. The inventory lists RIES and excludes the other selected identities.
- `meta.json` pins the immutable public snapshot; it was fetched before freeze without inspecting repository coverage. `inventory.json` retains the public-project roster.
- `http/` retains actual response bodies, statuses, URLs, and hashes. `attempts/` retains setup and command stdout/stderr, exit codes, and observed oracles.
- `observations.json` alternates paired order and binds every attempt log; `results.json` and `report.md` are scorer outputs.
- The host was not reserved; concurrent background compilation was observed. `bootstrap-environment.json` records tool versions and this limitation. Elapsed times cannot establish a causal latency advantage.
- Warm shared tool/download caches remain; each arm starts from a fresh checkout with fresh project outputs and virtual environments. Alternation does not remove dependency-cache carryover.
- Arm elapsed time includes explicit source/profile HTTP, local checkout, setup, execution and oracle work. HTTP requests/bytes count only the explicit repository-source/profile requests. Package-manager traffic, clone bootstrap, manual source adjudication, and preparation are not allocated.
- Upstream `python`/`python3` subprocess names resolve through uv launch shims using the runner interpreter. Upstream files remain unchanged. The interpreter and this adaptation are retained in `environment.json`.
- `runner-source.txt` is the exact executing runner, bound by `environment.json`. The maintained runner adds fixed-task and freeze-time code-hash checks for subsequent runs; the recorded packet is scored with its original inputs.
- Completion needs a nonempty test result or the named output/host-proof checks, not just a successful exit. Unavailable setup, failures, and timeouts remain in the denominator.
- An accepted unfamiliar scalar cannot be executed by this fixed runner. It is retained as an unexecuted context mismatch before source fallback. Such a row is not evidence of an observed command failure.
- Source decisions are manual and scripted. No model calls occur inside the runner; coding-session/preparation usage and maintenance allocations remain unknown. No independent adoption, model savings, total cost savings, or causal latency benefit is claimed.

## Replay and repeat

From `benchmarks/head-to-head`, replay scoring into a new output directory:

```bash
uv run python -m bench.tasks \
  --workload results/own-projects-2026-10-04/workload.json \
  --observations results/own-projects-2026-10-04/observations.json \
  --out /tmp/dotrepo-own-project-score-replay
```

For a new live run, clone the four pinned revisions, retain a new public metadata response and inventory, then use `bench.own_projects freeze` and `bench.own_projects run` with a new output directory. Never overwrite this packet. A later coverage correction needs a new dated snapshot comparison; it cannot improve this run retroactively.
