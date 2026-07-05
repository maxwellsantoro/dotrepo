# Evidence

- Imported repository name from README.md.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Inferred repo.build from .github/workflows/ci.yml as `cargo build --verbose`.
- Inferred repo.test from Cargo.toml as `cargo test --workspace`.
- Imported repo.toolchain.min from Cargo.toml as `1.85` (Rust).
- Discovered related relation to github.com/BurntSushi/ripgrep from Cargo.toml repository.
- Discovered related relation to github.com/BurntSushi/linux from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Deepened `owners.security_contact` from `README.md` during deterministic escalation.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
