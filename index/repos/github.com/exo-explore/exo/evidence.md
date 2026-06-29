# Evidence

- Imported repository name from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Left `repo.build` unset because `Cargo.toml` and `pyproject.toml` suggested conflicting build commands.
- Left `repo.test` unset because `Cargo.toml` and `pyproject.toml` suggested conflicting test commands.
- Discovered related relation to github.com/ml-explore/mlx from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Left `repo.build` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk.
- Left `repo.test` unset after deterministic escalation: no unique build/test candidate after deterministic tier walk.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Filled repo.description from GitHub repository metadata when the README surface did not provide one.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).
