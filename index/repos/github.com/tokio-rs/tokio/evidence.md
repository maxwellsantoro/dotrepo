# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md.
- Inferred repo.build from Cargo.toml as `cargo build --workspace`.
- Inferred repo.test from .github/workflows/ci.yml as `cargo test`.
- Imported repo.toolchain.min from README.md as `1.71` (Rust).
- Discovered related relation to github.com/tokio-rs/tokio from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.
