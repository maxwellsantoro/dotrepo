---
name: roadmap-coordination
description: "Coordinate an authorized DotRepo agent team: dispatch dependency-ready roadmap packets, preserve file ownership, independently review handoffs and integrate the required checks. Use for team execution or planning, not an isolated fix."
---

# Roadmap coordination

Read [AGENTS](../../../AGENTS.md), the selected
[roadmap packets](../../../ROADMAP.md#active-execution-order), and the
[execution guide](../../../docs/agent-execution.md). These own the constraints,
dependencies and dispatch contract; do not create another task queue here.

With a team authorized, reserve one coordinator and dispatch independently ready
work within available capacity. Distinguish preparation, interface integration
and outcome acceptance: wait only at the named join. Assign disjoint writable
paths and one owner for shared contracts before dispatch. Workers do not switch
a shared checkout's branch or overwrite other work.

Workers return a focused diff, source/fixture identity, narrow checks, retained
failures and unresolved dependencies. Rotate available capacity into independent
review; an author cannot accept its own change as independent evidence. The
coordinator integrates ready slices and owns the combined checks in
[CONTRIBUTING](../../../CONTRIBUTING.md#local-checks) and
[CI execution](../../../docs/ci.md). Do not repeat full gates per worker or reuse
receipts whose inputs changed.

Use the execution guide's [measurement and product-decision rules](../../../docs/agent-execution.md#measure-before-evaluating)
before and after comparisons. Review related delivery wording together before
merge, and use its [fresh closure review](../../../docs/agent-execution.md#review-goal-closure)
to distinguish accepted engineering, demonstrated benefit and external inputs.
Use the roadmap's current owner-operated pilot scope; collect available costs
while work proceeds. Missing independent-use evidence, complete costs or the
scheduled-history window limit claims rather than blocking bounded pilot work.

Use the user's configured agent models. Historical pilots, provider policies
and prepared releases neither assign worker models nor grant external-action
permission. A source merge, deployed site, useful result and independent use
remain distinct outcomes. For a single-agent task, keep the same dependencies
and evidence boundaries without inventing a team.
