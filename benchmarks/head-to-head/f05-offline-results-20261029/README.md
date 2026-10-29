# Actual offline qualification of three known native scopes

On 2026-10-29, one serialized, authorized attempt for each of the three previously
successful native scopes completed on the same source-free common image with
its separately audited, frozen download cache. All three produced the expected
complete default-command outcome and passed their tests. No task was retried,
replaced, filtered, or repaired during this packet.

| Frozen task | Native scope and observed result | Offline setup | Native tests | Driver elapsed |
| --- | --- | ---: | ---: | ---: |
| rust-02 | Sniffnet `lib/sniffnet-packet-parser`, default full features including pcap: both exact unit cases passed; separate zero-case default doc phase terminated | 0.792 s | 6.061 s | 22.647 s |
| typescript-02 | OpenHands `bin`: original wrapper and i18n preparation, both launcher cases passed | 28.253 s | 3.298 s | 41.061 s |
| go-03 | Vault `api`, `api/cliconfig`, `api/tokenhelper`: 93 top-level tests passed, no skips at any depth | 0.073 s | 72.130 s | 99.954 s |

Go's separate native discovery took 18.150 seconds. These stage times are not
additive substitutes for total effort: `report.json` retains preflight, setup,
discovery, tests, work, cleanup, metadata verification outside the task deadline,
and outer invocation measurements. Image/cache preparation belongs to its
separate retained preparation packet. Dollar cost is **null**, with explicit
exclusions; unavailable measurements have not been recorded as zero.

## Frozen authority and inputs

The external coordinator acceptance is copied byte-for-byte into `inputs/`.
Its SHA-256 is
`01ff9e6f9790de814907e71dae59d438d0ba7effde829959eaba3d52ad3e5110`;
the acceptance freeze is
`0763682faa7f3b1f255ccd518ccf55eab8f4e59b352e1c60ea749d18dbe274d4`.
The unchanged v5 plan is
`2d44b468d8954b42210cce44ae12c2571a835b8a89154d585a20f4cdbbce90e6`.
`BEFORE.v2.json` bound the exact helper/driver/plan/acceptance bytes and the three
unique output identities before the first attempt. `source-bindings.json` and
each raw result preserve complete revision, source archive, download cache,
original/native command, scope, and tool-hash bindings.

The common image is
`sha256:b47cd4a5061d271780bab25aa2637c2623dc675bd43380fc80cb65ec44e50092`.
This is Linux ARM64 container execution on a macOS host. Each fresh container
started with network `none`, nonroot UID/GID 1000, read-only root, all capabilities
dropped, no-new-privileges, no host mounts/socket/credentials, 3 CPUs, 4 GiB memory
and memory+swap, 256 PIDs, and explicit executable temporary filesystems. The
8 GiB workspace is a capacity ceiling, not a promise of resident memory. Task
work was bounded to 1800 seconds with a separate 60-second cleanup grace.
Source and cache bytes entered by stdin rather than host mounts. Initial source
and cache byte checks and post-test tracked-source byte checks passed.

## Retained evidence and verification

Each task directory is immutable and has its own `*-FREEZE.json`. It contains
the original driver's bounded raw stdout/stderr/JSON, acceptance and attempt
records, all stage receipts, container inspect output, cleanup result, and the
outer invocation receipt. After cleanup, separate read-only inspection of the
exact owned container failed as absent while a responsive `docker ps -a` query
returned no matching container. These observations are retained rather than
requiring the verifier to call Docker again. `report.json` is a data-only
aggregation; `checks.json` records read-only verification of all 60 command
receipts and replay of the frozen scorer against native outputs.

To recheck retained evidence without executing Docker or upstream code, choose a
new output path:

```sh
uv run --offline --no-sync python benchmarks/head-to-head/f05-offline-results-20261029/verify.py --output /tmp/dotrepo-offline-results-check-unique.json
uv run ruff check --no-cache benchmarks/head-to-head/f05-offline-results-20261029
uv run ruff format --check --no-cache benchmarks/head-to-head/f05-offline-results-20261029
```

`run_serial.v2.py` is the actual orchestration script; running it again would be
a new native attempt and is not authorized by this packet. The initial
`run_serial.py`/`BEFORE.json` were an unused prelaunch formatting snapshot, retained
without edits. Local Ruff format configuration excludes that historical script.
Generated Python/Ruff caches are excluded from evidence inventories.

## Interpretation limits

This is operator execution qualification of three known scopes on one common
image and frozen warm caches. It does not qualify the other nine task
environments, launch the 72-session campaign, or demonstrate autonomous agent
benefit. No model/provider calls, index/profile access, new package downloads,
VM changes, or network-enabled task containers occurred in these attempts.

OpenHands uses the explicitly frozen offline npm 11.12.1 bootstrap and
`npm ci --offline --ignore-scripts`. Its four npm deprecation warnings remain in
the raw logs. Passing this bounded setup does not establish ordinary `npm ci`
installation-hook equivalence. Its native wrapper/i18n test path was retained.

The archive provenance binds upstream revisions without inventing Git checkout
metadata. Rust's zero-case documentation phase establishes process-phase
completion, not exercised documentation behavior. The frozen default-fail-fast
assertion-failure policy was available but was not needed: all three native
processes exited zero. Independent result review is retained separately in
`f05-offline-results-review-20261029/`; this packet does not revise old evidence
or declare any broader environment/campaign acceptance.
