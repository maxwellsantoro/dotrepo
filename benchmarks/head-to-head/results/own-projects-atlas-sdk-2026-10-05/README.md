# Atlas SDK follow-up — October 5, 2026

This is a separately frozen, two-task operator follow-up to the [eight-task readiness repeat](../own-projects-readiness-2026-10-05/README.md). It keeps that repeat's 6/8 result and all four SDK failures visible. It evaluates the same Atlas build and correctness commands at the same `866fe127542178c35515f51afed30c41616bdd77` source revision, with all 19 admitted implementations and the same 900-second per-command budget.

The installed macOS 27 SDK's top-level `libSystem.tbd` targets include `arm64e-macos` without the `arm64-macos` entry that Zig 0.14 expects. The retained diagnostics reproduce unresolved libc symbols before project code builds. A task-local compatibility SDK uses the unmodified `libSystem.tbd` bundled with the checksum-verified Zig 0.14.0 distribution, alongside symlinks to the installed SDK's headers and frameworks. Installed compiler/SDK files remain unchanged.

The frozen context declares `DOTREPO_STUDY_ZIG_SDK` and the SDK prerequisite. The runner supplies an `xcrun` selector that returns this task-local root only for `--sdk macosx --show-sdk-path`; all other calls delegate to `/usr/bin/xcrun`. `sdkSource` binds the library declarations, header SDK settings, and selector hash. This is an explicitly prepared operator environment, not evidence that the unconfigured default SDK works.

The source/profile snapshot and acceptance policy remain those of the readiness repeat. Coverage is known. This targeted repair follow-up is not a new held-out workload, and its two-task denominator cannot replace the earlier eight-task result.

Shared tool/download caches are warm, while each arm starts with a fresh checkout, targets, and virtual environment. The host is unreserved; other work and local release validation overlap these runs. Timing differences do not establish a causal advantage. Explicit HTTP counts exclude clone bootstrap, package-manager traffic, SDK preparation, and unallocated operator/model/maintenance costs. No model calls occur inside the runner; unknown costs stay null. No independent observation or external adoption is claimed.

## Observed outcome and correction

Both arms complete **0/2** tasks. The standalone Zig hash/verify probe passed, and Zig builds in this follow-up, but the SDK selector was placed on the complete build process PATH. Cargo then selected the older library declarations too, causing four Rust backend link failures. Correctness was not reached because its complete-cohort setup failed. This is an operator setup defect, not evidence that those Rust backends fail under the default SDK.

The failing outputs, instructions, SDK scope, and all four attempts are retained. The [scoped SDK follow-up](../own-projects-atlas-scoped-sdk-2026-10-05/README.md) narrows SDK selection to the Zig child process and is frozen and scored separately. This packet cannot be overwritten to turn the probe into a successful cohort result.

## Reproduce the setup (retained failing configuration)

Install the checksum-verified Zig 0.14.0 distribution and Java 21 used by the parent packet. The task-local SDK has this layout; the source files are symlinked rather than edited:

| Task-local path | Source |
| --- | --- |
| `/tmp/dotrepo-readiness-tools/zig-sdk-compat/usr/lib/libSystem.tbd` | Zig 0.14.0 `lib/libc/darwin/libSystem.tbd` |
| `/tmp/dotrepo-readiness-tools/zig-sdk-compat/usr/include` | Installed macOS 27.0 SDK `usr/include` |
| `/tmp/dotrepo-readiness-tools/zig-sdk-compat/System` | Installed macOS 27.0 SDK `System` |

The layout's source paths and hashes are retained in `workload.json` and `environment.json`. `runner-source.txt` is the exact executing runner. `zig-sdk-protocol-validation.json` retains a separate hash/verify probe against independent SHA-256 digests before this freeze. The selector is exercised by the runner's tests.

From `benchmarks/head-to-head`, use `bench.own_projects freeze --study atlas-sdk-followup` with a new empty output directory, pinned sources root, and retained metadata/inventory files; then use `bench.own_projects run`. Put the declared Java/Zig binaries on PATH. Code, tool versions, and SDK hashes must remain unchanged between freeze and execution. Never overwrite this packet or either prior study.

Replay retained scoring into a new directory:

```bash
uv run python -m bench.tasks \
  --workload results/own-projects-atlas-sdk-2026-10-05/workload.json \
  --observations results/own-projects-atlas-sdk-2026-10-05/observations.json \
  --out /tmp/dotrepo-own-project-atlas-sdk-score-replay
```
