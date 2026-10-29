# Go01 collection stopped at environment preflight

This packet preserves two completed coordinator-authorized invocations for
`github.com/microsoft/TypeScript@25f823dc198a00744b458a7bc6984359f0dd7cac`.
Both remain **incomplete**. No package inventory or test-list command ran, and
this packet does not resolve the GOENV discrepancy or authorize a retry.

The first invocation rejected the coordinator's `/tmp` output/scratch identities
before daemon access. Its three original JSON files and outer stdout are retained
under `attempt-1/` and `outer/driver-1.log`. The coordinator then issued a fresh,
explicit path amendment using `/private/tmp` identities. The authorization changed
only those paths and the disclosed link to the first refusal; source, image,
Go-only projection, environment, commands and resource limits stayed fixed.
All original authorization bytes and freezes are under `authorization/`.

The second invocation made 15 daemon calls and ran the exact declared `go env`
command from `/workspace/repository/tsc`. That command exited 0, with no stderr,
but its JSON reported `GOENV: ""` where the frozen preflight expected `"off"`.
The retained container inspection reports `GOENV=off`. The strict check stopped
at that difference. `go list -json ./...` and `go test -json -list . ./...` did
not run. The driver's `nativeCollectionAttempted` and success/admission flags
remain false. Running the Go environment probe is distinct from compiling or
executing upstream test initialization, TestMain or test bodies.

Initial tool checks, checksum checks of source/cache, and the complete initial
source-tree observation passed. The early stop skipped the source/tool after
checks, so whole-run preservation is unestablished. The driver's own cleanup
receipts show force removal exit 0, subsequent inspect reporting no such object,
and a successful empty name-list lookup. There is **no separate independent
absence observation** and this packager issued no daemon calls.

The sum of the two retained driver elapsed values is 16.591300040949136 seconds;
the actual container attempt accounts for 16.5568172079511 seconds. The receipts
account for 585,257,959 stdin bytes and 11,171 raw stdout/stderr bytes. Dollar
cost is unknown (`null`), and broader setup, coordination and review effort is
unmeasured. These are preparation observations, not consumer savings.

`origin-ledger.json` binds 82 original observation, authorization and relevant
frozen input/review files, copied byte-for-byte (221,300 bytes). All 15 second
attempt receipt/raw-stream triplets are retained, along with its full trace,
attempt/result JSON, initial tree and raw Go environment output. The exact
reviewed driver sources and reused isolation source are retained as data under
`bindings/`; they are not executed by this packet. Source/cache archives and
build artifacts are not exported. `coordinator-handoff.json` records the reported
outer exit statuses and explicitly distinguishes this message transcription
from an unavailable complete outer invocation receipt.

Run the read-only verifier from the repository:

```sh
uv run python benchmarks/head-to-head/f05-go01-collection-result-20261029/verify.py
uv run python benchmarks/head-to-head/f05-go01-collection-result-20261029/verify.py --input-archives
```

The second form also reads the fixed local source and Go-only projection archives,
checks their hashes, reconstructs the full source-before tree and checksum stdin
manifests. It neither extracts nor executes source. `verification.json` retains
that check. `controls.py` and `controls.json` retain nine synthetic controls,
including raw corruption, fabricated completion, lost cleanup, exit mismatch,
consistent-hash but different GOENV/CC or effective-env observations, a later
collection artifact, and changed acceptance bytes. Controls use isolated local
copies only; no daemon, network, package, provider or upstream actions occur.

This is a known-development environment-preflight result. It establishes no
collection completeness, task outcome, campaign admission, global cache admission,
agent use or causal benefit. The packager authored the preceding driver and source
curation, so this verification is not an independent result review. Independent
review and any prospective semantic amendment remain separate gates. Original
frozen source, proposal, review, gold and earlier result packets are unchanged.
