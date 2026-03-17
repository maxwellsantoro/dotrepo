# Roadmap

## v0.1
- Canonical root `.repo` file format
- Overlay record format for the index
- `init`, `import`, `validate`, `validate-index`, `query`, `generate`, `doctor`, and `trust` commands
- First stdio MCP server wrapping `dotrepo-core`
- Mode-aware validation
- Basic generated README and compatibility surfaces
- Seed `index/` tree plus index validation checks
- Starter GitHub Action

## v0.2
- Managed-region sync rules
- Richer import heuristics for README, CODEOWNERS, and SECURITY.md
- LSP and VS Code extension

See [`docs/sync-boundaries.md`](./sync-boundaries.md) for the current
implementation boundary around managed sync and non-round-trippable cases.
See [`rfcs/0007-lsp-and-vscode-scope.md`](../rfcs/0007-lsp-and-vscode-scope.md)
for the first editor feature set and thin-extension model.

## Completed beyond v0.2
- Maintainer claim workflow and index-side authority handoff primitives
- Static public export with repository summary and trust responses
- CI artifacts and bundle packaging for the public export

## v1.0 launch track
- Freeze the public repository summary, trust, and query-wrapper contracts
- Ship a hosted/static read-only public surface on top of the existing export
- Harden the maintainer and operator loops into the formal adoption contract
- Complete claim and handoff behavior enough for real maintainer replacements of
  overlays
- Ship installable release artifacts for the CLI, LSP, MCP server, and thin VS
  Code shell
- Turn the current CI and packaging checks into an explicit 1.0 release gate

See [`PLAN.md`](../PLAN.md) for the concrete 1.0 launch plan, exit criteria,
and deferrals.
For the ticket-level post-v1 follow-on backlog grounded in the shipped surface,
see [`docs/post-v1-backlog.md`](./post-v1-backlog.md).

## Deferred after 1.0
- Bundle mode
- First-class workspace and relations support
- Discovery-first search and ranking UX
- Public mutation or submission APIs

The current downstream track after the completed v0.2 loop and first
maintainer-claim/public-export tranche is still public read-only serving. That
work should turn the existing index, trust, conflict, and claim-visibility
semantics into a stable repository inspection surface before bundle or
workspace semantics expand the protocol again.

See [`RFC 0008`](../rfcs/0008-maintainer-claim-lifecycle.md) for the first
lifecycle draft.
See [`RFC 0013`](../rfcs/0013-phased-maintainer-claim-implementation-plan.md)
for the phased implementation order from index artifacts to reviewer workflow
and later public claim surfaces.
See [`docs/maintainer-claim-review-workflow.md`](./maintainer-claim-review-workflow.md)
for the first operator-facing maintainer-claim loop built on the current CLI.
See [`RFC 0016`](../rfcs/0016-public-index-site-and-query-api.md) for the first
public index site and query-API design direction.
See [`RFC 0017`](../rfcs/0017-public-repository-summary-response.md) for the
first concrete public repository-summary response shape.
See [`RFC 0018`](../rfcs/0018-static-public-serving-and-freshness.md) for the
first static-serving and freshness-metadata strategy.
See [`RFC 0019`](../rfcs/0019-public-trust-and-query-wrappers.md) for the
public trust/query wrappers and claim-aware public visibility rules.
See [`docs/public-export-workflow.md`](./public-export-workflow.md) for the
current local-review and CI-artifact loop over the exported public JSON tree.
See [`docs/public-surface.md`](./public-surface.md) for the public surface
architecture.
See [`docs/public-release-note.md`](./public-release-note.md) and
[`docs/public-export-examples.md`](./public-export-examples.md) for the current
release summary and consumer examples.
See [`RFC 0014`](../rfcs/0014-bundle-mode-design.md) for the first bundle-mode
design note.
See [`RFC 0015`](../rfcs/0015-workspace-and-relations-model.md) for the first
workspace and relations design direction.
