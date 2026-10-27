# Evidence

- Imported repository name from README.md.
- Ignored component-scoped commands from `packages/astro/package.json` as repository defaults.
- Ignored component-scoped commands from `implementations/python-consumer/pyproject.toml` as repository defaults.
- Inferred repo.test from .github/workflows/publish-crate.yml as `cargo test --locked --manifest-path implementations/rust-generator/Cargo.toml`.
- Imported repo.toolchain.min from implementations/python-consumer/pyproject.toml as `3.9` (Python).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
