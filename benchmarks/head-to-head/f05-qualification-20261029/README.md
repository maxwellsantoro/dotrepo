# F-05 four-task execution qualification, October 29

Three of the four selected tasks produced complete passing native test evidence.
The fourth remains unqualified after two retained resource failures. This is an
operator qualification tranche, not an agent campaign or a demonstration of
consumer benefit. C1, the twelve-task environment/oracle qualification and the
72-session experiment remain open.

| Task | Exact retained scope | Observed result |
| --- | --- | --- |
| rust-02 | sniffnet `lib/sniffnet-packet-parser`, `ab4bf739d46448436cb68933bb8260ee264449d5` | Both native unit tests passed; default full feature preserved |
| typescript-02 | OpenHands `bin`, `2875056f93d6eebcd887f64ae557258a7b0b0108` | Both launcher tests passed through the npm wrapper, including `make-i18n` |
| go-03 | Vault `api`, `352089582444ea84feb03bc97eda97b35729e8ec` | 93 top-level tests passed across `api`, `api/cliconfig`, `api/tokenhelper`; separate `api/auth/*` modules excluded |
| go-01 | Microsoft TypeScript repository-default `test:tsc`, `25f823dc198a00744b458a7bc6984359f0dd7cac` | Full outcome unknown: first listing/compilation attempt OOM-killed; one serialized retry exhausted the 512 MiB temporary filesystem |

All three successful runs had no skipped expected tests and no changed tracked
source bytes. The TypeScript failures occurred before the default wrapper's full
test execution; they are not interpreted as test failures or correct abstentions.
The first failure has retained Docker `oom` events and exit 137. The retry used
the same 3 CPU/4 GiB outer bounds with `GOFLAGS=-p=1 -count=1` and `GOGC=50`;
it had no observed OOM event and reported `no space left on device` in
`/tmp/go-build...`. No additional retry was run. The latter establishes the
temporary-filesystem limit, not that every 4 GiB environment is infeasible.

`report.json` owns the combined result. `runs/` retains every attempt, including
the first Vault provisioning failure caused by Docker creating a root-owned child
workdir. `execution-freeze*.json` and exact prior runner snapshots preserve the
pre-execution contracts and append-only hardening/resource changes. No original
source packet, source gold or enrolled task was rewritten or replaced. Instruction
establishment and actual task execution remain separate: original required
abstention/unresolved gold has not become a correct task-abstention score.

## Source identities and omissions

The original source freeze remains
`fc756e0d5f8a25cddc9f19ece651b21078a68a1f601febdb8d772208c0a66d41`.
The four complete inventories contain 81,109 regular files and approximately
409 MB of source. No submodules, LFS pointers or symlinks are missing. Exact full
archives and bare Git objects remain in
`/tmp/dotrepo-f05-qualification-20261029-tranche-1/`; their absolute locations,
SHA-256 values, per-file Git blobs, modes and recursive inventories are retained
here. Normalized archives preserve upstream bytes and executable modes while
excluding generated Git metadata. They are attested source snapshots, not Git
checkouts. Whole repositories are not duplicated into this Git evidence packet.

Initial acquisition failures remain visible: TypeScript's recursive API tree was
truncated; sniffnet's codeload archive omitted export-ignored tracked documents;
and its 61.8 MB merchandise SVG exceeded the first proposed file limit. Exact
shallow bare Git-object retrieval completed those sources without source
execution or hooks. The final caps were 128 MiB/file, 1 GiB/source,
2 GiB/tranche and 200,000 files. No source was silently omitted.

Every final archive's full Git Merkle tree was computed and matched the tree in
the original frozen commit metadata. `source-tree-validation.json` files retain
those checks. They also correct two original provenance `gitTreeSha` fields that
copied the GitHub API's echoed requested commit SHA. The original provenance
bytes remain preserved; actual source/archive/revision identities are unchanged.

## Containment, setup and oracle

