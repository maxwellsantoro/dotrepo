# Evidence

- Imported repository name from README.md.
- Ignored component-scoped commands from `tools/test-helper/package.json` as repository defaults.
- Inferred repo.build from Cargo.toml as `cargo build --workspace`.
- Inferred repo.test from .github/workflows/ci.yml as `cargo test --workspace --no-fail-fast`.
- Imported repo.toolchain.min from Cargo.toml as `1.92` (Rust).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
