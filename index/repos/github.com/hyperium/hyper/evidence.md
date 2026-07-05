# Evidence

- Imported repository name from README.md.
- Imported the security reporting channel from SECURITY.md. SECURITY.md provided a policy or reporting URL rather than a direct mailbox, so `security_contact` preserves that URL.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Inferred repo.build from Cargo.toml as `cargo build`.
- Left `repo.test` unset because `.github/workflows/CI.yml` suggested an unsafe shell-like command.
- Imported repo.toolchain.min from Cargo.toml as `1.63` (Rust).
- Discovered related relation to github.com/hyperium/hyper from Cargo.toml repository.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `hyper` from `GitHub API` after deterministic escalation.
- Set `repo.test` to `cargo test` from `Cargo.toml` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.
