# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md.
- Imported repo.build from web/package.json as `npm run build`.
- Inferred repo.test from .github/workflows/api-testing.yml as `rye run pytest --ignore=tests/regression --ignore=tests/query_agent --ignore=tests/vortex --junitxml=junit-integration.xml`.
- Imported repo.toolchain.min from web/package.json as `20` (Node.js).
- Discovered related relation to github.com/openobserve/openobserve from Cargo.toml repository.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Command semantic correction (2026-10-03)

2026-10-03 semantic audit withheld repo.build pending command context or usable upstream instructions; repository-default applicability remains unresolved. Source inspection timestamps are unchanged.

- Withheld `repo.build` previously extracted from `web/package.json` as `npm run build`. Component command lacks repository-default scope and working directory.
