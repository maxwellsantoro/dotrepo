# DotRepo roadmap

Make repository understanding reusable: finish a useful decision, retain its
evidence and age, and revisit only the work affected by a change. Optimize the
combined publisher, indexer and consumer effort at declared quality and freshness.
Repository counts and passing checks do not establish that outcome.

This file owns priorities and dependency joins. [Workflow status](docs/workflow-status.md)
owns current capabilities and evidence; [release compatibility](docs/release-compatibility.md)
owns installed-package boundaries. The [execution guide](docs/agent-execution.md)
owns dispatch and integration. The former long roadmap is preserved in the
[November 4 checkpoint](docs/archive/roadmap-before-agent-delivery-20261104.md).

## Active execution order

**Start D1, D2 preparation and D3 together.** The numbers rank product outcomes;
they are not a serial work schedule. With one coordinator and three worker slots,
run these three lanes, then reuse released slots for review and downstream work.
For a joint Lazy Collective team, D1 and PageDigest PD1 take two worker slots;
use the third for the most valuable independent evaluation/publisher packet.
Do not start a second coordinator or exceed the available concurrency.

### Ready lanes and joins

| Packet | Can start now | Wait only for | Done when |
| --- | --- | --- | --- |
| **D1 — Reproducible decision entrypoint** | One versioned source command or local artifact, setup/recovery guide and bounded persistence design using the existing Python/SQLite service and Rust importer | Coordinator settles the invocation, workspace layout and saved-result boundary before a dependent harness is integrated | A fresh environment discovers → shortlists → describes → qualifies → decides, exits, restarts and inspects the retained result/evidence. Include unknown and missing-source recovery; verify any local package candidate separately. |
| **D2 — Useful decisions across visits** | Freeze six independently authored questions over at most three already indexed repositories; prepare source truth, same-cache baseline and scoring before looking at treatment answers | Run the end-to-end comparison against the accepted D1 interface and a frozen source/policy revision; independent acceptance follows the run | Account for all questions and attempts across initial, unchanged, relevant-change and irrelevant-change visits. Report correct/incorrect assertions, useful decisions, unknowns and unfinished attempts. Changed evidence reopens affected requirements; reuse never renews inspection age. |
| **D3 — Affordable publisher upkeep** | Use the existing publisher helper on two representative repository layouts through setup and two ordinary updates; prepare ambiguity/drift/recovery cases | No D1 or favorable D2 result is required. Coordinate only if a shared importer or fixture needs changes | Record operator time, interventions, unresolved fields and source/declaration drift. Unchanged updates need no manual recataloging; genuine disagreements remain visible. Feed these costs into D2/D5. |
| **D4 — One finding handed to a second reader** | Inventory existing stored findings and source bindings; agree with PageDigest on the small test vocabulary, recipient policy and changed/missing/conflicting cases | Implementation uses a frozen D1 persistence/export interface. The usefulness comparison needs an accepted useful D2 finding | Transfer one finding between isolated stores with claim/task scope, source references/hashes, assessed revision, assumptions, attribution and original date. Recipient checks it under its own policy. Compare with sharing the same cached sources alone. |
| **D5 — One independently operated recurring workflow** | Prepare the bounded run protocol, cost ledger, operating guide and unsent participation brief from existing evidence | Real independent operation needs D1 acceptance, D2 useful completion, D3 upkeep evidence and an authorized operator. D4 is required only when findings cross readers | Freeze scope, freshness, completion criteria, finite runs and budget. Count publisher/indexer/consumer work, fallback and unfinished attempts; report losing results. Outreach, spend and package publication must fit the user's authorization. |

Preparation is useful work but cannot close its outcome gate. In particular,
D4 cases can be designed before a useful finding exists; a synthetic handoff
does not substitute for that finding. D5 documents do not establish consent or
independent operation. No favorable economic result is required to report a
completed, honest comparison.

### Ownership for simultaneous work

These are suggested writable areas, not permission to edit every file in a row.
The coordinator assigns exact files and test paths in each dispatch and resolves
overlap before work. Workers may read other lanes; one writer owns a shared file.

| Lane | Existing source and likely writable area | Reserved boundary |
| --- | --- | --- |
| D1 | `scripts/repodigest_service.py`, `repodigest_selection.py`, `repodigest_store.py`, focused tests and the decision setup/selection guides | Service arguments, persistence shape and packaging/lockfiles have one owner |
| D2 | A new dated evaluation packet and its harness/fixtures; existing source-cache baseline | Frozen task/answer inputs stay out of treatment sessions. A change author does not independently accept that change or author its held-out result |
| D3 | `scripts/publisher_workflow.py`, its tests, publisher fixtures and maintainer guide | Shared Rust importer changes are a separately assigned dependency, not concurrent edits from D1/D3 |
| D4 | A small export/import adapter and focused recipient-policy tests after the interface join | Shared vocabulary and storage semantics need coordinator agreement; no shared runtime or protocol extension by default |
| D5 | Dated protocol, operating guide and cost/attempt records | Coordinator owns external actions and release/publication decisions |

