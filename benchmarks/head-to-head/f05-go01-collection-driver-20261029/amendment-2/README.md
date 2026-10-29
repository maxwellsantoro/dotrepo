# Collection driver amendment 2: GOENV query semantics

This append-only successor corrects one expected query value. Container input
remains `GOENV=off`; `go env -json ... GOENV ...` is expected to return `GOENV: ""`.
The environment hash remains
`3649e45b9b1c1f62faeb2c3a168d93d91a7be7a62e7e2905c07d9ba69ddb65fe`.
All other expected query fields are exact and unchanged.

The correction is source-established independently of the historical result.
Exact Go sources from the retained image export are preserved under `sources/`,
matched to the frozen image inventory. `alldocs.go:2449–2453` documents the input;
`cfg/cfg.go:344–347` returns an empty environment-file name for `off`;
`envcmd/env.go:79–89` emits that name in the query. `cfg.go:364–369` skips the user
config file but separately reads GOROOT/go.env. Thus this disables the user config
file, not all Go defaults. Source hashes, exact excerpts and image bindings are
in `goenv-source-semantics.json`.

The actual raw query and receipt from the failed authorized attempt are retained
unchanged as `actual-go-env-stdout.bin` and `actual-go-env-receipt.json`. The query
exited zero and its stdout SHA256 is
`bfa88e9ed8bc5888d6bd3376082142b1e8e743cbbb971fb9794a89d7b5cd266b`.
That attempt stopped at the erroneous environment comparison after 15 daemon
calls, took 16.557 seconds and retained successful cleanup/absence evidence. It
performed no package listing or native collection. Its failed result and earlier
root-path admission failure are historical evidence, not rewritten successes.
No fresh daemon or Go operation ran for this correction.

The runtime delta is limited to the new packet identity, the expected GOENV query
value and the declared closure for the new source/query fixtures and fake controls.
`collection.py.diff` and `make_plan.py.diff` show the changes. Source revision,
image, projection, environment input/hash, commands, cwd, resources, bounds,
namespace/network policy, source/tool observations, stop rules and cleanup are
unchanged. Listing, transport, tree observer and prior control scripts are copied
byte-for-byte. The prior 33-file author packet, 29-file amendment 1 and 14-file
amendment 1 review all match their original freezes.

The new identity is `go01-collection-driver-amendment-2`; plan SHA256 is
`c7dbacdf6c3966f66fd0ef805a85db452ce72180d3db22347a5c8a06f941d4a0`.
Authorization still requires the exact current plan plus author freeze, and
scope acceptance plus independent passed review must name that exact subject.
All existing subject/closure/postcheck logic remains intact. The historical
passed parent review cannot authorize this successor. The authorization template
is explicitly unresolved and not authorized. No passed review, scoped acceptance
or actual execution authorization is created here.

The 59 prior fake driver controls, 40 amendment controls, two fake transport
controls and 22 new GOENV controls pass. New controls use the exact historical raw
query as a positive fixture; the old expected `off`, every changed query field,
missing/null/duplicate/extra fields, malformed/multiple JSON objects and altered
container input values are refused. A wholly fake full driver crosses the gate
with those recorded query bytes and retains synthetic flags. This is not a new
native collection or reproduction of upstream execution. Node observer evidence
is reused only for unchanged source/tool inputs; Node was not run.

`checks.json` records closure and history checks. Ruff check and format check pass
with `--no-cache`. Only trusted local uv/Python source/metadata and fake controls
ran. No new daemon, Go, Node, network, package, upstream import/execution or
provider/model call occurred. Dollar cost is unknown/null. Native task, campaign
and global-cache admission remain false. Independent amendment review and a fresh
coordinator decision/one-attempt authorization remain required before any run.

Do not rerun metadata generators or exclusive-output controls inside this frozen
packet. Review replays must use a separate copy, omitting generated control JSON
before executing controls; the copy is a synthetic review subject. The actual
author freeze remains immutable.
