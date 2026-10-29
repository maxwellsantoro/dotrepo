# Draft invitation for a consenting external pilot

This is a preparation draft. No recipient, consent, outreach, or participation
is claimed. An engineer on an external team already using a coding agent is the
preferred participant; an existing contact reduces coordination overhead.

> We are evaluating whether dotrepo helps a coding agent find usable repository
> build and test instructions. Would you be willing to try a small paired pilot
> using repositories and tasks you select?
>
> We propose a small workload, initially 12 tasks across roughly 8–10 repositories,
> with its size and selection rule agreed with you and frozen before we inspect
> dotrepo coverage. This external pilot would have its own protocol and would not
> inherit the internal F-05 campaign's roster or prescribed session count. We want
> ordinary build/test work, prerequisites, parameterized commands, monorepo scope,
> and tasks that require
> source fallback or an honest absence report. We retain all selected tasks,
> including unindexed repositories and failures.
>
> For each task, compare source-first and dotrepo access at the same revision in
> fresh independent agent sessions, with randomized order and isolated workspaces
> and caches. Before execution we would agree on and freeze the model/settings,
> environment, tools, cache state, snapshot, scoring, budgets and cost accounting.
> We provide a version-pinned compatible MCP/HTTP integration and outcome format.
> You choose and review the task-success oracles, kept outside the agent's readable
> environment; scoring happens afterward. Commands are metadata to inspect; the
> lookup client does not execute them.
>
> We would measure completed tasks, incorrect accepted instructions, failed
> attempts, setup and fallback work, elapsed time, actual model usage including
> failed-call charges, and allocated preparation/maintenance costs where available.
> Unknown costs stay unknown. An unfavorable result is useful and will be retained.
> Nothing will be described as your adoption or endorsement
> without your agreement.
>
> We would agree on a compatible deployed integration and observation window
> before collecting pilot outcomes. Repeated use and any adoption or endorsement
> claim would need a separate agreement.

Preparation can proceed alongside E1 and the internal F-05 evaluation; neither
must pass before recruitment preparation. Before sending, identify the proposed
contact, integration, ownership of execution/logs, treatment of confidential
source data, and observation window. Sending needs separate explicit authorization.
Participant consent, a compatible deployed integration and a complete new pilot
freeze are required before collecting independent outcomes. This draft remains
unsent.
See [the pilot acceptance criteria](../../docs/consumer-pilot.md#acceptance) and
[the autonomous F-05 design principles](../../benchmarks/head-to-head/experiments/applicability-2026-10-29/f05.md).
The [historical paired observation format](../../benchmarks/head-to-head/task-fixtures/README.md)
requires a compatible adapter before use with randomized autonomous sessions.
