# Evidence

- Imported maintainer candidates from CODEOWNERS.
- Inferred fallback values for `repo.name` and `repo.description` because the imported files did not provide enough structured metadata.
- Inferred repo.build from pgmq-rs/Cargo.toml as `cargo build`.
- Left `repo.test` unset because `.github/workflows/client-tests.yml`, `.github/workflows/crate_ci.yml`, and `.github/workflows/extension_upgrade.yml` suggested conflicting test commands.
- Imported repo.toolchain.min from pgmq-rs/Cargo.toml as `1.94.0` (Rust).
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.test` to `cargo test` from `pgmq-rs/Cargo.toml` after deterministic escalation.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Fresh verification

Prior verified authority was not inherited: this refresh must qualify using its current field scores.
