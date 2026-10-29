# Real container backend controls, 2026-10-29

These are provider-free controls of the F-05 Docker backend on the coordinator's
Linux ARM64 Docker engine. They qualify the recorded backend operations only.
They do not qualify an upstream task, completion oracle, provider, dependency
cache, campaign launch, or consumer benefit. Synthetic qualification flags in
the control driver are explicitly recorded as such.

The baseline runtime at `eb43ab20ac0368c4926660ae060347305197f936` could not
create a container: Docker rejects `--pid=private`. Its default PID namespace
is private. The first retained receipt records that actual failure, including
cleanup. The intermediate runtime removes the unsupported flag and reproduces
the next defect: copied ELF binaries cannot execute in either tmpfs. The final
runtime explicitly requests `exec,nosuid,nodev` for the two writable tmpfs
mounts. It passes both executable controls and the remaining controls for a
non-root user, read-only root, network isolation, absence of host mounts,
resource bounds, output limit, deadline, and cleanup. The independent
`cleanup-verification.json` confirms all three named containers are absent.

The final and intermediate receipts each have ten passing checks. Passing the
intermediate receipt means the expected *failure to execute* was reproduced;
it is not a successful task environment. The initial receipt remains failed.
No provider was called; monetary preparation and maintenance costs are unknown.

The image is built from the pinned Python filesystem in `Dockerfile`, with a
minimal image configuration. It contains no task source, gold, profile or
credentials. Its exact image ID, inspect response, build log, runtime snapshots,
and driver are retained. This is a control image, not the campaign image.

Reproduce in a new output directory with the retained image available locally:

```sh
uv run python benchmarks/head-to-head/runtime-qualification-20261029/check_backend.py \
  --image sha256:8032a060e0198814ffe1868893bf89bdb02fa79f4de617873f23eb8dd3915af4 \
  --runtime-source benchmarks/head-to-head/runtime-qualification-20261029/fixed-runtime.py.txt \
  --expect-exec allowed --out /tmp/dotrepo-backend-new-control
```

For the intermediate control, select `pid-corrected-runtime.py.txt` and
`--expect-exec denied`. The baseline snapshot intentionally fails admission at
container creation. `FREEZE.json` binds the retained files; it does not attest
to Docker or source authenticity independently.
