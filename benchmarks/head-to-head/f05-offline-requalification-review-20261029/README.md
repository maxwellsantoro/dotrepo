# Independent offline requalification v3 review — 2026-10-29

Two actionable findings were reproduced before native execution. The frozen
v3 packet remains unchanged; correction must use an append-only successor.
No Docker/daemon, network, upstream execution, package or provider call occurred.
One pinned upstream component manifest was statically inspected and retained.
This reviewer has prior development/source context, not fresh blind-agent context.

Inputs: packet freeze `daac836830a0f853e83dc2a67b0de8115ee4d73b42cce7eb468326f87ed82b78`,
plan v3 `43a2544d2dbedaaebfbb54302bf4be031f56089bef288cd6a0efd34bec77aa90`,
driver v3 `ed5a3503853981661e636b08e6306f320c68be61c114c3a5d7cac7a386dd82ba`.
[input-bindings.json](input-bindings.json) binds all 23 packet artifacts, source
manifest and historical Rust output. The metadata verifier and author's synthetic
controls passed again, including authorization false/numeric flags, exact
plan/image/cache bindings, isolation flags, three positive/eleven negative native
oracle controls, nested Go skips and complete assertion failure.

## Findings

1. **Accepted preflight failures lose their attempt receipt and effort.**
   `driver.v3.py:208-222` reads authorization and validates source/cache bytes before
   output creation, result initialization and the `try/finally` at line 295.
   A synthetic accepted archive-hash failure raises before any Docker call and
   leaves no output directory or result JSON. Its reason, elapsed/preflight effort
   and unknown cost are not retained by this driver. Initialize an accepted
   attempt's receipt before input-byte validation and retain stage/reason/timing
   on validation failure; keep invalid scratch-path rejection fail-closed and
   ensure no preflight failure creates a container. `main.verify_plan()` itself
   remains outside `run()`'s timing; any separate metadata/operator invocation
   overhead must be retained separately, not presented as causal task metrics.

2. **A later Rust doc-phase setup failure can be scored as a complete outcome.**
   `oracle.py:45-61` matches the expected unit names and first summary only.
   `driver.v3.py:378-390` scores stdout alone and treats oracle qualification plus
   `native.error is None` as a complete task outcome, independent of other Cargo
   phases and native exit status. Exact two-parser-test success lines plus their
   two-pass summary, followed by rustdoc compilation failure, native exit 101
   and no transport error produce `taskOutcomeObserved=true`, `testsPassed=false`
   and `offline-outcome-observed-pending-independent-review`. The complete driver
   path was reproduced using owned placeholders and entirely fake Docker replies.
   This is a setup/noncompletion case, not terminal test assertion failure.

The retained historical run has a separate terminal **zero-test doc phase** after
the two unit tests, and stderr identifies `Doc-tests sniffnet_packet_parser`.
The pinned component manifest does not disable doctests. A successor should bind
that phase policy and score native stdout/stderr/exit/error together. Preserve
complete terminal assertion failure as a possible requested default-command
outcome, with explicit Cargo default-stop/unexecuted-phase accounting; do not
force every nonzero process exit into noncompletion or narrow the task command.

[counterexamples.py](counterexamples.py) and
[counterexamples.json](counterexamples.json) preserve both the source-level and
full mocked driver cases. Synthetic audit JSON here is test data, never real
authorization or qualification. Every Docker call was forbidden or replaced by a
fake response, with no external subprocess. The full-mock source/cache placeholders
intentionally bypass archive admission to isolate downstream classification; they
are not source/environment qualification.

## Limits and handoff

No additional finding arose in the bounded frozen commands/resources, exact
acceptance bindings, regular archive/size checks, fresh copies, nonroot/read-only/
network-none flags, output caps or Go/Vitest controls. This is not an arbitrary
plan-hostility, general service or comprehensive security review. The actual
frozen task inputs already have separate source/cache/image audits. The review
establishes rejection/classification defects, not an actual failed native attempt
or a measured fallback cost. No descriptor, authorization, frozen source or runtime
file was changed. Wait for the append-only successor, then rerun these exact
counterexamples and positive terminal-failure controls before native attempts.
