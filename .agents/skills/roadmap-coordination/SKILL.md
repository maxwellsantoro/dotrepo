---
name: roadmap-coordination
description: "Coordinate authorized parallel agent work on the dotrepo roadmap: dispatch dependency-ready packets, integrate owned changes, and verify milestone evidence. Use for roadmap implementation or team planning, rather than an isolated fix."
---

# Roadmap Coordination

Read [AGENTS.md](../../../AGENTS.md) for repository constraints,
[ROADMAP.md](../../../ROADMAP.md) for current packet dependencies and acceptance
gates, and [the execution guide](../../../docs/agent-execution.md) for the packet,
ownership, handoff, and integration protocol. These documents own the process;
do not maintain a second task list here.

When the user authorizes a team, act as coordinator or accept a bounded worker
packet from the coordinator. Without that authorization, use the same packet
and dependency checks with one agent.

- Coordinator: dispatch independently ready packets within available capacity.
  Use roadmap priority to allocate contested resources and order integration;
  do not serialize independent preparation behind an outcome gate. Before
  dispatch, settle shared contract changes and assign disjoint writable paths.
- Worker: follow the assigned scope, produce the acceptance evidence, and hand
  back a focused diff plus checks and remaining dependencies using the execution
  guide. Ask the coordinator to resolve ownership overlap before editing it.
- Coordinator: integrate at a named checkpoint, verify affected shared contracts,
  and run combined gates once the relevant changes settle. Record unfinished
  outcomes as pending even when their implementation has passed its tests.

The roadmap separates agent-completable work from operations, publication,
consenting external use, and growth evidence. Keep those joins explicit; a
reference harness, a prepared release, or operator traffic cannot close them.
Use the agent models configured by the environment. The crawler's adjudication
provider policy is a separate project configuration, not a worker assignment.
