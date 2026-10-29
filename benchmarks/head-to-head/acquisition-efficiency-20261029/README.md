# Bounded acquisition efficiency — October 29

The first generic optimization reuses one successfully decoded recursive Git tree across existing language selectors within a single repository-file fetch. It changes neither discovery selection nor the public protocol. Owned controls establish selected path/body/order parity and reduce two tree requests to one for the mixed-language fixture. **The full frozen 100-repository comparison has not run; no upstream latency, total-cost or 10–15-request target is established here.**

## Implementation and independent controls

The cache is local to `fetch_repository_files`; subsequent calls, repositories and refs fetch afresh. It is lazy and reuses decoded empty successes. A 404 is not cached, preserving a later selector's chance to observe success. Fetched malformed/500 responses retain fatal handling. Root probes, limits, ranking, raw-file retrieval and all four discovery selectors remain intact. Removed later requests naturally cannot observe later transient/moving-ref changes; the parity contract is identical data at a fixed revision.

The [author handoff](tree-reuse/README.md) retains the initial owned-fixture failure, corrected baseline and final results. The [independent review](tree-reuse-review/report.json) passes nineteen focused GitHub tests, including seven new owned-localhost controls. Its request and byte assertions use known Content-Length fixtures; they do not establish complete upstream transfer accounting. No production source-selection, confidence, authority, inference route, writeback or instruction-acceptance policy changed.

The unit-cost renderer now states its existing limits: `improved` is a status-change proxy, unchanged rows exclude refresh planning/head costs, and Content-Length bytes can omit transfers with missing headers. Numeric telemetry/schema values remain unchanged. The hotspot retain rationale covers this bounded loading deduplication; new materialization/API features still need the documented focused split.

## Frozen comparison population and inputs

The [cohort](cohort/cohort.json) fixes 100 distinct indexed GitHub repositories and recorded revisions: 25 each from Rust, Python, JavaScript/TypeScript and Go. The declared hash ranking uses primary-language/revision/identity eligibility before comparison, without field-quality or acquisition-outcome selection. E1/F-05 evaluation identities and exposed Compose/Keras/Zellij development cases are excluded. Failures remain assigned without replacement. This is a stratified indexed population, not a fresh blind usefulness holdout.

The [independent cohort audit](cohort-review/report.json) reproduces all 615 input hashes, the exclusion union, eligible pools, rank ordering and all 100 record/revision bindings. Recorded revisions are provenance inputs, not fresh inspection or a guarantee of source availability. `language-inputs.json` additionally freezes the complete language arrays from those exact records for both variants. It supplies the existing acquisition API's language-hint input without inventing GitHub byte counts or fetching different current metadata in each arm.

## Remaining empirical work

The [measurement assessment](measurement/assessment.json) identifies a minimal experiment-only in-crate helper using the existing exact-SHA acquisition API; the ordinary CLI captures current heads and cannot stand in for this comparison. No production revision flag or general execution platform is required. The language-array input gap named in that assessment is now closed by the separately bound recorded input above.

The helper and measurement enforcement remain unimplemented. Before a live comparison, bind exact baseline/revised binaries, cache conditions/order and finite request/byte/output/time stops; preserve failures, partial transfers, retries and all 100 assigned opportunities. Measure acquisition and refresh-planning costs separately, including failed phases. Attempted requests, actual body bytes and partial failures need adequate observation; existing received-response/Content-Length counters alone are insufficient. The assessment's numeric bounds are prospective ceilings, not enforced limits or live-run authorization.

The full acceptance target also includes source opportunities, selected bytes, field dispositions, context/prerequisite recovery and newly missing/incorrect facts. An acquisition-only loop does not close that target: use the existing materializer/importer on the paired captured inputs, with fixed timestamps and identical policy, and retain source/extraction differences for adjudication. No upstream command execution or model call is needed to test acquisition/extraction parity. Cold/warm conditions cannot be inferred merely from running two fresh processes, because this cache exists only within each invocation.

This packet advances request reuse and freezes comparison inputs. It leaves the 100-repository experiment and its end-to-end cost targets open. F-05 remains at its separately recorded C1 no-go; no autonomous paid sessions or environment preparation are reopened.
