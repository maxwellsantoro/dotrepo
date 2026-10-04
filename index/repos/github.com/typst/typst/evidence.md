# Evidence

- Imported repository name from README.md.
- Imported repo.build from tools/test-helper/package.json as `npm run build`.
- Inferred repo.test from .github/workflows/ci.yml as `cargo test --workspace --no-run`.
- Imported repo.toolchain.min from Cargo.toml as `1.92` (Rust).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Fresh verification

Prior verified authority was not inherited: this refresh must qualify using its current field scores.

## Command semantic correction (2026-10-03)

2026-10-03 semantic audit withheld repo.build, repo.test pending command context or usable upstream instructions; repository-default applicability remains unresolved. Source inspection timestamps are unchanged.

- Withheld `repo.build` previously extracted from `tools/test-helper/package.json` as `npm run build`. Component command lacks repository-default scope and working directory.
- Withheld `repo.test` previously extracted from `.github/workflows/ci.yml` as `cargo test --workspace --no-run`. Command is an incomplete example or setup-only step.
