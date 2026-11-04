# Measurement review — November 3, 2026

The release's field-presence gate does not measure the project's objective:
useful, trustworthy repository understanding per unit of combined publisher,
indexer and consumer work. It is a deterministic regression control. The
available consumer studies have not established an all-in economic benefit.
Passing implementation gates must not be described as closing that gap.

## What the failed gate actually found

The first follow-up export at `2026-11-04T02:29:14Z` failed the existing 0.47
floor: 1,161 / 2,472 synthetic field bundles were complete (0.469660).
Before this packet, all 615 repositories at commit
`303ed90a6e052a017f0daa87ec776dcc805b3531` supplied 1,157 / 2,460 (0.470325).
The three additions supplied four / twelve. No old index record changed.
There were more complete bundles, with a lower average on a different population.
That alone is not evidence of a product regression, nor evidence of a benefit.

The original failed export, workload, timings and report remain under the local
`task/not-done` acceptance directory and `/tmp/lc-notdone-release-20261103/`.
The unsuccessful additional docs-file fetches remain in the crawl receipts;
they did not establish a documentation answer. They are not silently counted as
successful extraction or free work. No documentation values were added to clear
the threshold. General index growth remains zero; this was a named exception.

## What this measure rewards and misses

`build_public_lookup_workload.py --mode research` asks every indexed repository
the same four bundles. It selects repositories from the catalog itself, so an
unindexed project never enters its denominator. Each intent has equal weight,
without observed demand or an applicability judgment. For example, CPython's
overview fails solely because topics are empty, although its other requested
overview fields are present. That is not a test of whether someone understood
Python well enough to make their requested decision. A docs-only project also
gets asked for both build and test commands.

`measure_public_lookup_efficiency.py` treats any nonempty value as answered.
An inferred command or a wrong nonempty string can improve its score. It does
not consult source status, consumer policy, required context, factual accuracy,
freshness, actual execution or a completed decision. Filling a field to improve
this number is therefore the wrong optimization target. Honest abstention can
be better than a populated answer; universal abstention also fails the goal.
Both need independently justified expected outcomes to distinguish them.

The same export's reference-consumer report makes the distinction concrete:

| Measure | Result | What it establishes |
| --- | ---: | --- |
| Build and test fields present | 311 / 618 | Two nonempty values |
| Build and test accepted by scalar policy | 124 / 618 | Required extraction metadata and age pass the current policy |
| Complete root contextual build and test instructions accepted | 0 / 618 | No accepted pair with the required directory, scope, prerequisites and source |
| Documentation accepted by policy | 145 / 618 | Current source-declaration policy passes |
| Independent correctness and completed tasks in this report | Unmeasured | Neither is inferred from acceptance |

These are dated observations, not permanent catalog statistics. Missing root
instructions do not invalidate factual discovery or a preliminary selection.
Conversely, a scalar command pair is not a complete executable procedure.

The request comparison models 13 batched lookups against 1,236 local
record/evidence file fetches. It does not observe either consumer trajectory,
fallback or ordinary caching. The byte comparison counts public profile plus
query-input artifacts (7,090,044 bytes) against already normalized local
record/evidence (3,030,363 bytes), not two workflows producing equivalent
answers. It cannot establish network, token, latency or all-in savings. Padding
the proxy could improve the ratio without helping anyone. Legacy savings
fields clamp penalties to zero; signed differences now preserve them too.

## What the stronger evidence says

- The [twelve-session selection study](research-evidence-20261030/selection-results.md.txt)
  delivered three accepted treatment decisions and two control decisions; seven
  attempts were incomplete. In the two mutually completed pairs, treatment
  returned less source text but used 9.3% more native tokens. Whole-study cost
  remains unknown because incomplete sessions lack usage receipts. Incomplete
  attempts were not successful abstentions.
- The [corrected Discovery-100 comparison](research-evidence-20261030/discovery100-correction.md.txt)
  found the same supported recall with 86% more response tokens from enriched
  search. Cheap metadata discovery followed by selective evidence inspection is
  the current direction; expanding semantic search has not earned its cost.
- The [same-source-cache pilot](research-evidence-20261030/source-cache-readme.md.txt)
  did not establish an incremental semantic-cache token win. Including retained
  acquisition once reversed the consumer-only byte advantage in that cohort.
  Warm consumer hits are useful observations, not a cold-start payback proof.
- The [factual-accuracy suites](public-factual-accuracy-benchmark.md) test a
  curated 20-assertion regression pack and a dated independent 119-assertion,
  31-repository structured sample. Their scope does not cover all requirements,
  all catalog records or end-to-end decisions. Some expectations in the legacy
  pack are importer defaults, which test output stability rather than independent
  command applicability. Neither pack substitutes for source/answer review.

The implementation does useful work: exact source retention, bounded fallback,
explicit unknowns, source-backed assessments, invalidation and decision accounting.
The evidence supports those capabilities and some avoided source reading. It
does not yet establish that the project reduces total work at matched quality
and freshness. General growth and paid campaigns must not follow from more
fields, passing tests or a green presence gate.

## Changes to release measurement

The full catalog report still contains every repository, its complete denominator,
misses, per-intent counts and costs. Its moving-population presence rates are
diagnostics, rather than release floors. A separate frozen control contains
**every** pre-packet identity, not a favorable subset. The existing numeric
presence, intent and payload floors apply there. Missing repositories stay in
that fixed denominator. This separates population expansion from old-cohort
regression without lowering the old floors or promoting inferred values.

This cohort was frozen after the failure was observed. It is an engineering
regression baseline, explicitly not a preregistered or held-out benefit study.
Changing it requires a documented reason; it must not roll forward automatically
to absorb regressions. Validity, source policy, sampled accuracy, freshness,
conflict, delivery and normal CI checks continue to gate their own contracts.
Correcting a false field may legitimately reduce presence and requires an
explicit source-grounded baseline review; inventing a value is never a repair.

## Measuring the larger goal

Keep the following evidence separate rather than inventing one weighted score:

| Question | Appropriate observation |
| --- | --- |
| Can a consumer find relevant projects? | Tasks chosen before coverage inspection; relevant recall, irrelevant work, absent projects and exhausted searches retained |
| Can they finish the requested decision? | Independently source-judged supported choice or useful scoped none-established; errors, unsupported confidence and unfinished attempts retained |
| Is reuse valid now? | Declared task age target; unchanged, changed, missing and contradictory dependencies; source status distinct from interpretive correctness |
| Does participation repay its work? | Setup and ordinary update from publisher-owned sources; duplicate edits, interventions, ambiguity and maintenance recorded |
| Is less combined work required? | Paired competent metadata/source-cache baseline, same sources/tools/output rubric and freshness; actual acquisition, fallback, audits, review and update work in both arms |

The next benefit evaluation should freeze a small task set before inspecting
answers, include a repeated investigation and a source change, and stop at a
declared budget. Keep all attempts in the denominator. Compare semantic findings
against the **same** source cache so ordinary caching is not credited to semantic
interpretation. Include publisher/indexer setup and update work once, and report
allocation against observed reuse separately. Do not extrapolate a hypothetical
break-even count. Hold quality and freshness constant before comparing cost.

Report requests, bytes, CPU, wall time, native tokens, human interventions and
money separately. Missing usage is unknown. Source accuracy and useful completion
are required alongside savings, so neither confident fabrication nor universal
abstention can win. This review authorizes no new paid campaign or broader crawl.
