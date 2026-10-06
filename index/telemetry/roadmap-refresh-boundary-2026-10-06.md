# Scheduled refresh boundary — October 6, 2026

The scheduled [refresh run](https://github.com/maxwellsantoro/dotrepo/actions/runs/37421585019)
completed its 50-repository batch and machine gates, but the coordinator cancelled
it before landing after reproducing unsupported documentation acceptance.
[The receipt](roadmap-refresh-boundary-2026-10-06.json) retains the exact inputs,
source comparison, pinned-consumer decision and terminal outcomes. This is a new
operating observation; earlier cadence and audit reports remain unchanged.

The batch reported 50 proposed writes, 20 promotions, zero failures, zero model
calls/tokens and a zero adjudication budget. Its original base was `67cff47c`.
Telemetry, index/public checks and base preflight passed; exact-head
[CI 37422301243](https://github.com/maxwellsantoro/dotrepo/actions/runs/37422301243)
also passed on `d733e365`. These gates did not detect the semantic counterexample.

Bitcore's proposed record restored `docs.root = "https://bitcore.io/"`. Its own
assessment said no source declaration was retained: medium confidence,
unspecified method and no source. The refreshed pinned README was byte-identical
to the audited README and did not declare that documentation root. The actual
Rust exporter and immutable `67cff47c` reference consumer accepted the value.
The receipt binds the consumer and source bytes; concurrent fix edits were not
used as evidence for this historical observation.

The refreshed build string remained source-supported, but its execution context
and an unassessed component-test candidate disappeared. Contextual selection
correctly withheld that incomplete build instruction. The bounded comparison
also checked AlphaSeclab and the prompt archive, whose scalar abstentions remained
supported. This three-identity check is not a whole-batch accuracy assessment.

[PR #145](https://github.com/maxwellsantoro/dotrepo/pull/145) was subsequently closed
with its branch and commit preserved. Main stayed at `67cff47c`; none of the
proposed record changes landed, and no hosted publication occurred. Publication
was already disabled pending R2 setup; that was separate from the observed
semantic reason for cancellation. GitHub records cancellation, while this
receipt records the coordinator's stated reason.

The corrective source change preserves declared documentation or abstention
during GitHub metadata merge. The consumer independently requires a fresh,
present, extracted, high-confidence documentation assessment with a retained
source. Positive documentation declarations remain eligible; homepage fallback
requires source inspection. Regenerate future batches from validated current
source rather than rebasing this retained patch.
