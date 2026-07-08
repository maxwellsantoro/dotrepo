# Evidence

- Imported repository name from README.md.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Imported repo.build from README.md as `cargo build --release`.
- Imported repo.test from README.md as `cargo test --all`.
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

## Security contact normalization (2026-07-08)

Replaced non-actionable `security_contact` value `https://blog.burntsushi.net/about/` with `unknown`. The prior URL was not an email or actionable vulnerability-reporting surface (promotion scoring: medium-present). Honest absence unblocks auto-publish without inventing a reporting channel.

## Auto-promotion

Record auto-promoted to verified: all fields are honestly resolved by deterministic promotion scoring.
