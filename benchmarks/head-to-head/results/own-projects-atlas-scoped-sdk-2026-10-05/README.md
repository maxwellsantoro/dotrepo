# Atlas scoped SDK follow-up — October 5, 2026

This packet separately evaluates the two Atlas tasks remaining after the [eight-task readiness repeat](../own-projects-readiness-2026-10-05/README.md). It preserves that repeat's 6/8 result and the [failed broad SDK attempt](../own-projects-atlas-sdk-2026-10-05/README.md). The source pin, commands, 19 admitted implementations, oracles, snapshot, policy, and 900-second budget stay the same. Coverage and prior failures are known; this is targeted operator follow-up, not a held-out study.

The compatibility SDK uses the unmodified library declarations bundled with checksum-verified Zig 0.14.0 and symlinks to the installed macOS 27 SDK's headers/frameworks. `DOTREPO_STUDY_ZIG_SDK` is declared in each task context. A wrapper gives **only the Zig child process** the SDK selector on PATH. Cargo and the other compilers retain the default SDK. This corrects the broad selector's unintended effect on Rust backend linking. Installed SDK files remain unchanged.

`sdkSource`, `sdkSelectionScope`, the runner hash, source revisions, and task contexts bind the exact configuration. Environment labels are identifiers; the complete frozen SDK/environment fields describe the prepared setup. The two-task result is scored independently and cannot be substituted for the original eight-task denominator.

The host is unreserved; shared download/tool caches remain warm. Each arm has fresh checkout/build/venv outputs. Local validation and other work overlap execution. Timing differences do not establish a causal advantage. Explicit HTTP counts exclude bootstrap, package-manager traffic and SDK preparation. No model calls occur in the runner; unallocated model, preparation, and maintenance costs remain null. No external adoption or independent observation is claimed.

## Observed outcomes

Both arms complete **2/2** tasks. All 19 distinct implementations build, and every implementation passes all **1,020** correctness vectors in each arm. Lookup accepts no profile instruction and performs two successful source fallbacks (`repository-not-found`). The original eight-task packet remains **6/8**, and the preceding broad SDK attempt remains **0/2**; this result is not an eight-task rerun.

Source-first uses two explicit HTTP requests / 10,432 decoded bytes; lookup-first uses four / 10,432. Their recorded elapsed totals are about 651 and 874 seconds respectively. These observations demonstrate completion in the prepared environment. They do not demonstrate lookup latency or cost benefit, useful accepted-answer coverage, whole-project defaults for the other component tasks, or independent use.

## Setup and replay

Prepare the source/tool pins and compatibility SDK layout documented in the [preceding SDK attempt](../own-projects-atlas-sdk-2026-10-05/README.md). The retained `runner-source.txt` implements the Zig-only wrapper and selector. The isolation regression checks that ordinary `xcrun` queries still resolve the default SDK while the Zig child receives the declared SDK.

From `benchmarks/head-to-head`, freeze a new output directory with `bench.own_projects freeze --study atlas-sdk-scoped`, then execute `bench.own_projects run`. Supply the pinned sources root and retained metadata/inventory inputs, and put Java 21/Zig 0.14 on PATH. Code, tool versions, and SDK hashes must remain unchanged between freeze and execution. Never overwrite any retained packet.

Replay scoring into a new directory:

```bash
uv run python -m bench.tasks \
  --workload results/own-projects-atlas-scoped-sdk-2026-10-05/workload.json \
  --observations results/own-projects-atlas-scoped-sdk-2026-10-05/observations.json \
  --out /tmp/dotrepo-own-project-atlas-scoped-sdk-score-replay
```
