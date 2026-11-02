# Retained source cache and three-arm consumer pilot

The opt-in source backend now serves an admission-bound inventory and retained
source passages without GitHub or models on a cache hit. It keeps source bytes
separate from qualified instructions, environment applicability, execution success
and authorization. The public source-only instruction selector is unchanged.

Runtime commit: `52c6a785c07539ec55f602aff7e6daef1bb884d1`.
Protocol checkpoint: `f6bee150` (the comparison spec records its runtime base).
The frozen spec SHA256 is
`672f1e2fa5b3c9f9d3fd722cf94e8bee3385a72b2901ea09a5a1b3ca7bf3f372`.
The database SHA256 is
`5eccd306a9ce43f67ffd2b1a218bdefbc30d2044410c3ef856e00d88e8b93369`.

## Implementation and artifact

The rebuilt artifact contains five repository identities and 57 current component
keys. Four source inventories cover 1,378 tracked blob paths, with 55 retained
bodies totaling 517,294 bytes. The database is 1,040,384 bytes. Legacy iniconfig
observed evidence remains separate; its source inventory is not fabricated.
Local re-admission took 0.356 seconds including the legacy evidence replay, with
zero new publisher requests, model calls or upstream executions. The source
snapshots and original qualification costs were inherited, not free.

Admission binds inventory/body identities to exact repository/revision/tree and
current compiler policy. Serving verifies the record/admission/inventory joins,
SHA256 and path-specific Git blob. Only a genuine miss may reach separately
configured pinned HTTP. Corruption, policy change and identity mismatch refuse.
The common 32 KiB source JSON payload limit now covers cached, direct HTTP,
fallback and unavailable results; the transport envelope is additional. This
intentionally tightens the previous direct HTTP tool's large-output behavior.

The independent implementation reviewer found two output-limit bypasses in the
initial development version. Both were corrected and independently reproduced
as refusals before runtime freeze. The artifact/protocol reviewer then verified
all 23 frozen inputs and reconstructed every source inventory and retained body.
See the two `independent-*-review.txt` reports and
[the operating guide](../../../docs/experimental-repodigest-source-cache.md).

## Fresh consumer observations

Six independent ephemeral CLI sessions requested Luna/max, one session per
repository/arm, with the same prompt and budgets for each target. The direct arm
used pinned HTTP sources with a per-session cache. The source-cache arm added
shared retained source evidence. The knowledge-cache arm added RepoDigest facts
and leads over that identical source cache. No upstream execution endpoint or
shell was available. All six sessions completed and retained native usage.
Independent source/answer review found all six met the critical read-only task requirements; this does not
establish executable procedures or local test success. The exceptiongroup
knowledge answer mixed explanatory labels into command fields, a minor reuse
format limitation. See `independent-consumer-review.txt`.

| Task | Available knowledge | Seconds | Uncached input tokens | Output tokens | Host requests | Host body bytes |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| cattrs | Direct HTTP source | 64.6 | 31,814 | 8,202 | 11 | 118,526 |
| cattrs | Shared source cache | 58.5 | 25,341 | 5,792 | 0 | 0 |
| cattrs | RepoDigest + same cache | 53.5 | 28,007 | 6,970 | 1 | 6,495 |
| exceptiongroup | Direct HTTP source | 98.4 | 30,710 | 10,289 | 4 | 19,688 |
| exceptiongroup | Shared source cache | 67.4 | 17,874 | 6,384 | 1 | 1,377 |
| exceptiongroup | RepoDigest + same cache | 52.3 | 18,330 | 5,601 | 0 | 0 |

Relative to the same source cache, adding RepoDigest knowledge coincided with
8.5% less wall time on cattrs and 22.4% less on exceptiongroup, but 10.5% and 2.6%
more uncached input tokens respectively. These are two descriptive observations,
not average improvements, an isolated causal estimate or production model
qualification. Provider prompt caching, provider latency, task/arm order and
agent trajectories can affect results. This is a bounded read-only source-proxy
investigation task, not unrestricted coding or execution completion.

The two distinct missing source bodies were useful source inspections: exceptiongroup's
`tests/check_types.py` (1,377 bytes) and cattrs'
`tests/test_typing_structure.md` (6,495 bytes). The cattrs HTTP body served three
requested ranges using the session cache; three HTTP-backend route records are
one actual request. Invalid ranges, absent paths and over-limit list requests
remain in the traces. The cattrs direct agent still requested limit 200 despite
the advertised maximum 100, then recovered. Mechanical scores assert only basic
identity/non-execution/completion; independent source/answer review determines
critical task quality. Raw reports are not rewritten by adjudication.

## Cost boundary

Across the two tasks, direct consumers transferred 138,214 body bytes. Shared
source-cache consumers transferred 1,377 bytes; knowledge-plus-cache consumers
transferred 6,495 bytes. Consumer-only figures exclude setup and are not an
all-in economic result.

The inherited acquisition of just these two repositories cost 18 requests and
519,114 body bytes, including evidence not needed for these tasks. Adding that
setup once gives 520,491 bytes for the source-cache cohort and 525,609 bytes for
the knowledge-cache cohort, both greater than the direct cohort's 138,214 bytes.
Charging the whole four-repository bootstrap, demand acquisition and one refresh
adds 1,000,130 bytes instead. There is no demonstrated cold-start publisher-byte
payback in this cohort. We did not continue sampling until payback appeared.

Both cached arms use a common artifact built by the combined semantic/cache
compiler. This does not measure the minimal cost of a standalone source cache or
isolate incremental semantic admission expense. Original observed qualification,
engineering, independent review, maintenance, physical local I/O, optimal HTTP
freshness caching and actual model billing remain unknown rather than zero.
`COST-LEDGER.json` preserves native session counters and these limits; it makes
no actual dollar-cost claim.

## Counterfactual replay

The 12 historical source-request trajectories contained 168 calls. Replaying
those exact calls over the enriched artifact returned 85 from the compiled
cache, preserved six originally invalid calls as refusals, and verified retained
body equality wherever applicable. Their original host bodies totaled 3,167,834
bytes; counterfactual fallback bodies totaled 1,208,311 bytes. No network was
used for replay. Later demand evidence was present in the replay artifact even
for early sessions; this is an engineering cache-coverage check, not retroactive
consumer productivity or a claim that the early index already had that evidence.

## Validation and limits

The runtime passed 1,212 Python tests, 672 Rust workspace tests, formatting,
Clippy, cargo-deny, version/manifest checks, the operator gate and the full local
release gate including VSIX. Focused independent checks and synthetic
counterexamples cover corruption, cross-identity/Git bindings, misses, payload
bounds, LRU eviction and stdio tool isolation. Local validation is on macOS;
Linux/Windows CI has not been run and nothing was pushed. Detailed receipts are
under `validation/`.

This preserves a useful source-serving improvement and an honest signal about
knowledge reuse. The source-cache-only arm already showed lower consumer transfer,
time and uncached input than direct HTTP in these two trajectories; those
differences are not a causal decomposition. RepoDigest's additional facts did not
reduce token use against that control in this pilot. Further work should improve compact, task-relevant facts and test
repeat use on real tasks rather than expand qualification rules or infer broad
benefit from these six observations. Existing public/F-05 gates, historical
failures and PageDigest's unsuccessful P1 result remain unchanged.
