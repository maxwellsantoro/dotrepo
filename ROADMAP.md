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

### Fast team execution (from 2026-10-27)

The October 28 review makes contained writes, supported public links, consistent
release guidance, and value-bound query assessments prerequisites for 2.0 final.
The follow-up public audit also requires source-scoped command selection,
readable profile/miss states, package onboarding links and explicit release
channels. Its dated source dispositions and publication receipt live in
`index/telemetry/public-surface-review-20261028/`; source corrections and local
checks do not establish a deployed correction or a new package publication.
The [unreleased changelog](CHANGELOG.md#unreleased) records implementation;
complete release/operator checks and the original overwrite reproductions must
pass on the candidate being promoted. Source changes do not update installed RC
binaries or production by themselves.

The index is fresh (615/615 after the October 27 catch-up, #161), the landing
deadlock is fixed (#160, #164), `v2.0.0-rc.1` is published, and autonomous
refresh has landed unattended (#166). Optimize elapsed time, not agent count:

- **Calendar work starts first and never waits for code.** The elapsed-time
  gate is seven consecutive qualified scheduled refresh days, with retained
  budgets and exact-commit publication/smoke receipts. Run
  `scripts/check_refresh_streak.py report --require-pass` as documented in the
  [operating guide](docs/factual-crawl-automation.md#scheduled-enablement-and-landing).
  A green landing that skipped public deployment does not qualify. The window
  starts with the first qualifying receipt. Assign it on day zero; no worker can
  accelerate the observation window later.
- **Three concurrent worker lanes, disjoint by path:** (A) reliability —
  `crates/`, `scripts/`, and tests for F1/E1; (B) evidence — `benchmarks/`
  packets and frozen C1/C2 inputs; (C) surface/release — `docs/`, install and
  release surfaces for the 2.0 final promotion. Workflows and the shared
  fixtures (`scripts/fixtures/`, `crates/dotrepo-core/tests/`) are
  coordinator-owned and land in one integration PR per wave, not per worker.
- **Batch by CI scope.** Each wave lands as at most three PRs ordered
  docs/prose (minimal gate) → Python/workflows → Rust (full gate once on the
  combined tree). Workers run only focused checks; the coordinator runs the
  full gate once per wave on the integrated result (see CONTRIBUTING).
- **Twice-daily integration checkpoints.** Coordinator reviews handoffs,
  resolves contract conflicts the same checkpoint, and either lands the wave
  or returns it with the smallest missing evidence named. A packet idle for
  two checkpoints is re-scoped smaller or reassigned.
- **Stop conditions:** F2 closes when its checkpoint evidence exists; 2.0
  final ships after a clean RC window (no rc-blocking defect and successful
  scheduled runs), not after a fixed soak duration; C3 execution starts when one
  consenting participant is named in issue #170.

The current completion target is **a release-ready toolchain, qualified instruction
establishment, and a frozen autonomous unfamiliar-repository task experiment**.
The [October 29 specifications](benchmarks/head-to-head/experiments/applicability-2026-10-29/README.md)
separate representation, establishment and consumer benefit. Keep E1 development,
E1 qualification and F-05 task identities separate; freeze source-grounded tasks
before checking coverage. E1 and F-05 proceed concurrently with independent
acceptance decisions. The retained own-project study is operator evidence, not
the new holdout. Recruitment preparation can begin alongside these packets;
outreach requires authorization and independent use requires consent. Ecosystem
scale and protocol governance remain later gates.

### Start together

| Packet / priority | Work and bounded handoff | Dependencies and ownership |
| --- | --- | --- |
| F1 / 1: factual freshness | Inspect current overdue and risk-weighted audit queues; correct source-backed facts, preserve abstentions, add regression fixtures, and retain dated inspection evidence | Ready now. Own disjoint repository identities and audit/freshness changes; coordinate shared importer-policy edits with E1 |
| E1 / 2: instruction establishment | Extract complete source-grounded RFC 0021 tuples; iterate on a bounded development queue and qualify on disjoint frozen tasks under the [E1 specification](benchmarks/head-to-head/experiments/applicability-2026-10-29/e1.md) | Ready now: representation exists. Own extraction and focused tests; gold assessment is separate from implementation; reserve shared contract changes for coordinated integration |
| R1 / 3: delivery continuity | Maintain actual `ci-gate` enforcement, version-matched installation defaults, history restoration, and snapshot-coherent public smoke checks | Stable delivery evidence is retained in the changelog and dated receipts. Keep maintenance versions separate from main; repeat affected checks for future releases |
| C1 / 2: F-05 experiment preparation | Freeze unfamiliar tasks, hidden gold, model/settings, environment, snapshot, randomized independent sessions, scoring and accounting under the [F-05 specification](benchmarks/head-to-head/experiments/applicability-2026-10-29/f05.md) | Ready alongside E1, before checking coverage. Keep both evaluation sets disjoint from development and historical study repositories; own harness/client/reporting. No external participant or E1 qualification is required |

With three worker slots, start F1, E1, and C1; keep R1 delivery continuity moving
through coordinator maintenance or the next available slot. E1 and C1 have equal
priority and neither waits for the other's acceptance. Split F1 by identity or
ecosystem only when workers can avoid shared parser, policy, or record files.
Keep the coordinator available for cross-cutting decisions and integration.

Declare F1's checkpoint identities and fields before batching inspections, so
catch-up has a bounded handoff. C1 can freeze tasks and test adapters while F1/E1
evolve. C2 fixes an available export independently of E1's delivery; both arms
then run under the frozen assignment/configuration. A later improved export gets
a new experiment identity rather than replacing the earlier outcome.

### Join only where evidence is required

| Packet | Prerequisites | Completion evidence |
| --- | --- | --- |
| F2: factual checkpoint | F1 corrections and fresh inspections integrated | Current record-age/overdue gate; exact-value, missing-answer, incorrect-assertion, and correct-abstention results by ecosystem; disposition for every inspected audit case |
| E2: establishment qualification | E1 implementation fixed; disjoint E1 qualification sources/gold frozen before evaluation | Complete source-supported tuples, per-task applicability/abstention/error dispositions, scope/ecosystem breakdowns and the bounded [E1 qualification gate](benchmarks/head-to-head/experiments/applicability-2026-10-29/e1.md#decision-and-handoff); no C1/C2 result required |
| R2: stable delivery | R1 compatibility/release gates pass; publication authorized | Published artifacts and installation smoke tests before moving install defaults/generated maintainer CI; source merge alone is not a release |
| C2: F-05 agent task evaluation | C1 configuration, oracle, assignment and snapshot frozen; autonomous adapter/scorer controls pass | Independent-session randomized access comparison of correct completion, wrong actions, applicability, fallback, actual usage and costs; retain negative and inconclusive results. E1/E2 acceptance is not a prerequisite |
| C3: independent pilot | Preparation can begin now; execution needs a new frozen workload, consenting participant, compatible deployed surface, and declared policy/snapshot versions | Deployed integration, observation window, repeated independent use, and outcomes meeting [pilot acceptance](docs/consumer-pilot.md#acceptance); a prepared brief or operator result is not independent use |
| G1: first growth cohort | F2, E2, C2, C3 pass; operating budgets hold | A 50–100 repository cohort meets quality, freshness, reliability, and unit-cost budgets below |

C2 can evaluate an immutable published or development export while R2 proceeds.
The [contextual own-project packet](benchmarks/head-to-head/results/own-projects-contextual-2026-10-05/README.md)
now demonstrates direct profile instruction reuse on prepared, source-inspected
operator tasks. Use it as bounded C2 evidence; keep independent use, adoption,
population accuracy and net cost evaluation open. The next consumer milestone is
the disjoint F-05 agent task experiment or a practical independent pilot, rather
than another apparatus expansion or an automatic growth cohort.
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
The [withdrawal durability source review](index/telemetry/operating-readiness-20261029/f1-refresh-durability-review/README.md)
identifies generic Go fallbacks that can repopulate four corrected scalars. It
records proposed scope/setup controls and the separate default-evidence decision;
no refresh replay or durable enforcement fix is claimed by that review.
The subsequent [Go scope/setup development packet](index/telemetry/go-default-context-20261029/README.md)
adds bounded importer and escalation guards for those source patterns. Redigo's
build-default inference remains a separate evidence-policy decision; the fixture
results do not establish general workflow parsing or consumer benefit.
The separate [Go build-evidence packet](index/telemetry/go-build-evidence-20261029/README.md)
keeps module-only conventional build candidates diagnostic while requiring
eligible build evidence in selection and adjudication. Existing inferred workflow
commands remain observations, with their default intent and completeness separate.
The [scheduled boundary receipt](index/telemetry/roadmap-refresh-boundary-2026-10-06.md)
retains a completed batch cancelled before landing after an unsupported docs
answer passed the old reference policy. Future refreshes use the repaired source
boundary; a cancelled proposal is not operating rotation or publication proof.
E1 supports explicitly declared documentation contexts as candidates; general
nested-manifest extraction and assessed acceptance remain separate work.
The [October 29 E1 observations](benchmarks/head-to-head/e1-qualification-20261029/evaluation-remaining/README.md)
retain a negative qualification result and unresolved source gold at a frozen
implementation. Those exposed cases are known workloads for later development;
future generalization claims need fresh holdouts. The disjoint
[F-05 source packet](benchmarks/head-to-head/f05-agent-tasks-20261029/README.md)
and its [review addendum](benchmarks/head-to-head/f05-agent-tasks-review-20261029/README.md)
establish source enrollment, while executable oracles, qualified environments,
provider settings/budgets and a complete campaign freeze still gate C2.
The [next E1 development replay](benchmarks/head-to-head/e1-development-20261029b/README.md)
recovers an attributed multi-file candidate while retaining consumer abstention;
independent source-completeness review remains distinct from syntax recovery.
The [Keras source disposition](index/telemetry/e1-keras-source-disposition-20261029/README.md)
retains backend/release qualifications, local-install uncertainty and CI scope
differences. The bounded [installation-source follow-up](index/telemetry/e1-keras-install-source-20261029/README.md)
establishes helper/tool and backend-initialization conditions while retaining its
uninspected closure; it supplies no complete-instruction or execution claim.
The [mechanical source-binding verifier](index/telemetry/e1-context-binding-verifier-20261029/README.md)
checks integrity without promoting the candidate or closing completeness and
fresh held-out qualification gates.
The [Compose source disposition](index/telemetry/e1-compose-source-disposition-20261029/README.md)
establishes the documented default route and setup chain while retaining
unresolved unit coverage and the selected-input completeness gap. It authorizes
neither another candidate-only grammar nor automatic confidence promotion.
The [bounded task execution qualification](benchmarks/head-to-head/f05-qualification-20261029/README.md)
retains real native outcomes and resource failures without narrowing the frozen
tasks. The [published response capture](benchmarks/head-to-head/f05-snapshot-20261029/README.md)
retains every enrolled task, including absent profiles. Complete environment,
dependency-cache and oracle qualification still precedes the causal campaign;
no development replay, apparatus control or operator test result closes C2.
The [remaining-task source proposal](benchmarks/head-to-head/f05-qualification-next8-20261029/README.md)
and [prelaunch scope decisions](benchmarks/head-to-head/f05-prelaunch-decisions-20261029/README.md)
preserve unresolved aggregate coverage and declare exclusion policy before runs.
Faithful source-link provisioning has a bounded independent runtime review;
it does not qualify the affected upstream tasks. The
[common-image and download-cache preparation](benchmarks/head-to-head/f05-dependency-preparation-20261029/README.md)
has a bounded [independent audit](benchmarks/head-to-head/f05-dependency-preparation-review-20261029/README.md);
the [underlying image audit](benchmarks/head-to-head/f05-common-image-audit-20261029/README.md)
and [reviewed offline qualifications](benchmarks/head-to-head/f05-offline-results-review-20261029/README.md)
establish three known native scopes on that image and frozen warm caches.
The [append-only driver revisions](benchmarks/head-to-head/f05-offline-requalification-20261029/README.v5.md)
retain preflight failures, enforce exact native case identity and distinguish
assertion outcomes from later compilation/setup failure. The other task
environments and full campaign freeze remain open. The source-only
[Go-01 retry proposal](benchmarks/head-to-head/f05-go01-requalification-proposal-20261029/README.md)
retains the unknown earlier outcome and identifies setup, collection and exact
source-defined skip-policy prerequisites; it authorizes no further execution. The
[separately authorized download-only attempt](benchmarks/head-to-head/f05-go01-dependency-download-result-20261029/README.md)
retains an unqualified Go-01 cache. Its [bounded audit](benchmarks/head-to-head/f05-go01-dependency-download-review-20261029/README.md)
identifies a published compiler payload from the task's project family and
withholds runtime admission. A separately authorized
[offline npm setup observation](benchmarks/head-to-head/f05-go01-offline-setup-result-20261029/README.md)
retains successful installation under the frozen conditions; task equivalence,
native collection, exclusion-policy and campaign acceptance remain separate. The
[CI-evidence pilot](benchmarks/ci-evidence/pilot-20261029/README.md) retains
workflow/job observations without promoting them to independent execution or
consumer applicability.
An external participant is not a prerequisite for E1 qualification or F-05. C3
preparation is independent; both useful C2 results and C3 acceptance evidence are
required before G1 expansion. A complete negative C2 report closes its measurement
packet without satisfying the useful-outcome growth gate. If evaluation reveals
a defect, reopen the smallest affected packet and rerun dependent checks;
preserve successful independent work.

### Critical path and stopping rules

The independent experiment paths are `E1 development -> frozen E1 qualification -> E2`
and `C1 -> fixed snapshot/configuration -> C2 (F-05)`. Findings reopen affected
F1/E1 work under new experiment identities; F2/E2 establish broader quality.
Stable delivery is `R1 -> R2`. The independent-use path is
`new frozen workload + consent + compatible deployment -> C3`; recruitment
preparation can proceed before these execution prerequisites are met.
Join broader quality, independent-use evidence, and operating budgets before G1.
Establish the actual blocking path from evidence instead of invented dates.

Future C2 campaigns retain exporter/consumer plumbing controls and freeze the
consumer/scorer/runtime, while F-05 hides gold from the agent and scores after
execution. The historical fixed runner's pre-execution answer check cannot supply
an autonomous comparison. Preregister tasks, component paths and environments
before checking coverage; fix an immutable snapshot and randomized session plan.
Keep source verification, correct fallback and direct profile contribution
separate. Preserve all historical packets. Delivery maintenance must keep archive
retrieval after edge eviction, version-matched releases, and enforced CI working
across subsequent publications.

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
| M2: Useful shared semantic cache | Profiles and cache/freshness contracts exist; F2/E2 establish broader quality, C2 measures autonomous task benefit separately from retained operator reuse, and C3 supplies independent-use evidence |
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

The current checkpoint produces separate E1 qualification and F-05 task packets
under the [October 29 specifications](benchmarks/head-to-head/experiments/applicability-2026-10-29/README.md),
with an honest disposition for each failure or fallback. Neither needs to show
an advantage to be informative. A product-benefit claim requires the frozen
causal comparison, with verification, fallback and maintenance accounted for;
independent adoption needs C3 evidence. Retain unfavorable data and revise the
affected packet under a new experiment identity.

The retained repeat closes the original own-project readiness join and supplies
bounded direct reuse evidence. Broaden source-preserving task/environment evidence
when useful, freezing every changed input and retaining known coverage. Keep
independent consent/use and operating-cost gates open before adding a growth
cohort. Scoped commands remain scoped; successful fallback does not by itself
satisfy useful-answer or independent-use gates.
