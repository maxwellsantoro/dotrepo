# dotrepo Roadmap

Make repository understanding reusable infrastructure: extract compact facts,
preserve their evidence and age, and reuse them across agents, developers, and
tools. Overlay coverage works before maintainer adoption; API and MCP are the
primary consumer surfaces.

This file owns priorities, dependencies, and completion gates. [README](README.md)
owns shipped behavior, [CHANGELOG](CHANGELOG.md) owns completed implementation,
and [the documentation map](docs/README.md) routes detailed work. Code and tested
contracts outrank prose; installed binaries need [version-matched documentation](docs/release-compatibility.md).

## Active execution order

Use one coordinator and simultaneous workers. Priority determines allocation of
scarce worker slots, model budgets, and integration attention; unrelated
preparation can start together. Dispatch dependency-ready packets, land small
compatible changes, and release a worker slot when its handoff is reviewable.
Follow [the team execution guide](docs/agent-execution.md).

The current completion target is **a release-ready toolchain and a reproducible
operator study on the maintainer's other public projects**. Freeze source-grounded
tasks before checking coverage, run the paired workflows, and retain failures and
fallbacks. This is the practical next checkpoint; external recruitment is deferred.
Independent adoption, ecosystem scale, and protocol governance remain later gates.

### Start together

| Packet / priority | Work and bounded handoff | Dependencies and ownership |
| --- | --- | --- |
| F1 / 1: factual freshness | Inspect current overdue and risk-weighted audit queues; correct source-backed facts, preserve abstentions, add regression fixtures, and retain dated inspection evidence | Ready now. Own disjoint repository identities and audit/freshness changes; coordinate shared importer-policy edits with E1 |
| E1 / 2: execution metadata | Extract the complete source-grounded RFC 0021 context tuple; fixture repository/component layouts, missing prerequisites, ambiguity, and stale context | Ready now: authoring/validation/export contract exists. Own execution extraction and its tests; reserve schema/shared importer changes for coordinated integration |
| R1 / 3: delivery continuity | Maintain actual `ci-gate` enforcement, version-matched installation defaults, history restoration, and snapshot-coherent public smoke checks | Stable delivery evidence is retained in the changelog and dated receipts. Keep maintenance versions separate from main; repeat affected checks for future releases |
| C1 / 4: own-project study preparation | Freeze tasks and upstream answers from the maintainer's substantive public projects; prepare paired source-first/lookup-first runs and accounting | Ready now, before inspecting coverage. Exclude dotrepo self-tests and throwaway canaries from the primary roster; own harness/client/reporting. No external participant is needed |

With three worker slots, start F1, E1, and R1. The coordinator prepares C1's task
rubric and own-project roster, then dispatches C1 when a slot opens. With more
capacity, C1 starts immediately. Split F1 by identity or ecosystem only when
workers can avoid shared parser, policy, or record files. Keep the coordinator
available for cross-cutting decisions and integration.

Declare F1's checkpoint identities and fields before batching inspections, so
catch-up has a bounded handoff. C1 can run source-first baselines and offline
adapter tests while F1/E1 evolve; only the paired lookup-first outcome needs the
fixed integrated export. Reuse baseline runs only when inputs, policy, cache
conditions, and measured task environment remain comparable.

### Join only where evidence is required

