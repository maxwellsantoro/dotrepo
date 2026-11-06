# Native agent-token comparison — November 6, 2026

**Decision: retain the ordinary-note baseline for this measured workload.** The
new selected-finding recall is independently accepted engineering, but this
paired observation does not meet the predeclared savings rule. Do not infer an
agent-cost advantage from fewer source passages or successful tests.

The experimental source candidate is `67d6aed5f807df05fcbd8c70f20a83351a0cd8d8`.
It adds read-only `decision_findings.py recall`, combining one selected finding
with existing recipient-policy and source checks. Original dates, unknowns,
changed evidence and explicit semantic review remain intact. This is not a
package release.

## Matched task and quality

Fresh native Codex sessions used the recorded GPT-6.1 Sol / High configuration,
the same cached umbrella-site sources and equivalent validation primitives.
Each reader authored its own ordinary note initially. The product returned a
source-bound finding on revisit; the baseline retained its note and the same
source/validation opportunities. Neither reader was forced to reread everything.

The task covered the production build command, persistent PageDigest state,
publication boundary, manifest coverage, served-byte verification and limits on
deployment/savings claims. A return session handled unchanged, synthetic relevant
change, contextual change and missing/stale cases. All five answers per arm
passed independent cost-blind quality/freshness grading. Original dates stayed
intact under the same 3,600-second source-age bound; matching bytes never approved
an interpretation automatically.

## Actual native usage

These are native `turn.completed.usage` counters, not text-size estimates.
Cached input is part of input. **U = input − cached input + output**;
**total = input + output**. Reasoning output is already included in output.

| Phase / arm | Input | Cached input | Output | U | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Initial baseline | 149,155 | 119,168 | 2,524 | 32,511 | 151,679 |
| Initial product | 149,626 | 96,640 | 2,480 | 55,466 | 152,106 |
| Return baseline | 222,723 | 177,280 | 5,894 | 51,337 | 228,617 |
| Return product | 178,614 | 135,808 | 5,636 | 48,442 | 184,250 |
| **Initial + return baseline** | **371,878** | **296,448** | **8,418** | **83,848** | **380,296** |
| **Initial + return product** | **328,240** | **232,448** | **8,116** | **103,908** | **336,356** |

The product used **11.6% fewer total tokens but 23.9% more U** overall. Return-only
totals fell 19.4% and U fell 5.6%. The frozen rule required complete matched
quality, at least 10% lower initial-plus-return U and no increase in total tokens;
it was not met. Initial prompts were identical and native input totals were
close, while cached input differed by 22,528 tokens. This does not establish
that recall caused the initial difference. Same source caches do not guarantee
equal provider prompt-cache reuse.

On return the product made 5 observed commands versus 8 and read 10,494 explicitly
metered source-body bytes versus 31,042. Both readers called recall twice, with
the second call applying their own JSON projection. The first product response
was smaller (46,764 versus 48,184 bytes), but its reader's broader second projection
made aggregate observed recall output larger: 62,163 versus 54,531 bytes. Both
arms retained identical metered database/blob/index validation work. This points
to caller projection and repeated inspection as investigation targets; it does
not establish that the raw interface produced more bytes or caused native usage.
Ordinary shell reads and non-JSON helper output are incompletely metered; repeat
calls alone do not establish output truncation.

## Preserved failures and limits

The original read-only runtime had uv temporary-write failures and a Python
fallback missing a dependency. All four initial readers across both products
recovered and read verified sources; their original answers and full costs remain.
All four return arms were then run through the same independently verified pinned
interpreter. No semantic answer repair or favorable-run selection occurred.

Three original return attempts and two calibrations remain separate study
overhead: 937,025 total native tokens / 230,209 U. All 11 primary attempts and
two calibrations together used 2,171,170 total / 535,714 U. Those are totals for
the two-product instrumented study, not complete program economics. The amended
pair is not a clean initial-runtime replication. Provider caching and reader
trajectory vary; one pair supplies no confidence interval or causal/general claim.

No new remote source acquisition occurred in this cached engineering replay.
Original acquisition, publisher upkeep, human attention and implementation/
coordination/grading tokens remain unknown. No total-program or monetary saving
is claimed. Earlier D2/D4 and pilot observations remain frozen.

The [batch acceptance record](/Users/maxwell/Documents/Codex/2026-11-06/task/measured-savings/acceptance/report.md)
links immutable protocols, every raw attempt, runtime corrections, independent
[quality grading](/Users/maxwell/Documents/Codex/2026-11-06/task/measured-savings/acceptance/review/quality-review.md)
and [native reconciliation](/Users/maxwell/Documents/Codex/2026-11-06/task/measured-savings/acceptance/review/native-cost-review.md).
[Native counters](/Users/maxwell/Documents/Codex/2026-11-06/task/measured-savings/acceptance/evaluation/native-costs.json)
retain reasoning/cache-write fields and the separate local-read layers.
