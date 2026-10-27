# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md.
- Ignored component-scoped commands from `web/package.json` as repository defaults.
- Imported repo.build from CONTRIBUTING.md as `cargo build --release`.
- Inferred repo.test from Cargo.toml as `cargo test --workspace`.
- Imported repo.toolchain.min from web/package.json as `20` (Node.js).
- Conflicting documentation declarations in README.md; abstained from docs.root.
- Imported docs.getting_started as `https://openobserve.ai/docs/quickstart/`. Explicit documentation link at README.md:32: <a href="https://openobserve.ai/docs/quickstart/">Quickstart</a>
- Discovered related relation to github.com/openobserve/openobserve from Cargo.toml repository.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