**D1 has a real persistence gap.** Source bodies and assessments already persist
in SQLite, but selection IDs, attempts and final decisions are currently
process-local ([current bounds](docs/experimental-decision-selection.md#bounds-recovery-and-accounting)).
Specify what is retained and how restart recovers it before calling the whole
workflow durable. A startup wrapper alone does not close D1.

Freeze interfaces only as far as the next consumer needs them. Integrate a small
working path first; do not wait for every lane or invent a general framework.
While a gate runs, workers can prepare the next independent packet in isolated
outputs. Fix an exposed failure before enlarging its workload.

## Evidence and stopping rules

- The twelve-session selection study had seven unfinished attempts. Completed
  pairs reduced source reading but did not establish token or total-cost savings.
  Discovery-100 retained the same supported recall with 86% more response tokens.
  These [negative results](docs/workflow-status.md#latest-evidence) stand.
- D2/D5 compare against metadata plus the **same source cache**, at equal source
  opportunities, freshness and verification policy. Include acquisition, review,
  refresh, parsing, serving, local integrity reads and publisher upkeep. Unknown
  usage/cost stays unknown; bytes divided by four is not billed token use.
- Include publication-only churn: unchanged material facts can still produce
  different response bytes. Measure it before changing representation; preserve
  exact-byte checks, snapshot coherence and factual inspection age.
- Task authoring, implementation and acceptance have explicit owners. A fresh
  reviewer validates a changed contract; hidden expected answers and other arms'
  transcripts never enter consumer sessions. If independence is unavailable,
  label the result an operator/developer control and leave the independent gate open.
- Supported preliminary fit, scoped none-established/unknown and successful
  execution remain different outcomes. Keep incorrect assertions, refusals,
  incomplete work and failed attempts in the denominator.
- If matched work loses, simplify the interface or narrow the intended workload.
  Do not remove hard cases, audits or publisher cost to manufacture a win.

## Continuous reliability and deferred work

Freshness, source integrity, recovery and delivery continue alongside these
lanes. Collect existing scheduled receipts while implementation proceeds;
`check_refresh_streak.py` owns the seven-qualified-day control. Elapsed time in
that control does not block independent product work. An export refresh does
not inspect upstream sources again.

General catalog growth, additional providers/models, broad prose synthesis,
bundle/workspace protocols and a shared hosted-memory service remain deferred.
Reopen a bounded item when a completed workflow exposes its specific need.
Independent recurring-use and combined-cost evidence precede general growth;
no repository-count target or old pilot schedule overrides that join.

For required validation use [CONTRIBUTING](CONTRIBUTING.md#local-checks) and
[CI execution](docs/ci.md). Workers run focused checks; the coordinator accepts
the settled integration once per affected scope. Source merge, package release,
site deployment and independent use are separately recorded events.

## Historical entrypoints

The links below preserve earlier roadmap entrypoints. Their dated text and
original outcome bounds are in the checkpoint; they are not another ready queue.

<a id="vision-priorities--november-4-2026"></a>
<a id="delivered-source-and-retained-review-history"></a>
<a id="org-review-repairs--november-4-2026-authorized-delivery"></a>
<a id="authorized-review-follow-up--november-3-2026"></a>
<a id="second-review-follow-up--november-4-2026"></a>

[Earlier priorities and delivery observations](docs/archive/roadmap-before-agent-delivery-20261104.md#active-execution-order).

<a id="consumer-evidence-and-stopping-rules"></a>
<a id="operating-and-adoption-gates"></a>
<a id="quality-and-operating-constraints"></a>
<a id="partial-knowledge-and-bounded-efficiency-experiments"></a>

[Earlier evidence, operating constraints and scoped experiments](docs/archive/roadmap-before-agent-delivery-20261104.md#consumer-evidence-and-stopping-rules).

<a id="product-milestones"></a>
<a id="growth-after-consumer-proof"></a>
<a id="evidence-and-completion"></a>

[M0–M6 and earlier growth/adoption checkpoints](docs/archive/roadmap-before-agent-delivery-20261104.md#product-milestones)
retain their historical meaning. The D1–D5 joins above select current work.
