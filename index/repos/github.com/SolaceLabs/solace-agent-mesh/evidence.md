# Evidence

- Imported repository name and docs entry points from README.md.
- Imported repo.build from client/webui/frontend/package.json as `npm run build`.
- Imported repo.test from README.md as `pytest`.
- Imported repo.toolchain.min from pyproject.toml as `3.10.16` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.

## Archive-state refresh (2026-10-03)

- Rechecked only `x.github.archived` against `https://api.github.com/repos/SolaceLabs/solace-agent-mesh` at `2026-10-03T18:16:33Z`; the upstream API now reports `archived: true`.
- Preserved the September crawl timestamps and all other imported fields; this is a scoped factual correction, not a full recrawl.
- Retained the new independent API capture in `benchmarks/head-to-head/upstream-2026-10-03/SolaceLabs--solace-agent-mesh.json`. The original September capture remains unchanged.
