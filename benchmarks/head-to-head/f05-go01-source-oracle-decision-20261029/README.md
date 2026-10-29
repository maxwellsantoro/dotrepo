# Go01 prospective source-expectation oracle decision

Decision: prepare a narrowly scoped successor oracle that can use the observed,
reviewed source registry instead of requiring a successful separate native listing.
Do not admit it or change today's gate. This is a prospective assessment of a known
workload with extensive author context, not an independent consumer evaluation.

The observed helper result and its independent review now establish something the
previous source-only proposal lacked: the actual owned tool produced a bounded,
source-position-checked registry for the exact 104 packages selected by the retained
native `go list`. Its 6,031 declarations are **not** 6,031 required executing tests.
The unchanged oracle's top-level Test/Example/Fuzz kinds give 5,972 candidate event
names: 5,966 tests, zero examples, six fuzz functions. Forty packages have no names
in those kinds and must still receive package-level coverage. The 48 benchmarks
are diagnostic inventory, not an added benchmark task; the 11 TestMain wrappers
are not case-event identities. The physical declaration IDs are provenance IDs,
not Go runtime names. `expectation-recipe.json` binds the exact derivation and
per-package counts/name hashes; a future implementation must freeze the complete
242,536-byte canonical map, not accept this summary as an execution manifest.

## What can change and what must remain

The current oracle explicitly requires a complete native collection, so merely
setting that state on this registry would be false. Its successor must use an
explicitly different source-expectation state and bind the result/review/selection
subjects before execution. The former successful-list requirement can be replaced
by this source expectation plus **actual full-task runtime evidence**. A source
function can fail type checking or otherwise fail to become runnable; such a run
cannot satisfy the oracle's required events. An unknown source-discovery or
selection inconsistency must remain unresolved rather than reducing expectations.
The 61 failed native-listing packages remain uncompiled and unvalidated until any
future real task observes them; no pre-acceptance claim is justified.

Keep the original repository, revision, default task and normal setup. The exact
full command remains
`GOTESTSUM_JSONFILE=/workspace/go-test-events.jsonl GOFLAGS="-p=1 -count=1" npx hereby test`.
The retained Hereby source binds `test` to `test:tsc` (1046–1062), `runTests` to
`./...` from `./tsc` (983–1009), default test flags/environment (876–910), and the
source-owned offline gotestsum build through `tools` (1173–1218). No direct `go test`,
listing command, prebuilt helper, no-npm variant, package filter, or `test:all`
substitutes for this task. Normal npm setup has reviewed observations; that does
not establish the full wrapper, tool build or all dependency outcomes.

Keep all existing all-depth event and scoring requirements: exact intended
packages, nonempty active coverage, required top-level run/terminal events,
complete observed descendants, ancestor lifetime/failure consistency, no duplicate
or truncated events, no unexpected skips, exact approved skip conditions and
witnessed reasons, consistent package/wrapper exits, and rejection of build,
resource, runtime or transport failures as completed test outcomes. Complete
assertion-failure outcomes may still count as an observed task outcome with
`testsPassed=false` only when all required active coverage finishes.

Native listing never enumerated dynamic children or fuzz seeds. The existing
oracle already checks every **observed** descendant, rather than proving all
possible descendants ran. The registry introduces no warrant to weaken that rule
or to claim exhaustive dynamic coverage. Literal-slash hierarchy ambiguity,
capability skips, conditional fixture/config cases, TestMain effects and the
excluded-child-only limitation remain as previously documented. Unexpected or
unadjudicable cases remain noncompletion/unresolved; do not create skip exclusions
from failures. The 380-entry source exclusion proposal still needs explicit
acceptance; this assessment accepts none of it.

## Concrete requirements before a successor is usable

1. Bind the complete expected-name map and all 104 packages to the reviewed actual
   gzip/result, native package/file selection, selected source bytes, source
   archive, exact Go/image identity and target selection context. Retain every
   package including the forty with no required top-level names. Reconcile the
   full wrapper's effective flags, cwd and environment with that selection;
   selection-affecting changes require new selection/expectations. The helper's
   CGO=0/GOWORK=off compilation context cannot replace target CGO=1/workspace
   context. Harmless representation differences must be explicit, not hash-equal
   by assertion. Preserve tool/source integrity with allowed generated outputs
   declared separately from selected source/config changes.
2. Bind actual full-command/setup receipts and trustworthy event capture outside
   agent control. A hash of an agent-writable GOTESTSUM_JSONFILE, supplied JSON,
   printed name, or internally consistent receipt alone does not authenticate a
   run. Reuse the existing capture/isolation boundary and source-owned wrapper;
   freeze its effective tool/provenance and capture association. If that boundary
   cannot establish the file's origin/completeness, leave the oracle unavailable
   rather than adding a new execution platform. Gold and scorer remain hidden;
   runtime permissions cannot consult the hidden expected command.
3. Independently review and freeze the successor scorer, explicit skip policy,
   matching context, error taxonomy, resource/output limits and symmetric retry
   rules before sessions. Actual wrapper/tool compilation may fail in the first
   authorized task attempt; no separate successful baseline is required merely
   to prove those dependencies can succeed. Safety, bounded execution and honest
   failure scoring must be ready before allowing that attempt.

A small implementation packet suffices: an append-only Python post-run oracle
successor and derivation adapter consuming the frozen registry, existing native
inventory and full-command receipts; focused synthetic controls; independent
review. Reuse the hierarchy/lifecycle checks. Replace only the manifest-origin
predicate and its bindings, not the task or skip semantics. No new Go helper,
executor, environment reproduction service, cache or protocol is proposed. A
separate runtime integration patch is needed only for a concrete missing capture
binding found while joining the existing wrapper receipts; it is not authorized
by this decision.

Controls must reject stale/partial or edited registries, wrong package/file/context
selection, missing/unexpected top-level identities, benchmark/TestMain promotion,
listing-only or forged-file evidence, missing/late descendants, widened skips,
build-killed streams represented as completed failures, and passing flags despite
missing packages. Synthetic complete pass and complete assertion-failure traces
must remain distinct from actual outcomes; every synthetic task flag stays false.

## Known failed baseline and C1

C1 requires frozen conditions and a usable completion/error oracle, not passing
native baselines (`ROADMAP.md:152–157`; F-05 specification, Observation and analysis).
The known compiler-killed attempt may remain a frozen unavailable/incomplete
condition, with cause unknown and no resource retry. Reporting that blocker can be
correct agent behavior while the task remains noncompleted. Preserve all assigned
sessions, costs and failures with equal permissions and stop/retry rules. Do not
turn an unresolved oracle or owned harness bug into evidence of upstream failure.
A source-expectation successor could make that failure class scorable without a
successful native listing; it cannot make the failed run complete.

No current qualification/admission flags change. This assessment performed only
local source/hash/JSON checks; no daemon, Go, Node, package, native, network or
provider actions ran. Existing author/independent result review boundaries are
preserved. Coordinator acceptance, implementation controls, independent review,
and the remaining shared C1 freeze precede any campaign.

## Retained source owners

`source-bindings.json` pins the source versions read here. The principal contracts
are the original oracle README lines 73–105 and amendment-1 implementation; the
amendment README's excluded-child/collection limitations; the F-05 specification
lines 49–76 and 98–104; retained Hereby spans; actual registry result and independent
review. Historical source-only statements remain dated evidence and are not
rewritten to describe the later owned-helper execution.
