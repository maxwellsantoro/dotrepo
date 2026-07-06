# Evidence

- Imported repository name from README.md.
- Imported maintainer candidates from CODEOWNERS.
- Inferred fallback values for `repo.description` because the imported files did not provide enough structured metadata.
- Imported repo.build from justfile as `just all`.
- Imported repo.test from justfile as `just test`.
- Imported repo.toolchain.min from pyproject.toml as `3.13` (Python).
- Discovered related relation to github.com/ml-explore/mlx from README cross-link.
- This is an overlay record, not a maintainer-controlled canonical record.

- Set `repo.name` to `exo` from `GitHub API` after deterministic escalation.
- Augmented repo.license from GitHub repository metadata.
- Augmented repo.visibility from GitHub repository metadata.
- Augmented repo.languages from GitHub repository metadata.
- Constrained repo.description with GitHub repository metadata.
- Recorded GitHub-only crawl metadata under x.github (default branch, head SHA, stars, archive state, and fork state).

## Auto-promotion

All fields are high-confidence present or high-confidence absent. Record auto-promoted to verified status.
