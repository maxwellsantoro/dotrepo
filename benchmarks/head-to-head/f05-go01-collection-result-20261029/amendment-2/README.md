# Appended Go01 result: attempted collection with compiler kills

Run 4 is **incomplete**. Go environment preflight and the 104-package inventory
passed under the separately reviewed driver amendment 3. The actual command
`go test -json -list . ./...` then ran and exited 1 after
195.7369840000756 seconds. The attempt finished in 215.05245641618967 seconds,
including same-attempt cleanup. It was not cancelled or stopped by a recorded
wall-time or output cap. No retry is authorized by this result packet.

The lossless raw collection output is retained at
`evidence/logs/go-test-list/stdout.bin`: 127,015 stdout bytes, zero stderr bytes,
and 732 JSON events. The action counts are 2 `build-output`, 2 `build-fail`,
104 `start`, 520 `output`, 61 `fail`, 25 `pass` and 18 `skip`. All 104 packages
have package terminals, but the failures prevent complete test identity
collection. A package terminal during listing is not a test/task result. The
25 listing passes and 18 skips do not establish passed tests or accepted
exclusions. There are no observed per-test `Test` events.

Two build diagnostics report `/usr/local/go/pkg/tool/linux_arm64/compile:
signal: killed`, for `internal/compiler` in the `cmd/tsc` build variant and
`internal/ast`. The termination cause is **unresolved**. No cgroup OOM/kill
counters or final container inspection were retained, so OOM is not proved.
The initial 4 GiB resource policy is an observed bound, not a cause diagnosis.

`nativeCollectionAttempted=true` is preserved. The command permits compilation,
package initialization and TestMain; those may have occurred before or alongside
failure, and some binaries reached listing terminals. Their exact extent is
unresolved. `nativeCollectionOccurred=false` means complete collection was not
observed; it must not be read as proof that initialization never happened.
No test-body/default Hereby task execution was authorized or observed, and no
task outcome or campaign qualification follows from this attempt.

`package-inventory.json` preserves the successfully parsed 104-package inventory.
The nonzero collection command threw before the driver wrote a canonical
`collection-events.jsonl` or `collection-manifest.json`; its full partial raw
stdout is nevertheless retained in the original receipt triplet. No full native
collection manifest exists. Source/tool after checks and final isolation
inspection were not reached, so whole-run integrity remains unestablished.

Source, image, Go-only projection, container environment, directory, commands and
limits remain unchanged from the prior plans. The source-supported package parser
amendment is prospective and has its own author/review/acceptance/authorization
bindings. The original parent freeze and previous result child remain unchanged:
91 parent artifacts and 87 previous-child artifacts are checked by this verifier.

The 17 daemon receipts account for 585,257,959 stdin bytes and 869,478 raw output
bytes. Cleanup took 0.9095162919256836 seconds and force removal exited 0. The
same attempt's subsequent inspect and responsive name-list report absence.
There is no independent absence observation. Dollar cost stays `null`; broader
preparation, coordination and review effort is unmeasured. `report.json` also
retains total preparation accounting across all four invocations without calling
it a consumer comparison.

All 86 original observation, authorization and relevant reviewed closure files
(3,362,273 bytes) are copied byte-for-byte in `origin-ledger.json`. The outer
stdout is preserved; coordinator exit/session information is a labeled message
transcription, not an unavailable complete outer invocation receipt. Source,
cache and generated build artifacts are not exported. This packager performed
no daemon, Go, package, network, model-provider or upstream action.

Read-only checks:

```sh
uv run python benchmarks/head-to-head/f05-go01-collection-result-20261029/amendment-2/verify.py --input-archives
uv run python benchmarks/head-to-head/f05-go01-collection-result-20261029/amendment-2/controls.py
```

The verifier checks preserved bytes/current review and authorization subjects,
all 17 receipt/raw pairs, initial isolation/environment/resources/source/tools,
the 104-package inventory using the frozen owned parser, package scope/action
counts, unknown termination cause and same-attempt cleanup. It imports only
hash-bound owned static verification/parsing code. Optional archive checking is
local data hashing, without extraction or source execution. Nine synthetic
controls include fabricated completion, lost attempted flag, unproven OOM,
lost package evidence, invented full manifest, changed terminal scope with
consistent raw hashes, missing cleanup and fabricated deadline exhaustion.

This is a known-development preparation observation by the prior driver/result
author. Independent result review is separate. It establishes neither a complete
collection, full task qualification, agent task outcome nor causal benefit. All
prior frozen results, source/gold, protocols and admission flags stay intact.
