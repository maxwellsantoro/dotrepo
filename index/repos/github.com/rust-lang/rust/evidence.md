# Evidence

- Inferred fallback values for `repo.name` because the imported files did not provide enough structured metadata.
- Left `repo.build` unset because `.github/workflows/dependencies.yml` suggested an unsafe shell-like command.
- Inferred repo.test from .github/workflows/ci.yml as `CARGO_INCREMENTAL=0 cargo test`.
- This is an overlay record, not a maintainer-controlled canonical record.

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
