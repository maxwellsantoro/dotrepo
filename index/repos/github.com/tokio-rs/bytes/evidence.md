# Evidence

- Imported repository name and docs entry points from README.md.
- Imported the security reporting channel from SECURITY.md.
- Inferred repo.build from Cargo.toml as `cargo build`.
- Inferred repo.test from .github/workflows/ci.yml as `RUSTFLAGS="--cfg loom -Dwarnings" cargo test --lib`.
- Imported repo.toolchain.min from Cargo.toml as `1.57` (Rust).
- Discovered related relation to github.com/tokio-rs/bytes from Cargo.toml repository.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Fresh verification

Prior verified authority was not inherited: this refresh must qualify using its current field scores.
