# Appended Go01 result: package parser rejection

The third coordinator invocation remains **incomplete**. Under the separately
reviewed driver amendment 2, the prospective GOENV query expectation is empty
while the actual container environment remains `GOENV=off`. The environment
preflight passed. The unchanged `go list -json ./...` command exited 0 without
stderr, but the frozen parser rejected its raw output with:

```text
ValueError: package has no selected Go source
```

The raw `packages.jsonstream` contains 104 syntactically decodable JSON objects.
One raw package, `github.com/microsoft/TypeScript/tsc/internal/fourslash/tests`,
has no `GoFiles` or `CgoFiles`, but has 3 `TestGoFiles` and 4,368 `XTestGoFiles`.
The owned frozen parser requires production Go source and reproduces that
rejection on the retained stream. This is a diagnosis of the actual rejection,
not an accepted package inventory, a complete scope qualification or a parser
fix. The exact raw package bytes are retained twice as originally produced:
`evidence/packages.jsonstream` and `evidence/logs/go-list/stdout.bin`.

`go test -json -list . ./...` never ran. There is no test-list output, observed
upstream test initialization/TestMain execution, task outcome or campaign
qualification. Native collection and all task/campaign/global-cache admission
flags remain false. No new runtime attempt is authorized by this packet.

Source, image, Go-only projection, container environment, commands, directory
and resource limits match the preceding invocation. The new plan changed the
expected GOENV query result prospectively, with a new reviewed subject and fresh
single-attempt authorization. The prior failure is preserved under the parent
freeze `3d88c025332c325a17d3fe95a3b55aebcd9e67e75992950525727d84f1d7eca6`;
all its 91 bound files remain unchanged.

The attempt made 16 daemon calls and accounts for 17.91199929197319 seconds of
driver time, 585,257,959 stdin bytes and 742,463 raw output bytes. Dollar cost
remains `null`; broader preparation, coordination and review work is unmeasured.
`report.json` also sums all three preparation invocations without treating them
as an agent or consumer comparison.

Initial tools/checksum/tree checks passed. The early parser stop skipped source
and tool after checks; whole-run source/tool preservation is therefore unresolved.
Force removal exited 0 and the same driver's subsequent inspect/name-list
receipts report absence. No separate independent absence observation exists.
This packager performed no daemon, network, Go, package, task or provider action.

All 78 original observation, authorization and relevant reviewed closure files
(1,655,999 bytes) are copied byte-for-byte, indexed by `origin-ledger.json`.
The original outer stdout log is retained; the coordinator's exit-1/session
handoff is explicitly a message transcription rather than a complete outer argv
receipt. No source/cache archives or generated build artifacts are exported.

Run local checks with:

```sh
uv run python benchmarks/head-to-head/f05-go01-collection-result-20261029/amendment-1/verify.py --input-archives
uv run python benchmarks/head-to-head/f05-go01-collection-result-20261029/amendment-1/controls.py
```

The verifier imports only the hash-bound owned static parent verifier and owned
JSON parser, never a driver or upstream package. It validates retained bytes,
current-plan author/review/authorization bindings, all 16 receipt/raw pairs,
initial isolation/resources/environment, exact executed commands, same-attempt
cleanup, parent preservation and frozen parser rejection. The optional archive
mode reuses the read-only parent archive/hash/full-tree check and ties this
attempt's initial tree/manifests to the same fixed inputs. Eight local synthetic
controls reject fabricated success, missing cleanup, empty/truncated raw package
streams with consistent hashes, invented later artifacts and mismatched raw
copies. No live collection is run by these checks.

This is a known-development preparation result authored by the prior driver
and result curator. Independent result review remains separate. The raw 104
objects do not close native collection, wrapper qualification, task completion,
agent adoption or causal consumer benefit.
