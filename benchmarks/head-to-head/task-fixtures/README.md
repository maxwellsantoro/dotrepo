# Paired task measurement controls

`bench.tasks` scores a frozen workload against supplied paired task observations.
It does not run commands or independently witness participant execution. It keeps
source semantics, policy decisions, observed task completion, failed attempts,
fallback work, transport measurements, and unknown costs separate.

From `benchmarks/head-to-head`, use:

```bash
uv run python -m bench.tasks \
  --workload <frozen-workload.json> --observations <observations.json> \
  --out /tmp/dotrepo-task-score

# Safe operator rehearsal: executes only our fixed local fixture commands.
# Requires uv, make, and just. Choose a new output directory for every run.
uv run python -m bench.task_reference --out /tmp/dotrepo-task-controls-new
```

The reference runner freezes ten tasks before contacting its local HTTP fixture
server, alternates arm order, creates a fresh project copy per attempt, and
captures stdout, stderr, exit status, and the task-specific completion signal.
Its source decisions are scripted. It exercises ordinary build/test commands,
Make prerequisites, a required Just argument, component directory/environment,
non-running tests, absent metadata, unindexed fallback, and two intentionally
bad accepted commands. No upstream project is executed and no model is called.

The first retained [control packet](../results/task-controls-2026-10-05/) contains
workload, observations, hash-bound attempt logs, and scores. Its local timings
and source baseline do not measure product benefit. `cold` means no application
response cache; operating-system/process caches were not controlled. Model and
maintenance cost fields remain null; no net cost claim follows.

## Workload and observation contract

Use the control packet as a format example, replacing its synthetic identities
and `fixture-content` revisions with participant-selected repositories and exact
Git commits. Freeze tasks and ground-truth alternatives before coverage inspection;
retain the workload's byte digest in the observations. A participant-supplied
workload cannot use synthetic revisions.

A known-coverage operator follow-up may instead declare
`selectionBeforeCoverageInspection: false`, `knownCoverage: true`, and
`selectionFrozenBeforeExecution: true`. It still binds the frozen workload and
must not claim held-out or independent selection. This exception is restricted
to `consumerClass: operator-controlled`; participant-supplied studies retain
the before-coverage requirement.

Each task declares an identity, immutable revision, shared environment ID, task
class, and cited source evidence with locator, check time, and matching
`sourceRevision`. Acceptable instruction alternatives preserve the exact command,
working directory, repository/component scope, component, prerequisites,
parameters, environment, purpose, and source paths. An empty alternatives list
means the frozen task expects an honest absence report after source inspection.
It does not authorize execution or manufacture a replacement command.

Each task has exactly two runs. The first task runs source-first then lookup-first;
the next reverses that order, continuing to alternate. Revision, environment,
cache state, snapshot, and consumer policy must match the frozen declarations.
Timestamps cannot predate the freeze. Supply total HTTP requests, decoded bytes,
cache hits, and whole-run elapsed time including all attempts and fallback.
Actual model usage/cost and allocated maintenance cost can be null. Byte counts
are never converted to model tokens; partially unknown totals stay null.

A lookup-first record declares value presence, policy acceptance, the selected
instruction, and rejection reasons. An accepted instruction must be attempted;
a rejected instruction cannot appear as a profile attempt. Record source fallback
separately, including fallback after an accepted answer fails.

Every attempt binds a local JSON transcript by contained path and SHA-256. The
transcript must repeat task identity, instruction, exit status, and a Boolean
`oraclePassed`, with retained execution output or source-inspection observations.
The oracle must be declared and reviewed by the participant for the task; a
command's successful exit alone is insufficient. A plan outside the frozen source
alternatives is incorrect even if its transcript claims success. A final successful
fallback can complete the task while earlier wrong answers and failures remain.
For a timeout or runner failure with no exit status, bind a nonempty
`executionError` in both attempt and transcript and set `oraclePassed` to false.
The failed task remains in the denominator; an unexplained missing status is invalid.

Hashes establish consistency with supplied logs, not the truth or independence of
an externally asserted oracle. Independent verification and the external pilot's
consent, deployment, observation window, and repeated use remain separate gates.
The scorer never infers external adoption from a workload label.
