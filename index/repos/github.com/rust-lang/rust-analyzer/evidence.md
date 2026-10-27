# Evidence

- Imported repository metadata and docs entry points from README.md.
- Inferred fallback values for `repo.name` and `repo.description` because the imported files did not provide enough structured metadata.
- Ignored component-scoped commands from `editors/code/package.json` as repository defaults.
- Inferred repo.build from Cargo.toml as `cargo build --workspace`.
- Inferred repo.test from Cargo.toml as `cargo test --workspace`.
- Imported repo.toolchain.min from Cargo.toml as `1.98` (Rust).
- Imported docs.root as `./CONTRIBUTING.md`. Explicit documentation link at README.md:31: If you want to **contribute** to rust-analyzer check out the [CONTRIBUTING.md](./CONTRIBUTING.md) or
- This is an overlay record, not a maintainer-controlled canonical record.

- Deepened `owners.security_contact` from `README.md` during deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
