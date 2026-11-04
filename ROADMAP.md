# dotrepo Roadmap

Make repository understanding reusable infrastructure: extract compact facts,
preserve their evidence and age, and reuse them across agents, developers, and
tools. Overlay coverage works before maintainer adoption; API and MCP are the
primary consumer surfaces.

Optimize useful, trustworthy repository knowledge per unit of total cost.
Repository counts, extracted fields and verification labels are inputs to that
assessment, not the objective. Preserve reusable investigation, including the
limits of what was established.

This file owns priorities, dependencies, and completion gates. [README](README.md)
owns shipped behavior, [CHANGELOG](CHANGELOG.md) owns completed implementation,
and [the documentation map](docs/README.md) routes detailed work. Code and tested
contracts outrank prose; installed binaries need [version-matched documentation](docs/release-compatibility.md).

## Active execution order

### Org-review repairs — November 4, 2026 (authorized delivery)

The isolated `codex/address-org-review-20261104` checkout under
`/Users/maxwell/Documents/Codex/2026-11-04/task/address-org-review/dotrepo/`
starts from PR220's exact publisher-declaration repair. Both captured publisher
declarations reproduce their stored digests; live correction still requires a
normal merge/deployment and independent query verification. PR220 has now merged
as `d22f2205ecd992325c51228a68d2297ede62927f`; deployment verification is tracked
in the parent acceptance packet.

The read-only [refresh readiness preflight](scripts/check_refresh_readiness.py)
identified disabled Actions PR creation. After the user's explicit approval,
GitHub's organization prerequisite and DotRepo's coupled switch are enabled with
read-only defaults; the other two repositories remain disabled. The preflight
now passes. It never mutates policy or grants the scheduled token administration
access. Verify a whole bounded refresh afterward; no unattended streak is
established by a settings check.

The [captured-revision license audit](benchmarks/third-party-licenses/README.md)
recovers 46 license/notice texts, binds 52 capture roots / 530 original files,
and retains all historical source bytes. The owner subsequently authorized quarantining all three held groups. Their 108
source files are absent from the current tree, with an external hash-verified
archive, original inventories and Git history preserved. Historical restrictions
remain explicit; notices or quarantine do not establish legal clearance.

The [decision control](docs/review-outcomes-20261104/README.md) completes supported,
contradicted and unknown source decisions and retains an unfinished attempt.
Its same-cache baseline reaches the same narrow Python-declaration conclusion.
This is a developer-defined, post-exposure fixture using a synthetic reviewed
assessment; it does not close the independent utility or combined-cost gates.
The PageDigest companion control likewise retains its unfavorable request/byte
result. Existing negative studies and export-time churn remain unchanged.

Acceptance: Python suite, Ruff, captured-source/notice hashes, portable control
replay and the lightweight public/exporter/consumer gate; receipts live in the
parent packet's `acceptance/` directory. The user has authorized publishing and
merging the repair branches, deployment verification and the quarantine. Package
releases remain separate. General growth and model-provider calls are zero.

The review-follow-up deployment exposed transient R2 REST failures that restarted
whole 1,000-object batches. The bounded operator repair retries individual objects,
accounts for attempts on failure, preserves the existing authorization and rolling
request budget, and commits archive history only after validated payloads succeed.
Live delivery still requires the normal exact-commit pipeline and smoke checks.


The [November 3 measurement review](docs/measurement-review-20261103.md) separates
moving-catalog diagnostics from a fixed regression cohort. Presence and modeled
requests do not close the useful-completion or combined-work gates below. The
retained consumer results still do not establish all-in benefit; prioritize a
bounded comparison against the same source cache before general growth.


### Authorized review follow-up — November 3, 2026

The user authorized completing the remaining shared review items. This packet
binds requirement assessments to their declared source bytes and reports
`current` / `changed` / `unknown` independently of requirement outcomes; makes
publisher `.repo` discovery explicit without silently assigning maintainer
authority; indexes only `python/cpython`, `lazy-collective/dotrepo` and
`lazy-collective/pagedigest`; and repairs narrow-screen navigation. The private
coordination repository is excluded. General index-growth gates remain in place;
this named three-repository batch is the bounded exception, with no model calls.
Retain source revisions, incomplete results and validation receipts under the
November 3 `task/not-done` directory. Shared hosting and umbrella delivery stay
in the parent coordinator's scope, with separate Git and publication gates.

### Second review follow-up — November 4, 2026

