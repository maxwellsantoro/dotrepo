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

**November 4 local batch checkpoint:** D1 is locally accepted at
`fbf0898dbc52f8b4ef61968956886985da4fd5d1`: the
[durable source command](docs/decision-workflow.md) is pinned to one admitted
database/policy with restart inspection and explicit missing-source recovery.
The [D2 packet](docs/evaluations/next-team-batch-20261104/README.md) freezes six
questions, source fixtures, baseline and scoring before treatment outcomes.
Local implementation acceptance is recorded in the
[batch artifacts](/Users/maxwell/Documents/Codex/2026-11-04/task/next-team-batch/acceptance/).
D2 outcome runs, D3 upkeep costs and downstream usefulness/independent-operation
joins remain open; a local D1 command does not close them.

**Current dispatch:** Execute D2 from the sealed question/baseline packet and
run D3 on actual repository layouts; do not reimplement accepted D1 or author a
replacement question set. In a joint four-slot team, reserve one coordinator and
assign ready evaluation and actual publisher work to the other slots. Refill
capacity after bounded handoffs. Retain the bounded crawler timeout-fixture
regressions when broad integration gates run. D1 source integration passed required
exact-head checks in [PR226](https://github.com/lazy-collective/dotrepo/pull/226),
merged at `7cc1640c`, and passed main checks and existing website publication.
Package release is a separate action outside this continuation's scope.

Before selecting fresh work after a restart, reconcile canonical main, open PRs,
linked worktrees and accepted but unmerged receipts. Verify actual heads and dirty
state, then continue the earliest unmet join; a canonical folder or old dispatch
instruction does not establish that implementation is missing.

### Ready lanes and joins

| Packet | Can start now | Wait only for | Done when |
| --- | --- | --- | --- |
| **D1 — Reproducible decision entrypoint** | Accepted source command and setup/recovery path, merged in PR226; preserve it and repair demonstrated failures rather than rebuilding it | No entrypoint/source-integration prerequisite remains for D2. Use the accepted invocation, workspace and saved-result boundary; package publication remains separate and excluded | A fresh environment discovers → shortlists → describes → qualifies → decides, exits, restarts and inspects the retained result/evidence. Include unknown and missing-source recovery; verify any local package candidate separately. |
| **D2 — Useful decisions across visits** | Execute the existing sealed packet: six independently authored questions over at most three already indexed repositories and four visits, with its source truth, same-cache baseline and scoring. Use fresh outcome consumers and acceptance contexts; keep oracles, future visits and other arms out of consumer sessions | Run the end-to-end comparison against the accepted D1 interface and a frozen source/policy revision; independent acceptance follows the run | Account for all questions and attempts across initial, unchanged, relevant-change and irrelevant-change visits. Report correct/incorrect assertions, useful decisions, unknowns and unfinished attempts. Changed evidence reopens affected requirements; reuse never renews inspection age. |
| **D3 — Affordable publisher upkeep** | Run the existing publisher helper on two actual representative repository layouts through setup and two ordinary updates, including ambiguity/drift/recovery cases. Disposable fixture controls are preparation only | No D1 or favorable D2 result is required. Coordinate only if a shared importer or fixture needs changes | Record operator time, interventions, unresolved fields and source/declaration drift. Unchanged updates need no manual recataloging; genuine disagreements remain visible. Feed these costs into D2/D5. |
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
| D1 maintenance | `scripts/decision_workflow.py`, `repodigest_service.py`, `repodigest_selection.py`, `repodigest_store.py`, focused tests and decision guides, only for a demonstrated repair | Service arguments, persistence shape and packaging/lockfiles have one owner |
| D2 | Existing sealed evaluation inputs remain unchanged; new execution harness/output paths and the existing source-cache baseline | Frozen task/answer inputs stay out of treatment sessions. A change author does not independently accept that change or author its held-out result |
| D3 | `scripts/publisher_workflow.py`, its tests, publisher fixtures and maintainer guide | Shared Rust importer changes are a separately assigned dependency, not concurrent edits from D1/D3 |
| D4 | A small export/import adapter and focused recipient-policy tests after the interface join | Shared vocabulary and storage semantics need coordinator agreement; no shared runtime or protocol extension by default |
| D5 | Dated protocol, operating guide and cost/attempt records | Coordinator owns external actions and release/publication decisions |

**Durability boundary:** The legacy in-process MCP service alone retains
process-local selection IDs, attempts and final decisions
([service bounds](docs/experimental-decision-selection.md#bounds-recovery-and-accounting)).
The accepted D1 source command persists these across process exit, pins the
admitted database/policy and supports offline retained-result inspection. The
legacy bound is not an unresolved gap in that accepted command. Local acceptance
does not establish installed-release availability or useful-work outcomes.

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
