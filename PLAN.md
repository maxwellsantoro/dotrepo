# v1.0 Launch Plan

dotrepo is past the architecture-sketch phase. The v1.0 bar should be treated
as a launch program over the existing protocol, reference toolchain, and public
index, with public read-only serving as the critical path.

## What v1.0 means

dotrepo is ready for v1.0 when all of the following are true:

1. Maintainers can install the CLI, LSP, and MCP surfaces without building from
   source.
2. A repository can adopt the documented native flow and keep CI green with
   `validate`, `query`, `trust`, `doctor`, and `generate --check`.
3. Index operators can review overlays and claims, validate the index, and cut
   deterministic public exports from repeatable documented steps.
4. Public consumers can inspect repository identity and trust through a stable,
   read-only hosted/static surface with freshness metadata and a documented
   public query-wrapper contract.
5. The public promises, CI gates, and release process all match each other.

## Must ship before 1.0

### 1. Freeze the public read-only contract

- Freeze the repository summary, trust, and query-wrapper contracts now carried
  by RFCs 0016-0019.
- Treat the public response envelopes, link structure, freshness block, and
  query error behavior as release contract, not evolving guidance.
- Add compatibility coverage around contract drift, not just fixture parity for
  one exported tree.

Exit criteria:
- `public/v1/` (or equivalent versioned public path) has a documented stable
  layout.
- Public summary and trust responses are versioned and backward-compatibility
  tested.
- The query-wrapper contract is documented and validated against the same core
  semantics as local `query`.

### 2. Ship the public read-only product surface

- Promote the static export from proof artifact to real public surface.
- Publish hosted/static repository summary and trust responses at stable URLs.
- Keep the first public product identity-first and read-only; do not broaden it
  into search, submission, or mutation work before launch.
- Document freshness and snapshot expectations clearly enough for humans, agents,
  and caches to reason about staleness.

Exit criteria:
- A public consumer can fetch repository summary and trust JSON without cloning
  the index or running local tooling.
- Hosted/static output matches the documented contract and release examples.
- Freshness metadata and snapshot identity are included in every public
  response.

### 3. Harden the maintainer and operator loop

- Formalize the maintainer adoption contract around `init` or `import`, then
  `validate`, `query`, `trust`, `doctor`, and `generate --check`.
- Formalize the operator contract around `claim-init`, `claim-event`, `claim`,
  `validate-index`, and `public export`.
- Tighten failure handling, diagnostics, and docs so both happy-path and
  failure-path behavior are predictable.

Exit criteria:
- The example native repo exercises the documented maintainer CI loop.
- Operator docs cover review, correction, export, and release without manual
  guesswork.
- The intended release gate is reproducible in CI and locally.

### 4. Complete claim and handoff semantics enough for real use

- Finish the operator/reviewer claim workflow so scaffold, append, inspect,
  correct, accept or reject, and canonical handoff all feel operational rather
  than experimental.
- Surface claim context anywhere it materially explains current selection,
  including the public summary and trust responses.
- Exercise the handoff path on more than fixture-only cases so the first real
  maintainer replacements of overlays are not novel at launch time.

Exit criteria:
- Claim history remains append-only and index validation covers the expected
  edge cases.
- Public consumers can see claim context when it explains why one record won.
- At least one end-to-end maintainer handoff has been reviewed and exported
  through the normal workflow.

### 5. Ship installable distribution and thin integrations

- Publish release artifacts for the CLI, LSP, MCP server, and VS Code
  extension.
- Replace source-build-first install guidance with release install guidance.
- Keep editor and agent integrations thin, but make them install cleanly and
  smoke-test them against release-style binaries.

Exit criteria:
- Normal users can install dotrepo without cloning the repo and running
  `cargo build`.
- VS Code docs default to installed binaries instead of workspace-local
  development overrides.
- MCP and LSP smoke checks cover release-style installation paths.

### 6. Make the release gate explicit and credible

- Turn the current CI skeleton into the documented 1.0 release bar: formatting,
  workspace tests, example-repo loop, index validation, public-export fixture
  coverage, packaging, publish dry-runs, and integration smoke tests.
- Add versioning, compatibility, and upgrade guidance for the move from `0.x`
  to `1.0`.
- Fix release hygiene mismatches before launch, including branch and CI default
  branch alignment.

Exit criteria:
- One release checklist reproduces the promised behavior end to end.
- CI, branch configuration, and public docs no longer disagree about the normal
  release path.
- Core docs no longer need to frame dotrepo as "not production-hardened" to
  describe the shipped 1.0 surface.

## Safe to defer past 1.0

- Discovery-first search, ranking, and browse UX
- Public mutation or self-serve submission APIs
- Bundle mode
- First-class workspace and relations semantics
- Richer editor authoring flows, semantic autofix, and managed-marker UX
- Broader prose round-tripping beyond the current managed-surface boundary

## Sequencing

1. Freeze and test the public contracts.
2. Publish the hosted/static public surface.
3. Harden the maintainer, operator, and claim-handoff loop.
4. Ship installable release artifacts and tighten integration docs.
5. Cut the `1.0.0` release and the first versioned public export from the same
   release bar.

## Guardrails

- Do not invent a second public truth model that diverges from local trust and
  query semantics.
- Do not widen editor scope before the public surface and operator loop are
  ready.
- Do not treat bundle/workspace expansion as launch-critical scope.
- Do not turn internal cleanup into a milestone unless it directly reduces
  launch risk.
