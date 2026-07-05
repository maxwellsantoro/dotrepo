# Evidence

- Imported repository name and description from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred repo.build from Cargo.toml as `cargo build`.
- Left `repo.test` unset because `.github/workflows/CICD.yml` suggested an unsafe shell-like command.
- Imported repo.toolchain.min from Cargo.toml as `1.88` (Rust).
- Discovered related relation to github.com/sharkdp/bat from Cargo.toml repository.
- Discovered related relation to github.com/junegunn/fzf from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.test` to `cargo test` from `Cargo.toml` after deterministic escalation.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
