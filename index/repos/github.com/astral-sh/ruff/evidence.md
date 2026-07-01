# Evidence

- Imported repository name, description, and docs entry points from README.md.
- Imported maintainer candidates from CODEOWNERS. Maintainer information was imported from broad CODEOWNERS patterns with multiple team owners, so `owners.team` was left unset and `owners.maintainers` preserves the competing owner candidates.
- Left `repo.build` unset because `Cargo.toml` and `pyproject.toml` suggested conflicting build commands.
- Left `repo.test` unset because `Cargo.toml` and `pyproject.toml` suggested conflicting test commands.
- Discovered related relation to github.com/astral-sh/ruff from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.build` to `cargo build --workspace` from `Cargo.toml` after model escalation.
- Left `repo.test` unset after model escalation: The candidates represent mutually exclusive language ecosystems (Rust vs Python); no single primary value can represent the repository as a whole.. Preserved 2 candidate command(s) in `repo.test_candidates` instead of discarding them.
- Augmented repo.homepage from GitHub repository metadata.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Augmented repo.topics from GitHub repository metadata.
- Filled repo.description from GitHub repository metadata when the README surface did not provide one.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Downgrade guard

Status dropped from a prior verified record because the following previously present field(s) regressed: repo.test.
