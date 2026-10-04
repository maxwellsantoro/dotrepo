# Evidence

- Imported repository name from README.md.
- Imported repo.build from tools/bend-fmt-lsp/package.json as `npm run build`.
- Imported repo.test from tools/bend-fmt-lsp/package.json as `npm test`.
- Imported repo.toolchain.min from tools/bend-fmt-lsp/package.json as `22` (Node.js).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Command semantic correction (2026-10-03)

2026-10-03 semantic audit withheld repo.build, repo.test pending command context or usable upstream instructions; repository-default applicability remains unresolved. Source inspection timestamps are unchanged.

- Withheld `repo.build` previously extracted from `tools/bend-fmt-lsp/package.json` as `npm run build`. Component command lacks repository-default scope and working directory.
- Withheld `repo.test` previously extracted from `tools/bend-fmt-lsp/package.json` as `npm test`. Component command lacks repository-default scope and working directory.
