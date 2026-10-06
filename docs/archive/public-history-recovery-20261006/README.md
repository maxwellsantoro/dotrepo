# Published history recovery — October 6, 2026

The retained public log advertises twelve published snapshots. Deployment run
[37406801959](https://github.com/maxwellsantoro/dotrepo/actions/runs/37406801959)
succeeded without an archive upload or Worker archive binding. Older identities,
including the contextual study snapshot, had left the two-snapshot static edge
and returned 404. This is a delivery gap, not a reason to rewrite the log or
historical study outcomes.

`published-log.json` retains the observed log bytes. `plan.json` binds their hash,
the immutable index revision for each source digest, and each snapshot's original
successful deployment revision/run. Runtime binaries are built from those source
revisions with their locked dependencies, then hashed into the recovery receipt.
An exporter built from a newer revision is insufficient: snapshot identity binds
index/timestamp inputs, not the rendering implementation.

The plan includes independently retained byte anchors for the first snapshot's
complete file manifest and four contextual-study profiles. Recovery validates
every produced manifest leaf, exact snapshot identity/digest/timestamp/counts,
and those anchors before exposing the output directory. Original source pins and
reconstruction are distinct from independently observed historical bytes; only
the declared anchors provide the latter. No packet, source revision or history
entry is changed.

The manual `public-archive-recovery` workflow uses this frozen plan. It runs on
the default branch, serializes with ordinary publication, checks archive account
access before historical builds and reconstruction, provisions only the
declared bucket after a successful account listing, uploads validated public
payloads with bounded concurrency, and commits the merged log last. Private
`query-input` files are excluded. Authentication failures and incomplete payloads
remain failures. CI artifacts retain the runtime plan, payloads and receipt;
they supplement the persistent archive rather than replacing it.

Operational closure requires successful recovery/upload, a deployment with the
matching `SNAPSHOT_ARCHIVE` binding, and live retrieval of older logged identities
after edge eviction. The initial upload has tens of thousands of objects; pinned
Wrangler rate limiting can make it take roughly two hours. That estimate comes
from its implementation, not an observed successful cloud upload or cost study.

The [operating checkpoint](operating-checkpoint.md) retains the merged validation
and actual account-setup refusal separately from this frozen reconstruction plan.
