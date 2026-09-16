# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Imported SECURITY.md, but no explicit contact channel was parsed, so security_contact = "unknown" is intentional.
- Inferred repo.build from Cargo.toml as `cargo build --workspace`.
- Inferred repo.test from Cargo.toml as `cargo test --workspace`.
- Imported repo.toolchain.min from Cargo.toml as `1.96.1` (Rust).
- Discovered related relation to github.com/dani-garcia/vaultwarden from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `vaultwarden` from `GitHub API` after deterministic escalation.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Fresh verification

Prior verified authority was not inherited: this refresh must qualify using its current field scores.
