# Post-v1 Backlog

This doc turns the current post-v1 direction into a ticket-level backlog grounded
in the repo as it exists today.

Planning assumptions:

- the released public surface is already `v0`, compatibility-tested, and
  documented through RFCs 0016 through 0019
- the core public summary, trust, and query wrappers already exist in
  `dotrepo-core` and the CLI
- the hosted deployment is still GitHub Pages static hosting, so "ship hosted
  query" now means "add a thin serving/runtime layer over the existing wrapper"
  rather than inventing a new public contract
- sequencing should remain `stabilize -> compound -> expand`

## Program metrics

Use these as top-level program checks across blocks:

- public-surface regressions should be caught pre-merge by the canonical release
  gate rather than discovered from hosted drift after merge
- hosted query parity should cover at least success, missing-path,
  missing-repo, invalid-identity, and equal-authority conflict cases
- the checked-in index should contain at least two real independently reviewed
  maintainer-claim examples soon after launch
- the post-v1 seed-index growth program should hit one explicit first tranche
  such as 25 additional high-signal repos, then a larger follow-on tranche such
  as 100
- crawler readiness should first be measured by one factual-only crawl working
  end to end: discovery, materialization, writeback, and state persistence

## Priority blocks

### Block 1

- Epic 1: public contract hardening
- Epic 3: freshness and cache semantics
- Epic 4: maintainer adoption loop
- Epic 4A: managed-surface adoption tooling
- Epic 5: operator/reviewer loop

### Block 2

- Epic 2: thin hosted query serving
- remaining Epic 3 items tied to hosted query
- remaining Epic 5 items tied to release review

### Block 3

- Epic 6: claims and handoffs
- Epic 7: deliberate index growth
- Epic 8: thin extension cleanup only

### Block 4

- Epic 9: workspace/relations MVP
- Epic 10: crawler completion
- Epic 11: synthesis remains optional and subordinate

## Epic 1: Harden the released public contract

Goal: make the shipped `v0` public surface boringly reliable and make public
contract review start from one canonical gate.

Primary surfaces:
`docs/public-api-compatibility.md`,
`docs/public-release-checklist.md`,
`crates/dotrepo-core/tests/public_contract_compatibility.rs`,
`crates/dotrepo-core/tests/public_export_fixture_pack.rs`,
`crates/dotrepo-core/tests/public_query_fixture_pack.rs`,
`crates/dotrepo-core/tests/public_error_fixture_pack.rs`,
`scripts/check_release_gate.py`.

- `E1-01 Make the release gate the canonical reviewer entrypoint for public-surface changes`
  Depends on: none.
  Acceptance: `scripts/check_release_gate.py`, `docs/public-release-checklist.md`, and CI all describe the same one-command review path for fixture, compatibility, export, packaging, and hosted-link checks.

- `E1-02 Expand compatibility coverage from fixture parity to explicit drift detection`
  Depends on: `E1-01`.
  Acceptance: accidental drift in required keys, link-key names, or machine-readable error codes fails CI unless `compatibility.json` is intentionally updated as part of a versioned contract change.

- `E1-03 Add semantic drift coverage for selection and conflicts`
  Depends on: `E1-02`.
  Acceptance: public tests cover at least canonical-over-overlay, pending-canonical claim, and equal-authority conflict paths, and fail if `selection.reason` or `conflicts` semantics drift while keys stay the same.

- `E1-04 Align docs, examples, packaged export, and hosted output on one contract story`
  Depends on: `E1-01`.
  Acceptance: `docs/public-surface.md`, `docs/public-export-workflow.md`, `docs/public-export-examples.md`, the release checklist, and the CI artifact structure all describe the same `v0` contract family without contradictory caveats.

## Epic 2: Ship the thin hosted query serving layer

Goal: expose hosted query responses using the existing public query wrapper,
without inventing a second API dialect or broadening into search.

Primary surfaces:
`rfcs/0019-public-trust-and-query-wrappers.md`,
`docs/hosted-query-serving.md`,
`docs/cloudflare-hosted-query.md`,
`docs/public-surface.md`,
`.github/workflows/public-pages.yml`,
the future serving/deployment layer,
`crates/dotrepo-core/src/lib.rs` public wrapper entrypoints.

- `E2-01 Freeze the hosted query serving architecture`
  Depends on: `E1-02`.
  Acceptance: one design note picks the serving target beyond static GitHub Pages, explains request routing and cache boundaries, and keeps summary/trust static export plus query runtime under the same `v0` contract.

