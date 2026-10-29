# Independent offline v5 regression review — 2026-10-29

No remaining actionable finding in the bounded v5 regression review. The exact
v4 Rust name-collision defect and the two earlier v3 receipt/phase findings are
closed by the tested successor. This does not authorize native attempts, qualify
image/cache/task equivalence or establish an agent/consumer outcome.

Stable author handoff bindings:

- Plan v5: `2d44b468d8954b42210cce44ae12c2571a835b8a89154d585a20f4cdbbce90e6`.
- Driver v5: `bf24973c7fede7d1d379de4cf740f0bba815fcfb580a13f9c29b270def0e4c6d`.
- Oracle v5: `668242c28d89556d4e23eea384fe418b04ed5f4d26bfd3126298f1a4186db57f`.

The reviewer is `/root/withdrawal_diagnostic`, separate from author
`/root/f05_harness`, with prior development/source/runtime review context. This is
not fresh blind gold or unfamiliar paid-agent exposure. No shared/frozen file,
Go source, descriptor, acceptance or audit flag was edited. No actual Docker,
external process, network, upstream source execution, package, model/provider or
index/profile call occurred. Synthetic audit/acceptance data is test data only.

## Reproductions and controls

[exact_case_regression.py](exact_case_regression.py) replays the same frozen-v4
wrong-basename output through both oracles: v4 accepts and v5 rejects. Its retained
[receipt](exact-case-regression.json) establishes the exact regression, without
rewriting the old finding. V5 compares sorted full terminal IDs and cardinality
against source/historical-output-bound IDs, and reports the actual full observed
IDs when the unit phase qualifies. Suffix or basename similarity cannot substitute
for an expected ID.

[review_controls.py](review_controls.py) retargets the independently authored v4
review controls, adds strict identity variants and forbids every external process.
[controls.json](controls.json) records:

- **23 oracle cases:** two qualified outcomes and 21 rejections, including wrong
  basename, same basename in the wrong module, duplicate full ID, wrong name in
  a failing/default-stop branch, later doc compile/setup failure, missing phases,
  contradictory summaries, filtering, timeout and invalid exit identity.
- **Two actual synthetic archive-validator failures:** accepted source/cache hash
  mismatches retain attempt, acceptance and result receipts with stage/reason,
  nonzero-or-measured preflight/total operator timing, null dollar cost, zero
  Docker calls and no cleanup requirement for a never-created container.
- **Five complete mocked driver paths:** passing two-unit/zero-doc outcome;
  terminal unit assertion failure under the frozen default-stop policy; later
  doc compilation failure; wrong exact case; and cleanup failure. Wrong cases
  and doc setup failures remain noncompletion; cleanup failure is unresolved.
- Native argv, exact scope/commands/setup/image/environment/resources remain
  unchanged from the original plan. Fresh nonroot, readonly, network-none,
  pull-never, no-host-mount flags are checked on actual constructed argv.

The default-stop exception remains explicit: terminal unit assertion failure with
exit 101 and the ordinary `--lib` diagnostic may supply the requested default
command outcome, while the doc phase is `unexecuted-default-stop`, unexercised,
nonterminal and phase coverage incomplete. All-unit success requires the terminal
zero-case doc phase, both phase markers and exit zero. Policy semantics are
unchanged from the frozen coordinator v4 decision; v5 adds strict identities from
the same historical native output. No general nonzero-exit shortcut is used.

Metadata verification and the author's full synthetic controls also passed again;
the latter retain authorization binding/flag negatives and Go nested-skip/native
format controls. These are harness checks, not a real workload or execution-time
measurement. Metadata verification outside the per-task timer is separately
retained; no operator timing is described as causal agent task effort.

## Preserved evidence and limits

[input-bindings.json](input-bindings.json) verifies all nine frozen v4 packet
bindings and all nine independent v4 reviewer files remain unchanged. All 20
substantive original v3 artifacts remain unchanged. Exactly one historical Ruff
cache entry differs, matching the already frozen generated-cache disposition;
its old manifest/freeze bytes were not repaired. New review Ruff checks use
`--no-cache`. The v3 before review and locator erratum remain intact.

This is a bounded exact-case/preflight/phase/cleanup regression review, not a
comprehensive hostile-plan, output-forgery, filesystem or general service audit.
Real image/cache audit acceptance, final protected inputs, explicit coordinator
authorization and actual native offline attempts are separate gates. Nothing here
promotes false draft flags or claims setup completeness, passing native tests,
consumer applicability or benefit. Ruff, formatting and whitespace checks passed
for the two owned review scripts.
