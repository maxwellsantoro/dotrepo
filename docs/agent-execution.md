# Coordinated agent execution

Use this workflow when a coordinator and concurrent workers implement
[roadmap packets](../ROADMAP.md#active-execution-order). For isolated fixes,
use [AGENTS](../AGENTS.md) and [contributing](../CONTRIBUTING.md) directly.
The project [coordination skill](../.agents/skills/roadmap-coordination/SKILL.md)
routes team requests here rather than introducing another policy source.

## Coordinator

Read the current checkout, roadmap, and relevant contracts before dispatch.
Check existing prerequisite evidence so completed implementation is not assigned
again. Keep one small packet ledger in the task or run artifacts, rather than
duplicating the roadmap in permanent status documents:

| Packet | State | Owner / writable paths | Dependencies | Handoff / checks |
| --- | --- | --- | --- | --- |
| F1 example | ready | worker, assigned repository identities | none | dated sources, patch, focused checks |

Use `ready`, `running`, `review`, `done`, or `blocked`, with a concrete reason
for a blocked dependency. Record evidence, not an agent's confidence. Reassign
ready work when a worker waits on an external dependency. Reserve a coordinator
slot and use actual available concurrency; with four slots, three workers can
operate simultaneously.

The coordinator owns shared decisions, integration, and final roadmap/docs
reconciliation. Dispatch bounded changes with reviewable handoffs, rather than
"finish M4" or "improve all accuracy." Independent evaluation answers belong
to a separate assignment from implementing the extraction being evaluated.

## Dispatch contract

Give each worker these fields:

```text
Packet and desired behavior:
Base commit / checkout:
Read first: AGENTS.md plus the shortest relevant contract and source
Writable files or repository identities:
Shared files reserved for the coordinator:
Prerequisites / assumptions supported by evidence:
Acceptance artifacts and focused checks:
Budget or external action constraints:
Handoff destination:
```

One writer owns each file at a time. Workers may read the shared checkout but
edit only assigned paths. Agree on ownership transfer before touching a shared
facade, schema, compatibility manifest, workflow, or fixture expectation file.
The coordinator can apply small shared changes after workers propose their
deltas. Partition index work by identity; parser-policy changes need one owner
across those batches.

Use isolated worktrees for incompatible dependency states, different release
lines, or overlapping integration experiments. Start from a declared commit and
return branch/commit plus patch dependencies. Use `codex/` branches and preserve
user changes. Isolation does not resolve incompatible contract decisions; agree
on those before implementation. Never copy generated outputs between release lines.

## Worker handoff

Return a concise, reproducible handoff:

```text
Packet:
Result and changed files (or branch/commit):
Sources / frozen inputs / snapshot identity:
Checks run and outcomes:
Evidence artifacts and retained failures:
Unresolved dependency or material limitation:
Follow-up required before the outcome gate can close:
```

Report failed assumptions and the smallest missing contract/evidence promptly;
continue independent authorized work. Do not edit another worker's files,
silently change public semantics, rewrite frozen results, or claim an external
outcome from a local example. Publication, settings changes, and external outreach
must fit the user's authorization and be concrete and reviewable before execution.
Preparing a pilot does not authorize contacting another project.

## Integrate and validate

1. Review each handoff against its behavior and evidence. Check for conflicting
   assumptions, generated files, and authority/version changes. Integrate
   dependency-ready patches incrementally.
2. Workers run narrow checks for owned changes. The coordinator checks affected
   shared contracts, then the required combined gates from
   [contributing](../CONTRIBUTING.md#local-checks). Schedule shared Cargo builds
   and outputs to avoid lock contention or overwritten reports.
3. Keep output roots unique per packet/run. Reuse successful checks for unchanged
   integrated state; rerun affected checks after dependent edits. Old results do
   not cover changed patches or newly evaluated age gates.
4. Before landing, verify exact head and selected CI jobs, including `ci-gate`.
   Only classifier-authorized skips are acceptable. Workflow configuration is
   separate from actual merge enforcement settings.
5. Freeze integrated exports/inputs for C2. Evaluate completed tasks and all
   fallback/maintenance work; implementation tests cannot close C2 or C3.

All repository Python tooling uses `uv`. Preserve source evidence, historical
reports, and frozen inputs; add dated evidence. Manual claim authority review
remains distinct from routine machine-gated generated overlays.

## Keep the path short

Prepare participation, frozen workloads, and release requirements from the start.
Once the pilot's inputs/deployment are fixed, collect independent observations
alongside internal C2 measurement; join completed evidence before growth.
Wait only at documented dependency edges. Workers run focused checks; the
coordinator owns combined packaging and release gates. Defer unrelated cleanup
and model changes without task evidence. Maintain adjudication policy in its
owning source; coding workers inherit the user's configured model unless the
user requests an assignment.

A packet closes when its bounded acceptance evidence exists. Source merge is
not publication; local integration is not independent adoption; an enabled
schedule is not sustained operation. Report remaining outcome dependencies and
keep ready packets moving.
