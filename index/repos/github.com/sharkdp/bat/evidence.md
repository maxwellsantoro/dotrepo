# Evidence

- Imported repository name from README.md.
- Imported SECURITY.md, but no explicit contact channel was parsed, so security_contact = "unknown" is intentional.
- Imported repo.build from README.md as `cargo build --bins`.
- Imported repo.test from README.md as `cargo test`.
- Imported repo.toolchain.min from Cargo.toml as `1.88` (Rust).
- Discovered related relation to github.com/sharkdp/bat from Cargo.toml repository.
- Discovered related relation to github.com/junegunn/fzf from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.