All upstream commands ran in Linux ARM64 containers on Docker Desktop/macOS.
No task source ran on the host. Containers had no host mounts, credentials or
Docker socket, used UID/GID 1000, a read-only root, all capabilities dropped,
no-new-privileges, private default PID/IPC namespaces, explicit executable
temporary filesystems and resource limits. Environment and actual Docker inspect
receipts were checked before source provisioning. Network access was disconnected
before every upstream test/listing command; only trusted download-only package
manager stages ran online. Both qualification and failed-attempt containers were
removed.

Three source-free pinned toolchain images were used: Rust with Debian libpcap and
ALSA development packages; Node 24.22.2 with Go 1.27.3 and uv; and official Go
1.27.3. Exact IDs, source-free image recipes, package inventory and all preparation
failures are retained under `environment-preparation/`. A single common image is
feasible to investigate but has not been qualified for all four tasks.

Npm dependency acquisition used lifecycle scripts disabled online. The actual
OpenHands test wrapper ran unchanged offline. Equivalence to normal contributor
`npm ci` setup still needs independent review; this packet does not silently
declare those omitted setup hooks irrelevant. Vault's committed API generation
outputs and module-scoped Docker requirements are separately adjudicated in the
freeze, without claiming equivalence to root `make test`.

`oracle.py` has three positive and ten negative native-format controls covering
wrong scope, listing-only output, skipped/narrowed suites and zero-test stand-ins.
Actual success requires complete native test evidence and unchanged tracked
source, not just a proposed command or successful compilation. Go's intended test
set is enumerated separately and must subsequently appear in actual run/terminal
events. TypeScript's planned wrapper instrumentation uses the documented
[`GOTESTSUM_JSONFILE` interface](https://github.com/gotestyourself/gotestsum#json-file-output),
but its full wrapper did not run in this tranche. The oracle is post-run scoring
code and must stay hidden from future agent sessions; it does not authorize agent
shell choices by comparing them to gold.

## Accounting and remaining work

Raw commands, failures, elapsed time and container interface traffic are retained.
The latter includes protocol headers and incidental traffic. Dollar costs remain
null with exclusions: no metered host/container billing source exists, and complete
initial Node/Go image-transfer timing/bytes were not measured. No bytes-to-token
conversion, model calls, evaluated index/profile access or causal comparison was
performed. Qualification runs overlapped in pairs; their timings are observed
operator work, not a controlled effort comparison.

Each task started with empty caches, then used its explicitly recorded warm
download state offline. `cache-layout-diagnostic.json` describes prospective
`cargo/`, `go/pkg/mod/` and `npm-cache/` inputs while excluding build caches and
source-checkout `node_modules/`. No reusable cache archive was built. Inventory
content aliases include empty locks/shared licenses; the diagnostic authorizes no
cache policy exception. A separately frozen download-only preparation pass and
independent cache audit are still needed.

`next-eight-plan.json` preserves all remaining enrolled task identities and scope
problems. That plan includes primary-package Python coverage, GUI/browser setup,
native build prerequisites and cache backend services. No next-eight sources or
upstream commands were acquired/executed in this four-task packet.

Commands actually used include:

```bash
uv run python benchmarks/head-to-head/f05-qualification-20261029/acquire.py
uv run python benchmarks/head-to-head/f05-qualification-20261029/complete_sources.py
uv run python benchmarks/head-to-head/f05-qualification-20261029/qualify.v3.py.txt --task rust-02
uv run python benchmarks/head-to-head/f05-qualification-20261029/qualify.v3.py.txt --task typescript-02
uv run python benchmarks/head-to-head/f05-qualification-20261029/qualify.v3.py.txt --task go-03 --attempt 2
uv run python benchmarks/head-to-head/f05-qualification-20261029/qualify.py --task go-01 --attempt 2
uv run python benchmarks/head-to-head/f05-agent-tasks-20261029/verify_source_freeze.py
uv run python benchmarks/head-to-head/f05-qualification-20261029/finalize.py
```

The runner was named `qualify.py` when earlier freezes ran; exact prior bytes now
live in the named snapshots. Scripts refuse to overwrite retained outputs. A
reproduction needs a fresh copy/output root, matching frozen source archives and
local pinned images. No additional Go retry is authorized by this README.
