# Existing-CI evidence pilot — 2026-10-29

This source-only pilot found useful additional execution context and explicit
GitHub step outcomes at all three declared revisions. It did **not** establish
independent execution success, portable consumer instructions, or consumer benefit.
The three repositories were already exposed E1 development workloads. They are
not qualification holdouts, and no F-05 source or evaluated index was consulted.

The [plan](plan.json), retained source assertions and exact bytes were frozen in
[pre-api-freeze.json](pre-api-freeze.json) before the first public API request.
The fixed identities were:

| Repository | Exact revision | Selected existing runs |
| --- | --- | --- |
| keras-team/keras | `7efab4a60f5930fa81b0db15ed4ec6e4925e0c45` | [Tests 40602464413](https://github.com/keras-team/keras/actions/runs/40602464413), [GPU 40602464523](https://github.com/keras-team/keras/actions/runs/40602464523) |
| docker/compose | `343bb382d2192b88d84af49971bb5cb99bee268c` | [ci 40716799996](https://github.com/docker/compose/actions/runs/40716799996) |
| storytold/photocraft | `5f9b4391874aabc9deb2fcb905267613e4d93ec8` | [CI 40800573488](https://github.com/storytold/photocraft/actions/runs/40800573488) |

No revision was substituted. Each selected run and every returned job had the
exact declared head SHA, with run attempt 1. All four runs reported success;
their 54 jobs included 47 successes and seven skipped jobs. Entire step lists,
including skipped steps in successful jobs, are retained. Run/job listing totals
fit the first requested pages (100 per page); this is a bounded observation,
not a guarantee of historical completeness or continued retention.

[observations.json](observations.json) separates seven assertions: documented
command, workflow command/action presence, containing job success, actual API
step conclusion, log corroboration, independent execution and consumer
applicability. A GitHub step has a job-scoped **number**, not a separate opaque
step ID in these responses. The exact mappings retain that distinction.

| Case | What CI adds beyond README-level guidance | What remains unestablished |
| --- | --- | --- |
| Keras | Backend/NNX and CPU/GPU matrices; Python 3.11 containers; backend config and CUDA requirements; device checks; xdist/integration/multi-device variants; actual main-test and conditional-step conclusions. | NNX skips main tests. CPU applications/wrappers steps were skipped in this run; GPU excludes applications. The documented unfiltered root suite therefore cannot be described as having passed from these results. Resolved dependencies, outputs and hardware receipts are absent. |
| Compose | Source-bound Buildx bake unit target, Go/cgo/race/coverage recipe and caches; distinct E2E mode/engine/store matrix; opposite-mode skips in each E2E job. | The successful Test action may reuse cached BuildKit layers. It does not prove fresh inner Go command execution, exact action context or full repository E2E completion. |
| PhotoCraft | Windows unit/integration partition and doctest condition; font pin/env; corpus fetch/verify/test steps; optional-job skips; exact shared-gate workflow SHA reported by the run. | No full-sweep/GPU/font/corpus branch execution is inferred from run success. The mutable `craft-common-actions@main` gate resolved to a retained historical SHA, but its implementation and nested actions were not fetched. |

This context is additional to the README alone, not necessarily absent from other
maintainer files. The pilot retained those guides/build definitions before mining
CI and did not claim novelty merely because CI repeats them. Both source
representation and GitHub status attribution improve; no consumer acceptance or
high-confidence metadata was minted.

All four selected bounded log requests returned HTTP 403 with “Must have admin
rights to Repository.” These are retained failed observations, not evidence of
log expiry or failed tests. No credentials were inspected, no authentication
escalation was attempted, and no alternative run or revision was used to obtain
logs. There are no retained command outputs or test-count assertions.

The pilot stopped at **22 of 30** permitted read-only public requests, retaining
1,659,744 response bytes, with a 2 MiB metadata/source-response cap and a 5 MiB
log-response cap. No response exceeded its cap. No redirects were followed in the
actual observations. [request-ledger.json](request-ledger.json) records statuses,
selected headers, latency, sizes and body hashes; `raw/` preserves responses and
log errors. The GitHub connector's commit-run wrapper filters to PR events and
lacks a log cap, so the collector used unauthenticated public REST with all-event
exact-SHA filtering. No workflows were dispatched/rerun, project commands executed,
models called or packages installed. Existing hosted CI compute cost, download
charges and end-user savings were not measured; retained request latency/bytes
are acquisition overhead only.

Public workflows and logs remain untrusted data. Source references to optional
Codecov tokens, registry/release secrets and conditional debug tokens are preserved
without values or any inference that they are portable test prerequisites.
Third-party action behavior, mutable images, package indices, caches and services
remain explicit source-closure gaps. The selected workflows contain no explicit
`services:` blocks; Docker engines, GPU runners, corpora, fonts and downloads
still provide external dependencies. This pilot introduces no execution service,
protocol or schema change.

The minimum next evidence step is one exact-run test report/log obtained through
already authorized read access, retaining collection, skip and cache-hit details
and workflow dependency identities. Then independently adjudicate one applicable
task/environment tuple, allowing fallback when source closure is incomplete.
A subsequent consumer experiment should freeze unfamiliar tasks and matched
model/tool/environment/cache settings and randomize access to the qualified
observation. Measure completion/correctness plus total verification, fallback,
maintenance effort and cost. These known cases cannot supply generalization proof.

[source-bindings.json](source-bindings.json) retains all source file hashes and
line counts, along with exact workflow source/run bindings. Some pre-API planned
passage windows extended past short requirements files; the immutable full files
are authoritative and those windows are explicitly clipped to retained line
counts. Command mappings in `observations.json` use exact existing spans.
`raw/collector-executed.py.txt` retains the actual collector used; `collect.py`
received Ruff formatting only afterward. Acquisition drivers were local scratch
scripts; this packet is the complete retained observation, not a new product API.

[checks.json](checks.json) and [freeze.json](freeze.json) bind focused integrity
checks and the final handoff. Nothing here qualifies an instruction for autonomous
execution or demonstrates reduced consumer work.
