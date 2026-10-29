# Go01 amendment 2: source adapter and synthetic scorer preparation

This append-only packet implements the prospective decision `22e72402…` and its
independent review `f1e7ff04…` for preparation only. It freezes the complete canonical
source-expectation map and a post-run scorer successor. **The actual oracle join is
OPEN. No task, oracle, campaign, cache or execution admission is granted.**
All older source, oracle, policy, result and review packets remain unchanged.

`derive.py` verifies eleven pinned source/result/review owners, imports only the
hash-bound retained result verifier's pure data operations, rechecks the actual
owned registry and selection, and derives `expected-map.json`. This 242,536-byte
canonical map at SHA256
`768482aa2dcec46151e529a1126a8d74fbaba56f168d86c915002aa70d869e4a`
contains all 104 intended packages and 5,972 exact top-level Test/Example/Fuzz names.
Its serialization is UTF-8 sorted-key compact `json.dumps`, ASCII escapes, finite
JSON only, with no trailing LF. `expectation.json` binds the source subject, map,
package/file selection, image/Go/target context and the open capture dependency.
The actual 6,031 declaration population also includes 48 benchmarks and 11
TestMain wrappers; neither group is promoted to required case events. The helper's
CGO=0/GOWORK=off build remains distinct from the target selection context.

Forty packages have empty required-name arrays. The native file inventory says 39
have no selected TestGoFiles/XTestGoFiles. These are source-derived facts; **only
18 no-test diagnostics were observed in the earlier partial native listing**.
All 104 packages need package-level coverage. The successor refuses a synthetic
`[no test files]` skip for the zero-name package which has selected test source.
It retains source-only/unvalidated status for the 61 earlier failed packages.

## Scorer boundary

`oracle.py` copies amendment 1's hierarchy/lifecycle, exact exclusion policy and
assertion/process checks, replacing the native-manifest origin check with an
explicit `source-expectation-frozen-before-execution` state, exact full-map and
source-subject matching. It neither labels this data native collection nor accepts
a reduced package/name set. The lifecycle difference is only the stricter zero-name
package check above. `oracle.diff` retains the complete source delta; `verify.py`
compares the lifecycle AST and the unchanged skip and assertion/process sections.

Synthetic evaluation requires explicit synthetic context/capture fixtures, complete
full-scope events and matching hashes. Those fixtures exercise consistency; they
are never an origin-authentication claim. All synthetic results keep
`taskOutcomeObserved`, `oracleQualified`, `campaignAdmitted` and
`nativeCollectionOccurred` false, including candidate-complete traces.
**Actual evaluation always returns `reviewed-full-task-capture-join-unavailable`.**
Supplied setup/events booleans or a well-shaped hashed capture JSON cannot override
that refusal. There is no allow-incomplete mode or runtime authorization here.

The exact full Hereby/default command, normal setup and skip policy remain owned by
the original contracts. No direct Go command or no-npm variant substitutes for the
full task. Dynamic children/fuzz seeds are not enumerated by the source registry
or by native listing; every observed descendant still requires coherent lifecycle
and the original exact skip policy. No new skip exclusions are accepted.

## Concrete capture dependency

Read-only boundary tracing found that current `bench/agent_runtime.py` shell
operations retain argv, stdout/stderr and exit/error, but have no atomic event-file
capture/export association. Historical `qualify.py` reads the JSON file later;
its bytes and sequence alone do not bind full-wrapper/setup/tool/context origin.
The source-owned gotestsum writes scanned events to JSONFILE, which explains the
intended producer but does not authenticate an arbitrary supplied file.

The immutable capture assessment is bound in `capture-dependency.json` at
FREEZE `5cdae83d1f32a34d17f69f960fb68c2759a21636f8d5d66e203b2fc02b023016`.
The smallest later integration is an extension of that existing host-owned shell
operation: baseline a fresh fixed event path; retain the exact chosen operation's
setup/source/tool/effective-context and invocation; after it ends, export bounded
raw bytes/hash/stat before returning control to the agent; freeze completeness,
time/resource/after-check and cleanup association. The scorer checks command and
scope afterward; hidden gold must never gate the agent's choices. This is operator
consistency within the inspected source/process boundary, not a proof against an
actively adversarial same-UID test process. Exact event transport/cap and the join
descriptor need separate review; this packet implements no executor or descriptor.

A known build failure can remain noncompletion without a green baseline. Missing
capture/oracle plumbing is a preparation gap, not proof of upstream failure. All
prior compiler-killed observations remain unchanged, with cause unknown.

## Checks and reproduction

All commands below perform owned local Python/data operations only:

```sh
uv run python -B benchmarks/head-to-head/f05-go01-oracle-preparation-20261029/amendment-2/derive.py --output /tmp/FRESH-UNUSED-source-expectation
uv run python -B benchmarks/head-to-head/f05-go01-oracle-preparation-20261029/amendment-2/verify.py
uv run python -B benchmarks/head-to-head/f05-go01-oracle-preparation-20261029/amendment-2/controls.py --output /tmp/FRESH-UNUSED-source-oracle-controls.json
```

The derivation creates a fresh directory; controls create their report exclusively.
Forty-four synthetic/data controls pass: full map pass, complete assertion failure,
nested lifecycle, exact existing skip/bare-skip positives, missing/edited source,
wrong selection/image/command, package/name loss, benchmark/wrapper promotion,
unexpected skips, build-killed and incomplete setup, listing-only, forged file
fixture and actual-evaluation refusal. Ruff check/format passed without cache.
`development-observations.json` preserves the two local path mistakes and the
format-sensitive comparison correction. The unmodified original data and complete
map were rechecked after corrections. No Go, Node, daemon, network, package,
provider, model or task execution occurred for this amendment. Prior author context
is disclosed: this is known-workload preparation, not holdout or consumer evidence.
Independent implementation review and a concrete capture join precede usability.
