# Offline npm setup inspect admission amendment 1

This append-only successor fixes the independent source-review findings that the
original inspector accepted shared PID mode, an added SYS_ADMIN capability and
host IPC. Safe create argv was already unchanged and no live unsafe execution was
observed. Original 18 artifacts/freeze, before findings and all older receipts
remain unchanged. This amendment is plan/source/data only; no actual setup or
execution authorization follows.

The inspected policy now requires the retained Docker default private PID
representation PidMode="". Host, container-shared, "private" and unknown strings
are rejected. IPC and cgroup namespaces must be explicitly "private"; userns and
UTS must match the intended empty defaults. Init must be true. CapAdd must be
explicitly null or an empty list, CapDrop exactly ["ALL"], and SecurityOpt exactly
["no-new-privileges"]. Missing required fields, added capabilities and any extra,
duplicate, disabled or unconfined security option fail closed. Extra devices,
device requests, volumes-from, links or published ports are also rejected.
Earlier root/user/environment/network/resource/tmpfs checks remain in force.

The safe create command still uses --network=none, --ipc=private,
--cgroupns=private, --init, no explicit PID sharing, readonly root, UID/GID1000,
cap-dropALL and no-new-privileges. No host mounts, credentials or socket are added.
The current namespace/capability representations are bound to the independent
review's retained prior-inspect-representation.json, which is historical evidence,
not a fresh Go01 container observation. inspect-policy.json records the intended
whitelist; this is validation of this bounded operator plan, not a general Docker
execution platform.

The successor plan retains exactly the same command, inputs and bounds:

```
cd /workspace/repository; npm ci --offline --foreground-scripts
```

Source c583f283, cache 583fad50, image b47cd4, all environment/probe/package
observations, 900seconds plus60cleanup, 3CPU/4GiB equal-swap/256PID/8GiB workspace
are unchanged. No Go helper build/install, native collection/tests, Hereby task,
provider/model or package-network action is added. Hook/native --version effects
would still require a separately authorized offline setup attempt.

The new closure binds the original author freeze4f951efe, independent before
reviewfb021636, cache audit60b3833d and the published payload declaration0b3a5ad6.
Published typescript7.0.2/compiler artifacts remain in the unchanged cache. The
setup-only acceptance gate still requires the independent audit and an explicit
coordinator published-payload disposition with nativeTaskAdmitted=false and
campaignAdmitted=false. Original cache flags stay false, no bytes are pruned and
no global cache/native/campaign qualification is inferred.

controls.json retains64 no-daemon cases: the prior34 author controls plus30 exact
inspect positives/negatives and unchanged-plan controls. Complete valid-shaped
fixtures independently mutate shared/host/unknown PID, host/shared/unknown IPC,
host/unknown cgroupns, userns/UTS/init, added capabilities, security options,
container/device attachments and missing required fields. Null/empty CapAdd
positive representations pass. The full fake driver still succeeds for valid
metadata and retains admission/setup/cleanup failures. Synthetic outcomes are
explicitly marked and are not real setup evidence. No Docker/process-network or
upstream/native/provider action was used for these controls. Ruff check/format
with --no-cache and metadata verification pass.

Run source-only metadata verification with uv run --offline --no-sync python
<absolute-amendment-setup.py> verify. Copy the closure before replaying controls:
its output uses exclusive creation. The new invalid authorization template binds
the successor plan; a future live authorization must bind that new hash and fresh
output/scratch paths. The candidate CLI is:

```
uv run --offline --no-sync python /Users/maxwell/projects/agent/dotrepo/benchmarks/head-to-head/f05-go01-offline-setup-plan-20261029/amendment-1/setup.py run --authorization /absolute/coordinator-authorization.json --output /private/tmp/dotrepo-go01-offline-setup-evidence-UNIQUE --scratch /private/tmp/dotrepo-go01-offline-setup-scratch-UNIQUE
```

There is no accepted cache assertion or execution authorization in this packet.
Independent successor review and coordinator decision remain required. No earlier
frozen evidence or production/runtime source was edited.
