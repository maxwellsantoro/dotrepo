# Three original scopes: offline requalification plan

**Plan and synthetic controls only. No container, package setup, upstream source
inspection, native tests, provider/model or index/profile access occurred in this
packet.** Cache audit, common-image acceptance and coordinator authorization remain
pending. The three earlier successful native outcomes do not transfer to the new
image automatically.

The current executable is `driver.v3.py`, bound by `plan.v3.json`, SHA-256
`43a2544d2dbedaaebfbb54302bf4be031f56089bef288cd6a0efd34bec77aa90`.
It uses the exact common image
`sha256:b47cd4a5061d271780bab25aa2637c2623dc675bd43380fc80cb65ec44e50092`
and the immutable source/cache bytes from the prior packets. It does not rebind
those inputs to the current branch or HEAD. The plan retains original task scope,
commands, successful native observations, source/cache inventory and provenance,
preparation traces, image/tool evidence, and exact driver/oracle/helper hashes.

| Unchanged scope | Native test command | Offline setup |
| --- | --- | --- |
| rust-02 sniffnet parser, default features including pcap | `cargo test --locked --manifest-path lib/sniffnet-packet-parser/Cargo.toml -- --nocapture` | Locked offline fetch for `aarch64-unknown-linux-gnu`; exact new Cargo cache |
| typescript-02 OpenHands bin launcher | Original npm wrapper, including i18n, targeting `__tests__/bin/agent-canvas.test.ts` with its JSON reporter | Install npm **11.12.1** from the retained cache using `--offline --ignore-scripts`, then exact-version `npm ci --offline --ignore-scripts` |
| go-03 Vault API | `cd api && GOWORK=off go test -json -count=1 ./...` | `GOWORK=off GOPROXY=off go mod download`; toolchain local; separate native discovery |

Go coverage remains API, cliconfig and tokenhelper, with the 93 top-level tests in
the original successful observation. Rust retains both parser tests and native
default-feature behavior. OpenHands retains both launcher tests through its
unchanged npm wrapper. There are no narrower replacement commands or task repair
loops. The new nested-skip-rejecting Go oracle is copied byte-for-byte from the
append-only oracle revision. Expected identities come from retained native scope
observations; hidden curator gold/oracle files are not provisioned or read.

After authorization, the driver validates archive hashes, inventories, ordinary
member types, sizes and cache roots before creating any container. It then uses a
fresh nonroot container per task with **network none from creation**, no mounts,
Docker socket, host project, credential environment or privileged settings. Root
filesystem is read-only, all capabilities are dropped, no-new-privileges is set,
and PID/IPC namespaces remain private. Limits are 3 CPU, 4 GiB memory with equal
memory-swap limit, 256 PIDs and an 8 GiB workspace capacity. TMPDIR lives under that
workspace; both temporary filesystems explicitly allow execution with nosuid/nodev.
The tmpfs capacity does not promise available RAM: resident tmpfs and processes
share the same 4 GiB memory limit.

The 1,800-second task deadline begins before acceptance/input-byte validation and
is shared by preflight, provisioning, offline setup, discovery, native tests and
scoring/source checks. Actual preflight time is retained. Container cleanup has a
separate bounded 60-second best-effort grace and records its result even after
failure. Native command output is capped at 2 MiB per command. Source and cache
are copied into fresh temporary roots; initial byte checks use quiet native
SHA-256 verification. Every cache/source/image/tool identity is fixed by hashes;
native executable hashes are additionally recorded by a trusted source-free probe
after authorization. No tool byte hash is invented in advance.

Npm `--ignore-scripts` applies only to offline installation commands. It is **not**
set globally for native `npm run test`, so the existing test wrapper and i18n step
remain in force. This does not establish equivalence with ordinary online npm ci
or its installation hooks. Cargo is explicitly offline, Go cannot download a
toolchain, and npm offline mode remains enabled. There is no network fallback.

Scoring follows execution and never alters commands. Complete native assertion
failure can provide the requested outcome with `testsPassed=false`. Listing,
setup/collection failure, zero/missing/narrowed coverage, interruption or any
unadjudicated skip remains noncompletion. Go skips at every depth are rejected.
Task outcome, passing tests, source integrity and protocol validity remain separate
recorded facts. Raw stdout/stderr, native JSON, failures, times and cleanup are
retained; unavailable dollar costs remain null with exclusions.

The driver requires an **external coordinator acceptance file** before its `run`
mode can proceed. No actual acceptance or qualified audit receipt is created in
this packet. The acceptance must contain:

- `state`: `accepted-for-three-scope-offline-requalification`.
- `planSha256`: the exact current plan hash above, thereby accepting native scope,
  commands, oracle, resources and offline setup as a unit.
- `imageId`: the exact common image ID.
- `cacheAudits`: all three task IDs, each bound to an external `{path, sha256}`
  qualified audit receipt.

Each external audit receipt must identify `state=qualified-download-cache` and bind
the exact image, source revision/archive, cache archive and immutable draft
preparation receipt. It must explicitly assert `downloadOnly`,
`buildOutputsExcluded`, `taskSourceExcluded`, `credentialsExcluded` and
`protectedEvaluationAliasesExcluded` as booleans true. This is a consistency gate
over the coordinator's later dispositions, not authentication of authorship or
provenance. Root must authorize the run explicitly; a locally fabricated JSON file
does not confer that authorization. The existing draft false flags remain false
and their original bytes must never be rewritten to obtain admission.

Data-only checks are available now:

```sh
uv run python benchmarks/head-to-head/f05-offline-requalification-20261029/driver.v3.py verify
uv run python benchmarks/head-to-head/f05-offline-requalification-20261029/controls.v3.py
uv run ruff check benchmarks/head-to-head/f05-offline-requalification-20261029
uv run ruff format --check benchmarks/head-to-head/f05-offline-requalification-20261029
```

After the coordinator supplies explicit authorization and qualified audit inputs,
the planned interface is:

```sh
uv run python benchmarks/head-to-head/f05-offline-requalification-20261029/driver.v3.py run --task rust-02 --acceptance /absolute/path/to/coordinator-acceptance.json --output /tmp/dotrepo-f05-offline-requalification-rust02-unique
```

The same interface accepts `typescript-02` and `go-03`; outputs must be unique under
the declared scratch prefix. No `run` invocation occurred here. All three tasks
still require actual offline requalification after audit and acceptance.

The metadata verifier passed without Docker or upstream source-byte reads.
Synthetic controls reject changed plan/image/cache bindings, missing or pending
acceptance, incomplete or changed audit receipts, false audit flags and numeric
boolean aliases. A missing acceptance is rejected before any Docker call. Native
oracle controls passed (three positive, eleven negative), and additional controls
preserve complete assertion failures while rejecting nested skips and listing.
These are harness checks, not task outcomes.

Initial synthetic testing caught a fail-closed macOS path assumption: resolved
`/tmp` becomes `/private/tmp`. The first plan/code and failure are retained; v2
uses the resolved temporary root, and v3 includes host preflight in the deadline.
The original empty stdout is archived as `controls.initial-stdout.txt`.
`ruff.toml` preserves one explicit E402 exception for the frozen historical v2
dynamic loader; current v3 controls use ordinary import ordering. Ruff and format
checks passed for all nine retained Python files.
