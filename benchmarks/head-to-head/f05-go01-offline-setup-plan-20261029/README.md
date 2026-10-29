# Go-01 offline npm setup observation: plan only

This packet proposes one normal hook-enabled npm setup observation using the
unchanged source archive c583f283, cache archive 583fad50 and common image b47cd4.
No daemon, package setup, lifecycle/native code, collection, task, network,
provider or model action ran. The plan is unaccepted, and both acceptance and
authorization templates deliberately fail admission.

The sole proposed package command is:

```
cd /workspace/repository; npm ci --offline --foreground-scripts
```

Foreground lifecycle logging is an explicit observation setting. Npm 11.19.1,
Node v24.22.2, npm offline=true, ignore-scripts=false, registry/userconfig/cache
paths and effective environment are pinned and checked. Source configuration is
already frozen without npm/yarn override files. Normal hooks can copy/chmod
binaries, use their defined fallback paths and execute esbuild --version or libc
probes; these effects belong only inside a separately authorized offline sandbox.
No Go helper compilation/install, collection/tests or Hereby task is proposed.
The earlier ignored-hook preparation is not treated as setup-equivalent.

## Cache boundary and required acceptance

The independent audit identified published same-project payloads in this cache:
`@typescript/bundled-typescript` is an alias for published `typescript@7.0.2`, and
`@typescript/typescript-linux-arm64@7.0.2` carries a published compiler. Exact lock
integrities and cache-inventory identities are in published-task-payloads.json.
These are not generic-only libraries or source-compiled task evidence. The original
preparation excludes task-specific binaries; its unqualified result and false
flags remain unchanged. Nothing is pruned or replaced to manufacture admission.

Before any daemon call, the driver requires an external coordinator assertion:

- state `coordinator-accepted-go01-cache-for-offline-npm-setup`, synthetic=false;
- exact source/image/cache/spec hashes and a hash-bound independent audit freeze;
- publishedTaskPayloadDisposition state
  `allowed-only-for-offline-npm-setup-observation`, exact payload declaration SHA,
  nativeTaskAdmitted=false and campaignAdmitted=false.

A separate authorization must use state
`coordinator-authorized-single-offline-npm-setup`, synthetic=false, exact plan,
command, integer limits, maxAttempts=1, unique absolute output/scratch paths and
the acceptance artifact hash. The assertion is an internal coordinator contract,
not cryptographic proof of human authority or a new public schema. This accepts
inputs only for observing offline npm setup. No global cache qualification, native
task/campaign admissibility or source-compiled outcome follows, even if setup later
succeeds. Those require separate frozen policy and evidence.

## Proposed isolation and observations

A fresh pinned Linux ARM64 container starts with --network=none, nonroot UID/GID
1000, readonly root, all capabilities dropped, no-new-privileges and private
default PID namespace. There are no host mounts, credentials, Docker socket,
privileged options or inherited host container environment. The full source and
regular-only cache are hashed and streamed over stdin into fresh executable tmpfs.
No archive or checkout is executed on the host. Resources stay 3 CPUs, 4 GiB memory
with equal swap ceiling, 256 PIDs, 8 GiB workspace, 1 GiB cache and TMPDIR under
/workspace/tmp. Initial source+cache is bounded to 2 GiB and each transport to
512 MiB. Work is limited to 900 seconds plus separate 60-second cleanup grace.

The driver records image/config/resource/network admission, actual provisioned
stdin hashes, initial source/cache byte checks, exact tool versions and effective
npm configuration. It retains foreground hook markers, npm exit/error and raw
bounded stdout/stderr. A trusted data-only Node observer reads selected package
versions, including the published TypeScript payload versions, plus six native/
.bin file metadata, contained resolved paths, executable modes and hashes. It does
not invoke those binaries. Tools and original tracked source bytes are rechecked;
final inspect confirms offline isolation. Observing setup and these paths does
not demonstrate CLI semantics, full task module loading or task correctness.

Attempt records precede helper/plan/auth/input verification. Metadata verification
and preflight are included in work timing, and failures remain receipts. Every
attempted create, including create failure, leads to forced removal, post-removal
inspect and responsive exact-owned-name listing. Timeout kills the client, then
cleanup stops the container. Cleanup/absence uncertainty or bound overruns remain
incomplete. Dollar costs stay unknown/null. Raw command traces use the previously
reviewed 2 MiB bound and retain command byte hashes/counts/timing; no byte-to-token accounting.

## Checks and handoff

Thirty-four controls use deterministic fake receipts/owned assertion files only.
They cover missing/changed authorization/cache/audit/payload disposition, no-daemon
preflight/helper failures, create failure cleanup, bridge/mount rejection, changed
stdin/config/tools, hook/metadata/bin-link failures, deadline, source mutation
failure and cleanup/absence. Synthetic success is explicitly marked synthetic and
is not a real setup outcome. No production file or old frozen packet changed.

Local data-only preflight verified 68,062 source files (218,783,760 bytes) and
15,246 cache files (351,962,210 bytes) in 3.905 seconds. Hash/regular-only/path/root/
protected-alias checks passed. This does not replace the independent content audit.
Ruff check/format passed with --no-cache. Development metadata/control snapshots
are retained separately; none represents an actual setup attempt.

For review, copy the plan/script closure to a fresh directory before controls.py:
its output is exclusive and immutable originals must not be overwritten.
`uv run --offline --no-sync python <absolute-setup.py> verify` is data-only.
After separate acceptance and authorization, the proposed single-run CLI is:

```
uv run --offline --no-sync python /Users/maxwell/projects/agent/dotrepo/benchmarks/head-to-head/f05-go01-offline-setup-plan-20261029/setup.py run --authorization /absolute/coordinator-authorization.json --output /private/tmp/dotrepo-go01-offline-setup-evidence-UNIQUE --scratch /private/tmp/dotrepo-go01-offline-setup-scratch-UNIQUE
```

Output/scratch themselves must be fresh; their parent directories must exist.
This README authorizes no run. Unknown or failed setup remains visible, with no
retry, pruning, new task filter, exclusion or qualification inferred.