| Packet | Prerequisites | Completion evidence |
| --- | --- | --- |
| F2: factual checkpoint | F1 corrections and fresh inspections integrated | Current record-age/overdue gate; exact-value, missing-answer, incorrect-assertion, and correct-abstention results by ecosystem; disposition for every inspected audit case |
| E2: context usefulness | E1 integrated; command tasks frozen by C1 | Sources support command, directory, scope, component, prerequisites, and source together; consumer selection/fallback tests pass; component commands stay candidates unless they establish a repository default |
| R2: stable delivery | R1 compatibility/release gates pass; publication authorized | Published artifacts and installation smoke tests before moving install defaults/generated maintainer CI; source merge alone is not a release |
| C2: operator task evaluation | C1 inputs frozen; evaluated snapshot fixed | Paired reproducible outcomes on the maintainer's projects, errors/fallback work, cache state, elapsed time, and measurement boundaries; retain unfavorable results and unknown model/maintenance costs. Operator familiarity and shared cache carryover limit conclusions |
| C3: independent pilot (deferred) | Useful operator results justify recruitment; new workload frozen, consenting participant, compatible deployed surface, and declared policy/snapshot versions | Deployed integration, observation window, repeated independent use, and outcomes meeting [pilot acceptance](docs/consumer-pilot.md#acceptance) |
| G1: first growth cohort | F2, E2, C2, C3 pass; operating budgets hold | A 50–100 repository cohort meets quality, freshness, reliability, and unit-cost budgets below |

C2 can evaluate an immutable published or development export while R2 proceeds.
The [contextual own-project packet](benchmarks/head-to-head/results/own-projects-contextual-2026-10-05/README.md)
now demonstrates direct profile instruction reuse on prepared, source-inspected
operator tasks. Use it as bounded C2 evidence; keep independent use, adoption,
population accuracy and net cost evaluation open. The next consumer milestone is
broader task/environment evidence or a practical independent pilot, rather than
another apparatus expansion or an automatic growth cohort.
The [October 6 source checkpoint](index/telemetry/roadmap-factual-checkpoint-2026-10-06.md)
and [risk audit](index/telemetry/roadmap-risk-audit-2026-10-06.md) supply bounded
semantic dispositions and repairs. Whole-record verification and broader F2
quality evidence remain open; recent record age is not semantic correctness.
The [declared remainder](index/telemetry/roadmap-risk-remainder-2026-10-06.md)
completes source dispositions for that frozen audit queue, preserving partial
assessment and record-age boundaries. It does not expand the population or
replace a coherent full-record inspection.
The [cadence checkpoint](index/telemetry/roadmap-refresh-cadence-2026-10-06.md)
diagnoses stale-base refusal and prepares a bounded deterministic regeneration.
An enabled schedule and nominal capacity do not establish successful rotation;
retain actual refresh, landing and publication evidence separately.
E1 supports explicitly declared documentation contexts as candidates; general
nested-manifest extraction and assessed acceptance remain separate work.
An external participant is not a prerequisite for the current checkpoint. C3 is
deferred; both useful C2 results and C3 acceptance evidence are required before
G1 expansion. If evaluation reveals a defect,
reopen the smallest affected packet and rerun dependent checks; preserve successful
independent work.

### Critical path and stopping rules

The current study path is `C1 -> fixed snapshot -> C2`; findings reopen affected
F1/E1 work, with F2/E2 required to establish broader quality. Stable delivery is
`R1 -> R2`. The later independent-use path is
`useful operator results + new frozen workload + consent + compatible deployment -> C3`.
Join broader quality, independent-use evidence, and operating budgets before G1.
Establish the actual blocking path from evidence instead of invented dates.

Future C2 campaigns must retain contextual selection/execution controls and the
consumer/scorer/runtime freeze already exercised by the retained campaign.
Preregister new tasks, component paths and prepared environments before inspecting
their coverage; source-inspect assessments and fix a new immutable snapshot.
Keep source preparation, correct fallback and direct profile contribution
separate. Preserve all historical packets. The remaining delivery checkpoint is
archive provisioning/backfill and actual retrieval after edge eviction, alongside
version-matched release maintenance and enforced CI.

Close a packet only when its specified artifacts/checks exist. Distinguish
**implemented**, **validated**, **operating**, **published**, and **independently
used**. Source merge, operator traffic, and successful HTTP responses cannot
substitute for the corresponding outcome. Continual freshness is a maintained
service obligation, not a task marked permanently complete.

Park work that does not unblock these gates: unrelated refactors, adoption polish,
new SDKs, bundle/workspace semantics, broad ranking/synthesis tuning, and larger
cohorts. Split a hotspot when an active change requires it; preserve its facade
rather than starting a separate repository-wide cleanup.

## Quality and operating constraints

These constraints apply to every packet and cannot be traded away for speed:

- Parse facts first, then deterministic reconciliation, bounded candidate-constrained
  adjudication, an independent opinion, and a budgeted tail. Stop with partial
  publication or abstention when evidence is insufficient. Generated overlays
  have no routine human approval tier.
- Preserve authority, conflicts, and evidence. Automation never mints `reviewed`
  or `canonical`; native mode alone grants no canonical precedence. New verification
  needs fresh source inspection, not retained status labels.
- Scalar commands describe repository defaults; component scope belongs on
  candidates. Absent context stays unassessed. Shell screening and structural
  validation do not validate execution or grant permission.
- Record age differs from export age. Retained assessments bind exact values
  and inspection timestamps; refresh cannot make unrelated facts young.
- Freeze tasks before inspecting coverage. Report presence, policy acceptance,
  correctness, completed tasks, and independent use separately. Include cache,
  fallback, and maintenance work in task-cost comparisons.
- Preserve unfavorable runs, historical captures, and frozen benchmark results.
  Correct behavior with new fixtures and dated evidence.
- Keep the schema compact and factual; synthesis cannot overwrite facts.
  Coverage does not require native adoption.

Procedures live in [AGENTS](AGENTS.md), [trust semantics](docs/trust-model.md),
[execution context](rfcs/0021-value-bound-execution-context.md),
[consumer acceptance](docs/external-consumer-integration.md#positive-command-acceptance),
and [crawler operations](docs/factual-crawl-automation.md).

Model/provider choices must earn their place through task quality, latency, and
cost. Use [the request policy](scripts/openrouter_request_policy.py) and
[dated canaries](docs/m1-escalation-canary.md) rather than copying model IDs into
every plan. Project adjudication tiers and coding-agent assignments are
separate decisions. Cache identities bind evidence, field, prompt/policy, and
model; count failed calls and preserve partial progress. Avoid unchanged work
before spending additional model or network budget.

## Product milestones

Historical implementation lives in the changelog and retained reports. These
milestones describe outcome gates, not a second serial task list.

| Milestone | Position and remaining proof |
| --- | --- |
| M0: Working protocol/proof surface | Schema, CLI/MCP/LSP, generation, trust, hosted export exist; keep contracts and version boundaries coherent |
| M1: Autonomous index factory | Crawl, refresh, escalation, telemetry, landing exist; sustain freshness, recovery, cadence, and operating costs |
| M2: Useful shared semantic cache | Profiles and cache/freshness contracts exist; F2/E2 establish broader quality, C2 measures bounded operator task outcomes, and C3 supplies independent-use evidence |
| M3: Research substrate | Search, compare, relations, optional synthesis exist; representative calibration follows consumer demand |
| M4: Ecosystem scale | C3 and measured operating budgets gate G1 and subsequent cohorts |
| M5: Maintainer adoption | Bootstrap, readiness, CI, claims exist; independent native use and durable handoffs remain separate from overlay coverage |
| M6: Open metadata standard | Independent conformance, producers/consumers, interoperable indexes, and governance follow demonstrated use |

### Growth after consumer proof

Grow in 50–100 repository cohorts toward 1,000 maintained profiles. Select demand
from exported lookup misses and repeated fallbacks; package-registry rankings
are interim proxies. Balance ecosystems, layouts, and canary needs. Every cohort
must retain:

- exact-value accuracy, incorrect assertions, missing answers, and correct
  abstentions by intent and ecosystem
- failures, quarantine, retries, recovery, and partial-progress safety
- no more than 10% stale or unknown records under the 30-day policy, and maximum
  refresh overdue of seven days
- unchanged-work avoidance and cache hits, including planning costs
- requests/bytes, materialized files, CPU/accelerator work, peak memory,
  storage/export/serving cost, and wall time
- model calls, tokens, costs, and outcomes by tier/provider/task class
- separate unchanged, changed, improved-record, and monthly maintenance costs

Raise cohort size only while budgets hold. Forecast resources before moving
toward 10,000 and broader coverage. Measure field improvement separately from
status promotion; raw counts and verified ratios are not success criteria.
Start independent conformance before full scale to avoid overfitting the protocol
to its reference implementation.

The later adoption checkpoint remains ten maintainer-owned native records and
five accepted overlay-to-native handoffs, with conversion/retention telemetry.
Claim acceptance differs from canonical publication. Bundle mode, operational
workspace composition, and generalized prose round-tripping stay deferred until
consumer use justifies them.

## Evidence and completion

Generate current values from freshness, accuracy, coverage, telemetry, policy,
and unit-cost reports. Keep each run's snapshot, inputs, commands, costs, and
outcome artifacts together. Use [the benchmark guide](benchmarks/head-to-head/README.md)
for paired tasks, [the study and later pilot](docs/consumer-pilot.md), and
[archived reports](docs/archive/README.md) for history. Do not duplicate live
dashboards or completed inventories here.

The current checkpoint produces a frozen own-project workload, paired observed
outcomes, and an honest disposition for each failure or fallback. It need not
show an advantage to be informative. A product-benefit claim still requires
improvement after fallback and maintenance costs, and independent adoption needs
the later C3 evidence. Retain unfavorable data and revise the affected packet.

The retained repeat closes the original own-project readiness join and supplies
bounded direct reuse evidence. Broaden source-preserving task/environment evidence
when useful, freezing every changed input and retaining known coverage. Keep
independent consent/use and operating-cost gates open before adding a growth
cohort. Scoped commands remain scoped; successful fallback does not by itself
satisfy useful-answer or independent-use gates.