- `E2-02 Define the operational constraints for first hosted query serving`
  Depends on: `E2-01`.
  Acceptance: the serving plan makes cache boundaries, abuse or rate-limiting expectations, canonical base-path behavior, malformed identity or path handling, and the first runtime target explicit enough that they cannot be skipped during implementation.

- `E2-03 Implement a thin hosted query handler around public_repository_query_or_error_with_base`
  Depends on: `E2-01`, `E2-02`.
  Acceptance: hosted query accepts the same dot-path model, reuses the same public wrapper and error vocabulary, honors hosted base paths, and does not add discovery or search semantics.

- `E2-04 Add hosted query parity fixtures against local query semantics`
  Depends on: `E2-03`.
  Acceptance: representative success, missing-path, missing-repo, invalid-identity, and equal-authority conflict cases match the semantics already exercised by `public_query_fixture_pack`.

- `E2-05 Make queryTemplate resolve to a real hosted query surface`
  Depends on: `E2-03`.
  Acceptance: `queryTemplate` links emitted in inventory, summary, and trust responses point at a documented and deployed handler rather than a future placeholder.

- `E2-06 Select Cloudflare Worker + Static Assets as the hosted query runtime`
  Depends on: `E2-05`.
  Acceptance: one design note freezes Cloudflare as the first deployed target, keeps the `v0` contract unchanged, requires same-origin query resolution, and treats R2 as a scale fallback rather than a day-one dependency.

- `E2-07 Add export-time query input artifacts for edge serving`
  Depends on: `E2-06`.
  Acceptance: export produces one repo-level query-input artifact with enough snapshot data to reproduce current query semantics without runtime TOML parsing or checked-in index traversal.

- `E2-08 Refactor query serving into a pure snapshot function`
  Depends on: `E2-07`.
  Acceptance: one function can produce the current hosted query response or public error shape from identity, dot path, loaded query-input data, freshness, and base path, independent of filesystem-bound runtime assumptions.

- `E2-09 Implement the Cloudflare Worker query route`
  Depends on: `E2-08`.
  Acceptance: the Worker serves the current `v0` query route semantics, falls through to static assets for non-query requests, and preserves the existing base-path and error vocabulary.

- `E2-10 Add Wrangler project and deploy workflow`
  Depends on: `E2-09`.
  Acceptance: the repo can build and deploy one Worker-based hosted public surface from the reviewed export snapshot instead of relying on GitHub Pages as the primary hosted origin.

- `E2-11 Extend the canonical release gate for Worker smoke`
  Depends on: `E2-09`, `E2-10`.
  Acceptance: the release gate proves an emitted `queryTemplate` resolves against the Worker-hosted same-origin surface before deployment changes are treated as release-ready.

## Epic 3: Harden freshness and cache semantics

Goal: keep snapshot freshness explicit and aligned across every public surface,
while making it harder to confuse export freshness with per-record freshness.

Primary surfaces:
`rfcs/0018-static-public-serving-and-freshness.md`,
`docs/public-export-workflow.md`,
`docs/public-surface.md`,
`crates/dotrepo-core/tests/public_freshness_semantics.rs`,
`scripts/check_release_gate.py`.

- `E3-01 Publish one canonical freshness explainer for humans and agents`
  Depends on: none.
  Acceptance: docs define `generatedAt`, `snapshotDigest`, `staleAfter`, and `record.generated_at` in one place and cross-link every public-surface doc back to that explanation.

- `E3-02 Add release-gate checks for freshness regressions`
  Depends on: `E1-01`.
  Acceptance: the release gate fails if `meta.json`, inventory, summary, trust, and local public query responses drift on snapshot freshness, or if `staleAfter` stops being additive-only.

- `E3-03 Extend freshness parity to hosted query responses`
  Depends on: `E2-03`, `E3-02`.
  Acceptance: hosted query responses reuse the same freshness block semantics and snapshot identity as summary, trust, inventory, and `meta.json`.

- `E3-04 Add examples for "fresh snapshot, older record" cases`
  Depends on: `E3-01`.
  Acceptance: docs include at least one worked example where export freshness is new but the selected record's `generated_at` is older, with no suggestion that this is a trust conflict.

## Epic 4: Tighten the maintainer adoption loop

Goal: keep "install release binaries, adopt native flow, keep CI green" as a
first-class product surface.

