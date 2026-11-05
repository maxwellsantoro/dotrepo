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

Use the user's configured agent models. Historical pilots, provider policies
and prepared releases neither assign worker models nor grant external-action
permission. A source merge, deployed site, useful result and independent use
remain distinct outcomes. For a single-agent task, keep the same dependencies
and evidence boundaries without inventing a team.