Naming and shared-contract cleanup, with no new capability claims: record status
and provenance `verified` is renamed `checked` (legacy input accepted; see
[public API compatibility](docs/public-api-compatibility.md)); the decision
workflow's tools are `dotrepo.decision.*` and its guides `experimental-decision-*`;
the shared source-status rules run from PageDigest's vectors through
`scripts/source_status.py`; and a `.repo/` directory (Google's `repo` tool) now
gets a clear error instead of an I/O failure.

Open data-quality item: in mixed-language workspaces the importer can record only
the root package scripts. For example, `tauri-apps/tauri` records `pnpm build` /
`pnpm test` but not the Rust workspace's `cargo test`. Measure how often this
happens with the [factual accuracy benchmark](docs/public-factual-accuracy-benchmark.md)
before changing import heuristics, and keep partial commands labeled as partial
rather than inferring a combined command.

The current local priority is a usable **discovery → shortlist → requirement
assessment → preliminary decision** flow, source-bound recurring reuse, and a
publisher workflow derived from existing source. Execution is a separate outcome.
The [workflow status and evidence](docs/workflow-status.md) distinguishes released
interfaces from local experiments. These source changes are not a deployment.

| Workstream | Implemented locally | Next outcome gate |
| --- | --- | --- |
| Decision workflow | Bounded searches and shortlist, assessment keys independent of component pages, exact-revision describe, explicit page-limit recovery, final supported/none-established decisions and unfinished-attempt accounting | New independently authored tasks must finish with justified decisions or scoped unknowns; compare against metadata plus the same source cache |
| Source reuse | Admission-bound source cache, explicit receipt reuse, source-backed boolean assessments and separate observed recipes | Measure incremental value after verification, acquisition, review, refresh, failed attempts and maintenance |
| Publisher participation | Source-derived preview, safe first adoption and drift report using existing importer/MCP/CLI | Measure real setup/update effort, duplicate edits and unresolved ambiguity; local fixture success is not adoption |
| PageDigest companion | Recurring sync/findings and final-build publisher workflows in the sibling repository | Equivalent results/freshness against ordinary HTTP caching; no automatic extension or shared coordinator |
| Public reliability | Existing crawl, CI, history, landing and publication controls | Seven qualified scheduled days with exact-commit publication/smoke receipts; successful implementation or one day does not close the streak |

Run these bounded workflow controls before expanding coverage, introducing a
requirement interpreter, changing the public protocol, or launching another paid
campaign. Scope independent reviews by changed contract; use the
[execution guide](docs/agent-execution.md) when team work is authorized.

### Consumer evidence and stopping rules

The [latest twelve-session selection study](docs/research-evidence-20261030/selection-results.md.txt)
produced three accepted treatment decisions and two control decisions; seven
attempts did not finish. The two mutually completed pairs returned less source
text with the decision workflow but used more native tokens. Missing usage remains unknown.
The cohort was enriched after task authoring, so it is exploratory, not held out.
The new workflow fixes observed friction; local controls do not rewrite those
results or establish that a future agent will use the interface successfully.

The [corrected Discovery-100 comparison](docs/research-evidence-20261030/discovery100-correction.md.txt)
found no supported recall gain and 86% more response tokens from source-enriched
search. Prefer cheap metadata discovery and selective evidence inspection.
The [source-cache pilot](docs/research-evidence-20261030/source-cache-readme.md.txt)
did not establish an incremental token win from semantic facts over the shared
cache. The [p-limit pilot](docs/research-evidence-20261030/coding-pilot-results.md.txt)
delivered no patch passing the full test command. Preserve all failures.

A preliminary choice needs evidence appropriate to its requested requirements.
It does not require proof of every possible runtime property; it also cannot
assert an unchecked mandatory property. An exhausted shortlist may close as
none-established with explicit gaps. It is not a global absence claim.

The existing [F-05 launch no-go](benchmarks/head-to-head/f05-launch-feasibility-20261029/README.md)
and [E1 qualification result](benchmarks/head-to-head/e1-qualification-20261029/evaluation-remaining/README.md)
remain intact. Later read-only selection sessions do not qualify that separate
frozen coding campaign. Reopening it requires a bounded decision on its named
gaps, rather than another automatic environment-preparation chain.

### Operating and adoption gates

Maintain freshness, source correctness, delivery and recoverability while local
consumer work proceeds. Use [crawl operations](docs/factual-crawl-automation.md)
for current reports and `check_refresh_streak.py` for the seven-day gate; do not
copy historical counts into current-status claims. Refreshing an export is not
new source inspection. Local branches must be reconciled with current public
main and platform CI before publication.

Independent recurring use, maintainer adoption and all-in economic benefit remain
open. Outreach, publication and paid experiments need their own authorized scope.
First improve the observed workflow, then freeze a new comparison with every
attempt, including unfinished ones, in its denominator. No scaling multiplier
or break-even count follows from a microbenchmark or fixture.

The [prior execution roadmap](docs/archive/roadmap-before-workflows-20261102.md)
preserves the October E1/F-05 packet sequence and source investigations. Historical
packets remain evidence, not a parallel active task queue.

## Quality and operating constraints

These constraints apply to every packet and cannot be traded away for speed:

- **Accuracy is task-relative.** Judge an answer against requested scope and
  required context. A correct component command is not automatically a root
  instruction; an omitted essential prerequisite leaves it incomplete.
- **Abstention stays informative.** Distinguish unavailable or contradictory
  evidence, incomplete context, inapplicable scope, stale evidence and
  parser/model failure. Preserve the source and smallest next verification step
  when supported, rather than turning uncertainty into a generic command.
- **Scaling follows demonstrated utility.** Demand comes from lookup misses
  and repeated investigations. Raw profile, field and verified-record counts
  cannot substitute for usefulness after verification, fallback and maintenance.

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

### Partial knowledge and bounded efficiency experiments

Keep repository understanding, task guidance and actionable instructions
distinct. Purpose, structure, documentation and ownership need dated source
support; command candidates also need attributed scope and context. A qualified
instruction requires the complete context and task-specific consumer acceptance.
An investigation lead can remain useful with unresolved context when its source,
limitation and next verification step are explicit. The local source-cache and
selection studies now exercise those surfaces. Improve the bounded workflow
without relaxing instruction selection; measure lead usefulness separately from
instruction acceptance.

Avoid repeated work unless a relevant dependency changed. Separate repository
revision, source-blob contents, extractor/policy, inference model/prompt,
verification policy and export/snapshot identities. Reuse source acquisition
across extractor changes and unchanged blobs across revisions when sound; never
renew factual inspection age merely because an artifact was reused. Prefer
request elimination and tree reuse, then content-addressed intermediates,
persistent process/client batching, bounded concurrency and incremental export.
Keep the public format and storage architecture while measuring these changes.

Any further acquisition comparison must use a new frozen scope; Discovery-100
already retains substantial cold tree costs and incomplete traffic accounting. Retain baseline and revised results
with identical source opportunities, field dispositions, context/prerequisite
recovery, incorrect/missing facts, HTTP requests/bytes, wall/CPU time, peak memory
and refresh-planning cost. Compare equivalent cold/warm conditions and include
failures and fallback. The proposed 10–15 requests and roughly two seconds per
recrawl are targets to test, not achieved values; establish the measured baseline
first. Accept an optimization only without extraction/evidence regressions.
This experiment does not gate F-05 and authorizes no larger indexing cohort.

Keep production inference pinned while evaluating alternatives. Separate schema
compatibility, grounded task quality and production eligibility. A recurring,
versioned evaluation record should bind exact provider/model and API mode,
prompt/schema, disjoint development/qualification inputs, actual input/output/
reasoning/cached usage, retries, valid responses, correct/incorrect selections,
abstentions and cost per supported correct decision and repository including
escalation/fallback. The requested candidate families are Luna, Terra, Muse Spark
Contributor, Qwen and GLM; resolve current exact routes, availability and provider
terms at freeze time rather than treating these names as eligible endpoints.
Synthetic canaries establish compatibility only. Shadow comparisons cannot
replace the incumbent before disjoint quality requirements pass; choose the
cheapest eligible route for each decision class. Contributor-mode evaluation
requires the declared public-source privacy assumption and checked terms.
Model comparison does not block deterministic acquisition improvements or F-05.
The [October 29 comparison inventory](benchmarks/head-to-head/model-comparison-inventory-20261029/README.md)
binds current code policy and official-source observations separately. It leaves
exact evaluated routes, account/terms eligibility, frozen budgets and disjoint
grounded qualification open; advertised prices and synthetic compatibility
cannot establish cost per correct supported decision.

## Product milestones

Historical implementation lives in the changelog and retained reports. These
milestones describe outcome gates, not a second serial task list.

| Milestone | Position and remaining proof |
| --- | --- |
| M0: Working protocol/proof surface | Schema, CLI/MCP/LSP, generation, trust, hosted export exist; keep contracts and version boundaries coherent |
| M1: Autonomous index factory | Crawl, refresh, escalation, telemetry, landing exist; sustain freshness, recovery, cadence, and operating costs |
| M2: Useful shared semantic cache | Profiles, preliminary decisions and source-bound reuse exist locally; establish useful completed decisions, source accuracy and combined work at matched quality/freshness. Independent recurring use remains separate from operator controls and coding-execution evidence |
| M3: Research substrate | Search, compare, relations, optional synthesis exist; representative calibration follows consumer demand |
| M4: Ecosystem scale | Broader cohorts require observed consumer demand, independent recurring-use evidence and measured operating budgets. These growth gates do not block bounded local workflow improvements |
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
for paired tasks, [current workflow evidence](docs/workflow-status.md), and
[the scoped execution study/pilot](docs/consumer-pilot.md) and
[archived reports](docs/archive/README.md) for their historical or separate scope. Do not duplicate live
dashboards or completed inventories here.

The current checkpoint completes local consumer/publisher workflow controls,
while the separate E1/F-05 [October 29 specifications](benchmarks/head-to-head/experiments/applicability-2026-10-29/README.md)
retain their original qualification and launch boundaries. Neither needs to show
an advantage to be informative. A product-benefit claim requires the frozen
causal comparison, with verification, fallback and maintenance accounted for;
independent adoption needs consenting, independently operated recurring-use evidence. Retain unfavorable data and revise the
affected packet under a new experiment identity.

The retained repeat closes the original own-project readiness join and supplies
bounded direct reuse evidence. Broaden source-preserving task/environment evidence
when useful, freezing every changed input and retaining known coverage. Keep
independent consent/use and operating-cost gates open before adding a growth
cohort. Scoped commands remain scoped; successful fallback does not by itself
satisfy useful-answer or independent-use gates.
