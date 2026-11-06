# Coordinated agent execution

Use one coordinator and concurrent workers for an authorized team. The
[roadmap](../ROADMAP.md#active-execution-order) owns packets and dependency joins;
[AGENTS](../AGENTS.md) owns repository constraints. For an isolated fix, use
[CONTRIBUTING](../CONTRIBUTING.md) directly.

## Dispatch ready work

Keep a small ledger in the task/run artifacts, not another permanent roadmap:

| Packet | State | Owner / writable paths | Waits for | Handoff / evidence |
| --- | --- | --- | --- | --- |
| D1 example | ready / running / review / done / blocked | one writer and exact paths | named interface or acceptance receipt | diff, focused checks, remaining limit |

Reserve one coordinator slot; with four total slots, at most three workers run.
Start independent preparation together and rotate freed slots into review or the
next ready packet. A waiting outcome gate does not block independent fixture,
baseline or publisher work. For a joint two-project team, keep one shared
coordinator and respect each repository's validation/publication boundary.

The [current pilot policy](../ROADMAP.md#active-execution-order) permits bounded
owner/agent-operated work while complete costs, independent-use evidence and
scheduled operating history remain open. Those are limits on the corresponding
claims, not reasons to suspend an authorized useful task or demonstrated repair.

The coordinator settles only the shared contract needed by the next dependency:
arguments, saved-result shape, source-status meaning or fixture ownership. Assign
one owner for each shared facade, schema, lockfile and expectation file. Workers
can read the shared checkout but edit only assigned paths. Overlap requires an
explicit ownership transfer; it is not permission to revert another worker.

Use this compact dispatch:

```text
Outcome and roadmap packet:
Base commit / checkout:
Read first: shortest owning contract and source
Writable paths; shared paths reserved:
Dependency-ready inputs; interface/evidence still required:
Focused acceptance checks and artifact directory:
External-action/budget limits:
```

Read source and prerequisite receipts before assigning already completed work.
Workers inherit the user's model configuration. Crawler provider/adjudication
policy does not assign coding-agent models.

## Isolate the work, not the coordination

Use worktrees for incompatible dependency states, release lines or overlapping
experiments. In a shared checkout only the coordinator switches branches and
integrates commits. An unexpected branch/HEAD change is a stop signal for the
affected writer, not a reason to reset the workspace.

Assign unique report directories and Python environments. Partition index work
by repository identity and publisher state by path. Share a Cargo target only
when one assigned build owner schedules compatible builds; otherwise use an
isolated target. Locks prevent some corruption, but do not avoid wasted work,
report overwrites or model-budget contention. [CI execution](ci.md) owns the
concrete validation schedule and receipt-reuse rules.

## Keep review independent

Implementation, test authoring and independent acceptance are different roles.
A change author runs its focused tests and supplies evidence; a fresh reviewer
checks the contract and the exposing/counterexample cases before acceptance.
When capacity is full, rotate a finished worker into review rather than creating
a second coordinator. If independence is unavailable, label the evidence an
operator/developer control and keep the independent outcome gate open.

For useful-work comparisons, freeze tasks and source truth before inspecting
treatment answers. Consumers do not receive gold, another arm's transcripts or
review conclusions. Changing a failed task, rubric or source after exposure
requires a new experiment identity; preserve the earlier attempt. A reviewer
cannot call an outcome independent when it authored the change or the expected
result being accepted.

## Measure before evaluating

Before the first evaluation attempt, declare quality/freshness targets, cost
metrics, units, collection method and accounting boundaries for publisher,
indexer and consumer work. Collect available counters from setup onward,
including failed and unfinished attempts, fallback, audits and recovery. Keep
requests, bytes, elapsed time, CPU, tokens, money and human attention separate;
avoid summing overlapping layers. Name unavailable measurements and leave them
unknown. Do not backfill unmeasured human attention or billed usage from machine
time, byte estimates or retrospective guesses. A maintainer or implementer may
supply actual D3 upkeep measurements. Collect available measurements alongside
the owner/agent-operated D5 pilot; missing human attention, billing or all-in
costs do not block it. Independent third-party use remains a separate evidence
track, not a qualification for the owner-operated pilot.

After each comparison, record the product decision and its supporting evidence
in the owning roadmap: continue, simplify, narrow the intended workload, prefer
the baseline, or await named evidence. Preserve the original rubric, negatives
and incomplete outcomes. A decision to await evidence names what would unlock
it; a losing result does not justify expanding coverage to manufacture a win.

## Handoff and integrate

Return a bounded handoff:

```text
Result; changed files or commit; base and patch dependencies:
Source/fixture identities and observed behavior:
Focused checks, commands, outcomes and retained failure artifacts:
Unresolved assumption or outcome dependency:
```

Report an ownership conflict or failed assumption promptly, then continue any
independent authorized work. Do not silently change public semantics, edit
frozen results, or turn a local example into an adoption claim.

The coordinator reviews each handoff, integrates a small dependency-ready slice
and checks shared contracts. Workers run narrow checks; the coordinator runs the
required combined gates from [CONTRIBUTING](../CONTRIBUTING.md#local-checks) once
per settled integration. Reuse receipts only for unchanged inputs; rerun affected
checks after a dependent edit. Do not serialize all lanes until an entire wave
finishes, or run full packaging independently for every worker.

Before merging related delivery documentation, review roadmap, status,
dependency and completion wording together. Consolidate related corrections
where practical to avoid repeated publication cycles. Keep independently useful
implementation slices small; this is not permission to batch unrelated runtime
changes or weaken CI, serialized publication, archival-before-promotion,
source-freshness or exact-byte verification controls.

Before landing, verify the exact head and selected CI results, including
`ci-gate`. Only classifier-authorized skips count. Source merge, release,
deployment, enabled schedules and independent use require separate observations.
Proceed with actions already authorized by the user; preparation does not grant
new outreach, spending, publication or access-setting authority.

A packet closes when its declared acceptance evidence exists. Preserve incomplete
and losing outcomes, and name the smallest remaining dependency. The historical
execution/pilot track in [consumer evaluation](consumer-pilot.md) applies only
when that separate track is selected; it does not block a preliminary source
choice or local recurring-work control.

## Review goal closure

Before closing sustained execution, a fresh reviewer compares the original goal
scope and outcome criteria with accepted evidence, remaining executable work and
the canonical checkout/handoff map. Review scope and wording before the final
documentation merge, then confirm its exact identity and required delivery.
Resolve ready authorized work before using
an external-dependency stopping condition. Report engineering acceptance,
demonstrated product benefit and externally dependent outcomes separately; name
each missing input and what would unlock it. Preparation, developer controls and
manual retries do not substitute for independent use or qualified scheduled
history. Those observations do not block owner-operated work under the revised
pilot scope. Apply the user's actual stopping condition without weakening criteria
or inventing new work merely to keep agents occupied.
