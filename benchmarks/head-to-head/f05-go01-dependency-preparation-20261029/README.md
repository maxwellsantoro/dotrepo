# Go-01 dependency preparation: unaccepted plan and driver

This packet prepares one bounded download-only attempt for the frozen Microsoft
TypeScript Go-01 task. No container, download, native task, collection, provider,
or model action occurred in this preparation packet. The plan and every draft
cache audit flag remain false. The authorization template is deliberately invalid.

`plan.json` binds the exact retained full-source archive at revision
25f823dc198a00744b458a7bc6984359f0dd7cac, common Linux ARM64 image b47cd4, script
closure, earlier source/oracle/audit evidence and tool versions. The source-only
preflight checked 68,062 regular files and 218,783,760 expanded bytes against the
retained inventory and 125 protected raw/canonical digests. This is local data
verification, not a source fetch or collection result.

The only proposed package commands, in order, are:

```
cd /workspace/repository; npm ci --ignore-scripts
cd /workspace/repository/tsc; go mod download
cd /workspace/repository/tools; go mod download
```

The pinned source has no `.npmrc`, `.yarnrc` or `.yarnrc.yml`. Its selected
`go.work`, `tsc/go.mod` and `tools/go.mod` have no replace, exclude, retract,
toolchain or godebug directives. `go.work` selects `./tools` and `./tsc` and Go
1.27. The npm lock's 242 external resolved entries use registry.npmjs.org; three
workspace links are source-declared. Exact hashes, configuration and lock facts
are retained in `source-download-config.json`. npm 11.19.1, Go 1.27.3,
GOTOOLCHAIN=local and GOENV=off are explicit; lifecycle scripts are disabled.
This does not establish equivalence to normal npm setup.

The attempt permits 900 seconds plus a separate 60-second cleanup allowance,
3 CPUs, 4 GiB memory with equal memory-swap ceiling, 256 PIDs, executable 8 GiB
workspace tmpfs and TMPDIR inside that workspace. The container is fresh,
nonroot, readonly-root, capability-dropped and no-new-privileges. There are no
host mounts, socket mounts, credentials or inherited host container environment.
The existing image is re-admitted by identity, environment, volume and onbuild
checks. Bridge networking is limited by the trusted command policy and pinned
package endpoints, not an egress firewall. No source scripts, compilation,
`go install`, tests or wrapper commands are authorized.

Before export the driver disconnects bridge networking and verifies no network
attachments. Only `npm-cache/_cacache` and `go/pkg/mod` may be exported. It refuses
links, special files, unsafe/duplicate paths and protected aliases; it does not
silently prune meaningful bytes. Safe PAX path metadata is allowed for retained
long paths. Regular bytes are hashed and preserved during normalized plain-tar
packing. Expanded cache is bounded to 1 GiB, plain transport to 512 MiB, each
file to 128 MiB and source plus cache to 2 GiB. A sampled quarter-second apparent
size watcher complements the hard tmpfs capacity; it is not an instantaneous
universal logical-byte guarantee. Every command has bounded raw byte traces.

Attempt records precede plan/auth/preflight checks. Invalid authorization makes
no daemon call. A create attempt always reaches cleanup, including failed creates;
post-removal inspect and responsive exact-name listing separately establish
absence. Timeout/cap failures kill the client and force-remove the owned container.
Failures and effort receipts are retained; infrastructure dollar cost is unknown
and remains null. Archives stay in unique scratch paths, with only bounded
metadata and traces intended for Git. A successful download would emit a draft
source/image/cache-bound descriptor, never mint audit acceptance or campaign
admission. Native collection, 380 proposed oracle exclusions, dynamic skip
conditions, full default wrapper scope and environment equivalence remain
separate gates.

`controls.json` retains 32 synthetic controls, including authorization/preflight
failures without daemon calls, failed create cleanup, deadline/cache/archive
caps, tool/source changes and cleanup/absence failures. `io-controls.json`
retains seven tiny owned uv transport controls (raw bytes, input hash, missing
input, timeout and text/binary caps). These are not upstream workloads. Earlier
local development control/preflight receipts are retained as such.

For independent replay, copy the script closure and plan to a fresh directory
first: control results use exclusive creation and frozen originals must remain
unchanged. `prepare.py verify` performs metadata verification without daemon
access. No actual run is authorized by this README or template. After independent
review, the coordinator must create an external authorization with synthetic=false,
state=coordinator-authorized-single-download-only-attempt and exact plan/image/
source/bounds/command/output/scratch bindings. Both output and scratch themselves
must be fresh; parent directories must exist. The proposed single-run command is:

```
uv run --offline --no-sync python /Users/maxwell/projects/agent/dotrepo/benchmarks/head-to-head/f05-go01-dependency-preparation-20261029/prepare.py run --authorization /absolute/coordinator-owned-authorization.json --output /tmp/dotrepo-go01-prep-evidence-UNIQUE --scratch /tmp/dotrepo-go01-prep-cache-UNIQUE
```

The same authorization cannot be reused at different output paths; existing
attempt paths are refused. This is a bounded operator assertion contract, not
cryptographic human-identity authentication. Root approval remains required
before the daemon/network attempt. A later successful cache would still need
independent content audit and separate native task qualification.