Primary surfaces:
`docs/install.md`,
`docs/maintainer-happy-path.md`,
`examples/native-minimal/`,
`.github/workflows/release-artifacts.yml`,
`.github/workflows/ci.yml`.

- `E4-01 Audit install docs against real tagged release assets`
  Depends on: none.
  Acceptance: install docs name the actual shipped CLI, LSP, MCP, and VSIX assets and no longer rely on source-build-first instructions for the normal path.

- `E4-02 Keep examples/native-minimal as the contract test for maintainer adoption`
  Depends on: none.
  Acceptance: CI and docs keep the example repo aligned with the released command loop, and release-bundle smoke tests continue validating it with packaged binaries rather than workspace-only builds.

- `E4-03 Make init and import the shortest path into a passing CI loop`
  Depends on: `E4-02`.
  Acceptance: maintainer docs show a shortest zero-to-green path starting with `init` or `import` and ending with `validate`, `query`, `trust`, `doctor`, and `generate --check`.

- `E4-04 Improve rough failure messages in validate, query, trust, doctor, and generate --check`
  Depends on: `E4-03`.
  Acceptance: the most common unhappy paths produce corrective guidance that is tutorial-quality enough to use directly in maintainer docs and example CI output.

## Epic 4A: Add managed-surface adoption tooling

Goal: help maintainers adopt `.repo` incrementally without falsely labeling rich
handwritten policy files as fully generated when dotrepo cannot reproduce them.

Primary surfaces:
`docs/maintainer-happy-path.md`,
`docs/sync-boundaries.md`,
`crates/dotrepo-core/src/lib.rs`,
`crates/dotrepo-cli/src/main.rs`,
`examples/native-minimal/`,
native-repo CI scaffolding.

- `E4A-01 Add a per-surface adoption planner for README, SECURITY, and CONTRIBUTING`
  Depends on: `E4-03`.
  Acceptance: maintainers can ask dotrepo what ownership mode is honest for an existing file, and the tool can distinguish "fully generated is safe", "managed regions are the right fit", and "leave this unmanaged".

- `E4A-02 Add managed-marker insertion for supported Markdown surfaces`
  Depends on: `E4A-01`.
  Acceptance: dotrepo can convert an existing supported Markdown file into a valid managed-region file without discarding prose outside the managed block.

- `E4A-03 Add per-surface preview and diff before generate`
  Depends on: `E4A-01`.
  Acceptance: maintainers can preview the effect of dotrepo ownership on one surface at a time and see whether content would be rewritten, preserved in managed regions, or left unmanaged.

- `E4A-04 Teach doctor to detect lossy full-generation choices`
  Depends on: `E4-04`.
  Acceptance: `doctor` warns when a file is opted into `generate` but the current renderer can only reproduce a narrow stub and recommends `partially_managed` or `skip` where that is the more truthful ownership mode.

- `E4A-05 Make import choose safer compat defaults from on-disk files`
  Depends on: `E4A-01`.
  Acceptance: `import` defaults toward managed regions or `skip` for rich handwritten Markdown files and reserves `generate` for surfaces that are actually reproducible from current manifest data.

- `E4A-06 Add native-repo CI scaffolding for validate, doctor, and generate --check`
  Depends on: `E4-03`.
  Acceptance: maintainers can scaffold a pinned CI loop that enforces `.repo` validity and managed-surface drift checks instead of relying on local convention alone.

## Epic 5: Tighten the operator and reviewer loop

Goal: make public export review, artifact inspection, and release review
reproducible without requiring reviewers to reverse-engineer raw diffs.

Primary surfaces:
`scripts/check_release_gate.py`,
`scripts/check_operator_claim_gate.py`,
`docs/public-export-workflow.md`,
`docs/public-release-checklist.md`,
`.github/workflows/ci.yml`,
`.github/workflows/public-pages.yml`.

- `E5-01 Treat check_release_gate.py as the canonical operator release script`
  Depends on: none.
  Acceptance: docs stop describing parallel ad hoc reviewer paths as equally authoritative and instead position the script as the default end-to-end release review entrypoint.

- `E5-02 Publish one operator runbook that maps directly onto scripts and CI artifacts`
  Depends on: `E5-01`.
  Acceptance: one doc covers review order, claim correction handling, export packaging, hosted Pages inspection, and artifact upload names exactly as CI emits them.

