# October 27 structured metadata recapture

This packet replays 31 of the 32 identities frozen in
`../upstream-2026-10-04/identities.txt`. Identity selection was not re-opened.
The one exclusion is `SolaceLabs/solace-agent-mesh`: the repository moved to
`SolaceProducts/solace-agent-mesh` (same GitHub repository ID 914964527; see
`index/identity-migrations.json`). The destination was freshly crawled, the
old overlay removed, and the moved identity leaves this cohort rather than
asserting facts under a stale identity. It is a repeated source check on a
known cohort, not a new independent holdout, command evaluation, or completed
consumer-task measurement.

Each repository JSON retains the relevant GitHub API metadata and check time.
`workload.json` contains 119 exact-value assertions derived from those upstream
responses without reading dotrepo's asserted values.

Why this packet exists: after the 2026-10-27 full-index catch-up refresh, the
October 4 frozen capture failed on exactly two assertions, and in both cases
the refreshed record was right and the frozen capture was stale —
`InsertKoinIO/koin` shortened its upstream description, and
`microsoft/computervision-recipes` was archived upstream. Previous captures
remain frozen as historical evidence; the release gate now points here.

An exact match to these API fields does not establish command usefulness,
abstention calibration, factual coverage beyond this cohort, or independent
consumer adoption.
