# Go-01 offline setup plan: independent synthetic review

This review withholds live setup readiness for the frozen plan whose freeze SHA256
is `4f951efe4fd345ac034a23e234f074f91b543d92da9b56ad01cd93faa3e7c3ca`.
The container-state admission check accepts three states outside the intended
isolation boundary. No real container, network request, package setup, lifecycle
hook, upstream/native command, provider or model call ran during this review.
The original plan, source/cache archives and prior results remain unchanged.

## Finding

In frozen `setup.py:199`, the capability/namespace predicate requires CapDrop=ALL
and rejects only the literal PID mode `host`. Independent mutations of an otherwise
accepted synthetic inspect record show that it still accepts:

- `HostConfig.PidMode = "container:another"`, sharing another container's PID namespace;
- `HostConfig.CapAdd = ["SYS_ADMIN"]`, adding a capability despite CapDrop=ALL;
- `HostConfig.IpcMode = "host"`, contrary to the create command's private IPC request.

These are admission-check gaps. The exact frozen create argv requests a default
private PID namespace, private IPC/cgroup namespaces, all capabilities dropped,
and no added capability. This review does not show that an unsafe container was
created, that Docker ignored the argv, or that a host escape occurred. The intended
post-create verification nevertheless fails to detect these mismatches and should
be amended and independently retested before any live setup is authorized. Admit only
the intended private/default PID representation, private IPC/cgroup namespaces, no
added capabilities and the exact intended security options; reject unknown values
rather than enumerating only known dangerous names. Prior real inspect field
representations are retained separately in `prior-inspect-representation.json`;
they establish no current Go-01 observation. The
cgroup namespace field is also not checked by this predicate; that is a static
observation rather than an additional reproduced case. Exact mutated records and
outcomes are retained in `counterexamples.json`.

## Evidence and preserved boundaries

All 18 files listed by the original freeze matched before review. Five script/plan
inputs were copied byte-for-byte to `isolated-copy/`; controls wrote only into that
copy and owned temporary directories. The copied script closure verifies its
retained helper hashes before import. Real subprocess creation and socket creation
were replaced with rejecting functions before importing/running the controls.

The 34 author controls replayed successfully. Twelve independent cases reproduced
the three admission gaps, confirmed bridge-network and unexpected-environment
refusal, rejected cache symlinks/hardlinks/traversal/out-of-root files/protected
source-content aliases, accepted an ordinary owned regular cache file, and retained
an incomplete result when preflight used 901 seconds before any daemon call.
That last case records zero daemon calls, the work overrun, null dollar cost and
false task/campaign/global-cache flags. These are synthetic outcomes, including
synthetic cleanup and authorization observations; no actual cleanup or isolation
was demonstrated.

Source review found the proposed command remains exactly
`cd /workspace/repository; npm ci --offline --foreground-scripts`, with pinned image,
source/cache identities, 900-second work and separate 60-second cleanup bounds.
Authorization and cache acceptance are external exact-plan/output/scratch/command/
limit assertions checked before daemon access. They are internal coordinator
contracts, as the plan already discloses, rather than cryptographic proof of human
authority. Attempt/result retention precedes helper/plan/auth/input failures;
created-container cleanup and responsive owned-name absence checks are required.
Transport retains bounded stdout/stderr, stdin hashes/counts and null unknown costs.
Source/cache preflight uses regular-only archives, exact inventories and protected
source aliases. This review exercised tiny owned archive counterexamples and read
the reused source/cache checks; it did not rescan the large actual archives or
replace the separate content audit.

The published same-project TypeScript 7.0.2 compiler payload is explicitly disclosed
in the proposed cache disposition. Accepting that payload for an offline npm setup
observation would establish neither native-task/campaign admissibility nor global
cache qualification. Original false flags remain unchanged. Hook-enabled npm setup
may execute esbuild's native version probe inside the proposed sandbox; no such
execution is approved by this review. Actual success, resource behavior, complete
task loading and consumer benefit remain unobserved.

## Checks and handoff

`replayed-controls.stdout` retains the 34-control result; `counterexamples.stdout`
and JSON retain all 12 independent outcomes. Ruff check and format-check passed
for the two new reviewer scripts with `--no-cache`. Copied author scripts were not
reformatted. Generated Python caches are excluded from the review freeze.

The reviewer is the existing E1/F05 curator/implementation agent, independently
reviewing this setup driver's author, not a fresh blinded curator or consumer.
No production or original frozen files were edited. The coordinator and author
were notified of the three mismatches before this handoff. Any correction belongs
in a separate append-only successor; this review supplies no live authorization.
