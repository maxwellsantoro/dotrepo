# Draft invitation for a consenting external pilot

This is a preparation draft. No recipient, consent, outreach, or participation
is claimed. An engineer on an external team already using a coding agent is the
preferred participant; an existing contact reduces coordination overhead.

> We are evaluating whether dotrepo helps a coding agent find usable repository
> build and test instructions. Would you be willing to try a small paired pilot
> using repositories and tasks you select?
>
> The initial workload would contain 12 tasks across roughly 8–10 repositories,
> frozen before we inspect dotrepo coverage. We want ordinary build/test work,
> prerequisites, parameterized commands, monorepo scope, and tasks that require
> source fallback or an honest absence report. We retain all selected tasks,
> including unindexed repositories and failures.
>
> For each task, run source-first and lookup-first at the same revision and
> environment, alternating order. We provide the pinned stable MCP/HTTP client
> and outcome format. You choose and review the task-success oracles. Commands
> are metadata to inspect; the lookup client does not execute them.
>
> We would measure completed tasks, incorrect accepted instructions, failed
> attempts, fallback work, elapsed time, and actual model usage/cost where
> available. Unknown costs stay unknown. An unfavorable result is useful and
> will be retained. Nothing will be described as your adoption or endorsement
> without your agreement.
>
> If the bounded experiment is useful, we can separately agree on a deployed
> integration and observation window for repeated independent use.

Before sending, fill in the consenting contact, proposed integration, ownership
of execution/logs, treatment of confidential source data, and observation window.
See [the pilot acceptance criteria](../../docs/consumer-pilot.md#acceptance) and
[the paired observation format](../../benchmarks/head-to-head/task-fixtures/README.md).
