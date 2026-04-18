# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Left `repo.build` unset because `.github/workflows/ci.yml`, `.github/workflows/release.yml`, and `Cargo.toml` suggested conflicting build commands.
- Imported repo.test from Cargo.toml as `cargo test --workspace`.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
