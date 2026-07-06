# Evidence

- Imported repository name from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns; `owners.team` prefers `@juspay/hyperswitch-maintainers` from the repo-wide rule, and `owners.maintainers` preserves narrower owner candidates.
- Left `repo.build` unset because `Makefile` and `justfile` suggested conflicting build commands.
- Imported repo.test from Makefile as `cargo test --all-features`.
- Imported repo.toolchain.min from Cargo.toml as `1.85.0` (Rust).
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `hyperswitch` from `GitHub API` after deterministic escalation.
- Set `repo.build` to `cargo build --workspace` from `Cargo.toml` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.
