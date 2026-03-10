# Roadmap sketch

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

## v0.3+
- Maintainer claim workflow and index-side authority handoff
- Bundle mode
- First-class workspace and relations support
- Public index site and query API

The next strategic track after the current v0.2 execution loop is maintainer
claim workflow and index-side handoff. That work should turn the existing claim,
supersede, and conflict semantics into a maintainer-controlled product flow
before broader public index surfaces become the center of gravity.

See [`RFC 0008`](../rfcs/0008-maintainer-claim-lifecycle.md) for the first
lifecycle draft.
See [`RFC 0013`](../rfcs/0013-phased-maintainer-claim-implementation-plan.md)
for the phased implementation order from index artifacts to reviewer workflow
and later public claim surfaces.
See [`RFC 0014`](../rfcs/0014-bundle-mode-design.md) for the first bundle-mode
design note.
See [`RFC 0015`](../rfcs/0015-workspace-and-relations-model.md) for the first
workspace and relations design direction.
See [`RFC 0016`](../rfcs/0016-public-index-site-and-query-api.md) for the first
public index site and query-API design direction.
