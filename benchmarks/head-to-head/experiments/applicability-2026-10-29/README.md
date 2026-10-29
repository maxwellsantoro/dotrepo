# Applicability and consumer benefit experiments

Specification date: October 29, 2026. These are prospective specifications, not
a frozen workload, completed experiment, or claim of independent use. Repository
identities, runtime configuration, budgets and artifact hashes must be filled in
and frozen before either evaluation launches. The [roadmap](../../../../ROADMAP.md)
owns priority and dependencies.

Hypothesis: prior repository investigation remains useful after accounting for
verification, fallback and maintenance.

| Evidence boundary | Question | What cannot establish it |
| --- | --- | --- |
| Representation | Can the existing interface describe a complete instruction? | A valid schema does not establish its contents |
| Establishment | Do inspected sources support the instruction's applicability? | Policy acceptance and successful parsing do not establish correctness |
| Consumer benefit | Does access improve an agent's task outcome or reduce work? | Lookup hits, instruction reuse and final completion alone do not establish causation |

[E1](e1.md) evaluates establishment using the existing
[context contract](../../../../rfcs/0021-value-bound-execution-context.md).
[F-05](f05.md) evaluates consumer benefit; its roadmap handoffs are C1 (freeze)
and C2 (task evaluation). External participant use remains C3. E1 and F-05 may
proceed concurrently and decide acceptance independently. F-05 can report a
negative current-product result while E1 is unfinished. A later improved snapshot
gets a new experiment identity; it cannot replace that first result.

## Population and separation

| Set | Purpose | Permitted activity |
| --- | --- | --- |
| E1 development | Improve source-grounded extraction | Inspect, repair and iterate; retain failures as regressions |
| E1 held-out qualification | Measure correctness and task applicability | Freeze source gold and extractor before evaluation; no tuning against results |
| F-05 agent tasks | Measure causal consumer outcomes | Freeze tasks, environment, snapshot, configuration and scoring before runs |

Use canonical host/owner/repository plus upstream revision and task identity in
the split ledger. Identify mirrors, forks and shared upstream task sources as
potential leakage. For this first packet, exclude development and historical
evaluation repositories from both fresh evaluation sets, and keep E1 qualification
and F-05 repositories disjoint. Different task names or revisions do not make a
known repository a fresh holdout. If this separation proves infeasible, amend
the design before evaluation, declare overlaps and report them separately from
the primary holdout denominator.

Choose an external sampling frame, deterministic selection order and eligibility
rules without consulting the evaluated index, its evidence or lookup results.
Keep a screening ledger with source-based exclusions. Freeze selected identities
before any coverage check; then retain all selected tasks, including missing
profiles, unavailable setup and failed tasks. Report coverage as an observed
stratum. Do not replace tasks to manufacture a desired indexed/fallback balance.
A missing stratum limits conclusions and can motivate a separate new sample.

The PR #179 withdrawal audit is a development diagnostic, with each field keyed
to the retained [correction packet](../../../../index/telemetry/public-surface-review-20261028/README.md).
Count its actual manifest entries rather than copying a live count here. Have a
source assessor classify each original assertion before seeing its correction
disposition: contradicted/wrong scope, potentially applicable but insufficiently
supported, supported for the claimed task, or unresolved. Compare those labels
with the retained policy decision afterward. Report lost supported instructions,
removed incorrect assertions and unresolved cases separately. This measures
diagnostic precision/availability tradeoffs; additional fallback effort requires
observed task work. These known cases cannot supply generalization evidence.

## Freeze and retained artifacts

Before evaluation, retain a content-hashed manifest covering:

- Experiment identity, declared hypothesis, eligibility frame, selection rule,
  split/overlap ledger, exact task roster, scope, ecosystem and source revisions.
- Source bytes, locators and check dates; gold alternatives and completion/error
  rubrics, held outside the agent's readable environment.
- Exact extractor/consumer/scorer source and dependency locks; runtime and
  environment identities; immutable snapshot/profile bytes where applicable.
- Model/provider identity and inference settings for any model-assisted stage,
  prompts, tool permissions, cache conditions, enforced budgets and stop rules.
- Analysis rules, assignment seed/order where applicable, cost allocation and
  handling of failures, missing observations and protocol deviations.

Record who prepared development cases, authored gold, operated runs and scored
outputs. Gold assessment must be separate from extractor tuning. A fresh agent
session can separate contexts, but does not establish external participation or
erase prior corpus exposure. Declare operator familiarity and model pretraining
exposure as limitations.

The manifest must have no unresolved required fields at launch. Verify hashes
before each run; abort on changed inputs and retain the aborted receipt. Keep
raw outputs, transcripts, usage records, scorer decisions and unfavorable results
under a new dated result directory. Corrections append a disposition or create
a new run; do not rewrite source evidence or historical packets. An exposed
qualification case becomes development material for future iterations.

No new protocol, general execution service or broader metadata system is required.
If a frozen task demonstrates an interface gap, retain the failure and propose
the smallest separate change. CI evidence, release publication, operating history
and recruitment preparation retain their own gates. Preparing a brief or roster
does not send an invitation or establish consent.

## Implementation and source preparation

The [F-05 offline tooling](../../bench/agent_experiment.py) prepares/verifies
assignments and validates post-run observations under a separate randomized
contract; see [usage and receipt requirements](f05.md#tooling). Live session
isolation and enforced stopping still require runner integration.

[Source screening rules](screening-rules.md), `source-frame.json` and
`screening-reservations.json` retain the external candidate frame, prior-exposure
exclusions and disjoint screening queues before candidate source inspection.
They do not enroll tasks, establish coverage or satisfy either evaluation freeze.

The frozen [withdrawal diagnostic](../../../../index/telemetry/command-withdrawal-diagnostic-20261029/README.md)
and its subsequent comparison distinguish scope errors from insufficiently
established or prerequisite-dependent instructions. The
[operating checkpoint](../../../../index/telemetry/roadmap-operating-checkpoint-20261029/README.md)
retains the scheduled-receipt gap separately from product evidence.