- `E5-03 Add regression coverage for common operator mistakes`
  Depends on: `E5-01`.
  Acceptance: the release gate or operator gate catches wrong base paths, broken inventory links, stale release-note or example references, and accidental public-contract drift.

- `E5-04 Make artifact review less dependent on raw file diffs`
  Depends on: `E5-02`.
  Acceptance: reviewer-facing docs or generated summaries identify source-index changes, contract changes, claim-visibility changes, and freshness-only changes as distinct review buckets.

## Epic 6: Operationalize claims and handoffs without over-productizing them

Goal: keep claims read-only, audit-first, and materially useful in public
selection, while avoiding a premature public claim product surface.

Primary surfaces:
`docs/maintainer-claim-review-workflow.md`,
`rfcs/0013-phased-maintainer-claim-implementation-plan.md`,
`index/repos/github.com/maxwellsantoro/ries-rs/`,
`crates/dotrepo-core/tests/claim_fixture_pack.rs`,
`crates/dotrepo-cli/tests/claim_command_contract.rs`,
`scripts/check_operator_claim_gate.py`.

- `E6-01 Add a second independently reviewed real maintainer claim example`
  Depends on: `E5-02`.
  Acceptance: the checked-in index contains one more real reviewed claim path beyond `ries-rs`, with public export and operator-gate coverage of the resulting visibility or handoff state.

- `E6-02 Expand claim fixture coverage around corrected, withdrawn, rejected, disputed, and superseded histories`
  Depends on: none.
  Acceptance: claim validation and public visibility behavior remain deterministic across the full accepted and non-accepted history matrix already modeled in fixtures.

- `E6-03 Keep ordinary public claim context limited to current visibility`
  Depends on: `E1-03`, `E6-02`.
  Acceptance: summary, trust, and query responses include claim context only when it explains current selection or conflict visibility, and do not replay irrelevant rejected or withdrawn history.

- `E6-04 Extend the operator gate to cover real-claim review artifacts`
  Depends on: `E6-01`.
  Acceptance: `scripts/check_operator_claim_gate.py` produces inspectable artifacts for at least two real reviewed claim paths, not just fixture-only and staged examples.

## Epic 7: Grow the index deliberately

Goal: increase the usefulness of the overlay index without relaxing evidence or
freshness discipline.

Primary surfaces:
`index/README.md`,
`index/evidence-template.md`,
`index/review-checklist.md`,
`index/repos/`,
the factual import/crawl tooling.

- `E7-01 Set concrete post-v1 seed-index growth targets`
  Depends on: none.
  Acceptance: docs define one near-term target such as 25 high-signal repos and one follow-on target such as 100, along with the review bar for each tranche.

- `E7-02 Add review discipline for record.generated_at refreshes`
  Depends on: `E3-01`.
  Acceptance: the index review checklist and evidence template make refresh timing explicit enough that overlays do not silently age into stale folklore.

- `E7-03 Expand the index toward repos agents actually encounter often`
  Depends on: `E7-01`, `E7-02`.
  Acceptance: new overlays are evidence-backed, explicit about unknowns, and selected using a visible rubric that favors dependency centrality, popular OSS runtime or tooling repos, repositories commonly referenced in docs and tutorials, and repos that are hard for agents to infer reliably from convention alone.

## Epic 8: Keep the thin extension thin

Goal: preserve the editor shell as a wrapper around core semantics instead of a
competing product surface.

Primary surfaces:
`editors/vscode/`,
`crates/dotrepo-lsp/`,
`docs/install.md`,
`docs/maintainer-happy-path.md`,
`docs/current-status.md`.

- `E8-01 Fix only extension issues that block the core maintainer loop`
  Depends on: `E4-01`.
  Acceptance: extension fixes are scoped to installability, diagnostics, or trust/validation visibility needed for the documented maintainer path.

- `E8-02 Keep extension and LSP semantics downstream of dotrepo-core`
  Depends on: none.
  Acceptance: no editor-only trust, query, claim, or managed-sync semantics are introduced without first landing in core contracts and tests.

- `E8-03 Avoid README, SECURITY, and CODEOWNERS editing assistance beyond the current shell`
  Depends on: none.
  Acceptance: roadmap and editor docs keep richer authoring or autofix work explicitly deferred until higher-priority public and operator work is complete.

## Epic 9: Workspace and relations MVP

Goal: expand the protocol in the next justified direction without rethinking the
public contract family from scratch.

