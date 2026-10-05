# Own-project readiness repeat — October 5, 2026

This packet is a targeted operator follow-up to the [October 4 study](../own-projects-2026-10-04/README.md). It retains the same eight tasks across RamenOS, sha256-benchmark-atlas, ries-rs, and pagedigest. Repository selection and commands remain those of the original preregistration. Coverage is now known; this is not a held-out or independent study.

`workload.json` freezes the evaluated deployed snapshot, source revisions, exact commands, task contexts, source hashes, setup, completion oracles, runner hash, and per-command time budget. The `repeatOfWorkloadSha256` binds the original workload. The original packet is unchanged.

## Explicit changes from the first study

- RamenOS uses proposed prerequisite-fix commit `4faea185ccd0b5bf310f2b949ce51b31fcbe0503`, exposed in [PR 33](https://github.com/maxwellsantoro/RamenOS/pull/33). Its `foundry-agent-task-proof-rt` wrapper now depends on `codegen`. The fix was pending separate A3 review and merge at freeze. The command remains `just foundry-agent-task-proof-rt`, with the prerequisite represented in its context. The other three source revisions are unchanged.
- Java 21 was already installed but absent from the first task process's PATH. This repeat puts `/opt/homebrew/opt/openjdk@21/bin` on PATH and uses a task-local, checksum-verified Zig 0.14.0 download matching Atlas's pinned campaign CI. It retains all 19 admitted implementations; no candidate is removed to obtain completion.
- Upstream Python subprocess names resolve through uv using the fresh project's virtual environment when available. This preserves Atlas's installed candidate dependencies rather than using only the dotrepo runner environment. Projects without that environment use the runner interpreter. Source files remain unchanged.
- Every command receives a frozen 900-second limit, increased from 300 seconds to allow the clean RamenOS/Wasmtime compilation on the shared host. This is a declared budget change, not a retroactive change to either study.
- The evaluated public snapshot is `8384e75929143cbe8a6d8fb27e375d5863eb9c591105765eba1402783336b4cd`, which contains the prior RIES scalar correction and withheld command assessments. This repeat does not change records during execution.

## Observed outcomes

| Task | Source first | Lookup first |
| --- | --- | --- |
| RamenOS-host-build | Complete | Complete |
| RamenOS-host-proof | Complete | Complete |
| sha256-benchmark-atlas-build | Failed setup | Failed setup |
| sha256-benchmark-atlas-correctness | Failed setup | Failed setup |
| ries-rs-core-build | Complete | Complete |
| ries-rs-core-test | Complete | Complete |
| pagedigest-consumer-test | Complete | Complete |
| pagedigest-generator-test | Complete | Complete |

Both arms complete **6/8** tasks. Lookup accepts **zero** commands, records **zero accepted wrong answers**, and performs **eight** source fallbacks. It makes 16 explicit HTTP requests / 53,976 decoded bytes versus source-first 8 / 45,068. The six successful fallbacks count as correct fallback. Both Atlas tasks fail because Zig 0.14 cannot match the installed SDK's ARM `libSystem` targets; correctness is not reached after its required full build fails. Java now builds and 18/19 implementations succeed.

The RIES values remain present but unassessed and rejected (`missing-command-assessment`). The earlier two accepted WASM context mismatches are no longer accepted. Zero accepted wrong answers here accompanies zero accepted answers; it does not establish an incorrect-answer rate for a useful-answer population.

Source-first totals about 1,534 seconds and lookup-first 1,591 seconds. Changed budgets, SDK conditions, warm cache carryover and host contention prevent a latency-advantage claim. No task, request, model, or net-cost benefit from lookup is demonstrated.

A separate [SDK follow-up](../own-projects-atlas-sdk-2026-10-05/README.md) evaluates only the two remaining Atlas tasks after a new environment freeze. It cannot replace this eight-task denominator or retroactively change these failures.

## Measurement and claim boundaries

Both arms use fresh checkouts, project targets, and virtual environments. Shared tool/download caches remain warm. Order alternates by task. The host is unreserved; other compilation and the initial standalone RamenOS validation overlap the start of this repeat. Neither within-run timing differences nor comparison with the first study establish a causal latency advantage.

Task scopes stay explicit: RamenOS host build/proof, RIES Rust core/CLI, and PageDigest consumer/generator work are component tasks. Atlas build/correctness cover the complete admitted cohort. Component successes do not establish whole-project defaults. Corrected native RIES defaults still require complete field verification; scoped source success does not justify inventing assessments or refreshing unrelated factual age.

Explicit profile/source HTTP counts and decoded bytes exclude clone bootstrap, package-manager requests, and prerequisite preparation. `readiness-environment.json` records the downloaded tool archive and setup boundary. No model calls occur in the runner; coding-session and preparation usage, model costs, and allocated maintenance costs remain unknown. No external adoption, autonomous-agent performance, total cost savings, or independent observation is claimed.

The fixed runner refuses an unfamiliar accepted scalar before execution and records that mismatch before fallback. Completion requires nonempty test results or the named artifacts/proof checks. Failures and timeouts stay in the denominator. Artifact hashes establish consistency, not independent witnessing.

## Evidence

- `meta.json` and `inventory.json` retain the deployed snapshot and original four-project selection rule.
- `runner-source.txt` is the exact executing runner, bound by the frozen workload and runtime environment.
- `http/` retains actual response bodies, status/URL/hash receipts, and source byte matches.
- `attempts/`, `observations.json`, `results.json`, and `report.md` retain execution logs, paired ordering, oracle outcomes, and scorer results.
- `ramen-proposed-fix.patch`, `ramen-justfile-source.txt`, `atlas-campaign-source.txt`, `ries-native-source.txt`, and `pagedigest-agent-source.txt` retain source context and prerequisite owners.
- `ramen-standalone-proof.log` and `ramen-standalone-proof/` retain the separate clean-checkout host validation. It passed 45 tests and the named valid-output, denied-without-mapping, durable-retry, and receipt-replay checks. This is host evidence; it does not establish kernel/hardware or complete Linux/Docker readiness.

## Replay

From `benchmarks/head-to-head`, score the retained observations into a new directory:

```bash
uv run python -m bench.tasks \
  --workload results/own-projects-readiness-2026-10-05/workload.json \
  --observations results/own-projects-readiness-2026-10-05/observations.json \
  --out /tmp/dotrepo-own-project-readiness-score-replay
```

For a new live repeat, prepare the four `REPEAT_REVISIONS` in `bench/own_projects.py`, retain new deployed metadata/inventory inputs, and set the declared Java/Zig binaries on PATH. Use `bench.own_projects freeze --study readiness-repeat` followed by `bench.own_projects run`, each with the new output directory and sources root. The runner must be unchanged between freeze and execution. Never overwrite this packet or the original study.
