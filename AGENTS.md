# Repository guide

DotRepo is an open repository metadata protocol, a Rust reference toolchain and
an overlay index at `index/repos/<host>/<owner>/<repo>/`. It exposes facts,
evidence, conflicts and age through `.repo`, JSON and MCP. Code and tested
contracts outrank prose; a source implementation is not a package release,
consumer benefit or independent adoption.

## Start with the owning document

Check the actual branch, HEAD, working state and linked worktrees before changes.
Preserve unpublished work and other agents' changes. Relative guides describe
this checkout; use [release compatibility](docs/release-compatibility.md) for
installed tools.

| Need | Read first |
| --- | --- |
| Product entrypoint and shipped behavior | [README](README.md) |
| Select work or resolve a dependency | The relevant [roadmap packet](ROADMAP.md#active-execution-order) |
| Coordinate an authorized team | [Agent execution](docs/agent-execution.md); [coordination skill](.agents/skills/roadmap-coordination/SKILL.md) |
| Choose local checks or understand CI | [CONTRIBUTING](CONTRIBUTING.md#local-checks); [CI execution](docs/ci.md) |
| Decide which contract or guide applies | [Documentation map](docs/README.md) |
| Distinguish released, source-only and measured outcomes | [Workflow status](docs/workflow-status.md) |

A worker reads its dispatch, this guide, the selected packet and the owning
contract/source. Load supporting docs only when they answer a live question.
Archived plans, benchmark captures and RFC phases are not another work queue.
`CLAUDE.md` is a pointer here; do not duplicate these instructions there.

## Work routes and ownership

| Work | Owning guide and source |
| --- | --- |
| Discovery → shortlist → preliminary decision | [Decision flow](docs/experimental-decision-selection.md); `scripts/repodigest_selection.py`, `repodigest_service.py` |
| Requirement evidence and reuse | [Requirements](docs/experimental-decision-requirements.md), [source cache](docs/experimental-decision-source-cache.md); `scripts/repodigest_requirements.py` |
| Publisher setup and updates | [Maintainer path](docs/maintainer-happy-path.md); `scripts/publisher_workflow.py` |
| Rust implementation | [Toolchain layout](docs/toolchain-maintainability.md); core owns behavior, CLI/MCP/LSP delegate |
| Crawl, refresh and writeback | [Crawler guide](crates/dotrepo-crawler/README.md), [operations](docs/factual-crawl-automation.md), [index guide](index/README.md) |
| Public export, hosting or release | [Export workflow](docs/public-export-workflow.md), [Cloudflare](docs/cloudflare-deploy.md), [release checklist](docs/public-release-checklist.md) |

For an authorized team, keep one coordinator and dispatch dependency-ready work
within available capacity. One writer owns each file, index identity and shared
state path. Reserve shared interfaces/lockfiles for one owner. Workers do not
switch a shared checkout's branch or integrate other workers' patches; use
isolated worktrees when dependency states or experiments conflict. Inherit the
user's agent model configuration; crawler provider policy is a separate concern.
The execution guide owns the packet ledger, handoff and review procedure.

All repository Python commands use `uv`/`uv run`. External consumer instructions
and retained upstream examples keep their own scope. `public/`, `release-gate/`,
`operator-gate/` and `dist/` are generated outputs; fix their source rather than
editing generated files. Use unique output roots and Python environments for
concurrent work; coordinate shared Cargo builds to avoid contention.

## Contracts to preserve

- **Selection and trust:** canonical native outranks canonical mirror, then
  `checked` (legacy `verified`), `reviewed`, `imported`, `inferred`, `draft`.
  Native mode alone grants no authority. Preserve conflicts rather than silently
  blending records. [Trust model](docs/trust-model.md) owns the details.
- **Autonomy:** deterministic parsing first, bounded candidate-constrained
  escalation and fresh verification before promotion. Automation never mints
  `reviewed` or `canonical`, and cannot replace native/reviewed/canonical records.
  A previous status cannot outweigh insufficient current evidence.
- **Claims:** append-only events, legal transitions and matching identities.
  Accepted claims without canonical links remain pending. Corrections add events;
  they do not erase history. [Claim workflow](docs/maintainer-claim-review-workflow.md)
  owns the operator path.
- **Generation:** preserve unmanaged prose and refuse ambiguous layouts.
  README/SECURITY/CONTRIBUTING support managed regions; CODEOWNERS and PR templates
  support full generation. [Sync boundaries](docs/sync-boundaries.md) owns states.
- **Source age and partial knowledge:** export time does not renew factual
  inspection. Findings bind declared source dependencies and original dates;
  unchanged bytes do not prove interpretation or external premises. Missing or
  conflicting evidence stays unknown. Never invent legacy assessments.
- **Execution:** discovery, source-supported suitability and successful execution
  are separate. Scalar commands describe defaults; withhold incomplete scope or
  prerequisites. Shell screening is not runtime validation or permission.
- **MCP lookup:** preserve allowlisted origins, same-origin snapshot paths,
  redirect refusal, private-address checks and DNS pinning. Deliberate local/base
  overrides do not weaken the default. Read `crates/dotrepo-mcp/src/lookup.rs`
  and the applicable release contract before changing lookup behavior.
- **Evidence:** preserve frozen inputs, unsuccessful attempts, source captures and
  original experiment paths. Distinguish presence, correctness, useful completed
  work and independent adoption; include publisher/indexer/consumer costs at equal
  quality and freshness. No unbounded provider spend.

## Acceptance and documentation

Workers run focused checks for their owned changes. The coordinator reviews the
handoff and runs the affected combined gates once the integration settles; a
worker cannot independently accept its own repair. Reuse a successful receipt
only when its inputs remain unchanged. Changed contracts need meaningful
regressions, including the exposing case; prose changes need scope, factual and
link review, not tests that mirror wording.

Use the classifier and required `ci-gate` as described in [CI execution](docs/ci.md).
Unknown/runtime/protocol changes retain broad checks. Inspect actual branch
settings before landing; workflow configuration alone does not enforce merges.
The standalone CLI alias is outside workspace tests and has separate locked
checks. Third-party workflow actions stay full-SHA pinned with a trailing tag
comment; Rust toolchain steps specify the toolchain explicitly.

Keep one authority per fact: README for use, roadmap for dependencies, workflow
status for evidence, CONTRIBUTING/CI for gates, and the relevant contract for
semantics. Use [the documentation map](docs/README.md) instead of copying tables
or command lists. Keep counts in generated reports and completed work in the
changelog or a dated archive. Before moving a guide, preserve inbound links and
historical access. Project skills route to these owners; they do not carry
another task list, version catalog or model assignment.

Publication, deployment, external contact, spending and settings changes must
fit the user's current authorization. Existing authorization persists; do not
create an approval loop for already-authorized routine work.
