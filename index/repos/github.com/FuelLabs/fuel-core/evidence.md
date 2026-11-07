# Evidence

- Imported repository name and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns with multiple team owners, so `owners.team` was left unset and `owners.maintainers` preserves the competing owner candidates.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Withheld `repo.build` from `CONTRIBUTING.md` because its Cargo selector describes a component, not the repository default.
- Imported repo.build from Makefile as `make build`.
- Imported repo.test from CONTRIBUTING.md as `cargo test --all-targets`.
- Imported repo.toolchain.min from Cargo.toml as `1.95.0` (Rust).
- Imported docs.root as `https://docs.rs/fuel-core/`. Explicit documentation link at README.md:6: [![docs](https://docs.rs/fuel-core/badge.svg)](https://docs.rs/fuel-core/)
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `fuel-core` from `GitHub API` after deterministic escalation.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to checked status (automated pipeline checks, not human review).
