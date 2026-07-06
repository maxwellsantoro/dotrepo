# Evidence

- Imported repository name from README.md.
- Left `repo.build` unset because `.github/workflows/ci.yml` suggested an unsafe shell-like command.
- Left `repo.test` unset because `.github/workflows/ci.yml` suggested an unsafe shell-like command.
- Imported repo.toolchain.min from Cargo.toml as `1.85` (Rust).
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.build` to `cargo build --workspace` from `Cargo.toml` after deterministic escalation.
- Set `repo.test` to `cargo test --workspace` from `Cargo.toml` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