Primary surfaces:
`rfcs/0015-workspace-and-relations-model.md`,
`crates/dotrepo-schema/`,
`crates/dotrepo-core/`,
new workspace fixtures and docs.

- `E9-01 Narrow RFC 0015 into a post-v1 MVP`
  Depends on: `E1-04`.
  Acceptance: the MVP is limited to workspace membership plus a small number of directed relation kinds and keeps single-repo records primary.

- `E9-02 Add schema and validation support for workspace_root and workspace_member`
  Depends on: `E9-01`.
  Acceptance: relations are explicit, directed, identity-scoped, and trust-bearing, with narrow validation and no graph-completeness requirements.

- `E9-03 Surface workspace relations through query and trust inspection without a second truth model`
  Depends on: `E9-02`.
  Acceptance: common monorepo orientation tasks are possible through the existing trust/query mental model, with no hidden inheritance or automatic authority changes.

## Epic 10: Complete the crawler before promising scale

Goal: finish the factual crawl, scheduler, and writeback path end to end before
pretending the project can scale beyond deliberate seeding.

Primary surfaces:
`crates/dotrepo-crawler/src/discover.rs`,
`crates/dotrepo-crawler/src/main.rs`,
`crates/dotrepo-crawler/src/pipeline.rs`,
`crates/dotrepo-crawler/src/materialize.rs`,
`crates/dotrepo-crawler/src/writeback.rs`,
`crates/dotrepo-crawler/src/state.rs`,
`crates/dotrepo-crawler/src/schedule.rs`.

- `E10-01 Hit a factual-only end-to-end crawler milestone`
  Depends on: none.
  Acceptance: one milestone definition makes "discovery works, factual materialization works, writeback works, state persists, synthesis ignored" the first crawler success bar before richer scheduling or synthesis behavior is treated as important.

- `E10-02 Implement GitHub discovery in discover.rs`
  Depends on: none.
  Acceptance: `seed_repositories` returns real candidate repositories across configured star bands and honors archived and fork filters instead of bailing as scaffold-only.

- `E10-03 Wire the dotrepo-crawler CLI to the library entrypoints`
  Depends on: `E10-01`, `E10-02`.
  Acceptance: the crawler binary exposes discovery, crawl, scheduling, and state-management commands well enough to exercise the pipeline outside Rust tests.

- `E10-04 Finish factual crawl materialization and writeback as a reviewable flow`
  Depends on: `E10-03`.
  Acceptance: one end-to-end crawl can fetch GitHub metadata and conventional surfaces, build a factual overlay plan, write it back, and persist crawler state in a form operators can inspect.

- `E10-05 Use scheduler reasons as the crawler control plane`
  Depends on: `E10-04`.
  Acceptance: refresh orchestration visibly distinguishes `MissingFactualCrawl`, `HeadChanged`, `MissingSynthesis`, `PreviousSynthesisFailed`, and `SynthesisModelChanged`, and factual refresh works before synthesis is treated as important.

## Epic 11: Keep synthesis optional and subordinate

Goal: preserve the current factual-first philosophy while leaving synthesis as an
opt-in helper rather than part of the authority model.

Primary surfaces:
`crates/dotrepo-crawler/src/synth.rs`,
`crates/dotrepo-core/tests/synthesis_io_semantics.rs`,
the crawler pipeline and state model.

- `E11-01 Preserve factual build and test fields as authoritative over synthesis`
  Depends on: none.
  Acceptance: synthesis writes remain rejected when they conflict with factual `repo.build` or `repo.test`, and docs keep this as an invariant rather than a best-effort rule.

- `E11-02 Report synthesis failures without poisoning the factual substrate`
  Depends on: `E10-04`.
  Acceptance: synthesis failures are recorded, classed, and reviewable, but factual crawl outputs and refresh scheduling stay usable when synthesis is absent or failing.

- `E11-03 Delay broader synthesis rollout until factual crawl refresh is stable`
  Depends on: `E10-05`.
  Acceptance: roadmap and crawler docs position synthesis as a later optimization, not as the default way to produce trustworthy build or test guidance.

## Near-term non-goals

Do not open near-term tickets for:

- discovery-first search, browse, or ranking UX
- public mutation or submission APIs
- a public claim workflow product surface
- bundle mode
- field-level provenance as a new public-contract surface
- relation families beyond the workspace MVP
- richer editor authoring or semantic autofix flows
- sync ambitions beyond the current narrow managed-surface contract
