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
- Bundle mode
- First-class workspace and relations support
- Public index site and query API
- Maintainer claim workflow
