# Prospective owned source-registry runtime

This packet implements a bounded runner for the owned stdlib Go registry helper.
It is **source-only and not authorized for execution**. No Go, Node, Docker daemon,
network, package, target or provider command was run. Fake lifecycle/transport
fixtures cannot establish a real helper result or target acceptance.

The runtime binds corrected helper amendment 1, plan
`74258ec831c551ad1b39a497ed09320c3824aa0be9a836fb3d076684f5703482`,
freeze `e569edd4888a092aa46745d950614964ca86fc755637827fd9723fad0413da4d`.
Its three unchanged Go files remain in the original helper root. The amended
Python receiver and strict JSON builder remain under the helper's `amendment-1/`;
input provenance remains in the original root. These locations are resolved
explicitly rather than assuming one directory. Static pass reviews are separate
external inputs required in a fresh root authorization; none is assumed here.

The only proposed helper commands are:

```text
cd /workspace/owned-module; go test -json -count=1 -timeout=60s .
cd /workspace/owned-module; go build -o /workspace/owned-bin/registry .
/workspace/owned-bin/registry
```

Provisioning creates a tar containing only `go.mod`, `registry.go` and
`registry_test.go`. No upstream `.go` files or retained Go tool source enters the
built module. The CLI receives exactly 21,446,036 hash-bound JSON bytes by stdin;
source byte payloads remain data and are never materialized as a target module.
Only owned tests/fixtures and owned stdlib code may be compiled/executed.

The helper environment exactly reuses the helper proposal: CGO0, GOWORKoff,
GOENVoff, local toolchain, GOPROXY/GOSUMDBoff and initially empty owned build/module/
GOPATH directories. Original target CGO1/GOWORKrepository context stays attributed
input data and cannot set helper environment. No Go environment query is used;
exact container inspection and the audited Go binary checksum are checked instead.
An initial root-selected `/workspace/registry` alternative and extra LANG setting
were superseded before freeze; retained development plans/source show that change.

`runtime.py` hash-binds the existing reviewed isolation source and extracts only
its pure `flags`/strict `inspect` wrappers, retaining the same image, namespaces,
no-network/no-mount policy, nonroot identity, read-only root, caps, tmpfs and
3CPU/4GiB/256PID limits. It uses900seconds including preflight and60cleanup;
all command output shares a2MiB binary+text cap. Source before/after is an exact
three-file tar observation (including mode/hash/type), outside which Go writes
only its binary and fresh ephemeral compiler scratch. Go tool bytes and final
isolation are checked again. No caches or binaries are exported/reused.

The byte transport is a narrow owned copy of reviewed `process_io.py`, with its
original bytes and exact diff retained. It tightens binary+stderr combined caps
and fixes cancellation ordering: a loop BaseException kills a live client before
the finally wait. A fake-process control exposed the prior wait-before-kill
behavior; the initial failure and development receipts are preserved. There was
no real cancellation or upstream failure. Binary output goes to `registry.gz`,
never through UTF8 decoding; stdout.bin is empty for binary-mode commands and
receipt binary byte/hash fields bind the raw stream.

The frozen receiver remains unchanged:2MiB compressed,8MiB expanded, deterministic
single gzip header, CRC/eof/truncation/trailing/multi-member and strict JSON/schema/
source-context checks. Exit0 must accompany source-derived-uncompiled; exit1 may
accompany a receiver-valid unresolved-source-discovery registry with explicit
diagnostics. Both are owned-tool observations only. Exit2, malformed/capped output
or exit/state mismatch remains incomplete. A CLI attempt flag is separate from
validated output observation, including on nonzero/failed runs.

The unit observer requires exactly8owned top-level tests plus21named child cases,
with run/pass terminals, correct package, no skips/failures or unknown tests, and
children terminating before parents/package. Authorization binds the current
runtime plan+author freeze, immutable corrected helper subject, both scoped
independent static review objects, exact commands/input/limits and fresh canonical
output/scratch paths. Arbitrary hash-valid or findings-present review JSON fails.
This is a bounded operator consistency contract, not proof of human authority.

Every created-or-partially-created owned container is force-removed in finally,
then checked by inspect and a responsive name-list. These are same-attempt
observations; no independent absence proof is claimed. Preflight refusals retain
attempt/result/reason with zero daemon calls. Failures, cancellation, truncation,
unknown dollar costs and incomplete after checks remain visible.

Focused controls pass:14fake lifecycle cases,11authorization-shape cases and5fake
process transport cases. Positive registry fixtures are explicitly synthetic,
valid-shaped empty declaration lists, not source gold. They cover both allowed
exit/state routes; negatives cover namespace/environment/source changes, missing
unit coverage, failed commands, CRC/multi-member/cap/exit mismatch, cleanup and
stale/unrelated/findings-present reviews. Fake transport controls preserve invalid
UTF8 binary bytes and enforce combined limits, deadline and cancellation. Controls
never launch a process or socket. `checks.json` binds final commands and outputs.

Run source-only checks with:

```sh
uv run python benchmarks/head-to-head/f05-go01-source-registry-runtime-20261029/controls.py
uv run python benchmarks/head-to-head/f05-go01-source-registry-runtime-20261029/transport_controls.py
uv run ruff check --no-cache benchmarks/head-to-head/f05-go01-source-registry-runtime-20261029
```

A real helper run still requires independent runtime/helper reviews and explicit
root one-attempt authorization. Later actual output and partial crosscheck review
are separate. Target compilation validity, native collection, nested/dynamic case
coverage, skip acceptance, the current Go01 oracle and all task/campaign/global
cache gates remain unchanged. The author previously wrote the collection driver
and result packets; this is no fresh holdout or independent consumer experiment.
