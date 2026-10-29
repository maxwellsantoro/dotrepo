# Go-01 next qualification decision: collection only, unaccepted

The smallest remaining native evidence gate is a successful source-compiled
package/top-level test listing, frozen before any real task execution. Normal
offline npm setup now has retained, independently reviewed evidence. Native
collection, full Hereby wrapper/tool compilation, dynamic skip qualification and
task outcome remain unobserved. This source/data packet authorizes no execution.

## Proposed next gate

Inside a fresh isolated container, from `/workspace/repository/tsc`, propose:

```
go env -json GOOS GOARCH GOVERSION GOTOOLCHAIN GOENV GOWORK GOFLAGS CGO_ENABLED CC CXX
go list -json ./...
go test -json -list . ./...
```

plan.json fixes source revision/archive, image, environment, commands, outputs,
limits and stop conditions. Proposed limits are 900 seconds including preflight,
60 seconds cleanup, 3 CPUs, 4 GiB memory/equal swap, 256 PIDs, 8 GiB workspace,
TMPDIR under that workspace and 2 MiB combined stdout/stderr per command. There
is no memory/VM increase. A full output, native environment match and complete
package inventory including zero-test packages are mandatory. Explicit CGO=1 is
a proposed frozen context, not an observed go-env fact; mismatch stops before
compilation, without automatic adjustment. The driver/control/authorization for
this native gate does not exist in this packet.

Direct Go collection does not need the source-owned gotestsum helper or load
Hereby/Node modules. The retained Go1.27 tool source says -list runs no test bodies
and lists top-level identities only. M.Run returns through its listing branch;
package initializers and TestMain still execute. Source examples include watcher
capability probes and baseline tracking; the content-mapper helper environment
must remain unset. Thus collection is native preparation, not harmless text
parsing or task completion. Native Go selection/build/init is still unobserved.

The package manifest must come from actual native outputs, not the lexical source
catalog. Keep Test/Example/Fuzz names, zero-test packages and benchmark diagnostics
separate. No nested cases, fuzz seeds, successful tests or package/case counts are
invented. Freeze raw outputs, receipts, package inventory, context and timestamps
before later execution. Reuse requires matching source/platform/tags/Go context;
changes affecting selection/init require a new collection epoch.

## Cache boundary

No installed npm tree is different from no readable npm payload. Seeding the full
original cache would leave published npm compiler bytes readable even without
npm ci. The proposed collection-only input therefore selects exactly all regular
parent members under `go/pkg/mod/`: 14,922 files / 278,162,103 bytes. The canonical
selected-member map SHA256 is
bf5aefaa56222f9337752edebddd50d2cfc4759ed8954f7f9f74bf3d70765131.
The exact parent inventory/hash and derivation are in
go-cache-projection-proposal.json. No derived archive is materialized here; its
actual tar hash and independent acceptance remain prerequisites. Original cache
bytes/flags are unchanged. This is an explicit proposed scoped input, not silent
pruning, generic-only reclassification or global cache admission.

The no-npm variant requires independent source review confirming no eager npm
requirement for collection. Selected init/TestMain and Go helper sources support
it as a candidate, but the lexical scan is not a universal call graph or native
build-tag resolution. A missing setup requirement or failed listing remains a
failure; no npm fallback or scope change is allowed inside an attempted variant.
Full normal npm setup must remain for the eventual whole default task.

## Published compiler roles

The source-owned `jstest.EvalNodeScriptWithTS` explicitly imports root
node_modules/typescript/lib/typescript.js into comparison scripts. The frozen
lock identifies that reference library as TypeScript6.0.3. It is a declared test
dependency, not automatically answer contamination; blanket full-task npm removal
would change intended prerequisites.

The published native TypeScript7.0.2 payload is separately reached through the
@typescript/bundled-typescript alias and release/VSIX helpers. Shared project
identity alone does not prove its actual role in default tests. Prior acceptance
covered only npm setup observation. That remains distinct from source-compiled
Go test subjects, raw native collection and task outcome. The host-side Python
JSON oracle imports no npm/compiler package and must stay outside the container.
Full Hereby module loading/transitive effects remain separately unobserved.

The future full wrapper still owns an offline gotestsum build/install from the
tools module (v1.13.0) through createCachedTool. No manually supplied/prebuilt
helper may substitute. It is unnecessary for this direct collection gate, and
its compilation/wrapper execution needs separate authorization. No test:all,
generation command, package filter or narrower task replaces the fixed default.

The 380 source exclusions remain unaccepted. Dynamic compiler output/options,
fuzz seed identities, watcher/capability conditions and slash/hierarchy ambiguity
remain unresolved. Unexpected skips at any depth remain noncompletion; nothing
in this packet expands the exclusion set or credits excluded behavior.

## Source evidence and limits

The complete exact source archive is retained; no source fetch is missing for
this bounded proposal. Selected source members, exact spans, prior oracle/setup/
review bindings and Go tool source are retained. A lexical pass read 5,171 Go
files under its initial 2 MiB per-file bound, then separately read the single
4,029,319-byte named file under an explicit 8 MiB bound. Those diagnostics are
not native collection. A speculative generate-ast-helpers.ts path was absent and
is not a retained literal dependency; no new acquisition is proposed.

checks.json records local text/hash/span and deterministic subset checks. All
Python used uv. No daemon, network, package/native commands, source execution,
provider/model, Go or Cargo calls occurred. Costs remain unknown/null. No task,
native or campaign admission is minted. Independent plan/projection review and
explicit coordinator authorization remain required before a bounded native run.
