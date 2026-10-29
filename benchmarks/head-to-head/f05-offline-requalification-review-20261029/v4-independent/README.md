# Independent offline-driver v4 amendment review — 2026-10-29

The two v3 findings are fixed in the frozen v4 amendment. One additional exact
Rust case-identity defect remains; the reviewed v4 should not authorize native
attempts until an append-only successor addresses that defect and is retested.
No driver, oracle, plan, frozen source, earlier review or Go source was edited.

This review was authored by `/root/e1_establishment`, independently of the v4
driver author `/root/f05_harness`. The reviewer has prior F05 curation and runtime
implementation context. This is neither a blind agent session nor an independent
second gold curation. Only metadata, retained source evidence and synthetic
reviewer-owned data were used. No daemon, upstream test, network, model/provider,
index or real native workload call occurred.

## Frozen inputs

- Plan v4: `a53d9917f427464544b1b7d4bd0a50a3cd6240db8d0dcd73e72ac89e3b4f7382`.
- Driver v4: `ca4b3743c0785574f406ae81a7eb4cb9857cb22d2019ed31e1188d3013de5355`.
- Rust oracle v4: `a0846130ba9a00af4597eb17792da4ad9dc40d3ce17350c1af72b4878180b606`.

`input-bindings.json` binds these inputs, prior v3 findings, helper code, the
coordinator's frozen default-stop policy, original request, component manifest,
historical two-unit/zero-doc output and retained Cargo help. The author explicitly
handed off the v4 source/plan/control bytes as immutable before retesting.

## Fixed v3 findings and successful controls

Accepted source-archive and cache-archive hash failures now retain an initial
attempt, acceptance binding and final result. Independent controls exercised the
actual archive validator on tiny reviewer-owned tar files, with real process and
daemon functions forbidden. Both cases retain failure stage, full reason,
preflight/work/total measured timing and unknown dollar cost. They report zero
Docker calls and no container cleanup requirement. Metadata verification time is
accounted separately when supplied. This is an operator-harness receipt check,
not measured causal task effort.

Rust scoring now receives stdout, stderr, exact integer process status and
transport error. Normal passing outcome requires the terminal two-unit phase,
terminal zero-case doc phase, both stderr phase markers and exit zero. A unit
success followed by doc compilation failure is noncompletion. The frozen
coordinator policy allows a terminal unit assertion failure with native exit 101
and ordinary `--lib` failure diagnostic to provide the default-command outcome;
it explicitly records the doc phase as `unexecuted-default-stop`, unexercised,
nonterminal, with incomplete phase coverage. Compiler/setup/unknown error
diagnostics, timeout, missing phases, contradictory counts, filtering, wrong
exit and absent policy are rejected.

The independent controls passed 19 oracle cases (two expected qualified outcomes
and 17 negative cases), two accepted preflight failures and four complete mocked
driver paths: normal success, default-stop assertion failure, later doc compile
failure and unresolved cleanup. Native command strings and nonroot/read-only/
network-none/no-mount provisioning are checked on actual constructed argv; all
container replies remain synthetic. Cleanup occurs once after container creation;
a failed cleanup changes state to `cleanup-unresolved`.

Static equality checks confirmed v4 retained all three v3 tasks, exact source and
cache identities, native commands, offline setup, image, environment, resource
limits, tool command and isolation declaration. The author's metadata verifier
and full synthetic controls also passed independently again. These checks do not
qualify the real image/cache bytes or authenticate an acceptance receipt.

## Remaining finding: wrong Rust test basename accepted by suffix

`oracle_v4.py:54` delegates expected-case identification to the old helper, whose
`oracle.py:48` expression permits any nonspace prefix before an expected name.
The new case check at `oracle_v4.py:59-64` verifies only the number and terminal
statuses, then reports the helper's expected names as observed at line 71.

Replacing the terminal case
`link_type::tests::test_link_type_from_pcap_supported` with
`link_type::tests::unrelated_test_link_type_from_pcap_supported`, while retaining
the second expected case, two-pass summary, zero-case doc phase and exit zero,
still returns `qualified=true`. It also reports the missing original expected
case as observed. The actual replacement basename is different; it is not one
of the two frozen expected cases.

`name_counterexample.py` and `name-counterexample.json` retain this exact
reproduction. This is a synthetic oracle rejection defect, not an observed
upstream run or an assertion about malicious output. The same underlying match
can admit a wrong case for the fail-fast branch as well. Compare actual terminal
identities against exact frozen full IDs or exact final Rust path components,
retain those observed IDs accurately, and add a wrong-prefix case to an
append-only successor. Do not rewrite v4 or earlier observations.

## Reproduce and limits

```sh
uv run python benchmarks/head-to-head/f05-offline-requalification-review-20261029/v4-independent/review_controls.py
uv run python benchmarks/head-to-head/f05-offline-requalification-review-20261029/v4-independent/name_counterexample.py
uv run python benchmarks/head-to-head/f05-offline-requalification-20261029/driver.v4.py verify
uv run python benchmarks/head-to-head/f05-offline-requalification-20261029/controls.v4.py
```

The first review script forbids every external process and replaces all Docker
helpers. It validates owned input bytes in preflight controls; downstream fake
controls intentionally bypass source/cache archive admission to isolate driver
classification. They establish no real environment or workload qualification.
Ruff check and format checks passed for the two new review scripts.

No other actionable amendment defect was found in this bounded review. This is
not a comprehensive output-forgery, hostile-plan, filesystem or security proof.
The generated Ruff-cache entries accidentally included in the earlier v3
artifact list remain an author-disclosed freeze-disposition matter; original v3
substantive inputs and original freeze bytes are not rewritten here. Real cache
and image audit acceptance, coordinator authorization, the exact-case successor
review and actual offline attempts remain pending. No consumer campaign or
benefit claim follows from these controls.
