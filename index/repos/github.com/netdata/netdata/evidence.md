# Evidence

- Imported repository name from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from CODEOWNERS; `owners.team` is `@netdata/agent-sre` because it is the clearest imported team signal, but `owners.maintainers` still preserves narrower owner candidates.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Ignored component-scoped commands from `src/crates/Cargo.toml` as repository defaults.
- Imported repo.toolchain.min from src/crates/Cargo.toml as `1.91` (Rust).
- This is an overlay record, not a maintainer-controlled canonical record.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.
