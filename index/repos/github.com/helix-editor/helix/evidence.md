# Evidence

- Imported repository name and docs entry points from README.md.
- Inferred repo.build from Cargo.toml as `cargo build --workspace`.
- Inferred repo.test from .github/workflows/build.yml as `cargo test --workspace`.
- Imported repo.toolchain.min from Cargo.toml as `1.90` (Rust).
- Imported docs.root as `https://docs.helix-editor.com/`. Explicit documentation link at README.md:13: [![Documentation](https://shields.io/badge/-documentation-452859)](https://docs.helix-editor.com/)
- Imported docs.getting_started as `https://docs.helix-editor.com/install.html`. Explicit documentation link at README.md:48: [Installation documentation](https://docs.helix-editor.com/install.html).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
