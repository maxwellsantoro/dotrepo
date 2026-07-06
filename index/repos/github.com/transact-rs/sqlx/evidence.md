# Evidence

- Imported repository name from README.md.
- Inferred repo.build from .github/workflows/examples.yml as `cargo build`.
- Left `repo.test` unset because `.github/workflows/sqlx-cli.yml` and `.github/workflows/sqlx.yml` suggested conflicting test commands.
- Imported repo.toolchain.min from Cargo.toml as `1.94.0` (Rust).
- Discovered related relation to github.com/rusqlite/rusqlite from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.test` to `cargo test --workspace` from `Cargo.toml` after deterministic escalation.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

A prior verified status was preserved because no previously present field regressed in this refresh.
