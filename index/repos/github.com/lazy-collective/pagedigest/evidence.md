# Evidence

- Imported repository name from README.md.
- Ignored component-scoped commands from `packages/astro/package.json` as repository defaults.
- Ignored component-scoped commands from `implementations/python-consumer/pyproject.toml` as repository defaults.
- Withheld `repo.test` from `.github/workflows/publish-crate.yml` because its Cargo selector describes a component, not the repository default.
- Imported repo.toolchain.min from implementations/python-consumer/pyproject.toml as `3.9` (Python).
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

## Publisher declaration

Observed `https://github.com/lazy-collective/pagedigest` root `.repo` at `9cf6a733835d08976228936fde0e5447452d0c56`; SHA-256 `f53c9fedd8078d952eef7e0cea23a4afc50ed679313574a0d09fb4219ada1c4e`, declared status `draft`. Exact bytes are retained in `x.dotrepo.publisher_declaration.manifest_toml`. Observed facts and declaration remain separate; no maintainer authority or execution qualification is inferred.
